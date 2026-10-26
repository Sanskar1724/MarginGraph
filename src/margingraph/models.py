"""E3 baseline scorers. Each one scores the whole catalog for a batch of baskets.

All scorers are fit on the train split only. ``score(ctx, customers)`` takes a
list of context item-index lists and returns a dense (batch, n_items) array;
callers mask the context items themselves.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp


class ItemIndex:
    def __init__(self, items: list[str]):
        self.items = list(items)
        self.pos = {it: i for i, it in enumerate(self.items)}

    def __len__(self) -> int:
        return len(self.items)

    def encode(self, items: list[str]) -> list[int]:
        return [self.pos[i] for i in items if i in self.pos]


def basket_matrix(lines: pd.DataFrame, index: ItemIndex) -> sp.csr_matrix:
    """Binary invoice x item matrix."""
    lines = lines[lines["item"].isin(index.pos)]
    inv_codes, _ = pd.factorize(lines["invoice"])
    cols = lines["item"].map(index.pos).to_numpy()
    X = sp.csr_matrix((np.ones(len(lines), dtype=np.float32), (inv_codes, cols)), shape=(inv_codes.max() + 1, len(index)))
    X.data[:] = 1.0
    return X


class Popularity:
    name = "popularity"

    def __init__(self, lines: pd.DataFrame, index: ItemIndex, since: pd.Timestamp | None = None):
        if since is not None:
            lines = lines[lines["ts"] >= since]
        cnt = lines.groupby("item")["invoice"].nunique()
        self.vec = np.zeros(len(index), dtype=np.float32)
        for it, c in cnt.items():
            if it in index.pos:
                self.vec[index.pos[it]] = c

    def score(self, ctx, customers):
        return np.tile(self.vec, (len(ctx), 1))


class Repeat:
    """How often this customer bought the item before (history before the split)."""

    name = "repeat"

    def __init__(self, history: pd.DataFrame, index: ItemIndex):
        h = history[(history["customer"] != "") & history["item"].isin(index.pos)]
        self.cust_pos = {c: i for i, c in enumerate(h["customer"].unique())}
        rows = h["customer"].map(self.cust_pos).to_numpy()
        cols = h["item"].map(index.pos).to_numpy()
        self.M = sp.csr_matrix((np.ones(len(h), dtype=np.float32), (rows, cols)), shape=(len(self.cust_pos), len(index)))
        self.n_items = len(index)

    def score(self, ctx, customers):
        out = np.zeros((len(ctx), self.n_items), dtype=np.float32)
        for r, c in enumerate(customers):
            i = self.cust_pos.get(c)
            if i is not None:
                row = self.M.getrow(i)
                out[r, row.indices] = row.data
        return out

    def n_invoices(self, customer: str) -> float:
        i = self.cust_pos.get(customer)
        return 0.0 if i is None else float(self.M.getrow(i).sum())


class CoPurchase:
    """Raw co-occurrence counts ("bought together"), summed or maxed over the basket."""

    name = "copurchase"

    def __init__(self, X: sp.csr_matrix):
        C = (X.T @ X).toarray().astype(np.float32)
        np.fill_diagonal(C, 0.0)
        self.C = C

    def score(self, ctx, customers):
        return np.stack([self.C[c].sum(0) if c else np.zeros(self.C.shape[0], np.float32) for c in ctx])

    def score_max(self, ctx):
        return np.stack([self.C[c].max(0) if c else np.zeros(self.C.shape[0], np.float32) for c in ctx])


class ItemKNN(CoPurchase):
    """Cosine-normalised co-occurrence."""

    name = "itemknn"

    def __init__(self, X: sp.csr_matrix):
        super().__init__(X)
        n = np.asarray(X.sum(0)).ravel().astype(np.float32)
        d = np.sqrt(np.maximum(n, 1.0))
        self.C = self.C / d[:, None] / d[None, :]


class EASE:
    """Steck 2019 closed-form item-item model."""

    name = "ease"

    def __init__(self, X: sp.csr_matrix, lam: float = 500.0):
        G = (X.T @ X).toarray().astype(np.float64)
        G[np.diag_indices_from(G)] += lam
        P = np.linalg.inv(G)
        B = -P / np.diag(P)[None, :]
        np.fill_diagonal(B, 0.0)
        self.B = B.astype(np.float32)

    def score(self, ctx, customers):
        return np.stack([self.B[c].sum(0) if c else np.zeros(self.B.shape[0], np.float32) for c in ctx])


class ALS:
    """implicit ALS on the invoice x item matrix; new baskets are folded in exactly."""

    name = "als"

    def __init__(self, X: sp.csr_matrix, factors: int, regularization: float, iterations: int, alpha: float, seed: int):
        from implicit.cpu.als import AlternatingLeastSquares

        m = AlternatingLeastSquares(
            factors=factors, regularization=regularization, iterations=iterations, alpha=alpha, random_state=seed
        )
        m.fit(X, show_progress=False)
        self.Y = np.asarray(m.item_factors, dtype=np.float64)
        self.alpha, self.reg = alpha, regularization
        self.YtY = self.Y.T @ self.Y

    def fold_in(self, ctx: list[int]) -> np.ndarray:
        if not ctx:
            return np.zeros(self.Y.shape[1])
        Yc = self.Y[ctx]
        A = self.YtY + self.alpha * Yc.T @ Yc + self.reg * np.eye(self.Y.shape[1])
        b = (1.0 + self.alpha) * Yc.sum(0)
        return np.linalg.solve(A, b)

    def score(self, ctx, customers):
        U = np.stack([self.fold_in(c) for c in ctx])
        return (U @ self.Y.T).astype(np.float32)
