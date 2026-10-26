"""Sync a store into a local folder the pipeline can train on.

Layout of the output folder::

    raw/products.parquet, raw/orders.parquet, raw/order_lines.parquet
                              merged store data in the common schema
    sync_state.json           source name + order watermark for incremental runs
    pipeline/lines.parquet    -> data.load_or_build (same columns as Online Retail II)
    pipeline/catalog.parquet
    pipeline/clean_log.json   cleaning counts + validation report
    pipeline/erp.parquet      the store's own unit cost and stock (NaN = unknown)
    config.yaml               base config pointed at the files above, with
                              split dates fitted to the store's date range

Orders sync incrementally (updated since the last watermark, upserted by
order id). Products are refetched in full every time: catalogs are small, and
stock changes do not reliably bump a product's updated_at.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from .schema import StoreData, normalise, to_pipeline, validate


class SyncError(RuntimeError):
    def __init__(self, report: dict):
        super().__init__("validation failed: " + "; ".join(report["errors"]))
        self.report = report


def _read(path: Path, table: str) -> pd.DataFrame | None:
    return normalise(table, pd.read_parquet(path)) if path.exists() else None


def _upsert(old: pd.DataFrame | None, new: pd.DataFrame, key: str) -> pd.DataFrame:
    if old is None or old.empty:
        return new.drop_duplicates(key, keep="last")
    if new.empty:
        return old
    return pd.concat([old[~old[key].isin(set(new[key]))], new], ignore_index=True).drop_duplicates(key, keep="last")


def _iso(ts) -> str | None:
    return None if pd.isna(ts) else pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def split_dates(lines: pd.DataFrame, val_q: float = 0.70, test_q: float = 0.85) -> tuple[str, str]:
    """Cut points at time quantiles of orders: oldest 70% train, next 15% val, newest 15% test."""
    inv_ts = lines.groupby("invoice")["ts"].min().sort_values()
    v, t = inv_ts.quantile(val_q), inv_ts.quantile(test_q)
    return str(v.floor("D").date()), str(t.floor("D").date())


def store_config(base_cfg: dict, out: Path, lines: pd.DataFrame, source: str) -> dict:
    cfg = copy.deepcopy(base_cfg)
    pipe = out / "pipeline"
    cfg["data"].update(
        source=source,
        raw_path=str(out / "raw"),  # only read if the pipeline/ cache is deleted; re-run sync instead
        clean_path=str(pipe / "lines.parquet"),
        erp_path=str(pipe / "erp.parquet"),
    )
    v, t = split_dates(lines)
    if v == t:  # store too young for day-level cuts
        raise SyncError({"errors": ["orders span less than a few days; need more history to split train/val/test"],
                         "warnings": [], "stats": {}})
    cfg["split"].update(val_start=v, test_start=t)
    cfg.setdefault("erp", {}).setdefault("cost_ratio", 0.6)
    cfg["erp"].setdefault("overstock_weeks", 12)
    return cfg


def sync(
    source,
    out_dir: str | Path,
    base_cfg: dict,
    full: bool = False,
    product_id_regex: str | None = None,
    min_orders: int = 200,
) -> dict:
    """Fetch (or load) store data, merge it into out_dir, validate, and write
    the pipeline input. `source` is a StoreData (file upload) or an API source
    with .name and .fetch(products_since, orders_since)."""
    out = Path(out_dir)
    raw_dir = out / "raw"
    state_path = out / "sync_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    name = getattr(source, "name", "csv")
    incremental = not full and state.get("source") == name and name != "csv"

    if isinstance(source, StoreData):
        new = source.normalised()
    else:
        new = source.fetch(products_since=None, orders_since=state.get("orders_watermark") if incremental else None)

    if incremental:
        old = {t: _read(raw_dir / f"{t}.parquet", t) for t in ("orders", "order_lines")}
        orders = _upsert(old["orders"], new.orders, "order_id")
        changed = set(new.orders["order_id"])
        ol = old["order_lines"]
        lines = new.order_lines if ol is None else pd.concat([ol[~ol["order_id"].isin(changed)], new.order_lines], ignore_index=True)
        store = StoreData(new.products, orders, lines)
    else:
        store = new
    store = store.normalised()

    report = validate(store, min_orders=min_orders)
    rep = report.to_dict()
    if not report.ok:
        raise SyncError(rep)

    raw_dir.mkdir(parents=True, exist_ok=True)
    for t in ("products", "orders", "order_lines"):
        getattr(store, t).to_parquet(raw_dir / f"{t}.parquet", index=False)

    lines, catalog, erp, log = to_pipeline(store, product_id_regex)
    if lines.empty:
        raise SyncError({**rep, "errors": ["no usable order lines after cleaning"]})
    pipe = out / "pipeline"
    pipe.mkdir(parents=True, exist_ok=True)
    lines.to_parquet(pipe / "lines.parquet", index=False)
    catalog.to_parquet(pipe / "catalog.parquet", index=False)
    erp.to_parquet(pipe / "erp.parquet", index=False)
    log["validation"] = rep
    (pipe / "clean_log.json").write_text(json.dumps(log, indent=2, default=str))

    cfg = store_config(base_cfg, out, lines, name)
    (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))

    upd = store.orders["updated_at"].fillna(store.orders["ordered_at"])
    new_state = {
        "source": name,
        "orders_watermark": _iso(upd.max()) if name != "csv" else None,
        "last_sync": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "incremental" if incremental else "full",
        "fetched_orders": len(new.orders),
    }
    state_path.write_text(json.dumps(new_state, indent=2))
    return {"state": new_state, "clean": log, "config": str(out / "config.yaml"),
            "split": {"val_start": cfg["split"]["val_start"], "test_start": cfg["split"]["test_start"]}}
