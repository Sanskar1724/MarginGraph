"""Turn public retail datasets into files `margingraph sync csv` reads.

Each converter writes two files in the connector's common schema, so no
column mapping is needed:

    orders.csv    order_id, product_id, title, quantity, unit_price, ordered_at, customer_id, country, status
    products.csv  product_id, title, category, price[, cost]

Then:

    margingraph sync csv --orders OUT/orders.csv --products OUT/products.csv --out data/store/NAME
    python scripts/public_datasets.py simulate-erp data/store/NAME/config.yaml
    margingraph --config data/store/NAME/config.yaml run --results results_NAME --artifacts artifacts_NAME
    python scripts/public_datasets.py compare results results_NAME ...

Public datasets have no unit cost or stock (Ta Feng's ASSET column may be
cost, unverified). `simulate-erp` makes `run` use the same simulated ERP as
Online Retail II, so Stage 2 numbers stay comparable and stay labelled
simulated. Stage 1 (Hit@K, NDCG) is what these datasets validate.

`--top-items` keeps the N most-ordered products. EASE builds a dense
item x item matrix (N^2 x 8 bytes while fitting), so 5,000 items is about
200 MB and safe on 8 GB of RAM; 10,000 is about 800 MB plus copies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ORDER_COLS = ["order_id", "product_id", "title", "quantity", "unit_price", "ordered_at", "customer_id", "country", "status"]


def _find(src: Path, *names: str) -> Path:
    """First file under src whose name matches one of names (case-insensitive)."""
    wanted = {n.lower() for n in names}
    for p in sorted(src.rglob("*")):
        if p.is_file() and p.name.lower() in wanted:
            return p
    raise FileNotFoundError(f"none of {names} under {src}")


def _read(path: Path, **kw) -> pd.DataFrame:
    df = pd.read_csv(path, **kw)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _keep_top_items(orders: pd.DataFrame, products: pd.DataFrame, top: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if top and orders["product_id"].nunique() > top:
        keep = orders.groupby("product_id")["order_id"].nunique().nlargest(top).index
        orders = orders[orders["product_id"].isin(keep)]
    products = products[products["product_id"].isin(orders["product_id"].unique())]
    return orders, products


def _sample_customers(df: pd.DataFrame, col: str, n: int | None, seed: int) -> pd.DataFrame:
    if not n:
        return df
    ids = df[col].drop_duplicates()
    if len(ids) <= n:
        return df
    keep = ids.sample(n, random_state=seed)
    return df[df[col].isin(keep)]


# ---- Instacart ---------------------------------------------------------------
def instacart(src: Path, max_customers: int | None, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Instacart Market Basket Analysis (2017). No prices and no real dates.

    Dates: each user's orders are placed on a timeline from
    days_since_prior_order, with every user's last order on 2017-06-30, so the
    newest orders become the test set. Prices are 1.0 (unknown), so only
    Stage 1 results are meaningful.
    """
    o = _read(_find(src, "orders.csv"))
    o = o[o["eval_set"].isin(["prior", "train"])]
    o = _sample_customers(o, "user_id", max_customers, seed)
    o = o.sort_values(["user_id", "order_number"])
    gap = o["days_since_prior_order"].fillna(0)
    cum = gap.groupby(o["user_id"]).cumsum()
    back = cum.groupby(o["user_id"]).transform("max") - cum
    o["ordered_at"] = pd.Timestamp("2017-06-30") - pd.to_timedelta(back, unit="D") + pd.to_timedelta(o["order_hour_of_day"], unit="h")
    keep_ids = set(o["order_id"])

    parts = []
    for name in ("order_products__prior.csv", "order_products__train.csv"):
        for chunk in pd.read_csv(_find(src, name), usecols=["order_id", "product_id"], chunksize=2_000_000):
            parts.append(chunk[chunk["order_id"].isin(keep_ids)])
    lines = pd.concat(parts, ignore_index=True)

    prod = _read(_find(src, "products.csv"))
    try:
        dept = _read(_find(src, "departments.csv"))
        prod = prod.merge(dept, on="department_id", how="left")
        prod["category"] = prod["department"].fillna("unknown")
    except FileNotFoundError:
        prod["category"] = prod["department_id"].astype(str)
    prod = prod.rename(columns={"product_name": "title"})
    prod["product_id"] = prod["product_id"].astype(str)
    prod["price"] = 1.0

    lines["product_id"] = lines["product_id"].astype(str)
    orders = lines.merge(o[["order_id", "user_id", "ordered_at"]], on="order_id")
    orders = orders.merge(prod[["product_id", "title"]], on="product_id", how="left")
    orders = orders.assign(quantity=1, unit_price=1.0, customer_id=orders["user_id"].astype(str), country="US", status="ok")
    return orders, prod[["product_id", "title", "category", "price"]]


# ---- Dunnhumby The Complete Journey -----------------------------------------
def dunnhumby(src: Path, max_customers: int | None, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """2,500 households, 2 years, real prices. DAY 1 is mapped to 2018-01-01."""
    t = _read(_find(src, "transaction_data.csv"))
    t = _sample_customers(t, "household_key", max_customers, seed)
    t = t[(t["quantity"] > 0) & (t["sales_value"] > 0)]
    hhmm = t["trans_time"].astype(int)
    t["ordered_at"] = (pd.Timestamp("2018-01-01") + pd.to_timedelta(t["day"] - 1, unit="D")
                       + pd.to_timedelta(hhmm // 100, unit="h") + pd.to_timedelta(hhmm % 100, unit="m"))
    p = _read(_find(src, "product.csv"))
    p["product_id"] = p["product_id"].astype(str)
    size = p.get("curr_size_of_product", pd.Series("", index=p.index)).fillna("").astype(str).str.strip()
    p["title"] = (p["commodity_desc"].fillna("").astype(str).str.strip() + " / "
                  + p["sub_commodity_desc"].fillna("").astype(str).str.strip() + " " + size).str.strip()
    p["category"] = p["department"].fillna("unknown").astype(str).str.strip()

    t["product_id"] = t["product_id"].astype(str)
    orders = pd.DataFrame({
        "order_id": t["basket_id"].astype(str),
        "product_id": t["product_id"],
        "quantity": t["quantity"],
        "unit_price": t["sales_value"] / t["quantity"],
        "ordered_at": t["ordered_at"],
        "customer_id": t["household_key"].astype(str),
        "country": "US",
        "status": "ok",
    }).merge(p[["product_id", "title"]], on="product_id", how="left")
    price = orders.groupby("product_id")["unit_price"].median().rename("price").reset_index()
    prod = p[["product_id", "title", "category"]].merge(price, on="product_id")
    return orders, prod


# ---- Olist Brazilian e-commerce ---------------------------------------------
def olist(src: Path, max_customers: int | None, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Marketplace orders 2016-2018 with prices. Most orders have one product,
    so expect few evaluation baskets: this tests the sparse-basket case."""
    o = _read(_find(src, "olist_orders_dataset.csv"))
    it = _read(_find(src, "olist_order_items_dataset.csv"))
    c = _read(_find(src, "olist_customers_dataset.csv"))
    p = _read(_find(src, "olist_products_dataset.csv"))
    try:
        tr = _read(_find(src, "product_category_name_translation.csv"))
        p = p.merge(tr, on="product_category_name", how="left")
        p["category"] = p["product_category_name_english"].fillna(p["product_category_name"])
    except FileNotFoundError:
        p["category"] = p["product_category_name"]
    p["category"] = p["category"].fillna("unknown")
    # Olist has no product names; the category plus a short id is the title.
    p["title"] = p["category"].str.replace("_", " ") + " #" + p["product_id"].str[:6]

    o = o.merge(c[["customer_id", "customer_unique_id", "customer_state"]], on="customer_id", how="left")
    o = _sample_customers(o, "customer_unique_id", max_customers, seed)
    g = it.groupby(["order_id", "product_id"], as_index=False).agg(quantity=("order_item_id", "size"), unit_price=("price", "mean"))
    orders = g.merge(o, on="order_id")
    orders = pd.DataFrame({
        "order_id": orders["order_id"],
        "product_id": orders["product_id"],
        "quantity": orders["quantity"],
        "unit_price": orders["unit_price"],
        "ordered_at": pd.to_datetime(orders["order_purchase_timestamp"]),
        "customer_id": orders["customer_unique_id"].astype(str),
        "country": "BR-" + orders["customer_state"].fillna("").astype(str),
        "status": np.where(orders["order_status"].isin(["canceled", "unavailable"]), "cancelled", "ok"),
    }).merge(p[["product_id", "title"]], on="product_id", how="left")
    price = orders.groupby("product_id")["unit_price"].median().rename("price").reset_index()
    return orders, p[["product_id", "title", "category"]].merge(price, on="product_id")


# ---- Ta Feng grocery ----------------------------------------------------------
def tafeng(src: Path, max_customers: int | None, seed: int, asset_as_cost: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Taiwanese grocery, Nov 2000 - Feb 2001. There is no basket id, so one
    customer's purchases on one day form one order (the usual convention)."""
    t = _read(_find(src, "ta_feng_all_months_merged.csv"), dtype={"CUSTOMER_ID": str, "PRODUCT_ID": str})
    t = _sample_customers(t, "customer_id", max_customers, seed)
    t = t[(t["amount"] > 0) & (t["sales_price"] > 0)]
    t["ordered_at"] = pd.to_datetime(t["transaction_dt"], format="mixed")
    orders = pd.DataFrame({
        "order_id": t["customer_id"].astype(str) + "-" + t["ordered_at"].dt.strftime("%Y%m%d"),
        "product_id": t["product_id"].astype(str),
        "quantity": t["amount"],
        "unit_price": t["sales_price"] / t["amount"],
        "ordered_at": t["ordered_at"],
        "customer_id": t["customer_id"].astype(str),
        "country": "TW",
        "status": "ok",
    })
    orders["title"] = "subclass " + t["product_subclass"].astype(str) + " #" + orders["product_id"].str[-6:]
    g = orders.assign(category=t["product_subclass"].astype(str).values)
    prod = g.groupby("product_id").agg(title=("title", "first"), category=("category", "first"), price=("unit_price", "median")).reset_index()
    if asset_as_cost:
        # ASSET is often read as the line's cost, but the dataset does not document it.
        cost = (t["asset"] / t["amount"]).groupby(orders["product_id"]).median().rename("cost")
        prod = prod.merge(cost, left_on="product_id", right_index=True, how="left")
    return orders, prod


CONVERTERS = {"instacart": instacart, "dunnhumby": dunnhumby, "olist": olist, "tafeng": tafeng}


def cmd_convert(a: argparse.Namespace) -> None:
    src, out = Path(a.src), Path(a.out)
    kw = {"asset_as_cost": a.asset_as_cost} if a.name == "tafeng" else {}
    orders, products = CONVERTERS[a.name](src, a.max_customers, a.seed, **kw)
    orders, products = _keep_top_items(orders, products, a.top_items)
    orders["ordered_at"] = pd.to_datetime(orders["ordered_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out.mkdir(parents=True, exist_ok=True)
    orders[ORDER_COLS].to_csv(out / "orders.csv", index=False)
    products.to_csv(out / "products.csv", index=False)
    sizes = orders.groupby("order_id")["product_id"].nunique()
    stats = {
        "dataset": a.name,
        "order_lines": len(orders),
        "orders": int(sizes.size),
        "orders_with_2plus_products": int((sizes >= 2).sum()),
        "products": int(orders["product_id"].nunique()),
        "customers": int(orders["customer_id"].nunique()),
        "first": orders["ordered_at"].min(),
        "last": orders["ordered_at"].max(),
        "has_cost": "cost" in products,
        "max_customers": a.max_customers,
        "top_items": a.top_items,
    }
    (out / "convert_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


def cmd_simulate_erp(a: argparse.Namespace) -> None:
    """Drop data.erp_path so `run` simulates cost and stock exactly as for Online Retail II."""
    import yaml

    p = Path(a.config)
    cfg = yaml.safe_load(p.read_text())
    cfg["data"].pop("erp_path", None)
    p.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"{p}: data.erp_path removed; Stage 2 will use the simulated ERP (erp.margin_beta etc.)")


def _pick(df: pd.DataFrame, **eq) -> pd.Series:
    m = np.ones(len(df), bool)
    for k, v in eq.items():
        m &= df[k].to_numpy() == v
    return df[m].iloc[0] if m.any() else pd.Series(dtype=object)


def cmd_compare(a: argparse.Namespace) -> None:
    """One markdown row per results folder: LightGBM vs the best baseline on test."""
    def pct(x):
        return f"{100 * float(x):.1f}%"

    rows = ["| Results | Test events | Pool recall | Best baseline (picked on val) | Baseline Hit@10 | LightGBM Hit@10 | Diff [95% CI] | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for d in map(Path, a.results):
        s = json.loads((d / "summary.json").read_text())
        e5 = pd.read_csv(d / "e5_rerank.csv")
        pair = _pick(pd.read_csv(d / "e5_paired.csv"), metric="hit@10")
        base = s.get("best_baseline_on_val", "?")
        lgb = _pick(e5, model="lightgbm", metric="hit@10")
        e3 = pd.read_csv(d / "e3_baselines.csv")
        b = _pick(e3, model=base, metric="hit@10", split="test")
        # The pool size is a config setting (100 at first, 150 since the accuracy
        # thread), so read the pool's own test recall rather than a fixed @K.
        rec = s.get("e4_test_pool_recall")
        lo, hi = float(pair["ci_low"]), float(pair["ci_high"])
        verdict = "LightGBM wins" if lo > 0 else ("baseline wins" if hi < 0 else "tie")
        rows.append(f"| `{d}` | {int(lgb['n'])} | {pct(rec) if rec is not None else '?'} | {base} | "
                    f"{pct(b['mean']) if len(b) else '?'} | {pct(lgb['mean'])} | "
                    f"{100 * float(pair['diff']):+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] | {verdict} |")
    print("\n".join(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="raw public dataset -> orders.csv + products.csv")
    c.add_argument("name", choices=sorted(CONVERTERS))
    c.add_argument("--src", required=True, help="folder with the unzipped dataset files")
    c.add_argument("--out", required=True, help="folder for orders.csv and products.csv")
    c.add_argument("--max-customers", type=int, default=None, help="random sample of customers, to fit in RAM")
    c.add_argument("--top-items", type=int, default=5000, help="keep the N most-ordered products (0 = all)")
    c.add_argument("--seed", type=int, default=42)
    c.add_argument("--asset-as-cost", action="store_true", help="tafeng: write ASSET/AMOUNT as products.cost (unverified meaning)")
    e = sub.add_parser("simulate-erp", help="make a synced store config use the simulated cost and stock")
    e.add_argument("config")
    m = sub.add_parser("compare", help="markdown table of LightGBM vs best baseline across results folders")
    m.add_argument("results", nargs="+")
    a = ap.parse_args()
    {"convert": cmd_convert, "simulate-erp": cmd_simulate_erp, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    main()
