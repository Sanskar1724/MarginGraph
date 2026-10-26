"""Build the small artifacts the demo Space ships with (run once, offline).

    python space/build_artifacts.py --xlsx /path/to/online_retail_II.xlsx

Protocol (same dates as the main repo, configs/default.yaml):
  train  < 2011-07-01          fit EASE
  val    2011-07 .. 2011-09    fit p(accept) calibration (leave-one-out)
  test   2011-10 .. 2011-12    backtest, EASE refit on train+val (as the repo does)
  serve  all dates             EASE refit on everything for the live demo

Cost and stock are SIMULATED with margingraph.data.simulate_erp (seed 42):
Online Retail II has neither. Every profit number in the demo says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from margingraph.data import build_catalog, clean, read_raw, simulate_erp  # noqa: E402

import core  # noqa: E402

VAL, TEST = pd.Timestamp("2011-07-01"), pd.Timestamp("2011-10-01")


def load(args, cfg):
    if args.lines and Path(args.lines).exists():
        return pd.read_parquet(args.lines), pd.read_parquet(args.catalog)
    raw = read_raw(args.xlsx)
    lines, _ = clean(raw, cfg["data"]["product_code_regex"])
    raw_ok = raw.assign(item=raw["item"].astype(str).str.strip().str.upper())
    cat = build_catalog(raw_ok[raw_ok["item"].isin(lines["item"].unique())], lines)
    return lines, cat


def encode(lines, pos):
    lines = lines[lines["item"].isin(pos)].sort_values("ts")
    g = lines.groupby("invoice", sort=False)["item"].apply(lambda s: [pos[i] for i in dict.fromkeys(s)])
    return [b for b in g.tolist() if 1 <= len(b) <= 50]


def backtest(B, calib, events, erp, rng, n_boot=1000):
    price, cost = erp["price"].to_numpy(float), erp["unit_cost"].to_numpy(float)
    stock, over = erp["stock"].to_numpy(float), erp["overstock"].to_numpy(bool)
    strategies = {
        "top2_relevance": None,
        "margingraph_lam0.5": core.Policy(lam=0.5),
        "margingraph_lam1.0": core.Policy(lam=1.0),
        "margingraph_lam1.0_overstock2x": core.Policy(lam=1.0, overstock_weight=2.0),
    }
    rec = {k: [] for k in strategies}
    for ctx, hid in events:
        s = core.scores_for(B, ctx)
        top = np.argsort(-s)[:20]
        p = core.proba(calib["w"], s[top], np.arange(20))
        pr, co, st, ov = price[top], cost[top], stock[top], over[top]
        for name, pol in strategies.items():
            if pol is None:
                chosen = [(j, 0.0) for j in [j for j in range(20) if st[j] > 0][:2]]
            else:
                chosen = core.solve(p, pr, co, ov, st, pol, calib["p_bar"])
            hit = any(top[j] == hid for j, _ in chosen)
            realized = sum(pr[j] - co[j] for j, _ in chosen if top[j] == hid)
            rec[name].append({
                "hit": hit, "realized_profit": realized,
                "exp_profit": sum(p[j] * (pr[j] - co[j]) for j, _ in chosen),
                "violations": sum(int(pr[j] - co[j] < 0.15 * pr[j]) for j, _ in chosen),
                "overstock_offers": sum(int(ov[j]) for j, _ in chosen),
                "offers": len(chosen),
            })
    out, base = {}, pd.DataFrame(rec["top2_relevance"])
    for name, r in rec.items():
        df = pd.DataFrame(r)
        d = (df["realized_profit"] - base["realized_profit"]).to_numpy()
        boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)]
        out[name] = {
            "hit@2": float(df["hit"].mean()),
            "realized_profit_per_basket": float(df["realized_profit"].mean()),
            "expected_profit_per_basket": float(df["exp_profit"].mean()),
            "margin_floor_violations_per_basket": float(df["violations"].mean()),
            "overstock_share_of_offers": float(df["overstock_offers"].sum() / max(df["offers"].sum(), 1)),
            "realized_profit_vs_top2_pct": float(100 * (df["realized_profit"].mean() / base["realized_profit"].mean() - 1)),
            "realized_profit_diff_ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="/mnt/project-files/online_retail_II.xlsx")
    ap.add_argument("--lines", help="optional cached clean lines parquet")
    ap.add_argument("--catalog", help="optional cached catalog parquet")
    ap.add_argument("--n-items", type=int, default=2000)
    ap.add_argument("--out", default=str(HERE / "artifacts"))
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs/default.yaml").read_text())
    lam = float(cfg["baselines"]["ease_lambda"])
    rng = np.random.default_rng(42)

    lines, catalog = load(args, cfg)
    lines["ts"] = pd.to_datetime(lines["ts"])
    tr, va, te = lines[lines.ts < VAL], lines[(lines.ts >= VAL) & (lines.ts < TEST)], lines[lines.ts >= TEST]

    # Catalog = the n most-bought items in train+val (no test leakage).
    items = lines[lines.ts < TEST].groupby("item")["invoice"].nunique().nlargest(args.n_items).index.tolist()
    pos = {s: i for i, s in enumerate(items)}
    cover = te["item"].isin(pos).mean()

    B_tr = core.fit_ease(encode(tr, pos), len(items), lam)
    calib = core.calibrate(B_tr, core.loo_events(encode(va, pos), rng))

    erp = simulate_erp(lines[lines.ts < TEST], catalog, cfg, seed=42)
    erp = erp.merge(catalog[["item", "description", "category"]], on="item").set_index("item").reindex(items)

    B_trva = core.fit_ease(encode(lines[lines.ts < TEST], pos), len(items), lam)
    test_events = core.loo_events(encode(te, pos), rng, max_events=4000)
    calib_test = core.calibrate(B_trva, test_events)
    bt = backtest(B_trva, calib, test_events, erp.reset_index(), rng)

    B_all = core.fit_ease(encode(lines, pos), len(items), lam)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "ease.npz", B=B_all.astype(np.float16), items=np.array(items))
    erp.reset_index()[["item", "description", "category", "price", "unit_cost", "stock", "overstock", "weekly_demand"]] \
        .round({"price": 2, "unit_cost": 2, "weekly_demand": 2}).to_csv(out / "catalog.csv", index=False)

    # Example baskets: real test invoices of 3-6 catalog items.
    ex = [b for b in encode(te, pos) if 3 <= len(b) <= 6]
    picks = [ex[i] for i in rng.choice(len(ex), 12, replace=False)]
    examples = [[items[i] for i in b[:-1]] for b in picks]

    meta = {
        "calibration": calib,
        "test_ranking": {k: v for k, v in calib_test.items() if k != "w"},
        "backtest": bt,
        "n_items": len(items),
        "test_line_coverage": float(cover),
        "n_test_events": len(test_events),
        "ease_lambda": lam,
        "examples": examples,
        "note": "unit_cost and stock are SIMULATED (Online Retail II has neither); "
                "backtest = Oct-Dec 2011, model fit on Dec 2009-Sep 2011.",
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: v for k, v in meta.items() if k != "examples"}, indent=2))


if __name__ == "__main__":
    main()
