"""Reranker comparison: LightGBM vs XGBoost, CatBoost, HistGB and logistic regression.

Every model sees the same candidate pools (150 items), the same 35 features and the
same training events as the production LightGBM reranker (validation events whose
candidates come from train-only models). They are scored on a seeded sample of UCI
test invoices (default 1,000, seed 42).

    python scripts/reranker_comparison.py --n-test 1000 --out results/reranker_comparison

Writes summary.csv (one row per model) and ranks.csv (per-event target rank per model).
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from margingraph import data, split
from margingraph.features import CandidateGenerator, feature_columns
from margingraph.models import Repeat
from margingraph.rerank import Reranker, pool_ranks, split_events
from margingraph.stats import bootstrap_ci, paired_bootstrap, ranking_metrics


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def build_features(cfg: dict, n_test: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Candidate pools + features for all val events (training) and n_test test events."""
    seed, sc = cfg["seed"], cfg["split"]
    lines, catalog, _ = data.load_or_build(cfg)
    splits = split.temporal_split(lines, sc["val_start"], sc["test_start"])
    ev = {
        "val": split.make_events(splits["val"], sc["min_basket_items"], sc["max_basket_items"], sc["max_events_val"], seed),
        "test": split.make_events(splits["test"], sc["min_basket_items"], sc["max_basket_items"], n_test, seed),
    }
    hist = {"val": splits["train"], "test": pd.concat([splits["train"], splits["val"]])}
    gens = {"val": CandidateGenerator(splits["train"], splits["train"], catalog, cfg)}
    gens["test"] = (
        CandidateGenerator(hist["test"], hist["test"], catalog, cfg)
        if cfg["retrieval"].get("refit_for_test", False)
        else gens["val"]
    )
    feats = {}
    for k in ("val", "test"):
        g = gens[k]
        g.scorers["repeat"] = Repeat(hist[k], g.index)
        g.set_stream(splits[k])
        e = ev[k]
        n_hide = sc.get("train_events_per_invoice", 1)
        if k == "val" and n_hide > 1:
            e = split.add_extra_hides(splits[k], e, n_hide, sc["min_basket_items"], sc["max_basket_items"], seed)
        log(f"candidates + features for {k}: {len(e)} events")
        f, _ = g.generate(
            e["context"].tolist(), e["customer"].tolist(), e["target"].tolist(), e["event_id"].to_numpy(),
            times=e["ts"].tolist(),
        )
        feats[k] = f
    return feats["val"], feats["test"]


def _positive_events(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.groupby("event_id")["label"].transform("max") > 0]


def _groups(df: pd.DataFrame) -> np.ndarray:
    return df.groupby("event_id", sort=False).size().to_numpy()


def make_models(cfg: dict, seed: int) -> dict:
    """name -> (fit(fit_df, es_df, cols), score(df, cols)) closures."""
    r = cfg["rerank"]
    models = {}

    def lgbm():
        m = Reranker(cfg, seed)
        return (lambda f, e, c: m.fit(f, e)), (lambda d, c: m.score(d))

    def xgb(objective):
        import xgboost as xgb_

        m = xgb_.XGBRanker(
            objective=objective, n_estimators=r["n_estimators"], learning_rate=r["learning_rate"],
            max_depth=6, tree_method="hist", random_state=seed, n_jobs=-1,
            eval_metric="ndcg@10", early_stopping_rounds=r["early_stopping_rounds"],
        )

        def fit(f, e, c):
            f, e = _positive_events(f), _positive_events(e)
            m.fit(f[c], f["label"], group=_groups(f), eval_set=[(e[c], e["label"])], eval_group=[_groups(e)], verbose=False)

        return fit, (lambda d, c: m.predict(d[c]))

    def catboost():
        from catboost import CatBoostRanker, Pool

        m = CatBoostRanker(
            loss_function="YetiRank", iterations=r["n_estimators"], learning_rate=0.1, depth=6,
            random_seed=seed, verbose=False, od_type="Iter", od_wait=r["early_stopping_rounds"],
            eval_metric="NDCG:top=10", thread_count=-1,
        )

        def fit(f, e, c):
            f, e = _positive_events(f), _positive_events(e)
            m.fit(Pool(f[c], f["label"], group_id=f["event_id"]), eval_set=Pool(e[c], e["label"], group_id=e["event_id"]),
                  use_best_model=True)

        return fit, (lambda d, c: m.predict(d[c]))

    def histgb():
        from sklearn.ensemble import HistGradientBoostingClassifier

        m = HistGradientBoostingClassifier(max_iter=r["n_estimators"], learning_rate=r["learning_rate"],
                                           max_leaf_nodes=r["num_leaves"], early_stopping=True, random_state=seed)
        return (lambda f, e, c: m.fit(f[c], f["label"])), (lambda d, c: m.predict_proba(d[c])[:, 1])

    def logreg():
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))

        def prep(d, c):
            x = d[c].replace([np.inf, -np.inf], np.nan)
            return x.fillna(0.0)

        return (lambda f, e, c: m.fit(prep(f, c), f["label"])), (lambda d, c: m.predict_proba(prep(d, c))[:, 1])

    models["LightGBM LambdaRank"] = lgbm
    models["XGBoost rank:pairwise"] = lambda: xgb("rank:pairwise")
    models["XGBoost rank:ndcg"] = lambda: xgb("rank:ndcg")
    models["CatBoost YetiRank"] = catboost
    models["sklearn HistGradientBoosting"] = histgb
    models["Logistic regression"] = logreg
    return models


def compare(cfg: dict, feats_val: pd.DataFrame, feats_test: pd.DataFrame, n_boot: int = 2000) -> tuple[pd.DataFrame, pd.DataFrame]:
    seed = cfg["seed"]
    fit_df, es_df, _ = split_events(feats_val)
    cols = feature_columns(fit_df)
    event_ids = np.sort(feats_test["event_id"].unique())
    ranks, timing = {}, {}
    for name, make in make_models(cfg, seed).items():
        fit, score = make()
        t0 = time.perf_counter()
        fit(fit_df, es_df, cols)
        t1 = time.perf_counter()
        s = score(feats_test, cols)
        t2 = time.perf_counter()
        ranks[name] = pool_ranks(feats_test, np.asarray(s)).reindex(event_ids).to_numpy()
        timing[name] = (t1 - t0, t2 - t1)
        log(f"{name}: train {t1 - t0:.1f}s, score {t2 - t1:.2f}s, Hit@10 {(ranks[name] <= 10).mean():.3f}")

    ref = "LightGBM LambdaRank"
    in_pool = np.isfinite(ranks[ref])
    rows = []
    for name, rk in ranks.items():
        m = ranking_metrics(rk, ks=(2, 5, 10))
        hit10, lo, hi = bootstrap_ci(m["hit@10"], n_boot, seed)
        row = {
            "model": name, "hit@10": hit10, "hit@10_ci_low": lo, "hit@10_ci_high": hi,
            "hit@2": m["hit@2"].mean(), "hit@5": m["hit@5"].mean(), "ndcg@10": m["ndcg@10"].mean(),
            "train_s": timing[name][0], "score_s": timing[name][1], "n_events": len(rk),
            "pool_recall": in_pool.mean(),
        }
        if name != ref:
            pb = paired_bootstrap(m["hit@10"], ranking_metrics(ranks[ref], ks=(10,))["hit@10"], n_boot, seed)
            row.update({"d_hit@10": pb["diff"], "d_ci_low": pb["ci_low"], "d_ci_high": pb["ci_high"], "p_boot": pb["p_boot"]})
        rows.append(row)
    summary = pd.DataFrame(rows)
    rank_df = pd.DataFrame(ranks, index=event_ids).rename_axis("event_id").reset_index()
    return summary, rank_df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--n-test", type=int, default=1000)
    ap.add_argument("--out", default="results/reranker_comparison")
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    fv, ft = build_features(cfg, a.n_test)
    summary, ranks = compare(cfg, fv, ft, cfg["stats"]["n_boot"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "summary.csv", index=False)
    ranks.to_csv(out / "ranks.csv", index=False)
    print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
