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


# ---------------------------------------------------------------------------
# Extra candidate sources (accuracy thread). Each one is optional and switched
# on by the config; docs/worklog/accuracy.md records which ones won.


def decay_weights(lines: pd.DataFrame, half_life_days: float) -> np.ndarray:
    """Per-invoice weight 0.5 ** (age / half_life), in basket_matrix row order."""
    inv_codes, _ = pd.factorize(lines["invoice"])
    ts = lines.groupby(inv_codes)["ts"].min().sort_index()
    age = (lines["ts"].max() - ts).dt.total_seconds().to_numpy() / 86400.0
    return np.power(0.5, age / half_life_days).astype(np.float32)


class DecayEASE(EASE):
    """EASE on a time-weighted Gram matrix: recent baskets count more."""

    name = "ease_decay"

    def __init__(self, X: sp.csr_matrix, w: np.ndarray, lam: float = 250.0):
        Xw = sp.diags(np.sqrt(w)) @ X
        super().__init__(Xw.tocsr(), lam)


class CustomerEASE:
    """EASE scores of the customer's past items: "people like you buy" for known customers."""

    name = "cust_ease"

    def __init__(self, B: np.ndarray, scorers: dict):
        # reads scorers["repeat"] at call time: the pipeline swaps in a history per split
        self.B, self.scorers = B, scorers

    def score(self, ctx, customers):
        rep = self.scorers["repeat"]
        out = np.zeros((len(ctx), self.B.shape[0]), dtype=np.float32)
        for r, c in enumerate(customers):
            i = rep.cust_pos.get(c)
            if i is not None:
                row = rep.M.getrow(i)
                out[r] = self.B[row.indices].sum(0)
        return out


class TextSim:
    """TF-IDF cosine between product descriptions (word + char n-grams).

    Finds variants the basket data cannot (PINK EGG COSY -> BLUE EGG COSY) and
    works for items with few sales.
    """

    name = "text"

    def __init__(self, descriptions: np.ndarray):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize

        docs = [str(d).lower() for d in descriptions]
        W = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit_transform(docs)
        C = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4), min_df=2, sublinear_tf=True).fit_transform(docs)
        V = normalize(sp.hstack([W, C]).tocsr())
        S = (V @ V.T).toarray().astype(np.float32)
        np.fill_diagonal(S, 0.0)
        self.C = S

    def score(self, ctx, customers):
        return np.stack([self.C[c].max(0) if c else np.zeros(self.C.shape[0], np.float32) for c in ctx])


class Item2Vec:
    """word2vec (skip-gram) over baskets; score = cosine to the mean basket vector."""

    name = "item2vec"

    def __init__(
        self, lines: pd.DataFrame, index: ItemIndex, dim: int = 64, epochs: int = 10, seed: int = 0,
        max_basket: int = 50, window: int = 20,
    ):
        from gensim.models import Word2Vec

        lines = lines[lines["item"].isin(index.pos)]
        baskets = lines.groupby("invoice", sort=False)["item"].agg(list)
        rng = np.random.default_rng(seed)
        sents = []
        for b in baskets:
            # huge wholesale invoices dominate the cost and carry little pair signal
            if 1 < len(b) <= max_basket:
                b = list(b)
                rng.shuffle(b)  # basket order carries no meaning
                sents.append(b)
        m = Word2Vec(
            sents, vector_size=dim, window=window, min_count=1, sg=1, negative=10,
            sample=1e-3, epochs=epochs, seed=seed, workers=4,
        )
        V = np.zeros((len(index), dim), dtype=np.float32)
        for it, i in index.pos.items():
            if it in m.wv:
                V[i] = m.wv[it]
        n = np.linalg.norm(V, axis=1, keepdims=True)
        self.V = V / np.maximum(n, 1e-9)

    def score(self, ctx, customers):
        out = np.zeros((len(ctx), self.V.shape[0]), dtype=np.float32)
        for r, c in enumerate(ctx):
            if c:
                q = self.V[c].mean(0)
                out[r] = self.V @ (q / max(np.linalg.norm(q), 1e-9))
        return out


class Fresh:
    """Signals from sales since the models were fit, refreshed nightly.

    ``stream`` holds invoices after the fit cutoff. For an event on day d only
    invoices from days before d are used, as a nightly batch job would. Gives
    two scores: ``trend`` (invoices with the item in the last ``days`` days) and
    ``fresh_co`` (co-purchase counts with the basket over the whole stream).
    """

    uses_time = True

    def __init__(self, index: ItemIndex, days: int = 14):
        self.index, self.days = index, days
        self.stream: pd.DataFrame | None = None
        self._cache: dict = {}

    def set_stream(self, lines: pd.DataFrame | None) -> None:
        self.stream = None if lines is None else lines[lines["item"].isin(self.index.pos)][["invoice", "item", "ts"]]
        self._cache = {}

    def _day(self, day: pd.Timestamp):
        if day in self._cache:
            return self._cache[day]
        n = len(self.index)
        s = self.stream
        if s is None or not len(s):
            res = (np.zeros(n, np.float32), sp.csr_matrix((n, n), dtype=np.float32))
        else:
            past = s[s["ts"] < day]
            rec = past[past["ts"] >= day - pd.Timedelta(days=self.days)]
            trend = np.zeros(n, np.float32)
            if len(rec):
                cnt = rec.groupby("item")["invoice"].nunique()
                trend[cnt.index.map(self.index.pos).to_numpy()] = cnt.to_numpy()
            if len(past):
                X = basket_matrix(past, self.index)
                C = (X.T @ X).tocsr()
                C.setdiag(0)
                C.eliminate_zeros()
            else:
                C = sp.csr_matrix((n, n), dtype=np.float32)
            res = (trend, C)
        if len(self._cache) > 8:
            self._cache.pop(next(iter(self._cache)))
        self._cache[day] = res
        return res

    def score_time(self, ctx, ts) -> dict[str, np.ndarray]:
        n = len(self.index)
        trend = np.zeros((len(ctx), n), np.float32)
        co = np.zeros((len(ctx), n), np.float32)
        for r, (c, t) in enumerate(zip(ctx, ts)):
            tr, C = self._day(pd.Timestamp(t).normalize())
            trend[r] = tr
            if c:
                co[r] = np.asarray(C[c].sum(0)).ravel()
        return {"trend": trend, "fresh_co": co}
