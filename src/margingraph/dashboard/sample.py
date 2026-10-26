"""Seed a demo store with a catalog and a SIMULATED A/B event log.

Catalog: real Online Retail II prices from ``results/erp_simulated.csv``, with
the pipeline's simulated unit cost, stock and overstock flags.

Events: a 50/50 A/B test. Control shows the 2 most "relevant" items (sampled
by real weekly demand). Treatment shows 2 items picked by the store's policy
(margin floor, exclusions, overstock weight, profit weight lambda). Per-item
purchase rates are set from the offline E8 result (ranker top-2 Hit@2 16.7%,
MILP lambda=0.5 15.6%), so conversion is lower in treatment and any profit
gain comes only from which items get shown. This is demo data for the UI,
not evidence; every row is stored with source='sample'.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import db

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.normpath(os.path.join(HERE, "..", "..", "..", "results"))
DEFAULT_ERP = os.path.join(RESULTS, "erp_simulated.csv")
DESCRIPTIONS = os.path.join(RESULTS, "item_descriptions.csv")  # real descriptions from Online Retail II

# Per-slate hit rates from results/e8_strategies_simulated_erp.csv, turned into a per-item rate for 2 slots.
HIT_CONTROL, HIT_TREATMENT = 0.167, 0.156
CLICK_TO_BUY = 0.55


def _per_item(hit: float, k: int = 2) -> float:
    return 1 - (1 - hit) ** (1 / k)


def load_catalog_csv(con, store_id: str, path: str = DEFAULT_ERP) -> int:
    erp = pd.read_csv(path, dtype={"item": str})
    erp["item"] = erp["item"].str.upper()
    if os.path.exists(DESCRIPTIONS):
        d = pd.read_csv(DESCRIPTIONS, dtype=str).dropna()
        erp["description"] = erp["item"].map(dict(zip(d["item"], d["description"])))
    return db.import_catalog(con, store_id, erp)


def seed(con, store_id: str = "demo", days: int = 28, requests_per_day: int = 400, seed: int = 42,
         erp_path: str = DEFAULT_ERP) -> dict:
    rng = np.random.default_rng(seed)
    load_catalog_csv(con, store_id, erp_path)
    s = db.get_settings(con, store_id)
    db.save_settings(con, store_id, s)
    rules = db.item_rules(con, store_id)
    cat = pd.read_sql_query("SELECT * FROM catalog WHERE store_id = ?", con, params=[store_id])
    erp = pd.read_csv(erp_path, dtype={"item": str})
    erp["item"] = erp["item"].str.upper()
    cat = cat.merge(erp[["item", "weekly_demand"]], on="item", how="left")
    cat = cat[(cat["stock"] > 0) & (cat["weekly_demand"] > 0)].reset_index(drop=True)
    excluded = {k for k, v in rules.items() if v["excluded"]}
    cat = cat[~cat["item"].isin(excluded)].reset_index(drop=True)

    price, cost = cat["price"].to_numpy(), cat["unit_cost"].to_numpy()
    over = cat["overstock"].to_numpy().astype(bool)
    rel = cat["weekly_demand"].to_numpy()
    p_ctrl = rel / rel.sum()
    margin = (price - cost) / price
    w = np.where(over, s.overstock_weight, 1.0)
    for item, r in rules.items():
        if r["overstock_weight"] is not None:
            w[(cat["item"] == item).to_numpy()] = r["overstock_weight"]
    value = p_ctrl * ((1 - s.lam) * price.mean() + s.lam * w * (price - cost))
    value[margin < s.margin_floor] = 0
    p_trt = value / value.sum()

    k = max(1, min(s.max_addons, 2))
    rates = {"control": _per_item(HIT_CONTROL, k), "treatment": _per_item(HIT_TREATMENT, k)}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    rows = []
    for d in range(days):
        n = rng.poisson(requests_per_day)
        for _ in range(n):
            ts = start + timedelta(days=d, seconds=int(rng.integers(0, 86400)))
            variant = "treatment" if rng.random() < s.treatment_share else "control"
            probs = p_trt if variant == "treatment" else p_ctrl
            items = rng.choice(len(cat), size=k, replace=False, p=probs)
            rid = uuid.UUID(int=int(rng.integers(0, 2**63))).hex
            for i in items:
                base = dict(store_id=store_id, request_id=rid, variant=variant, item=cat["item"][i],
                            price=float(price[i]), unit_cost=float(cost[i]), overstock=int(over[i]), source="sample")
                t = ts.isoformat(timespec="seconds")
                rows.append({**base, "ts": t, "event": "impression"})
                bought = rng.random() < rates[variant]
                if bought or rng.random() < rates[variant] * (1 / CLICK_TO_BUY - 1):
                    rows.append({**base, "ts": (ts + timedelta(seconds=5)).isoformat(timespec="seconds"), "event": "click"})
                if bought:
                    rows.append({**base, "ts": (ts + timedelta(seconds=40)).isoformat(timespec="seconds"),
                                 "event": "purchase", "qty": int(rng.integers(1, 4))})
    with con:
        con.execute("DELETE FROM events WHERE store_id = ? AND source = 'sample'", (store_id,))
    db.insert_events(con, rows)
    return {"store_id": store_id, "catalog_items": int(len(cat)), "events": len(rows), "days": days}
