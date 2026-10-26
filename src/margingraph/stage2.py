"""E8-E11: offline strategy comparison and sequential inventory simulation.

Every Stage 2 number depends on the SIMULATED cost and stock (data.simulate_erp)
and on the assumed discount elasticity; results files say so in their name/column.

Two ways to score an offer:
  * replay: the customer accepts an offered item only if it is the item they
    really bought (the held-out one). Grounded in real behaviour; conservative.
  * expected: sum of p(accept) * unit profit over offered items, using the
    calibrated reranker. Model-based; depends on calibration.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .optimize import Policy, check_constraints, solve_enum


def build_slates(feats: pd.DataFrame, proba: np.ndarray, score: np.ndarray, n: int) -> pd.DataFrame:
    """Keep the top-n candidates per event by ``score`` (reranker or a baseline)."""
    df = feats[["event_id", "item_idx", "label"]].copy()
    df["p"] = proba
    df["score"] = score
    df = df.sort_values(["event_id", "score"], ascending=[True, False])
    return df.groupby("event_id", sort=False).head(n).reset_index(drop=True)


def _choose(g: pd.DataFrame, strategy: str, pol: Policy, erp_arrays, p_bar: float, stock_now=None):
    price, cost, over, stock = erp_arrays
    items = g["item_idx"].to_numpy()
    st = stock[items] if stock_now is None else stock_now[items]
    if strategy == "topk":
        order = np.argsort(-g["score"].to_numpy(), kind="stable")
        order = [j for j in order if st[j] > 0][: pol.max_addons]
        return [(int(j), 0.0) for j in order]
    return solve_enum(g["p"].to_numpy(), price[items], cost[items], over[items], st, pol, p_bar)


def evaluate(slates: pd.DataFrame, strategy: str, pol: Policy, erp: pd.DataFrame, p_bar: float) -> pd.DataFrame:
    """Static-stock evaluation, one row per event."""
    price, cost = erp["price"].to_numpy(), erp["unit_cost"].to_numpy()
    over, stock = erp["overstock"].to_numpy(), erp["stock"].to_numpy()
    rows = []
    for eid, g in slates.groupby("event_id", sort=False):
        items = g["item_idx"].to_numpy()
        chosen = _choose(g, strategy, pol, (price, cost, over, stock), p_bar)
        rows.append(_score_offer(eid, g, items, chosen, price, cost, over, pol))
    return pd.DataFrame(rows)


def _score_offer(eid, g, items, chosen, price, cost, over, pol):
    lab, p = g["label"].to_numpy(), g["p"].to_numpy()
    real = [items[j] for j, _ in chosen]
    hit, realized, exp_profit, over_hit = 0, 0.0, 0.0, 0
    for j, d in chosen:
        i = items[j]
        unit = price[i] * (1 - d) - cost[i]
        exp_profit += min(1.0, p[j] * (1 + pol.elasticity * d)) * unit
        if lab[j] == 1:
            hit, realized, over_hit = 1, unit, int(over[i])
    # baselines run without a floor; count how often they would break the per-item one
    check_pol = pol if pol.floor_mode != "none" else replace(pol, floor_mode="item")
    viol = check_constraints([(items[j], d) for j, d in chosen], price, cost, check_pol)
    return {
        "event_id": eid,
        "n_offered": len(chosen),
        "hit": hit,
        "realized_profit": realized,
        "expected_profit": exp_profit,
        "overstock_offered": int(sum(over[i] for i in real)),
        "overstock_hit": over_hit,
        "mean_discount": float(np.mean([d for _, d in chosen])) if chosen else 0.0,
        "violations": viol,
    }


def simulate_inventory(
    slates: pd.DataFrame, strategy: str, pol: Policy, erp: pd.DataFrame, p_bar: float, seed: int | None
) -> dict:
    """Replay test baskets in time order with shared, decrementing stock.

    seed=None -> replay acceptance (accept only the real held-out item);
    otherwise each offered item is accepted with its calibrated p (one unit).
    """
    price, cost = erp["price"].to_numpy(), erp["unit_cost"].to_numpy()
    over = erp["overstock"].to_numpy()
    stock = erp["stock"].to_numpy().astype(float).copy()
    start_over_units = stock[over].sum()
    rng = None if seed is None else np.random.default_rng(seed)
    profit, accepts, over_units, stockout_skips = 0.0, 0, 0.0, 0
    for _, g in slates.groupby("event_id", sort=False):
        items = g["item_idx"].to_numpy()
        stockout_skips += int((stock[items[:2]] <= 0).sum())
        chosen = _choose(g, strategy, pol, (price, cost, over, stock), p_bar, stock_now=stock)
        lab, p = g["label"].to_numpy(), g["p"].to_numpy()
        for j, d in chosen:
            i = items[j]
            pa = min(1.0, p[j] * (1 + pol.elasticity * d))
            ok = lab[j] == 1 if rng is None else rng.random() < pa
            if ok and stock[i] > 0:
                stock[i] -= 1
                accepts += 1
                profit += price[i] * (1 - d) - cost[i]
                over_units += over[i]
    return {
        "profit": profit,
        "accepts": accepts,
        "overstock_units_cleared": over_units,
        "overstock_share_cleared": over_units / max(start_over_units, 1),
        "top2_stockouts_seen": stockout_skips,
    }
