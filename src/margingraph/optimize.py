"""Stage 2: choose at most K add-ons that trade relevance against margin.

For each basket the reranker gives calibrated p(accept) for the top-N
candidates. Decision x[i,d] = 1 offers item i at discount d.

    max  sum x[i,d] * p[i,d] * ((1 - lam) * P_bar + lam * w_i * profit[i,d])
    s.t. sum_d x[i,d] <= 1                       one discount per item
         sum x[i,d]   <= max_addons
         x[i,d] = 0 if stock_i <= 0
         margin floor, either per item:  profit[i,d] >= floor * rev[i,d]
                           or per bundle: sum x*profit >= floor * sum x*rev

p[i,d] = min(1, p_i * (1 + elasticity * d)) is an ASSUMED discount response.
lam = 0 is pure relevance, lam = 1 is overstock-weighted expected profit.

``solve_milp`` uses PuLP (CBC if installed, else HiGHS) and is what the API
runs. ``solve_enum`` enumerates every feasible bundle of size <= 2 exactly and
is used for the bulk offline sweeps; tests check that both agree.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pulp


@dataclass
class Policy:
    lam: float = 1.0
    overstock_weight: float = 1.0
    floor: float = 0.15
    floor_mode: str = "item"          # "item" | "bundle" | "none"
    discounts: tuple[float, ...] = (0.0,)
    elasticity: float = 1.5
    max_addons: int = 2


def option_table(p, price, cost, overstock, stock, pol: Policy, p_bar: float):
    """Expand candidates into (item, discount) options with value, profit and revenue."""
    n = len(p)
    d = np.asarray(pol.discounts, dtype=float)
    rev = price[:, None] * (1 - d[None, :])
    profit = rev - cost[:, None]
    pa = np.minimum(1.0, p[:, None] * (1 + pol.elasticity * d[None, :]))
    w = np.where(overstock, pol.overstock_weight, 1.0)[:, None]
    value = pa * ((1 - pol.lam) * p_bar + pol.lam * w * profit)
    ok = np.repeat((stock > 0)[:, None], len(d), axis=1)
    if pol.floor_mode == "item":
        ok &= profit >= pol.floor * rev - 1e-9
    return {
        "item": np.repeat(np.arange(n), len(d)),
        "disc": np.tile(d, n),
        "value": value.ravel(),
        "profit": profit.ravel(),
        "rev": rev.ravel(),
        "pa": pa.ravel(),
        "ok": ok.ravel(),
    }


def solve_enum(p, price, cost, overstock, stock, pol: Policy, p_bar: float) -> list[tuple[int, float]]:
    """Exact solution for max_addons <= 2 by enumerating singles and pairs."""
    o = option_table(p, price, cost, overstock, stock, pol, p_bar)
    idx = np.flatnonzero(o["ok"])
    if len(idx) == 0:
        return []
    v, pr, rv, it = o["value"][idx], o["profit"][idx], o["rev"][idx], o["item"][idx]
    best_val, best = 0.0, []
    single_ok = pr >= pol.floor * rv - 1e-9 if pol.floor_mode == "bundle" else np.ones(len(idx), bool)
    if single_ok.any():
        j = np.argmax(np.where(single_ok, v, -np.inf))
        if v[j] > best_val:
            best_val, best = v[j], [j]
    if pol.max_addons >= 2 and len(idx) >= 2:
        V = v[:, None] + v[None, :]
        feas = (it[:, None] != it[None, :]) & np.triu(np.ones((len(idx),) * 2, bool), 1)
        if pol.floor_mode == "bundle":
            feas &= (pr[:, None] + pr[None, :]) >= pol.floor * (rv[:, None] + rv[None, :]) - 1e-9
        V = np.where(feas, V, -np.inf)
        a, b = np.unravel_index(np.argmax(V), V.shape)
        if V[a, b] > best_val + 1e-12:
            best_val, best = V[a, b], [a, b]
    return [(int(it[j]), float(o["disc"][idx][j])) for j in best]


def _binary(prob, name: str):
    # PuLP >= 4 creates variables through the problem; 2.x through LpVariable.
    if hasattr(prob, "add_variable"):
        return prob.add_variable(name, cat="Binary")
    return pulp.LpVariable(name, cat="Binary")


def _solver():
    """CBC when installed (PuLP 2.x bundles it), otherwise HiGHS via highspy."""
    for name in ("PULP_CBC_CMD", "COIN_CMD", "HiGHS", "HiGHS_CMD"):
        cls = getattr(pulp, name, None)
        if cls is not None and cls(msg=False).available():
            return cls(msg=False)
    raise RuntimeError(f"no MILP solver available: {pulp.listSolvers(onlyAvailable=True)}")


def solve_milp(p, price, cost, overstock, stock, pol: Policy, p_bar: float) -> list[tuple[int, float]]:
    o = option_table(p, price, cost, overstock, stock, pol, p_bar)
    prob = pulp.LpProblem("addons", pulp.LpMaximize)
    x = {j: _binary(prob, f"x{j}") for j in np.flatnonzero(o["ok"])}
    if not x:
        return []
    prob += pulp.lpSum(float(o["value"][j]) * x[j] for j in x)
    prob += pulp.lpSum(x.values()) <= pol.max_addons
    for i in np.unique(o["item"][list(x)]):
        prob += pulp.lpSum(x[j] for j in x if o["item"][j] == i) <= 1
    if pol.floor_mode == "bundle":
        prob += pulp.lpSum(float(o["profit"][j] - pol.floor * o["rev"][j]) * x[j] for j in x) >= 0
    prob.solve(_solver())
    return [(int(o["item"][j]), float(o["disc"][j])) for j in x if (x[j].value() or 0) > 0.5]


def check_constraints(chosen, price, cost, pol: Policy) -> int:
    """Number of violated hard rules in one solution (should always be 0)."""
    v = int(len(chosen) > pol.max_addons)
    items = [i for i, _ in chosen]
    v += int(len(items) != len(set(items)))
    rev = np.array([price[i] * (1 - d) for i, d in chosen])
    prof = np.array([price[i] * (1 - d) - cost[i] for i, d in chosen])
    if pol.floor_mode == "item":
        v += int((prof < pol.floor * rev - 1e-9).sum())
    elif pol.floor_mode == "bundle" and len(chosen):
        v += int(prof.sum() < pol.floor * rev.sum() - 1e-9)
    return v
