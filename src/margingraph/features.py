"""E3/E4 in one pass: full-catalog baseline ranks, candidate pools and reranker features.

``CandidateGenerator`` is fit once on train and used for val events, test events
and single API requests, so offline and online features are computed by the
same code.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import models as M

SOURCES = ["popularity", "recent_pop", "repeat", "copurchase", "itemknn", "ease", "als"]


class CandidateGenerator:
    def __init__(self, train: pd.DataFrame, history: pd.DataFrame, catalog: pd.DataFrame, cfg: dict):
        b = cfg["baselines"]
        self.cfg = cfg
        items = sorted(train["item"].unique())
        self.index = M.ItemIndex(items)
        X = M.basket_matrix(train, self.index)
        cutoff = train["ts"].max()
        self.scorers = {
            "popularity": M.Popularity(train, self.index),
            "recent_pop": M.Popularity(train, self.index, since=cutoff - pd.Timedelta(days=b["recent_days"])),
            "repeat": M.Repeat(history, self.index),
            "copurchase": M.CoPurchase(X),
            "itemknn": M.ItemKNN(X),
            "ease": M.EASE(X, lam=b.get("ease_lambda", 500.0)),
            "als": M.ALS(X, b["als"]["factors"], b["als"]["regularization"], b["als"]["iterations"], b["als"]["alpha"], cfg["seed"]),
        }
        cat = catalog.set_index("item").reindex(self.index.items)
        self.price = cat["price"].fillna(cat["price"].median()).to_numpy(np.float32)
        self.log_price = np.log1p(self.price)
        self.category, _ = pd.factorize(cat["category"].fillna("UNKNOWN"))
        self.description = cat["description"].fillna("").to_numpy()
        last = train.groupby("item")["ts"].max().reindex(self.index.items)
        first = train.groupby("item")["ts"].min().reindex(self.index.items)
        self.days_since_last = (cutoff - last).dt.days.to_numpy(np.float32)
        self.item_age = (cutoff - first).dt.days.to_numpy(np.float32)

    # ------------------------------------------------------------------
    def _scores(self, ctx: list[list[int]], customers: list[str]) -> dict[str, np.ndarray]:
        S = {name: s.score(ctx, customers) for name, s in self.scorers.items()}
        S["copurchase_max"] = self.scorers["copurchase"].score_max(ctx)
        S["itemknn_max"] = self.scorers["itemknn"].score_max(ctx)
        return S

    @staticmethod
    def _rank_matrix(score: np.ndarray) -> np.ndarray:
        order = np.argsort(-score, axis=1, kind="stable")
        ranks = np.empty_like(order)
        rows = np.arange(score.shape[0])[:, None]
        ranks[rows, order] = np.arange(1, score.shape[1] + 1)[None, :]
        return ranks

    def generate(
        self,
        contexts: list[list[str]],
        customers: list[str],
        targets: list[str] | None = None,
        event_ids: np.ndarray | None = None,
        batch: int = 1000,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return (candidate feature rows, per-event baseline ranks of the target).

        Baseline ranks are over the full catalog with context items removed; the
        target rank is inf when the target never appeared in train.
        """
        rc = self.cfg["retrieval"]
        pool_size, per_source = rc["pool_size"], rc["per_source"]
        n = len(contexts)
        event_ids = np.arange(n) if event_ids is None else np.asarray(event_ids)
        tgt = None if targets is None else np.array([self.index.pos.get(t, -1) for t in targets])
        enc = [self.index.encode(c) for c in contexts]
        rng = np.random.default_rng(self.cfg["seed"])
        feat_parts, rank_parts = [], []

        for s in range(0, n, batch):
            ctx, cust = enc[s : s + batch], customers[s : s + batch]
            S = self._scores(ctx, cust)
            b = len(ctx)
            mask = np.zeros((b, len(self.index)), dtype=bool)
            for r, c in enumerate(ctx):
                mask[r, c] = True
            # tiny noise so ties (e.g. all-zero co-purchase rows) are broken randomly, not by item id
            noise = rng.random((b, len(self.index)), dtype=np.float32) * 1e-6
            R = {}
            for name, sc in S.items():
                ranked = np.where(mask, -np.inf, sc + noise * (np.abs(sc).max() + 1.0))
                R[name] = self._rank_matrix(ranked)

            if tgt is not None:
                t = tgt[s : s + b]
                rk = {"event_id": event_ids[s : s + b]}
                for name in SOURCES:
                    rk[name] = np.where(t >= 0, R[name][np.arange(b), np.maximum(t, 0)], np.inf).astype(float)
                rank_parts.append(pd.DataFrame(rk))

            # candidate pool: per-source top lists, then popularity fill
            pools = []
            for r in range(b):
                cand = []
                for src, k in per_source.items():
                    cand.extend(np.argpartition(R[src][r], k)[:k].tolist())
                cand = list(dict.fromkeys(cand))
                if len(cand) < pool_size:
                    fill = np.argsort(R["popularity"][r])[: pool_size * 2]
                    cand = list(dict.fromkeys(cand + fill.tolist()))
                cand = [c for c in cand if not mask[r, c]][:pool_size]
                pools.append(cand)

            rows = np.repeat(np.arange(b), [len(p) for p in pools])
            cols = np.concatenate([np.asarray(p, dtype=int) for p in pools])
            f = {"event_id": event_ids[s : s + b][rows], "item_idx": cols}
            if tgt is not None:
                f["label"] = (cols == tgt[s : s + b][rows]).astype(np.int8)
            for name, sc in S.items():
                f[f"s_{name}"] = sc[rows, cols]
                f[f"r_{name}"] = R[name][rows, cols].astype(np.float32)
            f["log_price"] = self.log_price[cols]
            f["days_since_last"] = self.days_since_last[cols]
            f["item_age"] = self.item_age[cols]
            bsize = np.array([max(len(c), 1) for c in ctx], dtype=np.float32)
            ctx_lp = np.array([self.log_price[c].mean() if c else np.nan for c in ctx], dtype=np.float32)
            f["basket_size"] = bsize[rows]
            f["price_vs_basket"] = self.log_price[cols] - ctx_lp[rows]
            same_cat = np.array(
                [np.mean(self.category[ctx[r]] == self.category[c]) if ctx[r] else 0.0 for r, c in zip(rows, cols, strict=True)],
                dtype=np.float32,
            )
            f["same_category_share"] = same_cat
            f["customer_known"] = np.array([c in self.scorers["repeat"].cust_pos for c in cust], dtype=np.int8)[rows]
            feat_parts.append(pd.DataFrame(f))

        feats = pd.concat(feat_parts, ignore_index=True)
        ranks = pd.concat(rank_parts, ignore_index=True) if rank_parts else pd.DataFrame()
        return feats, ranks


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in {"event_id", "item_idx", "label"}]
