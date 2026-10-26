"""E5/E6 LLM reranker: pointwise yes/no scoring of the top-20 LightGBM slate.

Runs on a free GPU (Kaggle / Colab T4). The model reads product descriptions;
it never has to recall item IDs. Its score is log P("Yes") - log P("No") for:
"A shopper's basket contains ... Would they also add <candidate>?"

Usage (GPU notebook):
    slates = pd.read_parquet("artifacts/test_slates.parquet")
    catalog = pd.read_parquet("artifacts/catalog.parquet")
    slates["llm"] = score_slates(slates, catalog, "Qwen/Qwen2.5-1.5B-Instruct")
    print(compare(slates))
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import paired_bootstrap

SYSTEM = "You are a retail merchandiser for a UK gift and homeware wholesaler. Answer only Yes or No."


def build_prompt(basket_desc: list[str], candidate_desc: str, max_items: int = 15) -> str:
    items = "\n".join(f"- {d.title()}" for d in basket_desc[:max_items])
    return (
        f"A customer's order contains:\n{items}\n\n"
        f"Would this customer also add \"{candidate_desc.title()}\" to the same order?"
    )


def prompts_for(slates: pd.DataFrame, catalog: pd.DataFrame) -> list[str]:
    desc = catalog.set_index("item")["description"].astype(str).to_dict()
    out = []
    for ctx, cand in zip(slates["context"], slates["description"]):
        out.append(build_prompt([desc.get(i, i) for i in ctx.split("|")], str(cand)))
    return out


def score_slates(slates: pd.DataFrame, catalog: pd.DataFrame, model_name: str, batch_size: int = 32) -> np.ndarray:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    assert torch.cuda.is_available(), "no GPU attached"
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, device_map={"": 0}).eval()  # one GPU; T4 x2 splitting only slows a 1.5-3B model
    yes = tok.encode("Yes", add_special_tokens=False)[0]
    no = tok.encode("No", add_special_tokens=False)[0]
    texts = [
        tok.apply_chat_template(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": p}],
            tokenize=False,
            add_generation_prompt=True,
        )
        for p in prompts_for(slates, catalog)
    ]
    scores = []
    with torch.no_grad():
        for s in range(0, len(texts), batch_size):
            enc = tok(texts[s : s + batch_size], return_tensors="pt", padding=True).to(model.device)
            logits = model(**enc).logits[:, -1, :].float()
            lp = torch.log_softmax(logits, -1)
            scores.append((lp[:, yes] - lp[:, no]).cpu().numpy())
    return np.concatenate(scores)


def _ranks(df: pd.DataFrame, col: str) -> pd.Series:
    r = df.groupby("event_id")[col].rank(ascending=False, method="max")
    hit = df.assign(r=r)[df["label"] == 1].set_index("event_id")["r"]
    return hit.reindex(df["event_id"].unique()).fillna(np.inf)


def compare(slates: pd.DataFrame, llm_col: str = "llm", ks=(1, 5, 10), n_boot: int = 2000) -> pd.DataFrame:
    """LightGBM order vs LLM order vs rank-average blend, on the same 20 candidates."""
    df = slates.copy()
    df["blend"] = -(
        df.groupby("event_id")["score"].rank(ascending=False) + df.groupby("event_id")[llm_col].rank(ascending=False)
    )
    rk = {name: _ranks(df, col) for name, col in [("lightgbm", "score"), ("llm", llm_col), ("blend", "blend")]}
    rows = []
    for k in ks:
        for name in ("llm", "blend"):
            a = (rk[name] <= k).astype(float).to_numpy()
            b = (rk["lightgbm"] <= k).astype(float).to_numpy()
            rows.append({"metric": f"hit@{k}", "a": name, "b": "lightgbm", "a_mean": a.mean(), "b_mean": b.mean(), **paired_bootstrap(a, b, n_boot)})
    return pd.DataFrame(rows)


def verdict(table: pd.DataFrame, k: int = 5) -> str:
    """E6 gate: GO only if the LLM or the blend beats LightGBM with a paired CI above zero."""
    rows = table[table["metric"] == f"hit@{k}"]
    wins = rows[rows["ci_low"] > 0]
    if len(wins):
        best = wins.sort_values("diff", ascending=False).iloc[0]
        return f"GO: {best['a']} beats LightGBM on hit@{k} by {best['diff']:+.4f} (95% CI {best['ci_low']:+.4f} to {best['ci_high']:+.4f})"
    best = rows.sort_values("diff", ascending=False).iloc[0]
    return f"NO-GO: best is {best['a']} at {best['diff']:+.4f} on hit@{k} (95% CI {best['ci_low']:+.4f} to {best['ci_high']:+.4f}); keep LightGBM"


def _slate_features(df: pd.DataFrame, llm_col: str) -> pd.DataFrame:
    g = df.groupby("event_id")
    return pd.DataFrame(
        {
            "lgbm": df["score"],
            "lgbm_rank": g["score"].rank(ascending=False),
            "llm": df[llm_col],
            "llm_rank": g[llm_col].rank(ascending=False),
            "llm_z": (df[llm_col] - g[llm_col].transform("mean")) / (g[llm_col].transform("std") + 1e-6),
        }
    )


def stack(val: pd.DataFrame, test: pd.DataFrame, llm_col: str = "llm", n_boot: int = 2000) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Option 1: learn how much to trust the LLM, on held-out val slates only.

    A logistic regression on (LightGBM score/rank, LLM score/rank/z) is fit on
    val slates, then re-orders the test slates. Returns (paired comparison vs
    LightGBM, coefficients).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    Xv, Xt = _slate_features(val, llm_col), _slate_features(test, llm_col)
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(Xv, val["label"])
    t = test.copy()
    t["stacked"] = clf.predict_proba(Xt)[:, 1]
    rk = {"lightgbm": _ranks(t, "score"), "stacked": _ranks(t, "stacked")}
    rows = []
    for k in (1, 5, 10):
        a = (rk["stacked"] <= k).astype(float).to_numpy()
        b = (rk["lightgbm"] <= k).astype(float).to_numpy()
        rows.append({"metric": f"hit@{k}", "a": "stacked", "b": "lightgbm", "a_mean": a.mean(), "b_mean": b.mean(), **paired_bootstrap(a, b, n_boot)})
    coef = pd.DataFrame({"feature": Xv.columns, "coef": clf[-1].coef_[0]})
    return pd.DataFrame(rows), coef
