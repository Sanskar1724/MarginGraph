"""WooCommerce REST API (wc/v3) connector.

Create a read-only key in WooCommerce > Settings > Advanced > REST API.
Credentials come from the environment:

    WC_STORE_URL        https://shop.example.com
    WC_CONSUMER_KEY     ck_...
    WC_CONSUMER_SECRET  cs_...
    WC_QUERY_AUTH       optional, "1" sends the key as query parameters for
                        hosts that strip the Authorization header
    WC_COST_META_KEY    optional, product meta key holding unit cost

WooCommerce has no built-in cost field. Cost-of-goods plugins keep it in
product meta; the keys below are checked in order unless WC_COST_META_KEY is
set. Incremental sync uses `modified_after` (WooCommerce 5.8+).
"""
from __future__ import annotations

import base64
import os
from typing import Iterator

import pandas as pd

from .http import HttpClient
from .schema import StoreData

COST_META_KEYS = ["_wc_cog_cost", "_alg_wc_cog_cost", "_purchase_price", "_cost_price", "cost_price"]
CANCELLED = {"cancelled", "refunded", "failed", "trash", "pending", "checkout-draft"}


def _meta_cost(meta: list | None, keys: list[str]):
    by_key = {m.get("key"): m.get("value") for m in meta or [] if isinstance(m, dict)}
    for k in keys:
        v = by_key.get(k)
        if v not in (None, ""):
            return v
    return None


class WooCommerceSource:
    name = "woocommerce"

    def __init__(self, url: str, key: str, secret: str, query_auth: bool = False,
                 cost_meta_keys: list[str] | None = None, client: HttpClient | None = None):
        url = url.rstrip("/")
        if not url.startswith(("https://", "http://")):
            url = f"https://{url}"
        self.base = f"{url}/wp-json/wc/v3"
        self.client = client or HttpClient()
        self.auth_params = {}
        if query_auth:
            self.auth_params = {"consumer_key": key, "consumer_secret": secret}
        else:
            tok = base64.b64encode(f"{key}:{secret}".encode()).decode()
            self.client.headers["Authorization"] = f"Basic {tok}"
        self.cost_keys = cost_meta_keys or COST_META_KEYS

    @classmethod
    def from_env(cls, client: HttpClient | None = None) -> "WooCommerceSource":
        url, key, secret = (os.environ.get(k) for k in ("WC_STORE_URL", "WC_CONSUMER_KEY", "WC_CONSUMER_SECRET"))
        if not (url and key and secret):
            raise RuntimeError("set WC_STORE_URL, WC_CONSUMER_KEY and WC_CONSUMER_SECRET (see docs/CONNECTORS.md)")
        meta = os.environ.get("WC_COST_META_KEY")
        return cls(url, key, secret, os.environ.get("WC_QUERY_AUTH") == "1", [meta] if meta else None, client)

    def _pages(self, path: str, params: dict) -> Iterator[dict]:
        page = 1
        while True:
            r = self.client.get(f"{self.base}/{path}", {**params, **self.auth_params, "per_page": 100, "page": page})
            batch = r.data or []
            yield from batch
            total = int(r.headers.get("x-wp-totalpages") or 0)
            if (total and page >= total) or (not total and len(batch) < 100) or not batch:
                return
            page += 1

    def _row(self, item: dict, title: str, category: str) -> dict:
        return {
            "product_id": str(item["id"]), "title": title, "category": category,
            "price": item.get("price") or item.get("regular_price"),
            "cost": _meta_cost(item.get("meta_data"), self.cost_keys),
            "stock": item.get("stock_quantity"),  # null when the store does not track stock
            "updated_at": item.get("date_modified_gmt") or item.get("date_modified"),
        }

    def fetch_products(self, since: str | None = None) -> pd.DataFrame:
        rows = []
        base = {"modified_after": since, "dates_are_gmt": "true" if since else None, "orderby": "id", "order": "asc"}
        for prod in self._pages("products", base):
            cats = prod.get("categories") or []
            cat = cats[0].get("name", "") if cats else ""
            if prod.get("type") == "variable":
                for v in self._pages(f"products/{prod['id']}/variations", {"orderby": "id", "order": "asc"}):
                    attrs = " / ".join(str(a.get("option")) for a in v.get("attributes") or [] if a.get("option"))
                    row = self._row(v, f"{prod.get('name', '')} - {attrs}" if attrs else prod.get("name", ""), cat)
                    if row["cost"] is None:
                        row["cost"] = _meta_cost(prod.get("meta_data"), self.cost_keys)
                    rows.append(row)
            else:
                rows.append(self._row(prod, prod.get("name", ""), cat))
        return pd.DataFrame(rows, columns=["product_id", "title", "category", "price", "cost", "stock", "updated_at"])

    def fetch_orders(self, since: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        orders, lines = [], []
        params = {"status": "any", "modified_after": since, "dates_are_gmt": "true" if since else None,
                  "orderby": "id", "order": "asc"}
        for o in self._pages("orders", params):
            oid = str(o["id"])
            bill = o.get("billing") or {}
            ship = o.get("shipping") or {}
            orders.append({
                "order_id": oid,
                "ordered_at": o.get("date_created_gmt") or o.get("date_created"),  # naive *_gmt values parse as UTC
                "updated_at": o.get("date_modified_gmt") or o.get("date_modified"),
                "customer_id": str(o["customer_id"]) if o.get("customer_id") else (bill.get("email") or ""),
                "country": ship.get("country") or bill.get("country") or "",
                "status": "cancelled" if o.get("status") in CANCELLED else "ok",
            })
            for li in o.get("line_items") or []:
                pid = li.get("variation_id") or li.get("product_id")
                if not pid:  # product deleted from the store
                    continue
                qty = float(li.get("quantity") or 0)
                total = float(li.get("total") or 0)  # after discounts, before tax
                lines.append({
                    "order_id": oid, "product_id": str(pid), "title": li.get("name"),
                    "quantity": qty, "unit_price": total / qty if qty else float(li.get("price") or 0),
                })
        return (pd.DataFrame(orders, columns=["order_id", "ordered_at", "updated_at", "customer_id", "country", "status"]),
                pd.DataFrame(lines, columns=["order_id", "product_id", "title", "quantity", "unit_price"]))

    def fetch(self, products_since: str | None = None, orders_since: str | None = None) -> StoreData:
        products = self.fetch_products(products_since)
        orders, lines = self.fetch_orders(orders_since)
        return StoreData(products, orders, lines).normalised()
