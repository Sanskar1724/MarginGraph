"""Stage 1 accuracy experiments (docs/worklog/accuracy.md).

Same data, temporal split and leave-one-out events as ``margingraph run``.
Each variant builds val features with train-only models and test features with
models refit on train+val, trains the LightGBM ranker on val, and is compared
with the baseline on the same test events (paired bootstrap).

Selection rule: a change is kept only if it wins on the held-out part of val
(last 30% of val events by time, never used to fit trees). Test is reported for
every variant, winners and losers alike.

    python scripts/accuracy_experiments.py --stage all
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import time
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pandas as pd
import yaml

from margingraph import data, split
from margingraph.features import CandidateGenerator
from margingraph.models import Repeat
from margingraph.rerank import Reranker, pool_ranks, split_events
from margingraph.stats import bootstrap_ci, paired_bootstrap, ranking_metrics

OUT = Path("results/accuracy")
CACHE = Path("data/exp")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def setup(cfg: dict) -> dict:
    lines, catalog, _ = data.load_or_build(cfg)
    sc = cfg["split"]
    splits = split.temporal_split(lines, sc["val_start"], sc["test_start"])
    ev = {
        k: split.make_events(splits[k], sc["min_basket_items"], sc["max_basket_items"], sc[f"max_events_{k}"], cfg["seed"])
        for k in ("val", "test")
    }
    hist = {"val": splits["train"], "test": pd.concat([splits["train"], splits["val"]])}
    return {"lines": lines, "catalog": catalog, "splits": splits, "ev": ev, "hist": hist}


def build(cfg: dict, S: dict, tag: str, val_events: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Candidate features for val and test under ``cfg`` (cached by tag)."""
    paths = {k: CACHE / f"{tag}_{k}.parquet" for k in ("val", "test")}
    if all(p.exists() for p in paths.values()):
        return {k: pd.read_parquet(p) for k, p in paths.items()}
    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    out = {}
    stream = {"val": S["splits"]["val"], "test": S["splits"]["test"]}
    for k in ("val", "test"):
        g = CandidateGenerator(S["hist"][k], S["hist"][k], S["catalog"], cfg)
        g.scorers["repeat"] = Repeat(S["hist"][k], g.index)
        g.set_stream(stream[k])
        e = S["ev"][k] if (k == "test" or val_events is None) else val_events
        f, _ = g.generate(
            e["context"].tolist(), e["customer"].tolist(), e["target"].tolist(), e["event_id"].to_numpy(),
            times=e["ts"].tolist(),
        )
        f.to_parquet(paths[k], index=False)
        out[k] = f
        del g
    log(f"built {tag} in {time.time() - t0:.0f}s: val {len(out['val'])} rows, test {len(out['test'])} rows")
    return out


def recall(f: pd.DataFrame, all_ids: np.ndarray) -> np.ndarray:
    return f.groupby("event_id")["label"].max().reindex(all_ids).fillna(0).to_numpy()


def rank_eval(
    cfg: dict, F: dict[str, pd.DataFrame], ev: dict, drop: tuple[str, ...] = (), seed: int = 42,
    params: dict | None = None,
) -> dict:
    """Train the ranker on val; return per-event ranks on val-holdout and test."""
    dc = [c for c in F["val"].columns if any(c == d or c.endswith("_" + d) for d in drop)]
    fv, ft = F["val"].drop(columns=dc), F["test"].drop(columns=dc)
    fit_df, es_df, cal_df = split_events(fv)
    c2 = copy.deepcopy(cfg)
    if params:
        c2["rerank"].update(params)
    rr = Reranker(c2, seed)
    for k, v in (params or {}).items():
        if k not in ("num_leaves", "learning_rate", "n_estimators", "early_stopping_rounds"):
            rr.model.set_params(**{k: v})
    rr.fit(fit_df, es_df)
    hold = pd.concat([es_df, cal_df])
    # val holdout ids: base events only (augmented copies have ids >= 1e6)
    hold_ids = np.sort(ev["val"]["event_id"].to_numpy())
    hold_ids = hold_ids[np.isin(hold_ids, hold["event_id"].unique())]
    rv = pool_ranks(hold, rr.score(hold)).reindex(hold_ids).fillna(np.inf).to_numpy()
    test_ids = ev["test"]["event_id"].to_numpy()
    rt = pool_ranks(ft, rr.score(ft)).reindex(test_ids).fillna(np.inf).to_numpy()
    return {"val": rv, "test": rt, "imp": rr.importance(), "iters": rr.model.best_iteration_}


def summarize(name: str, res: dict, base: dict | None, F: dict, ev: dict, n_boot: int, note: str = "") -> dict:
    row = {"variant": name, "note": note}
    row["val_pool_recall"] = float(recall(F["val"], ev["val"]["event_id"].to_numpy()).mean())
    rt = recall(F["test"], ev["test"]["event_id"].to_numpy())
    row["test_pool_recall"], row["test_pool_recall_lo"], row["test_pool_recall_hi"] = bootstrap_ci(rt, n_boot, 0)
    row["pool_rows_per_event"] = len(F["test"]) / F["test"]["event_id"].nunique()
    for split_ in ("val", "test"):
        m = ranking_metrics(res[split_])
        for metric in ("hit@5", "hit@10", "ndcg@10", "mrr"):
            row[f"{split_}_{metric}"] = float(m[metric].mean())
    if base is not None:
        for split_ in ("val", "test"):
            mb, ma = ranking_metrics(base["rank"][split_]), ranking_metrics(res[split_])
            for metric in ("hit@10", "ndcg@10"):
                pb = paired_bootstrap(ma[metric], mb[metric], n_boot, 0)
                row[f"{split_}_d_{metric}"] = pb["diff"]
                row[f"{split_}_d_{metric}_lo"] = pb["ci_low"]
                row[f"{split_}_d_{metric}_hi"] = pb["ci_high"]
        rb = recall(base["F"]["test"], ev["test"]["event_id"].to_numpy())
        pb = paired_bootstrap(rt, rb, n_boot, 0)
        row["test_d_recall"], row["test_d_recall_lo"], row["test_d_recall_hi"] = pb["diff"], pb["ci_low"], pb["ci_high"]
    row["best_iter"] = res.get("iters")
    log(
        f"{name}: recall val {row['val_pool_recall']:.3f} test {row['test_pool_recall']:.3f} | "
        f"hit@10 val {row['val_hit@10']:.3f} test {row['test_hit@10']:.3f}"
        + (f" | d_test_hit@10 {row['test_d_hit@10']:+.4f} [{row['test_d_hit@10_lo']:+.4f},{row['test_d_hit@10_hi']:+.4f}]"
           f" d_val_hit@10 {row['val_d_hit@10']:+.4f}" if base else "")
    )
    return row


def record(row: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "experiments.csv"
    df = pd.DataFrame([row])
    if p.exists():
        old = pd.read_csv(p)
        old = old[old["variant"] != row["variant"]]
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(p, index=False)


def with_retrieval(cfg: dict, **kw) -> dict:
    c = copy.deepcopy(cfg)
    for k, v in kw.items():
        c["retrieval"][k] = v
    return c


def augment_val(S: dict, cfg: dict, k: int) -> pd.DataFrame:
    """k leave-one-out events per val invoice (original event first, then extra hides)."""
    base = S["ev"]["val"]
    sc = cfg["split"]
    parts = [base]
    for j in range(1, k):
        e = split.make_events(S["splits"]["val"], sc["min_basket_items"], sc["max_basket_items"], sc["max_events_val"], cfg["seed"] + 1000 * j)
        e = e.set_index("invoice").reindex(base["invoice"]).reset_index()
        e["event_id"] = base["event_id"].to_numpy() + 1_000_000 * j
        # drop copies that hid the same product as the original event
        e = e[e["target"].to_numpy() != base["target"].to_numpy()]
        parts.append(e[base.columns])
    return pd.concat(parts).sort_values(["ts", "event_id"]).reset_index(drop=True)


def insert_after_ease(per_source: dict, new: dict) -> dict:
    """Pools are filled in source order then cut at pool_size, so new sources go right after EASE."""
    out = {}
    for k, v in per_source.items():
        out[k] = v
        if k == "ease":
            out.update(new)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stage", default="all")
    ap.add_argument("--n_boot", type=int, default=2000)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    # the baseline is the configuration before this thread
    cfg["retrieval"].pop("extra", None)
    cfg["retrieval"]["index_scope"] = "train"
    S = setup(cfg)
    ev = S["ev"]
    nb = args.n_boot
    facts = {}
    tv_items = set(S["hist"]["test"]["item"])
    te = S["splits"]["test"]
    first_sale = te.groupby("item")["ts"].min()
    unseen = ev["test"][~ev["test"]["target"].isin(tv_items)]
    sold_before = [first_sale.get(t, pd.Timestamp.max).normalize() < ts.normalize() for t, ts in zip(unseen["target"], unseen["ts"], strict=True)]
    facts["test_targets_unseen_before_test"] = float(len(unseen) / len(ev["test"]))
    facts["of_those_sold_in_test_before_event_day"] = float(np.mean(sold_before)) if len(unseen) else 0.0
    log(f"facts: {facts}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "facts.json").write_text(json.dumps(facts, indent=2))

    stage = args.stage
    Fb = build(cfg, S, "base")
    rb = rank_eval(cfg, Fb, ev)
    base = {"F": Fb, "rank": rb}
    record(summarize("A0_baseline", rb, None, Fb, ev, nb, "pre-thread config, pool 100"))

    # ---- B: one new source at a time, as features and in the pool ----------
    extras = {
        "ease_decay": {"half_life_days": 120},
        "cust_ease": True,
        "text": True,
        "item2vec": {"dim": 64, "epochs": 5},
        "fresh": {"days": 14},
    }
    pool_k = {"ease_decay": 40, "cust_ease": 20, "text": 20, "item2vec": 20, "trend": 15, "fresh_co": 20}
    if stage in ("all", "B"):
        for name, opt in extras.items():
            c = with_retrieval(cfg, extra={name: opt})
            srcs = ["trend", "fresh_co"] if name == "fresh" else [name]
            c["retrieval"]["per_source"] = insert_after_ease(cfg["retrieval"]["per_source"], {s_: pool_k[s_] for s_ in srcs})
            if name == "fresh":
                c["retrieval"]["index_scope"] = "catalog"
            F = build(c, S, f"B_{name}")
            r = rank_eval(c, F, ev)
            record(summarize(f"B_{name}", r, base, F, ev, nb, f"+{name} as feature and pool source; pool 100"))
            del F

    # ---- C: combine sources, then grow the pool ---------------------------
    keep = [k for k in os.environ.get("KEEP", "").split(",") if k]
    if stage in ("all", "C") and keep:
        ex = {k: extras[k] for k in keep}
        srcs = [s_ for k in keep for s_ in (["trend", "fresh_co"] if k == "fresh" else [k])]
        scope = "catalog" if "fresh" in keep else "train"
        for pool in [int(p) for p in os.environ.get("POOLS", "100,150,200").split(",")]:
            c = with_retrieval(cfg, extra=ex, index_scope=scope, pool_size=pool)
            c["retrieval"]["per_source"] = insert_after_ease(cfg["retrieval"]["per_source"], {s_: pool_k[s_] for s_ in srcs})
            if pool > 100:
                c["retrieval"]["per_source"] = {k: int(round(v * pool / 100)) for k, v in c["retrieval"]["per_source"].items()}
            tag = f"C_{'+'.join(keep)}_pool{pool}"
            F = build(c, S, tag)
            r = rank_eval(c, F, ev)
            record(summarize(tag, r, base, F, ev, nb, f"sources {keep}; pool {pool}"))
            del F

    # ---- D: ranker: more training events, then LambdaRank params ----------
    pool = int(os.environ.get("POOL", "100"))
    if stage in ("all", "D"):
        ex = {k: extras[k] for k in keep}
        srcs = [s_ for k in keep for s_ in (["trend", "fresh_co"] if k == "fresh" else [k])]
        scope = "catalog" if "fresh" in keep else "train"
        c = with_retrieval(cfg, extra=ex, index_scope=scope, pool_size=pool)
        c["retrieval"]["per_source"] = insert_after_ease(cfg["retrieval"]["per_source"], {s_: pool_k[s_] for s_ in srcs})
        if pool > 100:
            c["retrieval"]["per_source"] = {k: int(round(v * pool / 100)) for k, v in c["retrieval"]["per_source"].items()}
        tag = f"C_{'+'.join(keep)}_pool{pool}" if keep else "base"
        F = build(c, S, tag)
        ref = rank_eval(c, F, ev)
        refb = {"F": F, "rank": ref}
        for aug in (3,):
            va = augment_val(S, cfg, aug)
            Fa = build(c, S, f"{tag}_aug{aug}", val_events=va)
            # fit on originals and copies of invoices before the holdout cut (copies of
            # holdout invoices are dropped); holdout = the original events >= cut
            ids = np.sort(ev["val"]["event_id"].to_numpy())
            cut = ids[int(len(ids) * 0.7)]
            v = Fa["val"].copy()
            base_id = v["event_id"] % 1_000_000
            v = v[(base_id < cut) | (v["event_id"] < 1_000_000)]
            fit = (v["event_id"] % 1_000_000) < cut
            codes, _ = pd.factorize(v.loc[fit, "event_id"])
            v.loc[fit, "event_id"] = -(codes + 1)
            Faug = {"val": v, "test": Fa["test"]}
            r = rank_eval_aug(c, Faug, ev, cut)
            if keep:
                # the final configuration against the pre-thread baseline
                record(summarize("F_final_vs_baseline", r, base, Faug, ev, nb, f"{tag} + {aug} events per invoice; ref = A0_baseline"))
            record(summarize(f"D_{tag}_aug{aug}", r, refb, Faug, ev, nb, f"{aug} hidden-item events per val invoice for training; ref = {tag}"))
        grid = [
            {"num_leaves": 63, "learning_rate": 0.03, "n_estimators": 1500, "min_child_samples": 50},
            {"num_leaves": 15, "learning_rate": 0.05, "n_estimators": 1500, "min_child_samples": 100},
            {"num_leaves": 31, "learning_rate": 0.03, "n_estimators": 1500, "colsample_bytree": 0.7, "subsample": 0.8, "subsample_freq": 1},
            {"num_leaves": 31, "learning_rate": 0.05, "n_estimators": 1500, "lambdarank_truncation_level": 20},
        ]
        for i, p in enumerate(grid):
            r = rank_eval(c, F, ev, params=p)
            record(summarize(f"D_{tag}_lgb{i}", r, refb, F, ev, nb, f"params {p}; ref = {tag}"))


def rank_eval_aug(cfg: dict, F: dict, ev: dict, cut: int) -> dict:
    """rank_eval for augmented val: fit = negative ids, early stop + holdout = original ids >= cut."""
    v = F["val"]
    fit_df = v[v["event_id"] < 0]
    hold = v[v["event_id"] >= 0]
    hid = np.sort(hold["event_id"].unique())
    half = hid[len(hid) // 2]
    es_df = hold[hold["event_id"] < half]
    rr = Reranker(cfg, 42).fit(fit_df, es_df)
    hold_ids = np.sort(ev["val"]["event_id"].to_numpy())
    hold_ids = hold_ids[hold_ids >= cut]
    rv = pool_ranks(hold, rr.score(hold)).reindex(hold_ids).fillna(np.inf).to_numpy()
    rt = pool_ranks(F["test"], rr.score(F["test"])).reindex(ev["test"]["event_id"].to_numpy()).fillna(np.inf).to_numpy()
    return {"val": rv, "test": rt, "imp": rr.importance(), "iters": rr.model.best_iteration_}


if __name__ == "__main__":
    main()
