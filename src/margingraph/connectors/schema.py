"""Common store schema shared by every connector, plus validation and the
conversion into the pipeline's input (lines / catalog / erp Parquet).

Three tables, one row each per product, order and order line:

products     product_id, title, category, price, cost, stock, updated_at
orders       order_id, ordered_at, customer_id, country, status, updated_at
order_lines  order_id, product_id, title, quantity, unit_price

`product_id` is the sellable unit (a Shopify/WooCommerce variant when the
product has variants). `status` is normalised to "ok" or "cancelled"; only
"ok" orders reach the model. `cost` and `stock` may be missing: the pipeline
then falls back to the cost-ratio assumption and the stock simulation, and
flags every item it did that for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PRODUCT_COLUMNS = ["product_id", "title", "category", "price", "cost", "stock", "updated_at"]
ORDER_COLUMNS = ["order_id", "ordered_at", "customer_id", "country", "status", "updated_at"]
LINE_COLUMNS = ["order_id", "product_id", "title", "quantity", "unit_price"]

REQUIRED = {
    "products": ["product_id"],
    "orders": ["order_id", "ordered_at"],
    "order_lines": ["order_id", "product_id", "quantity", "unit_price"],
}


def _ids(s: pd.Series) -> pd.Series:
    """Ids as clean upper-case strings ("123.0" from a float column -> "123")."""
    out = s.astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.upper()
    return out.fillna("")


def _utc_naive(s: pd.Series) -> pd.Series:
    """Parse timestamps; tz-aware values go to UTC, then drop the tz."""
    ts = pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
    return ts.dt.tz_localize(None)


def empty(table: str) -> pd.DataFrame:
    cols = {"products": PRODUCT_COLUMNS, "orders": ORDER_COLUMNS, "order_lines": LINE_COLUMNS}[table]
    return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})


def normalise(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a table to the schema's columns and dtypes (missing optional
    columns become empty)."""
    cols = {"products": PRODUCT_COLUMNS, "orders": ORDER_COLUMNS, "order_lines": LINE_COLUMNS}[table]
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[cols]
    for c in ("product_id", "order_id", "customer_id"):
        if c in df.columns:
            df[c] = _ids(df[c])
    for c in ("price", "cost", "quantity", "unit_price", "stock"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in ("ordered_at", "updated_at"):
        if c in df.columns:
            df[c] = _utc_naive(df[c])
    for c in ("title", "category", "country", "status"):
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()
    if table == "orders":
        df["status"] = df["status"].fillna("ok")
    return df.reset_index(drop=True)


@dataclass
class StoreData:
    products: pd.DataFrame = field(default_factory=lambda: empty("products"))
    orders: pd.DataFrame = field(default_factory=lambda: empty("orders"))
    order_lines: pd.DataFrame = field(default_factory=lambda: empty("order_lines"))

    def normalised(self) -> "StoreData":
        return StoreData(
            normalise("products", self.products),
            normalise("orders", self.orders),
            normalise("order_lines", self.order_lines),
        )


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "stats": self.stats}


def validate(store: StoreData, min_orders: int = 200) -> Report:
    """Check a normalised StoreData. Errors block a sync; warnings do not."""
    r = Report()
    p, o, l = store.products, store.orders, store.order_lines

    for name, df in (("orders", o), ("order_lines", l)):
        if df.empty:
            r.errors.append(f"{name}: no rows")
    if r.errors:
        return r

    for name, df in (("products", p), ("orders", o), ("order_lines", l)):
        for c in REQUIRED[name]:
            if name == "products" and df.empty:
                continue
            bad = df[c].isna() | (df[c].astype(str) == "")
            if bad.all():
                r.errors.append(f"{name}.{c}: every value is missing or unparseable")
            elif bad.any():
                r.warnings.append(f"{name}.{c}: {int(bad.sum())} of {len(df)} rows missing or unparseable (dropped)")

    if not p.empty:
        dup = p["product_id"].duplicated().sum()
        if dup:
            r.warnings.append(f"products.product_id: {int(dup)} duplicates (last one kept)")
        neg = (p["cost"] < 0).sum()
        if neg:
            r.warnings.append(f"products.cost: {int(neg)} negative values (treated as missing)")
        over = (p["cost"] > p["price"]).sum()
        if over:
            r.warnings.append(f"products.cost: {int(over)} products cost more than their price")
    dup = o["order_id"].duplicated().sum()
    if dup:
        r.warnings.append(f"orders.order_id: {int(dup)} duplicates (last one kept)")

    nonpos = ((l["quantity"] <= 0) | (l["unit_price"] <= 0)).sum()
    if nonpos:
        r.warnings.append(f"order_lines: {int(nonpos)} rows with quantity or price <= 0 (returns/free items, dropped)")
    orphan = ~l["order_id"].isin(set(o["order_id"]))
    if orphan.any():
        r.warnings.append(f"order_lines: {int(orphan.sum())} rows reference an unknown order (dropped)")
    if not p.empty:
        unknown = ~l["product_id"].isin(set(p["product_id"]))
        if unknown.any():
            r.warnings.append(
                f"order_lines: {int(unknown.sum())} rows reference a product missing from products "
                "(kept; title and price come from the order line)"
            )

    ok_orders = o[o["status"] == "ok"]
    sizes = l[l["order_id"].isin(set(ok_orders["order_id"]))].groupby("order_id")["product_id"].nunique()
    multi = int((sizes >= 2).sum())
    span = (o["ordered_at"].max() - o["ordered_at"].min()).days if o["ordered_at"].notna().any() else 0
    r.stats.update(
        products=len(p), orders=len(o), order_lines=len(l),
        cancelled_orders=int((o["status"] != "ok").sum()),
        orders_with_2plus_products=multi, days_covered=int(span),
    )
    if not p.empty:
        r.stats["cost_coverage"] = float(p["cost"].notna().mean())
        r.stats["stock_coverage"] = float(p["stock"].notna().mean())
    else:
        r.stats["cost_coverage"] = 0.0
        r.stats["stock_coverage"] = 0.0
    if multi < min_orders:
        r.warnings.append(
            f"only {multi} orders have 2+ products; add-on recommendations need a few hundred "
            f"(aim for {min_orders}+), results will be noisy"
        )
    if r.stats["cost_coverage"] < 1.0:
        r.warnings.append(
            f"unit cost known for {r.stats['cost_coverage']:.0%} of products; the rest use the "
            "cost-ratio assumption (erp.cost_ratio) and are flagged cost_source=assumed"
        )
    return r


def to_pipeline(store: StoreData, product_id_regex: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Turn a normalised StoreData into (lines, catalog, store_erp, log).

    lines and catalog match what data.load_or_build returns for Online Retail
    II, so the pipeline runs unchanged. store_erp holds the store's own cost
    and stock per item (NaN where unknown).
    """
    p, o, l = store.products, store.orders, store.order_lines
    log = {"source_orders": len(o), "source_lines": len(l)}
    o = o.dropna(subset=["ordered_at"]).drop_duplicates("order_id", keep="last")
    keep = o["status"] == "ok"
    log["dropped_cancelled_orders"] = int((~keep).sum())
    o = o[keep]

    l = l[(l["order_id"] != "") & (l["product_id"] != "")]
    df = l.merge(o[["order_id", "ordered_at", "customer_id", "country"]], on="order_id", how="inner")
    log["dropped_lines_without_valid_order"] = len(l) - len(df)
    keep = (df["quantity"] > 0) & (df["unit_price"] > 0)
    log["dropped_nonpositive_qty_or_price"] = int((~keep).sum())
    df = df[keep]
    if product_id_regex:
        pat = re.compile(product_id_regex)
        keep = df["product_id"].map(lambda s: bool(pat.match(s)))
        log["dropped_non_product_codes"] = int((~keep).sum())
        df = df[keep]

    df = df.assign(revenue=df["quantity"] * df["unit_price"])
    g = df.groupby(["order_id", "product_id"], sort=False)
    lines = g.agg(
        quantity=("quantity", "sum"), revenue=("revenue", "sum"), ts=("ordered_at", "min"),
        customer=("customer_id", "first"), country=("country", "first"),
    ).reset_index().rename(columns={"order_id": "invoice", "product_id": "item"})
    lines["price"] = lines["revenue"] / lines["quantity"]
    lines["customer"] = lines["customer"].fillna("").astype(str)
    lines["country"] = lines["country"].fillna("").astype(str)
    lines = lines[["invoice", "item", "quantity", "revenue", "ts", "customer", "country", "price"]]

    # Catalog: product table first, order lines fill the gaps.
    p = p[p["product_id"] != ""].drop_duplicates("product_id", keep="last").set_index("product_id")
    items = pd.Index(lines["item"].unique(), name="item")
    line_title = df.dropna(subset=["title"]).groupby("product_id")["title"].agg(lambda s: s.value_counts().index[0])
    line_price = lines.groupby("item")["price"].median()
    cat = pd.DataFrame(index=items)
    cat["price"] = p["price"].reindex(items).where(lambda s: s > 0).fillna(line_price.reindex(items))
    cat["description"] = p["title"].reindex(items).fillna(line_title.reindex(items)).fillna("").astype(str)
    words = cat["description"].str.upper().str.replace(r"[^A-Z ]", " ", regex=True).str.split()
    fallback = words.map(lambda w: w[-1] if w else "UNKNOWN")
    cat["category"] = p["category"].reindex(items).replace("", pd.NA).fillna(fallback).astype(str).str.upper()
    catalog = cat.reset_index()[["item", "price", "description", "category"]]

    cost = p["cost"].reindex(items)
    erp = pd.DataFrame({
        "item": items,
        "unit_cost": cost.where(cost >= 0).to_numpy(),
        "stock": p["stock"].reindex(items).clip(lower=0).to_numpy(),
    })

    log.update(
        clean_lines=len(lines), invoices=int(lines["invoice"].nunique()), items=int(lines["item"].nunique()),
        customers=int(lines.loc[lines["customer"] != "", "customer"].nunique()),
        lines_without_customer=int((lines["customer"] == "").sum()),
        items_with_store_cost=int(erp["unit_cost"].notna().sum()),
        items_with_store_stock=int(erp["stock"].notna().sum()),
    )
    return lines, catalog, erp, log
