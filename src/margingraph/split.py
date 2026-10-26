"""E2: one global temporal split and leave-one-out basket events."""
from __future__ import annotations

import numpy as np
import pandas as pd


def temporal_split(lines: pd.DataFrame, val_start: str, test_start: str) -> dict[str, pd.DataFrame]:
    """Split by invoice timestamp; an invoice belongs wholly to one split."""
    inv_ts = lines.groupby("invoice")["ts"].min()
    v, t = pd.Timestamp(val_start), pd.Timestamp(test_start)
    split_of = pd.Series(np.where(inv_ts < v, "train", np.where(inv_ts < t, "val", "test")), index=inv_ts.index)
    s = lines["invoice"].map(split_of)
    return {k: lines[s == k].reset_index(drop=True) for k in ("train", "val", "test")}


def make_events(
    lines: pd.DataFrame,
    min_items: int,
    max_items: int,
    max_events: int | None,
    seed: int,
) -> pd.DataFrame:
    """One event per eligible invoice: hide one product, keep the rest as context.

    The hidden product is chosen uniformly at random with a fixed seed. Events are
    sorted by time so later steps (inventory simulation) can replay them in order.
    """
    rng = np.random.default_rng(seed)
    g = lines.groupby("invoice", sort=False).agg(
        items=("item", list), ts=("ts", "min"), customer=("customer", "first")
    )
    n = g["items"].map(len)
    g = g[(n >= min_items) & (n <= max_items)]
    if max_events and len(g) > max_events:
        g = g.sample(n=max_events, random_state=seed)
    g = g.sort_values("ts")
    targets, contexts = [], []
    for items in g["items"]:
        k = rng.integers(len(items))
        targets.append(items[k])
        contexts.append(items[:k] + items[k + 1 :])
    ev = pd.DataFrame(
        {
            "event_id": np.arange(len(g)),
            "invoice": g.index.values,
            "ts": g["ts"].values,
            "customer": g["customer"].values,
            "context": contexts,
            "target": targets,
        }
    )
    return ev


def check_no_leakage(splits: dict[str, pd.DataFrame]) -> dict:
    """Assert the split is strictly ordered in time and invoices don't straddle it."""
    tr, va, te = splits["train"], splits["val"], splits["test"]
    out = {
        "train_max_ts": str(tr["ts"].max()),
        "val_min_ts": str(va["ts"].min()),
        "val_max_ts": str(va["ts"].max()),
        "test_min_ts": str(te["ts"].min()),
        "test_max_ts": str(te["ts"].max()),
        "invoice_overlap": int(
            len(set(tr["invoice"]) & set(va["invoice"])) + len(set(va["invoice"]) & set(te["invoice"]))
        ),
    }
    assert tr["ts"].max() < va["ts"].min() <= va["ts"].max() < te["ts"].min(), "split not ordered"
    assert out["invoice_overlap"] == 0, "invoice straddles split"
    return out


AUG_ID = 1_000_000  # extra-hide copies get event_id = original id + j * AUG_ID


def add_extra_hides(lines: pd.DataFrame, ev: pd.DataFrame, per_invoice: int, min_items: int, max_items: int, seed: int) -> pd.DataFrame:
    """More training events: hide a different product of the same invoices.

    Copy j re-draws the hidden product with seed + 1000 * j and keeps only the
    invoices where it differs from the original event. Copies are training-only;
    every reported metric uses the original events (event_id < AUG_ID).
    """
    parts = [ev]
    for j in range(1, per_invoice):
        e = make_events(lines, min_items, max_items, None, seed + 1000 * j)
        e = e.set_index("invoice").reindex(ev["invoice"]).reset_index()
        e["event_id"] = ev["event_id"].to_numpy() + AUG_ID * j
        e = e[e["target"].notna() & (e["target"].to_numpy() != ev["target"].to_numpy())]
        parts.append(e[ev.columns])
    return pd.concat(parts).sort_values(["ts", "event_id"]).reset_index(drop=True)
