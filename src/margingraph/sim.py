"""Retail store simulation: run MarginGraph day by day in a simulated store.

Flow per checkout (see docs/worklog/retail-sim.md for the diagram):
  shopper + cart -> candidate pool -> LightGBM p(accept) (top-20 slate)
  -> policy picks <= 2 add-ons (top-2 by relevance, or the MILP with a margin floor)
  -> shopper accepts/rejects -> stock, revenue, cost and profit update.

Inputs come from a real `margingraph run`: artifacts/test_slates.parquet
(real test checkouts, real LightGBM probabilities) and results/erp_simulated.csv
(SIMULATED cost, stock and overstock flags; Online Retail II has none).
Checkouts are replayed in time order and cut into `days` equal days.
Acceptance: "replay" = the shopper takes an add-on only if it is the item they
really bought; "stochastic" = each add-on is taken with its calibrated p.
Restock every `restock_every` days back to the starting level.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .optimize import Policy, solve_enum

POLICIES = {
    "ranker_top2": ("topk", Policy(lam=0.0, floor_mode="none")),
    "margingraph_item_floor": ("milp", Policy(lam=1.0, floor_mode="item")),
    "margingraph_bundle_floor": ("milp", Policy(lam=1.0, floor_mode="bundle")),
    "margingraph_overstock_w2": ("milp", Policy(lam=1.0, floor_mode="item", overstock_weight=2.0)),
}


def run_store(
    slates: pd.DataFrame,
    erp: pd.DataFrame,
    policy: str,
    days: int = 30,
    restock_every: int = 7,
    seed: int | None = None,
) -> pd.DataFrame:
    kind, pol = POLICIES[policy]
    price, cost = erp["price"].to_numpy(float), erp["unit_cost"].to_numpy(float)
    over = erp["overstock"].to_numpy(bool)
    start = erp["stock"].to_numpy(float)
    stock = start.copy()
    p_bar = float((price - cost).clip(min=0).mean())
    rng = None if seed is None else np.random.default_rng(seed)
    events = slates["event_id"].unique()
    day_of = dict(zip(events, np.arange(len(events)) * days // len(events), strict=True))
    rows, cur, led = [], None, {}
    for eid, g in slates.groupby("event_id", sort=False):
        d = day_of[eid]
        if d != cur:
            if cur is not None:
                rows.append(led)
            if d > 0 and d % restock_every == 0:
                stock = np.maximum(stock, start)
            cur = d
            led = dict(
                day=d,
                checkouts=0,
                offers=0,
                accepts=0,
                revenue=0.0,
                cost=0.0,
                profit=0.0,
                overstock_units=0,
                stockout_blocks=0,
                floor_breaks=0,
            )
        items = g["item_idx"].to_numpy()
        p, lab, sc = g["p"].to_numpy(), g["label"].to_numpy(), g["score"].to_numpy()
        led["checkouts"] += 1
        led["stockout_blocks"] += int((stock[items[np.argsort(-sc)[:2]]] <= 0).sum())
        if kind == "topk":
            order = [j for j in np.argsort(-sc, kind="stable") if stock[items[j]] > 0][: pol.max_addons]
            chosen = [(int(j), 0.0) for j in order]
        else:
            chosen = solve_enum(p, price[items], cost[items], over[items], stock[items], pol, p_bar)
        for j, disc in chosen:
            i = items[j]
            rev = price[i] * (1 - disc)
            led["offers"] += 1
            led["floor_breaks"] += int(rev - cost[i] < 0.15 * rev - 1e-9)
            ok = lab[j] == 1 if rng is None else rng.random() < min(1.0, p[j] * (1 + pol.elasticity * disc))
            if ok and stock[i] > 0:
                stock[i] -= 1
                led["accepts"] += 1
                led["revenue"] += rev
                led["cost"] += cost[i]
                led["profit"] += rev - cost[i]
                led["overstock_units"] += int(over[i])
    rows.append(led)
    out = pd.DataFrame(rows)
    out.insert(0, "policy", policy)
    out.insert(1, "seed", -1 if seed is None else seed)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="MarginGraph retail store simulation")
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="results/retail_sim")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seeds", type=int, default=5)
    a = ap.parse_args(argv)
    slates = pd.read_parquet(Path(a.artifacts) / "test_slates.parquet")
    erp = pd.read_csv(Path(a.results) / "erp_simulated.csv")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for pol in POLICIES:
        runs.append(run_store(slates, erp, pol, a.days, seed=None))
        for s in range(a.seeds):
            runs.append(run_store(slates, erp, pol, a.days, seed=s))
    daily = pd.concat(runs, ignore_index=True)
    daily.to_csv(out / "daily_ledger.csv", index=False)
    tot = daily.groupby(["policy", "seed"]).sum(numeric_only=True).drop(columns="day").reset_index()
    tot["mode"] = np.where(tot["seed"] < 0, "replay", "stochastic")
    summ = (
        tot.groupby(["mode", "policy"])
        .agg(
            profit=("profit", "mean"),
            profit_sd=("profit", "std"),
            revenue=("revenue", "mean"),
            accepts=("accepts", "mean"),
            offers=("offers", "mean"),
            overstock_units=("overstock_units", "mean"),
            stockout_blocks=("stockout_blocks", "mean"),
            floor_breaks=("floor_breaks", "mean"),
        )
        .reset_index()
    )
    summ["accept_rate"] = summ["accepts"] / summ["offers"]
    summ["margin"] = summ["profit"] / summ["revenue"]
    summ.to_csv(out / "summary.csv", index=False)
    print(summ.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
