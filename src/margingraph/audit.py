"""E1: is there learnable basket signal in the data at all?"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .models import CoPurchase, ItemIndex, basket_matrix
from .stats import target_rank


def popularity_skew(lines: pd.DataFrame) -> dict:
    cnt = lines.groupby("item")["invoice"].nunique().sort_values(ascending=False).to_numpy()
    total = cnt.sum()
    n = len(cnt)
    cum = np.cumsum(np.sort(cnt)) / total
    gini = 1 - 2 * cum.sum() / n + 1 / n
    return {
        "items": n,
        "share_top1pct_items": float(cnt[: max(1, n // 100)].sum() / total),
        "share_top10pct_items": float(cnt[: max(1, n // 10)].sum() / total),
        "gini": float(gini),
    }


def repeat_rate(lines: pd.DataFrame) -> dict:
    """Share of (customer, item) lines where that customer had bought the item before."""
    known = lines[lines["customer"] != ""].sort_values("ts")
    first = known.groupby(["customer", "item"])["ts"].transform("min")
    repeat = (known["ts"] > first).mean()
    inv_per_cust = known.groupby("customer")["invoice"].nunique()
    return {
        "lines_with_customer": float(len(known) / max(len(lines), 1)),
        "repeat_line_rate": float(repeat),
        "customers_with_2plus_invoices": float((inv_per_cust >= 2).mean()),
        "median_invoices_per_customer": float(inv_per_cust.median()),
    }


def basket_stats(lines: pd.DataFrame) -> dict:
    size = lines.groupby("invoice")["item"].nunique()
    return {
        "invoices": int(len(size)),
        "median_basket_items": float(size.median()),
        "mean_basket_items": float(size.mean()),
        "share_baskets_2plus": float((size >= 2).mean()),
    }


def shuffle_baskets(lines: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Null model: permute items across lines, keeping basket sizes and item counts."""
    rng = np.random.default_rng(seed)
    out = lines.copy()
    out["item"] = rng.permutation(out["item"].to_numpy())
    return out.drop_duplicates(["invoice", "item"])


def copurchase_signal(train: pd.DataFrame, events: pd.DataFrame, index: ItemIndex, seed: int, ks=(5, 10)) -> dict:
    """Leave-one-out Hit@k of co-purchase fit on real vs shuffled train baskets.

    If the real model is not clearly above the shuffled one, baskets carry no
    co-purchase signal and the dataset should be swapped (gate of E1).
    """
    tgt = np.array([index.pos.get(t, -1) for t in events["target"]])
    ctx = [index.encode(c) for c in events["context"]]
    out = {"events": len(events), "chance_hit@5": 5 / len(index), "chance_hit@10": 10 / len(index)}
    for label, data in [("real", train), ("shuffled", shuffle_baskets(train, seed))]:
        model = CoPurchase(basket_matrix(data, index))
        ranks = []
        for s in range(0, len(ctx), 2000):
            sc = model.score(ctx[s : s + 2000], None)
            for r, c in enumerate(ctx[s : s + 2000]):
                sc[r, c] = -np.inf
            # small popularity-free tie break so all-zero rows are not "hits"
            sc += np.random.default_rng(seed).random(sc.shape, dtype=np.float32) * 1e-6
            ranks.append(target_rank(sc, tgt[s : s + 2000]))
        rank = np.concatenate(ranks)
        for k in ks:
            out[f"{label}_hit@{k}"] = float((rank <= k).mean())
    out["lift_hit@10_vs_shuffled"] = out["real_hit@10"] / max(out["shuffled_hit@10"], 1e-9)
    return out


def top_pairs(train: pd.DataFrame, catalog: pd.DataFrame, index: ItemIndex, n: int = 20, min_support: int = 30) -> pd.DataFrame:
    """Highest-lift item pairs, for a human sanity check that they make sense."""
    X = basket_matrix(train, index)
    C = (X.T @ X).tocoo()
    n_inv = X.shape[0]
    freq = np.asarray(X.sum(0)).ravel()
    m = (C.row < C.col) & (C.data >= min_support)
    r, c, s = C.row[m], C.col[m], C.data[m]
    lift = s * n_inv / (freq[r] * freq[c])
    desc = catalog.set_index("item")["description"]
    df = pd.DataFrame(
        {
            "item_a": [index.items[i] for i in r],
            "item_b": [index.items[i] for i in c],
            "support": s.astype(int),
            "lift": lift,
        }
    ).sort_values("lift", ascending=False).head(n)
    df["desc_a"] = df["item_a"].map(desc)
    df["desc_b"] = df["item_b"].map(desc)
    return df
