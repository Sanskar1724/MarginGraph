"""Load and clean UCI Online Retail II into one row per (invoice, product)."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

RAW_COLUMNS = {
    "Invoice": "invoice",
    "StockCode": "item",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "ts",
    "Price": "price",
    "Customer ID": "customer",
    "Country": "country",
}


def read_raw(path: str | Path) -> pd.DataFrame:
    """Read the xlsx (both yearly sheets) or a csv export of it."""
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
        df = pd.concat(sheets.values(), ignore_index=True)
    else:
        df = pd.read_csv(path, dtype={"Invoice": str, "StockCode": str}, encoding="latin-1")
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    return df.rename(columns=RAW_COLUMNS)[list(RAW_COLUMNS.values())]


def clean(df: pd.DataFrame, product_code_regex: str) -> tuple[pd.DataFrame, dict]:
    """Drop cancellations, returns, non-products and duplicates.

    Returns the cleaned lines and a dict of row counts removed at each step,
    so the audit can report exactly what was filtered.
    """
    log = {"raw_rows": len(df)}
    df = df.copy()
    df["invoice"] = df["invoice"].astype(str).str.strip()
    df["item"] = df["item"].astype(str).str.strip().str.upper()
    df["ts"] = pd.to_datetime(df["ts"])

    keep = ~df["invoice"].str.startswith(("C", "A"))
    log["dropped_cancel_or_adjust"] = int((~keep).sum())
    df = df[keep]

    keep = (df["quantity"] > 0) & (df["price"] > 0)
    log["dropped_nonpositive_qty_or_price"] = int((~keep).sum())
    df = df[keep]

    pat = re.compile(product_code_regex)
    keep = df["item"].map(lambda s: bool(pat.match(s)))
    log["dropped_non_product_codes"] = int((~keep).sum())
    df = df[keep]

    before = len(df)
    df = df.drop_duplicates()
    log["dropped_exact_duplicates"] = before - len(df)

    # One row per (invoice, item): sum quantity, quantity-weighted price.
    df["revenue"] = df["quantity"] * df["price"]
    g = df.groupby(["invoice", "item"], sort=False)
    lines = g.agg(
        quantity=("quantity", "sum"),
        revenue=("revenue", "sum"),
        ts=("ts", "min"),
        customer=("customer", "first"),
        country=("country", "first"),
    ).reset_index()
    lines["price"] = lines["revenue"] / lines["quantity"]
    lines["customer"] = lines["customer"].astype("Int64").astype(str).replace("<NA>", "").fillna("")
    log["clean_lines"] = len(lines)
    log["invoices"] = int(lines["invoice"].nunique())
    log["items"] = int(lines["item"].nunique())
    log["customers"] = int(lines.loc[lines["customer"] != "", "customer"].nunique())
    log["lines_without_customer"] = int((lines["customer"] == "").sum())
    return lines, log


def build_catalog(raw_clean: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    """Per-item description (most common), median price and a coarse category.

    The category is the last word of the description (e.g. HOLDER, BAG, MUG),
    which is crude but free and readable by an LLM later.
    """
    desc = (
        raw_clean.dropna(subset=["description"])
        .groupby("item")["description"]
        .agg(lambda s: s.astype(str).str.strip().value_counts().index[0])
    )
    price = lines.groupby("item")["price"].median()
    cat = pd.DataFrame({"item": price.index, "price": price.values})
    cat["description"] = cat["item"].map(desc).fillna("")
    words = cat["description"].str.upper().str.replace(r"[^A-Z ]", " ", regex=True).str.split()
    cat["category"] = words.map(lambda w: w[-1] if w else "UNKNOWN")
    return cat


def load_or_build(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (lines, catalog, clean_log), caching Parquet next to clean_path."""
    clean_path = Path(cfg["data"]["clean_path"])
    cat_path = clean_path.with_name("catalog.parquet")
    log_path = clean_path.with_name("clean_log.json")
    if clean_path.exists() and cat_path.exists() and log_path.exists():
        import json

        return pd.read_parquet(clean_path), pd.read_parquet(cat_path), json.loads(log_path.read_text())

    raw = read_raw(cfg["data"]["raw_path"])
    lines, log = clean(raw, cfg["data"]["product_code_regex"])
    raw_ok = raw.assign(item=raw["item"].astype(str).str.strip().str.upper())
    catalog = build_catalog(raw_ok[raw_ok["item"].isin(lines["item"].unique())], lines)

    import json

    clean_path.parent.mkdir(parents=True, exist_ok=True)
    lines.to_parquet(clean_path, index=False)
    catalog.to_parquet(cat_path, index=False)
    log_path.write_text(json.dumps(log, indent=2))
    return lines, catalog, log


def simulate_erp(lines_train: pd.DataFrame, catalog: pd.DataFrame, cfg: dict, seed: int) -> pd.DataFrame:
    """Attach SIMULATED unit cost and stock to the catalog.

    Online Retail II has no cost or inventory, so these are drawn from the
    distributions in cfg['erp']. Reports must label Stage 2 results as
    depending on this simulation.
    """
    rng = np.random.default_rng(seed)
    e = cfg["erp"]
    erp = catalog[["item", "price"]].copy()
    margin = rng.beta(*e["margin_beta"], size=len(erp))
    erp["unit_cost"] = erp["price"] * (1 - margin)

    span_weeks = max((lines_train["ts"].max() - lines_train["ts"].min()).days / 7, 1)
    weekly = lines_train.groupby("item")["quantity"].sum() / span_weeks
    erp["weekly_demand"] = erp["item"].map(weekly).fillna(0.0)
    erp["stock"] = np.ceil(erp["weekly_demand"] * e["weeks_of_cover"]).astype(int)
    over = rng.random(len(erp)) < e["overstock_share"]
    mult = rng.uniform(*e["overstock_multiplier"], size=len(erp))
    erp["overstock"] = over & (erp["stock"] > 0)
    erp.loc[erp["overstock"], "stock"] = np.ceil(erp.loc[erp["overstock"], "stock"] * mult[erp["overstock"]]).astype(int)
    return erp


def store_erp(lines_train: pd.DataFrame, catalog: pd.DataFrame, store: pd.DataFrame, cfg: dict, seed: int) -> pd.DataFrame:
    """ERP fields from a connected store's own cost and stock.

    Where the store has no unit cost, cost = price * erp.cost_ratio and the
    item is flagged cost_source="assumed". Where it has no stock count, stock
    comes from the same weeks-of-cover rule as simulate_erp, flagged
    stock_source="simulated". An item is overstock when its stock covers more
    than erp.overstock_weeks of train demand.
    """
    e = cfg["erp"]
    sim = simulate_erp(lines_train, catalog, cfg, seed)
    s = store.drop_duplicates("item", keep="last").set_index("item").reindex(sim["item"])
    cost = s["unit_cost"].to_numpy(dtype=float)
    stock = s["stock"].to_numpy(dtype=float)
    has_cost, has_stock = ~np.isnan(cost), ~np.isnan(stock)
    erp = sim[["item", "price", "weekly_demand"]].copy()
    erp["unit_cost"] = np.where(has_cost, cost, erp["price"] * e.get("cost_ratio", 0.6))
    erp["cost_source"] = np.where(has_cost, "store", "assumed")
    erp["stock"] = np.where(has_stock, stock, sim["stock"].to_numpy()).astype(int)
    erp["stock_source"] = np.where(has_stock, "store", "simulated")
    cover = erp["weekly_demand"] * e.get("overstock_weeks", 12)
    erp["overstock"] = (erp["stock"] > 0) & (erp["stock"] > cover)
    # Items without a store stock count keep the simulated overstock draw.
    erp.loc[~has_stock, "overstock"] = sim.loc[~has_stock, "overstock"].to_numpy()
    return erp[["item", "price", "unit_cost", "weekly_demand", "stock", "overstock", "cost_source", "stock_source"]]
