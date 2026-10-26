"""CSV / TSV / Excel upload with column mapping.

The orders file has one row per order line (the usual POS / e-commerce
export), with order fields repeated on each line. A products file is
optional; without one the catalog comes from the order lines, and any
product fields mapped onto the orders file (cost, stock, category) are used.

A mapping says which source column feeds each schema field::

    columns:              # orders file
      order_id: Invoice
      product_id: StockCode
      ...
    product_columns:      # products file (optional)
      product_id: SKU
      cost: Unit Cost
    cancelled_values: [cancelled, refunded]   # status values to drop
    cancelled_order_prefixes: [C]              # e.g. "C536379" credit notes
    product_id_regex: '^\\d{5}[A-Za-z]{0,2}$'  # keep only matching ids
    decimal: "."                               # "," for 1.234,50 style numbers
    dayfirst: false
    drop_duplicate_rows: false                 # true if the export repeats identical rows

Fields not mapped default to a source column with the schema's own name, so a
file already using the schema headers needs no mapping at all.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .schema import StoreData

ORDER_FIELDS = ["order_id", "product_id", "title", "quantity", "unit_price", "ordered_at",
                "customer_id", "country", "status", "category", "cost", "stock", "price"]
PRODUCT_FIELDS = ["product_id", "title", "category", "price", "cost", "stock", "updated_at"]
REQUIRED_ORDER_FIELDS = ["order_id", "product_id", "quantity", "unit_price", "ordered_at"]

PRESETS: dict[str, dict] = {
    # UCI Online Retail II (dataset 502), the file the experiments use.
    "online_retail_ii": {
        "columns": {
            "order_id": "Invoice", "product_id": "StockCode", "title": "Description",
            "quantity": "Quantity", "unit_price": "Price", "ordered_at": "InvoiceDate",
            "customer_id": "Customer ID", "country": "Country",
        },
        "cancelled_order_prefixes": ["C", "A"],
        "product_id_regex": r"^\d{5}[A-Za-z]{0,2}$",
        "drop_duplicate_rows": True,  # same rule as data.clean
    },
    # Shopify admin "Export orders" CSV (one row per line item).
    "shopify_orders_export": {
        "columns": {
            "order_id": "Name", "product_id": "Lineitem sku", "title": "Lineitem name",
            "quantity": "Lineitem quantity", "unit_price": "Lineitem price", "ordered_at": "Created at",
            "customer_id": "Email", "country": "Shipping Country", "status": "Financial Status",
        },
        "cancelled_values": ["refunded", "voided"],
    },
}


def load_mapping(path: str | None = None, preset: str | None = None, overrides: list[str] | None = None) -> dict:
    m: dict = {"columns": {}, "product_columns": {}}
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; choose from {sorted(PRESETS)}")
        base = PRESETS[preset]
        m.update({k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()})
    if path:
        with open(path) as fh:
            user = yaml.safe_load(fh) or {}
        for k, v in user.items():
            if isinstance(v, dict):
                m.setdefault(k, {}).update(v)
            else:
                m[k] = v
    for o in overrides or []:
        key, _, col = o.partition("=")
        table, _, fld = key.rpartition(".")
        m["product_columns" if table == "products" else "columns"][fld] = col
    return m


def read_table(path: str | Path) -> pd.DataFrame:
    """Read csv / tsv / txt / xlsx / xls; every sheet of a workbook is stacked."""
    path = Path(path)
    suf = path.suffix.lower()
    if suf in {".xlsx", ".xlsm", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        return pd.concat(sheets.values(), ignore_index=True)
    sep = "\t" if suf in {".tsv", ".tab"} else None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, sep=sep, engine="python", dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"could not decode {path}")


def _num(s: pd.Series, decimal: str) -> pd.Series:
    s = s.astype("string").str.strip()
    if decimal == ",":
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        s = s.str.replace(",", "", regex=False)
    s = s.str.replace(r"[^0-9.\-eE]", "", regex=True)
    return pd.to_numeric(s, errors="coerce")


def _select(df: pd.DataFrame, mapping: dict, fields: list[str], required: list[str], label: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    missing = []
    for f in fields:
        col = mapping.get(f, f)
        if col in df.columns:
            out[f] = df[col]
        elif f in required:
            missing.append(f"{f} (looked for column {col!r})")
    if missing:
        raise ValueError(
            f"{label}: required fields not found: {', '.join(missing)}. "
            f"Columns in file: {list(df.columns)}. Map them with --map field=Column or a mapping file."
        )
    return out


def load_csv_store(orders_path: str, products_path: str | None, mapping: dict) -> StoreData:
    dec = mapping.get("decimal", ".")
    raw = read_table(orders_path)
    if mapping.get("drop_duplicate_rows"):
        raw = raw.drop_duplicates()
    src = _select(raw, mapping.get("columns", {}), ORDER_FIELDS, REQUIRED_ORDER_FIELDS, Path(orders_path).name)
    for c in ("quantity", "unit_price", "cost", "stock", "price"):
        if c in src:
            src[c] = _num(src[c], dec)
    src["ordered_at"] = pd.to_datetime(src["ordered_at"], errors="coerce", dayfirst=bool(mapping.get("dayfirst")),
                                       format=mapping.get("date_format", "mixed"), utc=True)
    src["product_id"] = src["product_id"].astype("string").str.strip().str.upper()
    oid = src["order_id"].astype("string").str.strip()
    status = pd.Series("ok", index=src.index, dtype="string")
    if "status" in src:
        bad = {str(v).strip().lower() for v in mapping.get("cancelled_values", ["cancelled", "canceled", "refunded", "voided", "failed"])}
        status = status.mask(src["status"].astype("string").str.strip().str.lower().isin(bad), "cancelled")
    for pre in mapping.get("cancelled_order_prefixes", []):
        status = status.mask(oid.str.upper().str.startswith(str(pre).upper()).fillna(False), "cancelled")
    src["status"] = status

    lines = src[[c for c in ("order_id", "product_id", "title", "quantity", "unit_price") if c in src]].copy()
    hdr = [c for c in ("order_id", "ordered_at", "customer_id", "country", "status") if c in src]
    orders = src[hdr].groupby("order_id", sort=False, dropna=True).agg(
        {**{c: "first" for c in hdr if c not in ("order_id", "ordered_at", "status")},
         "ordered_at": "min", "status": "max"}  # "ok" > "cancelled": an order with one ok row counts as ok
    ).reset_index()
    # A credit note prefix overrides: it is cancelled even if every row says ok.
    if mapping.get("cancelled_order_prefixes"):
        pre = tuple(str(p).upper() for p in mapping["cancelled_order_prefixes"])
        orders.loc[orders["order_id"].astype(str).str.upper().str.startswith(pre), "status"] = "cancelled"
    orders["updated_at"] = orders["ordered_at"]

    if products_path:
        praw = read_table(products_path)
        products = _select(praw, mapping.get("product_columns", {}), PRODUCT_FIELDS, ["product_id"], Path(products_path).name)
        for c in ("price", "cost", "stock"):
            if c in products:
                products[c] = _num(products[c], dec)
    else:
        extra = [c for c in ("title", "category", "cost", "stock", "price") if c in src]
        if extra:
            products = src[["product_id", *extra]].dropna(subset=["product_id"]).groupby("product_id", sort=False).last().reset_index()
            if "price" not in products:
                products["price"] = float("nan")
        else:
            products = pd.DataFrame(columns=["product_id"])
    return StoreData(products, orders, lines).normalised()
