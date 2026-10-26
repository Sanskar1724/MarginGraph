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
    for ctx, cand in zip(slates["context"], slates["description"], strict=True):
        out.append(build_prompt([desc.get(i, i) for i in ctx.split("|")], str(cand)))
    return out


def load_model(model_name: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    assert torch.cuda.is_available(), "no GPU attached"
    tok = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    # one GPU; splitting a 1.5-3B model across T4 x2 only slows it down
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, device_map={"": 0}).eval()
    return model, tok


def _chat(tok, prompts: list[str]) -> list[str]:
    return [
        tok.apply_chat_template(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": p}],
            tokenize=False,
            add_generation_prompt=True,
        )
        for p in prompts
    ]


def _yes_no_ids(tok) -> tuple[int, int]:
    return tok.encode("Yes", add_special_tokens=False)[0], tok.encode("No", add_special_tokens=False)[0]


def _yes_no_logits(model, tok, texts: list[str]):
    enc = tok(texts, return_tensors="pt", padding=True).to(model.device)
    # only the last position: full-sequence logits over a 151k vocab do not fit a T4
    logits = model(**enc, logits_to_keep=1).logits[:, -1, :]
    yes, no = _yes_no_ids(tok)
    return logits[:, [no, yes]].float()


def score_slates(
    slates: pd.DataFrame, catalog: pd.DataFrame, model_name: str | None = None, batch_size: int = 32, model=None, tok=None
) -> np.ndarray:
    """log P(Yes) - log P(No) per candidate row. Pass model/tok to reuse a loaded (or fine-tuned) model."""
    import torch

    if model is None:
        model, tok = load_model(model_name)
    model.eval()
    texts = _chat(tok, prompts_for(slates, catalog))
    scores = []
    with torch.no_grad():
        for s in range(0, len(texts), batch_size):
            lg = _yes_no_logits(model, tok, texts[s : s + batch_size])
            scores.append((lg[:, 1] - lg[:, 0]).cpu().numpy())
    return np.concatenate(scores)


def sft_examples(slates: pd.DataFrame, catalog: pd.DataFrame, neg_per_pos: int = 3, seed: int = 0) -> pd.DataFrame:
    """E6 training rows: every held-out item (Yes) plus its top-ranked wrong candidates (No).

    Only events whose target made the slate are used, so every positive has
    hard negatives from the same basket.
    """
    df = slates[slates.groupby("event_id")["label"].transform("max") > 0]
    df = df.sort_values(["event_id", "score"], ascending=[True, False])
    pos = df[df["label"] == 1]
    neg = df[df["label"] == 0].groupby("event_id").head(neg_per_pos)
    out = pd.concat([pos, neg]).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    out["prompt"] = prompts_for(out, catalog)
    return out[["event_id", "prompt", "label"]]


def _skip_torchao_check() -> None:
    """Kaggle images ship torchao 0.10, which recent peft rejects with an
    ImportError while wrapping plain Linear layers. We never use torchao, so
    tell peft it is absent."""
    import importlib

    for name in ("peft.import_utils", "peft.tuners.lora.torchao", "peft.utils.quantization_utils"):
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        if hasattr(mod, "is_torchao_available"):
            mod.is_torchao_available = lambda: False


def finetune_lora(
    model,
    tok,
    examples: pd.DataFrame,
    epochs: int = 2,
    lr: float = 2e-4,
    batch_size: int = 8,
    r: int = 16,
    log_every: int = 50,
):
    """LoRA fine-tune as a 2-way Yes/No classifier on the answer token.

    The loss is cross-entropy over the (No, Yes) logits at the last prompt
    position, which is exactly what ``score_slates`` reads, so training and
    scoring agree. Positives are up-weighted to balance the 1:neg_per_pos ratio.
    """
    import torch
    from peft import LoraConfig, get_peft_model

    _skip_torchao_check()
    if model.device.type == "cuda":  # trade compute for memory so 1.5B trains on a 15 GB T4
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        model.config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(r=r, lora_alpha=2 * r, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]),
    )
    for p in model.parameters():  # LoRA weights in fp32 for stable fp16 autocast training
        if p.requires_grad:
            p.data = p.data.float()
    model.print_trainable_parameters()
    texts = _chat(tok, examples["prompt"].tolist())
    y = torch.tensor(examples["label"].to_numpy(), dtype=torch.long)
    pos_w = float((y == 0).sum()) / max(float((y == 1).sum()), 1.0)
    weight = torch.tensor([1.0, pos_w], device=model.device)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)
    n_steps = epochs * ((len(texts) + batch_size - 1) // batch_size)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=n_steps, pct_start=0.05)
    use_amp = model.device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    model.train()
    step, run = 0, 0.0
    for ep in range(epochs):
        order = np.random.default_rng(ep).permutation(len(texts))
        for s in range(0, len(order), batch_size):
            idx = order[s : s + batch_size]
            with torch.autocast(device_type=model.device.type, dtype=torch.float16, enabled=use_amp):
                lg = _yes_no_logits(model, tok, [texts[i] for i in idx])
            loss = torch.nn.functional.cross_entropy(lg, y[idx].to(model.device), weight=weight)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            step += 1
            run = 0.98 * run + 0.02 * loss.item() if step > 1 else loss.item()
            if step % log_every == 0 or step == n_steps:
                print(f"epoch {ep + 1} step {step}/{n_steps} loss {run:.4f}", flush=True)
    model.eval()
    return model


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
