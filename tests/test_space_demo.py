"""Checks for the self-contained demo in space/ (runs without the full pipeline)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "space"))
core = pytest.importorskip("core")


def brute(p, price, cost, over, stock, pol, p_bar):
    from itertools import combinations
    opts = [(i, d) for i in range(len(p)) for d in pol.discounts]
    def val(i, d):
        r = price[i] * (1 - d); pr = r - cost[i]
        if stock[i] <= 0 or pr < pol.floor * r - 1e-9:
            return None
        pa = min(1.0, p[i] * (1 + pol.elasticity * d))
        return pa * ((1 - pol.lam) * p_bar + pol.lam * (pol.overstock_weight if over[i] else 1.0) * pr)
    best = 0.0
    for k in range(1, pol.max_addons + 1):
        for combo in combinations(opts, k):
            if len({i for i, _ in combo}) < k:
                continue
            vs = [val(i, d) for i, d in combo]
            if None not in vs and all(v > 0 for v in vs):
                best = max(best, sum(vs))
    return best


@pytest.mark.parametrize("seed", range(30))
def test_solver_matches_brute_force_and_respects_rules(seed):
    rng = np.random.default_rng(seed)
    n = 8
    p = rng.uniform(0.001, 0.2, n)
    price = rng.uniform(1, 20, n)
    cost = price * rng.uniform(0.3, 1.0, n)
    over = rng.random(n) < 0.3
    stock = rng.integers(0, 5, n)
    pol = core.Policy(lam=float(rng.uniform()), overstock_weight=float(rng.uniform(1, 2)),
                      floor=0.15, discounts=(0.0, 0.1, 0.2), max_addons=int(rng.integers(1, 3)))
    chosen = core.solve(p, price, cost, over, stock, pol, 0.02)
    assert len(chosen) <= pol.max_addons
    assert len({i for i, _ in chosen}) == len(chosen)
    got = 0.0
    for i, d in chosen:
        r = price[i] * (1 - d)
        assert stock[i] > 0 and r - cost[i] >= pol.floor * r - 1e-9
        pa = min(1.0, p[i] * (1 + pol.elasticity * d))
        got += pa * ((1 - pol.lam) * 0.02 + pol.lam * (pol.overstock_weight if over[i] else 1) * (r - cost[i]))
    assert got == pytest.approx(brute(p, price, cost, over, stock, pol, 0.02), rel=1e-9, abs=1e-12)


def test_merchant_training_end_to_end():
    rng = np.random.default_rng(0)
    # Two product families that co-occur; the model should learn them.
    baskets = [[f"A{j}" for j in rng.choice(10, 3, replace=False)] if k % 2 else
               [f"B{j}" for j in rng.choice(10, 3, replace=False)] for k in range(400)]
    cat = pd.DataFrame({"item": [f"{f}{j}" for f in "AB" for j in range(10)]})
    cat["description"] = cat["item"]
    cat["price"], cat["unit_cost"], cat["stock"], cat["overstock"] = 10.0, 6.0, 5, False
    cat.loc[cat["item"] == "A1", "unit_cost"] = 9.5          # 5% margin: never offered at floor 15%
    m = core.train_from_baskets(baskets, cat)
    assert m.calib["hit"]["hit@10"] > 0.5
    res = m.recommend(["A0", "A2"], core.Policy())
    picked = [res["candidates"].at[j, "item"] for j, _ in res["optimized"]]
    assert picked and all(s.startswith("A") for s in picked) and "A1" not in picked
    assert res["candidates"]["item"].str.startswith("A").head(5).all()


def test_unknown_items_and_missing_prices_are_safe():
    cat = pd.DataFrame({"item": ["X", "Y"], "description": ["x", "y"], "price": [5.0, None],
                        "unit_cost": [1.0, None], "stock": [3, None], "overstock": [False, None]})
    m = core.Model(["X", "Y", "Z"], np.ones((3, 3), np.float32) - np.eye(3, dtype=np.float32),
                   {"w": [1.0, -1.0, -3.0], "p_bar": 0.02}, cat)
    res = m.recommend(["X", "NOPE"], core.Policy())
    assert res["unknown"] == ["NOPE"]
    picked = {res["candidates"].at[j, "item"] for j, _ in res["optimized"]}
    assert picked <= {"X"} - {"X"}  # Y has no price, Z not in catalog: nothing sellable
