"""Tiny synthetic retail log with planted item pairs. For code tests only;
never used for any reported number."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml


def make_raw(n_invoices=1500, n_items=120, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    items = [f"{10000 + i}" for i in range(n_items)]
    ts0 = pd.Timestamp("2010-01-01")
    rows = []
    for k in range(n_invoices):
        a = rng.integers(0, n_items // 2)
        basket = {a, a + n_items // 2}  # planted pair
        basket |= set(rng.integers(0, n_items, rng.integers(1, 5)).tolist())
        ts = ts0 + pd.Timedelta(hours=int(k * 12))
        cust = float(rng.integers(1, 200))
        for i in basket:
            rows.append(
                {
                    "Invoice": str(500000 + k),
                    "StockCode": items[i],
                    "Description": f"ITEM {i} {['MUG', 'BAG', 'HOLDER'][i % 3]}",
                    "Quantity": int(rng.integers(1, 12)),
                    "InvoiceDate": ts,
                    "Price": float(1 + i % 17),
                    "Customer ID": cust,
                    "Country": "United Kingdom",
                }
            )
    rows.append({**rows[0], "Invoice": "C999999", "Quantity": -1})
    rows.append({**rows[0], "StockCode": "POST", "Invoice": "599999"})
    return pd.DataFrame(rows)


def tiny_config(d) -> dict:
    """Default config pointed at a fresh fixture in directory ``d``, scaled down to run in seconds."""
    raw = make_raw()
    raw.to_csv(d / "raw.csv", index=False)
    with open(Path(__file__).resolve().parents[1] / "configs" / "default.yaml") as fh:
        cfg = yaml.safe_load(fh)
    cfg["data"]["raw_path"] = str(d / "raw.csv")
    cfg["data"]["clean_path"] = str(d / "processed" / "lines.parquet")
    cfg["split"].update(val_start="2011-01-01", test_start="2011-05-01", max_events_val=400, max_events_test=300)
    cfg["baselines"]["als"]["iterations"] = 3
    cfg["retrieval"]["pool_size"] = 30
    cfg["simulate"]["seeds"] = 2
    cfg["stats"]["n_boot"] = 100
    cfg["rerank"]["n_estimators"] = 50
    return cfg


@pytest.fixture(scope="session")
def tiny_cfg(tmp_path_factory):
    d = tmp_path_factory.mktemp("mg")
    return tiny_config(d), d
