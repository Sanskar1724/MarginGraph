"""A/B summary with bootstrap 95% CIs straight from the service database.

Per request: converted (any shown add-on bought), profit from bought add-ons,
and unit profit (profit if one unit had been bought, which removes the effect
of wholesale order quantities).

    DATABASE_URL=sqlite:///data/margingraph.db python scripts/ab_report.py --store demo
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text


def boot_diff(a: np.ndarray, b: np.ndarray, n: int = 5000, seed: int = 0) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    d = rng.choice(a, (n, len(a))).mean(1) - rng.choice(b, (n, len(b))).mean(1)
    return float(a.mean() - b.mean()), float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="demo")
    ap.add_argument("--treatment", default="treatment")
    ap.add_argument("--control", default="control")
    args = ap.parse_args()
    eng = create_engine(os.environ.get("DATABASE_URL", "sqlite:///data/margingraph.db"))
    with eng.connect() as c:
        recs = pd.read_sql(text("SELECT request_id, variant FROM recommendations WHERE store_id=:s"), c, params={"s": args.store})
        ev = pd.read_sql(
            text("SELECT request_id, item, quantity, revenue, profit FROM rec_events WHERE store_id=:s AND event_type='purchase'"),
            c, params={"s": args.store},
        )
    ev["unit_profit"] = ev["profit"] / ev["quantity"]
    g = ev.groupby("request_id").agg(profit=("profit", "sum"), unit_profit=("unit_profit", "sum"))
    df = recs.set_index("request_id").join(g).fillna(0.0)
    df["converted"] = (df["profit"] != 0).astype(float)
    out = {}
    for v, d in df.groupby("variant"):
        out[v] = {"requests": len(d), **{m: round(float(d[m].mean()), 4) for m in ("converted", "profit", "unit_profit")}}
    t, c_ = df[df["variant"] == args.treatment], df[df["variant"] == args.control]
    if len(t) and len(c_):
        out["treatment_minus_control"] = {}
        for m in ("converted", "profit", "unit_profit"):
            diff, lo, hi = boot_diff(t[m].to_numpy(), c_[m].to_numpy())
            rel = diff / c_[m].mean() if c_[m].mean() else float("nan")
            out["treatment_minus_control"][m] = {"diff": round(diff, 4), "ci95": [round(lo, 4), round(hi, 4)], "relative": round(rel, 3)}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
