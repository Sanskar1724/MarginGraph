"""Shopify Admin REST API connector.

Needs a custom app (Shopify admin > Settings > Apps > Develop apps) with the
read_products, read_inventory and read_orders scopes (read_all_orders for
orders older than 60 days). Credentials come from the environment:

    SHOPIFY_SHOP           my-store.myshopify.com
    SHOPIFY_ACCESS_TOKEN   shpat_...
    SHOPIFY_API_VERSION    optional, default 2024-10

Items are variants (one row per sellable SKU). Unit cost is the variant's
InventoryItem.cost, which Shopify calls "Cost per item".
"""
from __future__ import annotations

import os
from typing import Iterator

import pandas as pd

from .http import HttpClient, next_link
from .schema import StoreData

DEFAULT_VERSION = "2024-10"


class ShopifySource:
    name = "shopify"

    def __init__(self, shop: str, token: str, api_version: str = DEFAULT_VERSION, client: HttpClient | None = None):
        shop = shop.replace("https://", "").replace("http://", "").strip("/")
        if "." not in shop:
            shop = f"{shop}.myshopify.com"
        self.base = f"https://{shop}/admin/api/{api_version}"
        self.client = client or HttpClient()
        self.client.headers["X-Shopify-Access-Token"] = token

    @classmethod
    def from_env(cls, client: HttpClient | None = None) -> "ShopifySource":
        shop, token = os.environ.get("SHOPIFY_SHOP"), os.environ.get("SHOPIFY_ACCESS_TOKEN")
        if not shop or not token:
            raise RuntimeError("set SHOPIFY_SHOP and SHOPIFY_ACCESS_TOKEN (see docs/CONNECTORS.md)")
        return cls(shop, token, os.environ.get("SHOPIFY_API_VERSION", DEFAULT_VERSION), client)

    def _pages(self, path: str, key: str, params: dict) -> Iterator[dict]:
        url, p = f"{self.base}/{path}", {"limit": 250, **params}
        while url:
            r = self.client.get(url, p)
            yield from (r.data or {}).get(key, [])
            # page_info URLs carry their own query; other params are not allowed with it
            url, p = next_link(r.headers.get("link")), None

    def fetch_products(self, since: str | None = None) -> pd.DataFrame:
        rows, inv_ids = [], {}
        for prod in self._pages("products.json", "products", {"updated_at_min": since}):
            for v in prod.get("variants") or []:
                vt = v.get("title") or ""
                title = prod.get("title") or ""
                if vt and vt != "Default Title":
                    title = f"{title} - {vt}"
                rows.append({
                    "product_id": str(v["id"]), "title": title, "category": prod.get("product_type") or "",
                    "price": v.get("price"), "stock": v.get("inventory_quantity"),
                    "updated_at": max(filter(None, [prod.get("updated_at"), v.get("updated_at")]), default=None),
                })
                if v.get("inventory_item_id"):
                    inv_ids[v["inventory_item_id"]] = str(v["id"])
        costs = self._costs(list(inv_ids))
        by_variant = {inv_ids[k]: c for k, c in costs.items() if k in inv_ids}
        for r in rows:
            r["cost"] = by_variant.get(r["product_id"])
        return pd.DataFrame(rows, columns=["product_id", "title", "category", "price", "cost", "stock", "updated_at"])

    def _costs(self, inventory_item_ids: list) -> dict:
        out = {}
        for i in range(0, len(inventory_item_ids), 100):
            chunk = inventory_item_ids[i : i + 100]
            ids = ",".join(str(x) for x in chunk)
            for it in self._pages("inventory_items.json", "inventory_items", {"ids": ids, "limit": 100}):
                if it.get("cost") not in (None, ""):
                    out[it["id"]] = it["cost"]
        return out

    def fetch_orders(self, since: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        orders, lines = [], []
        for o in self._pages("orders.json", "orders", {"status": "any", "updated_at_min": since}):
            oid = str(o["id"])
            cancelled = bool(o.get("cancelled_at")) or o.get("financial_status") in {"refunded", "voided"}
            addr = o.get("shipping_address") or o.get("billing_address") or {}
            cust = o.get("customer") or {}
            orders.append({
                "order_id": oid, "ordered_at": o.get("created_at"), "updated_at": o.get("updated_at"),
                "customer_id": str(cust["id"]) if cust.get("id") else "",
                "country": addr.get("country_code") or addr.get("country") or "",
                "status": "cancelled" if cancelled else "ok",
            })
            for li in o.get("line_items") or []:
                pid = li.get("variant_id") or (f"P{li['product_id']}" if li.get("product_id") else None)
                if pid is None:  # custom line item with no product behind it
                    continue
                qty = float(li.get("quantity") or 0)
                price = float(li.get("price") or 0)
                disc = sum(float(d.get("amount") or 0) for d in li.get("discount_allocations") or [])
                lines.append({
                    "order_id": oid, "product_id": str(pid), "title": li.get("name") or li.get("title"),
                    "quantity": qty, "unit_price": price - disc / qty if qty else price,
                })
        return (pd.DataFrame(orders, columns=["order_id", "ordered_at", "updated_at", "customer_id", "country", "status"]),
                pd.DataFrame(lines, columns=["order_id", "product_id", "title", "quantity", "unit_price"]))

    def fetch(self, products_since: str | None = None, orders_since: str | None = None) -> StoreData:
        products = self.fetch_products(products_since)
        orders, lines = self.fetch_orders(orders_since)
        return StoreData(products, orders, lines).normalised()
