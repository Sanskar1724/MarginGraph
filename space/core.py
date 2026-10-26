"""MarginGraph demo core: basket -> relevant add-ons -> margin-safe pick of 2.

Self-contained (numpy + pandas only) so it runs on a free CPU Space.

Stage 1  EASE item-item model (Steck 2019). On Online Retail II it is the
         strongest single baseline in the main repo (test Hit@10 31.1%); the
         repo's LightGBM reranker beats it (35.6%) but needs the full feature
         pipeline, so the demo ships EASE only.
Stage 1b Logistic calibration of the EASE score into p(accept), fitted on
         held-out baskets (leave-one-out: hide one item, can we find it?).
Stage 2  Exact solver for <= 2 add-ons: enumerate every feasible single and
         pair, maximize  sum p * ((1 - lam) * p_bar + lam * w * profit)
         subject to margin floor, stock > 0, one discount per item.
         Same objective and constraints as margingraph.optimize.solve_enum.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Stage 1: EASE
# --------------------------------------------------------------------------

def fit_ease(baskets: list[list[int]], n_items: int, lam: float = 250.0) -> np.ndarray:
    """Closed-form EASE weights B (n_items x n_items, zero diagonal)."""
    rows = np.concatenate([np.full(len(b), i) for i, b in enumerate(baskets)])
    cols = np.concatenate([np.asarray(b, dtype=int) for b in baskets])
    X = np.zeros((len(baskets), n_items), dtype=np.float32)
    X[rows, cols] = 1.0
    G = (X.T @ X).astype(np.float64)
    G[np.diag_indices(n_items)] += lam
    P = np.linalg.inv(G)
    B = -P / np.diag(P)[None, :]
    B[np.diag_indices(n_items)] = 0.0
    return B.astype(np.float32)


def scores_for(B: np.ndarray, basket: list[int]) -> np.ndarray:
    s = B[basket].sum(axis=0).astype(np.float64)
    s[basket] = -np.inf
    return s


# --------------------------------------------------------------------------
# Stage 1b: calibration  p(accept) = sigmoid(a * score + b * log1p(rank) + c)
# --------------------------------------------------------------------------

def _feat(score: np.ndarray, rank: np.ndarray) -> np.ndarray:
    return np.column_stack([score, np.log1p(rank), np.ones_like(score)])


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-3, iters: int = 50) -> np.ndarray:
    w = np.zeros(X.shape[1])
    for _ in range(iters):  # Newton steps
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def loo_events(baskets: list[list[int]], rng: np.random.Generator, max_events: int = 4000):
    """Leave-one-out events from held-out baskets: (context, hidden item)."""
    ev = []
    for b in baskets:
        if len(b) < 2 or len(b) > 50:
            continue
        h = int(rng.integers(len(b)))
        ev.append(([x for k, x in enumerate(b) if k != h], b[h]))
    rng.shuffle(ev)
    return ev[:max_events]


def calibrate(B: np.ndarray, events, top_n: int = 20) -> dict:
    X, y, hits, p_tops = [], [], {2: 0, 5: 0, 10: 0}, []
    for ctx, hid in events:
        s = scores_for(B, ctx)
        top = np.argsort(-s)[:top_n]
        top = top[np.isfinite(s[top])]  # small catalogs: fewer than top_n candidates
        X.append(_feat(s[top], np.arange(len(top))))
        y.append((top == hid).astype(float))
        for k in hits:
            hits[k] += int(hid in top[:k])
    X, y = np.vstack(X), np.concatenate(y)
    w = fit_logistic(X, y, l2=1.0)
    p = 1 / (1 + np.exp(-(X @ w)))
    n = max(len(events), 1)
    return {
        "w": w.tolist(),
        "p_bar": float(p.mean()),
        "n_events": len(events),
        "hit": {f"hit@{k}": hits[k] / n for k in hits},
        "recall_top_n": float(y.sum() / n),
        "top_n": top_n,
    }


def proba(w, score: np.ndarray, rank: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(_feat(score, rank) @ np.asarray(w))))


# --------------------------------------------------------------------------
# Stage 2: margin-aware selection (exact for max_addons <= 2)
# --------------------------------------------------------------------------

@dataclass
class Policy:
    lam: float = 1.0                 # 0 = pure relevance, 1 = profit-weighted
    overstock_weight: float = 1.0    # 1.0-2.0x boost for overstocked items
    floor: float = 0.15              # minimum post-discount margin per item
    discounts: tuple = (0.0,)
    elasticity: float = 1.5          # ASSUMED: p(accept|d) = p * (1 + e * d)
    max_addons: int = 2


def solve(p, price, cost, overstock, stock, pol: Policy, p_bar: float) -> list[tuple[int, float]]:
    """Return [(candidate index, discount), ...] maximizing the objective."""
    n = len(p)
    if n == 0:
        return []
    d = np.asarray(pol.discounts, dtype=float)
    rev = price[:, None] * (1 - d[None, :])
    profit = rev - cost[:, None]
    pa = np.minimum(1.0, p[:, None] * (1 + pol.elasticity * d[None, :]))
    w = np.where(overstock, pol.overstock_weight, 1.0)[:, None]
    value = (pa * ((1 - pol.lam) * p_bar + pol.lam * w * profit)).ravel()
    ok = (np.repeat((stock > 0)[:, None], len(d), axis=1) & (profit >= pol.floor * rev - 1e-9)).ravel()
    item, disc = np.repeat(np.arange(n), len(d)), np.tile(d, n)
    idx = np.flatnonzero(ok & (value > 0))
    if len(idx) == 0:
        return []
    v, it = value[idx], item[idx]
    best_val, best = v.max(), [int(np.argmax(v))]
    if pol.max_addons >= 2 and len(idx) >= 2:
        V = v[:, None] + v[None, :]
        feas = (it[:, None] != it[None, :]) & np.triu(np.ones((len(idx),) * 2, bool), 1)
        V = np.where(feas, V, -np.inf)
        a, b = np.unravel_index(np.argmax(V), V.shape)
        if V[a, b] > best_val + 1e-12:
            best = [int(a), int(b)]
    return [(int(it[j]), float(disc[idx][j])) for j in best]


# --------------------------------------------------------------------------
# Model bundle used by the app
# --------------------------------------------------------------------------

@dataclass
class Model:
    items: list[str]                 # stock codes, index = model column
    B: np.ndarray
    calib: dict
    catalog: pd.DataFrame            # item, description, price, unit_cost, stock, overstock
    pos: dict = field(default_factory=dict)

    def __post_init__(self):
        self.pos = {s: i for i, s in enumerate(self.items)}
        c = self.catalog.drop_duplicates("item").set_index("item").reindex(self.items)
        c.index.name = "item"
        c["description"] = c["description"].fillna("").astype(str)
        c.loc[c["description"] == "", "description"] = c.index[c["description"] == ""]
        c["price"] = pd.to_numeric(c["price"], errors="coerce").fillna(0.0)
        c["unit_cost"] = pd.to_numeric(c["unit_cost"], errors="coerce").fillna(c["price"])
        # Items without a price or stock count are never offered.
        c["stock"] = pd.to_numeric(c["stock"], errors="coerce").fillna(0).clip(lower=0)
        c.loc[c["price"] <= 0, "stock"] = 0
        c["overstock"] = c["overstock"].fillna(False).astype(bool)
        self.catalog = c.reset_index()

    def recommend(self, basket_codes: list[str], pol: Policy, top_n: int = 20) -> dict:
        codes = [str(c).strip().upper() for c in basket_codes]
        known = [self.pos[c] for c in dict.fromkeys(codes) if c in self.pos]
        unknown = [c for c in codes if c not in self.pos]
        if not known:
            return {"known": [], "unknown": unknown, "candidates": pd.DataFrame(), "optimized": [], "top": []}
        s = scores_for(self.B, known)
        top = np.argsort(-s)[:top_n]
        top = top[np.isfinite(s[top])]
        p = proba(self.calib["w"], s[top], np.arange(len(top)))
        c = self.catalog.iloc[top].reset_index(drop=True)
        price, cost = c["price"].to_numpy(float), c["unit_cost"].to_numpy(float)
        stock, over = c["stock"].to_numpy(float), c["overstock"].to_numpy(bool)
        # Why: the basket item with the largest EASE weight toward each candidate.
        contrib = self.B[np.ix_(known, top)]
        because = [self.catalog["description"].iat[known[k]] for k in contrib.argmax(axis=0)]
        cand = pd.DataFrame({
            "rank": np.arange(1, len(top) + 1),
            "item": c["item"], "description": c["description"],
            "p_accept": p, "price": price, "unit_cost": cost,
            "margin": np.divide(price - cost, price, out=np.zeros_like(price), where=price > 0), "stock": stock.astype(int), "overstock": over,
            "exp_profit": p * (price - cost), "because_of": because,
        })
        in_stock = [j for j in range(len(top)) if stock[j] > 0]
        topk = [(j, 0.0) for j in in_stock[: pol.max_addons]]
        opt = solve(p, price, cost, over, stock, pol, self.calib["p_bar"])
        return {"known": [self.items[i] for i in known], "unknown": unknown,
                "candidates": cand, "optimized": opt, "top": topk}


def offer_stats(cand: pd.DataFrame, chosen, pol: Policy) -> dict:
    """Expected profit / revenue / margin of an offer, plus floor violations."""
    ep = er = 0.0
    viol = 0
    for j, d in chosen:
        r = cand.at[j, "price"] * (1 - d)
        pr = r - cand.at[j, "unit_cost"]
        pa = min(1.0, cand.at[j, "p_accept"] * (1 + pol.elasticity * d))
        ep += pa * pr
        er += pa * r
        viol += int(pr < pol.floor * r - 1e-9)
    return {"exp_profit": ep, "exp_revenue": er, "exp_margin": ep / er if er else 0.0,
            "hit_prob": sum(min(1.0, cand.at[j, "p_accept"] * (1 + pol.elasticity * d)) for j, d in chosen),
            "floor_violations": viol}


def baskets_from_lines(df: pd.DataFrame, basket_col: str, item_col: str) -> list[list[str]]:
    df = df[[basket_col, item_col]].dropna().astype(str)
    df[item_col] = df[item_col].str.strip().str.upper()
    return df.groupby(basket_col, sort=False)[item_col].apply(lambda s: list(dict.fromkeys(s))).tolist()


def train_from_baskets(baskets: list[list[str]], catalog: pd.DataFrame, max_items: int = 2500,
                       lam: float = 250.0, seed: int = 42, holdout: float = 0.2) -> Model:
    """Fit EASE + calibration on a merchant's own order history.

    The last `holdout` share of baskets (file order, so sort by date first)
    calibrates p(accept) and gives an honest backtest; then EASE is refit on
    all baskets for serving.
    """
    counts = pd.Series([i for b in baskets for i in b]).value_counts()
    items = counts.index[:max_items].tolist()
    pos = {s: i for i, s in enumerate(items)}
    enc = [[pos[i] for i in b if i in pos] for b in baskets]
    enc = [b for b in enc if len(b) >= 1]
    cut = int(len(enc) * (1 - holdout))
    train, held = enc[:cut], enc[cut:]
    if len(train) < 20 or len(held) < 5:
        raise ValueError("need at least ~30 orders with 2+ items to train")
    B = fit_ease(train, len(items), lam)
    calib = calibrate(B, loo_events(held, np.random.default_rng(seed)))
    B = fit_ease(enc, len(items), lam)
    return Model(items, B, calib, catalog)
