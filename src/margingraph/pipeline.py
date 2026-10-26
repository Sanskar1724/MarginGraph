"""Run E1-E11 end to end and write every number to results/."""
from __future__ import annotations

import json
import pickle
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from . import audit, data, split, stage2
from .features import SOURCES, CandidateGenerator
from .models import Repeat
from .optimize import Policy, option_table, solve_enum, solve_milp
from .rerank import Reranker, pool_ranks, reliability_table, split_events
from .stats import bootstrap_ci, paired_bootstrap, ranking_metrics


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str))


def _metric_table(ranks: dict[str, np.ndarray], n_boot: int, seed: int) -> pd.DataFrame:
    rows = []
    for name, rank in ranks.items():
        for metric, arr in ranking_metrics(rank).items():
            m, lo, hi = bootstrap_ci(arr, n_boot, seed)
            rows.append({"model": name, "metric": metric, "mean": m, "ci_low": lo, "ci_high": hi, "n": len(arr)})
    return pd.DataFrame(rows)


def run(cfg: dict, results_dir: str = "results", artifacts_dir: str = "artifacts") -> dict:
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    seed, n_boot = cfg["seed"], cfg["stats"]["n_boot"]
    summary: dict = {}

    # ---- data ---------------------------------------------------------
    _log("loading data")
    lines, catalog, clean_log = data.load_or_build(cfg)
    _write_json(out / "clean_log.json", clean_log)

    # ---- E2 split -----------------------------------------------------
    sc = cfg["split"]
    splits = split.temporal_split(lines, sc["val_start"], sc["test_start"])
    split_info = split.check_no_leakage(splits)
    ev = {
        k: split.make_events(splits[k], sc["min_basket_items"], sc["max_basket_items"], sc[f"max_events_{k}"], seed)
        for k in ("val", "test")
    }
    split_info.update({f"{k}_lines": len(v) for k, v in splits.items()})
    split_info.update({f"{k}_events": len(v) for k, v in ev.items()})
    train_items = set(splits["train"]["item"])
    for k in ("val", "test"):
        split_info[f"{k}_target_seen_in_train"] = float(ev[k]["target"].isin(train_items).mean())
    tv_items = train_items | set(splits["val"]["item"])
    split_info["test_target_seen_in_train_or_val"] = float(ev["test"]["target"].isin(tv_items).mean())
    _write_json(out / "e2_split.json", split_info)
    _log(f"split: {split_info}")

    # ---- E1 audit -----------------------------------------------------
    _log("E1 audit")
    gen = CandidateGenerator(splits["train"], splits["train"], catalog, cfg)
    e1 = {
        "skew": audit.popularity_skew(splits["train"]),
        "repeat": audit.repeat_rate(lines),
        "baskets": audit.basket_stats(splits["train"]),
        "copurchase_vs_shuffled_on_val": audit.copurchase_signal(splits["train"], ev["val"], gen.index, seed),
    }
    _write_json(out / "e1_audit.json", e1)
    audit.top_pairs(splits["train"], catalog, gen.index).to_csv(out / "e1_top_pairs.csv", index=False)
    summary["e1"] = e1["copurchase_vs_shuffled_on_val"]

    # ---- E3/E4 candidates + baselines ---------------------------------
    # History for the repeat scorer = everything before the split's start.
    hist = {"val": splits["train"], "test": pd.concat([splits["train"], splits["val"]])}
    # Val events are scored by models fit on train (the reranker learns from them).
    # Test events by default use models refit on train+val: val ends before test
    # starts, so this adds fresher data without any leakage.
    gens = {"val": gen}
    if cfg["retrieval"].get("refit_for_test", False):
        _log("refitting candidate models on train+val for test")
        gens["test"] = CandidateGenerator(hist["test"], hist["test"], catalog, cfg)
    else:
        gens["test"] = gen
    feats, base_ranks = {}, {}
    for k in ("val", "test"):
        _log(f"E3/E4 candidates for {k}")
        g = gens[k]
        g.scorers["repeat"] = Repeat(hist[k], g.index)
        f, r = g.generate(
            ev[k]["context"].tolist(), ev[k]["customer"].tolist(), ev[k]["target"].tolist(), ev[k]["event_id"].to_numpy()
        )
        feats[k], base_ranks[k] = f, r

    e3 = pd.concat(
        [
            _metric_table({s: base_ranks[k][s].to_numpy() for s in SOURCES}, n_boot, seed).assign(split=k)
            for k in ("val", "test")
        ]
    )
    e3.to_csv(out / "e3_baselines.csv", index=False)

    e4_rows = []
    for k in ("val", "test"):
        f = feats[k]
        in_pool = f.groupby("event_id")["label"].max()
        m, lo, hi = bootstrap_ci(in_pool.to_numpy(), n_boot, seed)
        e4_rows.append({"split": k, "metric": f"recall@{cfg['retrieval']['pool_size']}", "mean": m, "ci_low": lo, "ci_high": hi})
        for src in SOURCES:
            for K in (20, 50, 100):
                arr = (base_ranks[k][src].to_numpy() <= K).astype(float)
                e4_rows.append({"split": k, "metric": f"{src}_recall@{K}", "mean": arr.mean(), "ci_low": np.nan, "ci_high": np.nan})
    e4 = pd.DataFrame(e4_rows)
    e4.to_csv(out / "e4_retrieval.csv", index=False)
    summary["e4_test_pool_recall"] = float(e4.query("split=='test'").iloc[0]["mean"])

    # ---- E5 LightGBM reranker + E7 calibration ------------------------
    _log("E5 LightGBM reranker")
    fit_df, es_df, cal_df = split_events(feats["val"])
    rr = Reranker(cfg, seed).fit(fit_df, es_df)
    cal = rr.calibrate(cal_df)
    test_score = rr.score(feats["test"])
    test_p = rr.proba(feats["test"])
    lgb_rank = pool_ranks(feats["test"], test_score).reindex(base_ranks["test"]["event_id"]).to_numpy()

    best_base = (
        e3.query("split=='val' and metric=='ndcg@10'").sort_values("mean", ascending=False).iloc[0]["model"]
    )
    ranks_test = {s: base_ranks["test"][s].to_numpy() for s in SOURCES}
    ranks_test["lightgbm"] = lgb_rank
    e5 = _metric_table({"lightgbm": lgb_rank, best_base: ranks_test[best_base]}, n_boot, seed)
    pairs = []
    for metric in ("hit@5", "hit@10", "ndcg@10"):
        a = ranking_metrics(lgb_rank)[metric]
        b = ranking_metrics(ranks_test[best_base])[metric]
        pairs.append({"a": "lightgbm", "b": best_base, "metric": metric, **paired_bootstrap(a, b, n_boot, seed)})
    e5.to_csv(out / "e5_rerank.csv", index=False)
    pd.DataFrame(pairs).to_csv(out / "e5_paired.csv", index=False)
    rr.importance().to_csv(out / "e5_importance.csv", index=False)
    summary["best_baseline_on_val"] = best_base
    summary["e5_paired"] = pairs

    reliability_table(test_p, feats["test"]["label"].to_numpy()).to_csv(out / "e7_reliability_test.csv", index=False)
    cal["test_brier"] = float(np.mean((test_p - feats["test"]["label"].to_numpy()) ** 2))
    _write_json(out / "e7_calibration.json", cal)

    # ---- Stage 2 ------------------------------------------------------
    _log("Stage 2")
    oc = cfg["optimize"]
    gen = gens["test"]  # Stage 2, the API and the LLM slates all live in the test model's item index
    cat_idx = catalog.set_index("item").reindex(gen.index.items).reset_index()
    cat_idx["price"] = cat_idx["price"].fillna(cat_idx["price"].median())
    erp_path = cfg["data"].get("erp_path")
    real_erp = bool(erp_path) and Path(erp_path).exists()
    if real_erp:
        # Connected store: its own cost and stock, assumptions only where it has none.
        erp = data.store_erp(hist["test"], cat_idx, pd.read_parquet(erp_path), cfg, seed)
        summary["erp"] = {
            "source": cfg["data"].get("source", "store"),
            "cost_from_store_share": float((erp["cost_source"] == "store").mean()),
            "stock_from_store_share": float((erp["stock_source"] == "store").mean()),
            "cost_ratio_assumed": cfg["erp"].get("cost_ratio", 0.6),
        }
        erp.to_csv(out / "erp_store.csv", index=False)
        _log(f"store ERP: {summary['erp']}")
    else:
        erp = data.simulate_erp(hist["test"], cat_idx, cfg, seed)
        summary["erp"] = {"source": "simulated"}
        erp.to_csv(out / "erp_simulated.csv", index=False)
    p_bar = float((erp["price"] - erp["unit_cost"]).clip(lower=0).mean())

    ft = feats["test"]
    slates = {
        "ranker": stage2.build_slates(ft, test_p, test_score, oc["candidates"]),
        "popularity": stage2.build_slates(ft, test_p, ft["s_popularity"].to_numpy(), oc["candidates"]),
        "copurchase": stage2.build_slates(ft, test_p, ft["s_copurchase"].to_numpy(), oc["candidates"]),
    }
    base = dict(floor=oc["margin_floor"], max_addons=oc["max_addons"], elasticity=oc["discount_elasticity"])
    strategies = {
        "popularity_top2": ("popularity", "topk", Policy(lam=0, floor_mode="none", **base)),
        "copurchase_top2": ("copurchase", "topk", Policy(lam=0, floor_mode="none", **base)),
        "ranker_top2": ("ranker", "topk", Policy(lam=0, floor_mode="none", **base)),
    }
    for lam in oc["tradeoff_lambdas"]:
        strategies[f"milp_lam{lam}"] = ("ranker", "milp", Policy(lam=lam, floor_mode="item", **base))
    for w in oc["overstock_weights"]:
        strategies[f"milp_lam1_w{w}"] = ("ranker", "milp", Policy(lam=1.0, overstock_weight=w, floor_mode="item", **base))
    strategies["milp_lam1_bundlefloor"] = ("ranker", "milp", Policy(lam=1.0, floor_mode="bundle", **base))
    strategies["milp_lam1_discounts"] = (
        "ranker", "milp", Policy(lam=1.0, floor_mode="item", discounts=tuple(oc["discounts"]), **base)
    )

    per_event, rows = {}, []
    for name, (sl, kind, pol) in strategies.items():
        r = stage2.evaluate(slates[sl], kind, pol, erp, p_bar)
        per_event[name] = r
        row = {"strategy": name, **{k: v for k, v in asdict(pol).items() if k != "discounts"}, "discounts": str(pol.discounts)}
        for col in ("hit", "realized_profit", "expected_profit", "overstock_offered", "overstock_hit", "mean_discount", "violations"):
            m, lo, hi = bootstrap_ci(r[col].to_numpy(), n_boot, seed)
            row.update({col: m, f"{col}_lo": lo, f"{col}_hi": hi})
        rows.append(row)
        _log(f"  {name}: hit={row['hit']:.4f} realized={row['realized_profit']:.4f} expected={row['expected_profit']:.4f}")
    e8 = pd.DataFrame(rows)
    e8.to_csv(out / ("e8_strategies_store_erp.csv" if real_erp else "e8_strategies_simulated_erp.csv"), index=False)

    ref = "ranker_top2"
    e8p = []
    for name in per_event:
        if name == ref:
            continue
        for col in ("hit", "realized_profit", "expected_profit"):
            e8p.append({"a": name, "b": ref, "metric": col, **paired_bootstrap(per_event[name][col], per_event[ref][col], n_boot, seed)})
    pd.DataFrame(e8p).to_csv(out / "e8_paired_vs_ranker_top2.csv", index=False)

    # Solver check: PuLP MILP and enumeration agree on objective (E9 sanity).
    _log("E9 solver agreement check")
    sample = slates["ranker"][slates["ranker"]["event_id"].isin(ft["event_id"].unique()[:300])]
    pol = strategies["milp_lam1_bundlefloor"][2]
    pol_d = strategies["milp_lam1_discounts"][2]
    agree, worst, t_milp = 0, 0.0, 0.0
    price, cost = erp["price"].to_numpy(), erp["unit_cost"].to_numpy()
    over, stock = erp["overstock"].to_numpy(), erp["stock"].to_numpy()
    def obj(ch, g, pl):
        o = option_table(g["p"].to_numpy(), price[g.item_idx], cost[g.item_idx], over[g.item_idx], stock[g.item_idx], pl, p_bar)
        nd = len(pl.discounts)
        return sum(o["value"][j * nd + list(pl.discounts).index(d)] for j, d in ch)

    n_checked = 0
    for _, g in sample.groupby("event_id"):
        for pl in (pol, pol_d):
            args = (g["p"].to_numpy(), price[g.item_idx], cost[g.item_idx], over[g.item_idx], stock[g.item_idx], pl, p_bar)
            t0 = time.perf_counter()
            a = solve_milp(*args)
            t_milp += time.perf_counter() - t0
            b = solve_enum(*args)
            gap = abs(obj(a, g, pl) - obj(b, g, pl))
            worst = max(worst, gap)
            agree += gap < 1e-6
            n_checked += 1
    e9 = {"checked": n_checked, "objective_agree": int(agree), "max_gap": float(worst), "mean_milp_ms": 1000 * t_milp / max(n_checked, 1)}
    _write_json(out / "e9_solver_check.json", e9)

    # ---- E10 inventory simulation ------------------------------------
    _log("E10 inventory simulation")
    sim_rows = []
    for name in ["popularity_top2", "copurchase_top2", "ranker_top2", "milp_lam1.0", "milp_lam1_w1.5", "milp_lam1_w2.0"]:
        if name not in strategies:
            continue
        sl, kind, pol = strategies[name]
        sim_rows.append({"strategy": name, "mode": "replay", "seed": -1, **stage2.simulate_inventory(slates[sl], kind, pol, erp, p_bar, None)})
        for s in range(cfg["simulate"]["seeds"]):
            sim_rows.append({"strategy": name, "mode": "stochastic", "seed": s, **stage2.simulate_inventory(slates[sl], kind, pol, erp, p_bar, s)})
    sim = pd.DataFrame(sim_rows)
    sim.to_csv(out / "e10_inventory_runs.csv", index=False)
    sim.groupby(["strategy", "mode"]).agg(["mean", "std"]).drop(columns="seed").to_csv(out / "e10_inventory_summary.csv")

    # ---- E11 ERP sensitivity -----------------------------------------
    _log("E11 ERP sensitivity")
    e11 = []
    # With real store costs the simulated-margin sweep says nothing about the store.
    for mb in ([] if real_erp else ([2.0, 8.0], [4.0, 6.0], [6.0, 4.0])):
        for es in range(3):
            c2 = {**cfg, "erp": {**cfg["erp"], "margin_beta": mb}}
            erp2 = data.simulate_erp(hist["test"], cat_idx, c2, seed + 100 + es)
            pb2 = float((erp2["price"] - erp2["unit_cost"]).clip(lower=0).mean())
            ref_r = stage2.evaluate(slates["ranker"], "topk", strategies["ranker_top2"][2], erp2, pb2)
            milp_r = stage2.evaluate(slates["ranker"], "milp", strategies["milp_lam1.0"][2], erp2, pb2)
            for col in ("hit", "realized_profit", "expected_profit"):
                e11.append({"margin_beta": str(mb), "erp_seed": es, "metric": col, **paired_bootstrap(milp_r[col], ref_r[col], 500, seed)})
    if e11:
        pd.DataFrame(e11).to_csv(out / "e11_erp_sensitivity_milp_vs_ranker.csv", index=False)

    # ---- artifacts for the API ---------------------------------------
    art = Path(artifacts_dir)
    art.mkdir(parents=True, exist_ok=True)
    gen.scorers["repeat"] = Repeat(lines, gen.index)
    with open(art / "bundle.pkl", "wb") as fh:
        pickle.dump({"generator": gen, "reranker": rr, "erp": erp, "p_bar": p_bar, "cfg": cfg}, fh)

    # test-set candidate pools, for the LLM rerank notebook (E5/E6 on GPU)
    top = slates["ranker"].copy()
    top["item"] = [gen.index.items[i] for i in top["item_idx"]]
    top["description"] = gen.description[top["item_idx"].to_numpy()]
    top = top.merge(ev["test"][["event_id", "context", "target"]], on="event_id")
    top["context"] = top["context"].map(lambda c: "|".join(c))
    top.to_parquet(art / "test_slates.parquet", index=False)

    # held-out val events (not used to fit LightGBM trees), for training a
    # LightGBM + LLM stacker without touching test
    hv = pd.concat([es_df, cal_df])
    gv = gens["val"]
    vs = stage2.build_slates(hv, rr.proba(hv), rr.score(hv), oc["candidates"])
    vs["item"] = [gv.index.items[i] for i in vs["item_idx"]]
    vs["description"] = gv.description[vs["item_idx"].to_numpy()]
    vs = vs.merge(ev["val"][["event_id", "context", "target"]], on="event_id")
    vs["context"] = vs["context"].map(lambda c: "|".join(c))
    vs.to_parquet(art / "val_slates.parquet", index=False)

    # LLM fine-tuning data (E6): leave-one-out events from the last 90 days of
    # train, top-20 LightGBM slates. Hard negatives = LightGBM's wrong picks.
    # Train-period baskets only, so test stays untouched.
    tail = splits["train"][splits["train"]["ts"] >= splits["train"]["ts"].max() - pd.Timedelta(days=90)]
    ev_tr = split.make_events(tail, sc["min_basket_items"], sc["max_basket_items"], 6000, seed + 7)
    gv.scorers["repeat"] = Repeat(splits["train"], gv.index)
    ftr, _ = gv.generate(ev_tr["context"].tolist(), ev_tr["customer"].tolist(), ev_tr["target"].tolist(), ev_tr["event_id"].to_numpy())
    ts = stage2.build_slates(ftr, rr.proba(ftr), rr.score(ftr), oc["candidates"])
    ts["item"] = [gv.index.items[i] for i in ts["item_idx"]]
    ts["description"] = gv.description[ts["item_idx"].to_numpy()]
    ts = ts.merge(ev_tr[["event_id", "context", "target"]], on="event_id")
    ts["context"] = ts["context"].map(lambda c: "|".join(c))
    ts.to_parquet(art / "train_slates.parquet", index=False)
    catalog.to_parquet(art / "catalog.parquet", index=False)

    summary.update({"e3_test": e3.query("split=='test' and metric in ['hit@10','ndcg@10']").to_dict("records"), "e9": e9})
    _write_json(out / "summary.json", summary)
    _log("done")
    return summary
