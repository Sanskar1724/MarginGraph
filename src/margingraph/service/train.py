"""Nightly batch job for one store: retrain, evaluate, gate, publish.

1. Read the store's order history and catalog from the database.
2. Hold out the last ``holdout_days``: fit candidate models on the older
   orders, turn recent orders into leave-one-out checkout events, train the
   LightGBM ranker on the first 70% of them, early-stop on the next 15%,
   calibrate and evaluate on the last 15%.
3. Gate: the new ranker must match or beat the best single candidate source (EASE,
   ItemKNN, ...) on Hit@10 of the held-out events, or it is saved as
   ``rejected`` and the current model keeps serving.
4. Refit the candidate models on all orders (fresher co-purchase data, same
   ranker) and publish ``artifacts/<store>/<version>/bundle.pkl``.
5. Optionally refresh overstock flags from stock vs. recent demand.

Running instances pick the new version up within ~30 s with no restart.
"""
from __future__ import annotations

import gc
import json
import logging
import pickle
import resource
import secrets
import time
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from .. import split
from ..features import SOURCES, CandidateGenerator
from ..models import Repeat
from ..rerank import Reranker, pool_ranks, split_events
from ..stats import ranking_metrics
from . import db
from .schemas import StoreSettings

log = logging.getLogger("margingraph.train")


def _catalog_frame(products: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Catalog in the shape CandidateGenerator expects (item, price, description, category)."""
    cat = products[["item", "price", "description", "category"]].copy()
    missing = sorted(set(lines["item"]) - set(cat["item"]))
    if missing:  # sold historically but no longer listed: still useful as context
        med = lines[lines["item"].isin(missing)].groupby("item")["price"].median()
        cat = pd.concat([cat, pd.DataFrame({"item": med.index, "price": med.values, "description": "", "category": ""})])
    words = cat["description"].fillna("").str.upper().str.replace(r"[^A-Z ]", " ", regex=True).str.split()
    derived = words.map(lambda w: w[-1] if w else "UNKNOWN")
    cat["category"] = cat["category"].where(cat["category"].fillna("") != "", derived)
    return cat.reset_index(drop=True)


def _peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def refresh_overstock(engine: Engine, store_id: str, lines: pd.DataFrame, weeks: float, demand_days: int = 90) -> int:
    """Flag items holding more than ``weeks`` of stock at recent demand."""
    prods = db.load_products(engine, store_id)
    end = lines["ts"].max()
    recent = lines[lines["ts"] >= end - pd.Timedelta(days=demand_days)]
    weekly = recent.groupby("item")["quantity"].sum() / (demand_days / 7)
    w = prods["item"].map(weekly).fillna(0.0)
    flag = (prods["stock"] > 0) & (prods["stock"] > weeks * w)
    changed = prods[flag != prods["overstock"].astype(bool)]
    rows = [{"item": it, "overstock": bool(f)} for it, f in zip(changed["item"], flag[changed.index], strict=True)]
    if rows:
        db.upsert_products(engine, store_id, rows)
        db.bump_catalog_version(engine, store_id)
    return len(rows)


def train_store(
    engine: Engine,
    store_id: str,
    cfg: dict,
    artifacts_dir: str,
    holdout_days: int = 60,
    max_events: int = 20000,
    batch: int = 250,
    force: bool = False,
    min_events: int = 200,
) -> dict:
    t0 = time.time()
    store = db.get_store(engine, store_id)
    if store is None:
        raise KeyError(f"unknown store {store_id}")
    s = StoreSettings(**store["settings"])
    seed = cfg["seed"]
    lines = db.load_order_lines(engine, store_id)
    products = db.load_products(engine, store_id)
    n_orders = lines["invoice"].nunique() if len(lines) else 0
    if n_orders < s.min_train_orders:
        raise ValueError(f"store {store_id} has {n_orders} orders; needs {s.min_train_orders} to train")

    catalog = _catalog_frame(products, lines)
    cutoff = lines["ts"].max() - pd.Timedelta(days=holdout_days)
    old, recent = lines[lines["ts"] < cutoff], lines[lines["ts"] >= cutoff]
    sc = cfg["split"]
    ev = split.make_events(recent, sc["min_basket_items"], sc["max_basket_items"], max_events, seed)
    if len(ev) < min_events:
        raise ValueError(f"only {len(ev)} eligible baskets in the last {holdout_days} days; need {min_events}")
    log.info("store %s: %d lines, %d holdout events", store_id, len(lines), len(ev))

    gen = CandidateGenerator(old, old, catalog, cfg)
    gen.scorers["repeat"] = Repeat(old, gen.index)
    feats, base_ranks = gen.generate(
        ev["context"].tolist(), ev["customer"].tolist(), ev["target"].tolist(), ev["event_id"].to_numpy(), batch=batch
    )
    fit_df, es_df, cal_df = split_events(feats)
    rr = Reranker(cfg, seed).fit(fit_df, es_df)
    cal = rr.calibrate(cal_df)

    # held-out evaluation on the calibration events (never seen by the trees;
    # isotonic calibration is monotone, so it cannot change their ranking)
    ids = cal_df["event_id"].unique()
    lgb_rank = pool_ranks(cal_df, rr.score(cal_df)).reindex(ids).to_numpy()
    br = base_ranks.set_index("event_id").loc[ids]
    metrics = {"n_holdout_events": int(len(ids)), "calibration_brier": cal["brier"]}
    m_lgb = {k: float(v.mean()) for k, v in ranking_metrics(lgb_rank).items()}
    metrics["lightgbm"] = m_lgb
    best_src, best_hit = None, -1.0
    for src in SOURCES:
        m = {k: float(v.mean()) for k, v in ranking_metrics(br[src].to_numpy()).items()}
        metrics[src] = m
        if m["hit@10"] > best_hit:
            best_src, best_hit = src, m["hit@10"]
    metrics["best_baseline"] = best_src
    metrics["pool_recall"] = float(cal_df.groupby("event_id")["label"].max().mean())
    passed = m_lgb["hit@10"] >= best_hit
    metrics["gate"] = {"rule": "lightgbm hit@10 >= best single-source hit@10", "passed": bool(passed)}
    del gen, feats, fit_df, es_df
    gc.collect()

    # serving generator: all history, same feature code
    serve_gen = CandidateGenerator(lines, lines, catalog, cfg)
    serve_gen.scorers["repeat"] = Repeat(lines, serve_gen.index)

    # timestamp plus a random suffix: two runs in the same second must not collide
    version = time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + secrets.token_hex(2)
    out = Path(artifacts_dir) / store_id / version
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "store_id": store_id,
        "version": version,
        "trained_on_lines": int(len(lines)),
        "trained_on_orders": int(n_orders),
        "n_items": len(serve_gen.index),
        "data_end": str(lines["ts"].max()),
        "holdout_start": str(cutoff),
        "metrics": metrics,
    }
    with open(out / "bundle.pkl", "wb") as fh:
        pickle.dump({"generator": serve_gen, "reranker": rr, "meta": meta}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    status = "active" if (passed or force or db.active_model(engine, store_id) is None) else "rejected"
    meta["status"] = status
    meta["bundle_mb"] = round((out / "bundle.pkl").stat().st_size / 2**20, 1)
    meta["train_seconds"] = round(time.time() - t0, 1)
    meta["peak_rss_mb"] = round(_peak_rss_mb(), 0)
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    # stored relative to the artifacts dir so the volume can be mounted anywhere
    db.register_model(engine, store_id, version, f"{store_id}/{version}/bundle.pkl", status, meta)

    if s.auto_overstock_weeks:
        meta["overstock_flags_changed"] = refresh_overstock(engine, store_id, lines, s.auto_overstock_weeks)
    log.info("store %s: model %s %s (lightgbm hit@10 %.4f vs %s %.4f)", store_id, version, status, m_lgb["hit@10"], best_src, best_hit)
    return meta


def prune_artifacts(engine: Engine, store_id: str, artifacts_dir: str, keep: int = 3) -> list[str]:
    """Delete bundles of all but the newest ``keep`` non-active versions."""
    removed = []
    rows = [m for m in db.list_models(engine, store_id) if m["status"] != "active"]
    for m in rows[keep:]:
        p = Path(m["path"]) if Path(m["path"]).is_absolute() else Path(artifacts_dir) / m["path"]
        if p.exists():
            p.unlink()
            removed.append(m["version"])
    return removed


def nightly(engine: Engine, cfg: dict, artifacts_dir: str, stores: list[str] | None = None) -> list[dict]:
    """Train every store (or the given ones); one store failing does not stop the rest."""
    results = []
    for st in stores or [s["store_id"] for s in db.list_stores(engine)]:
        try:
            meta = train_store(engine, st, cfg, artifacts_dir)
            meta["pruned"] = prune_artifacts(engine, st, artifacts_dir)
            results.append({"store_id": st, "ok": True, "version": meta["version"], "status": meta["status"]})
        except Exception as e:  # noqa: BLE001 - report and continue
            log.exception("training failed for %s", st)
            results.append({"store_id": st, "ok": False, "error": str(e)})
    return results
