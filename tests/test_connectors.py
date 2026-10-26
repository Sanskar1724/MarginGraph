"""Connector tests. All HTTP is mocked through HttpClient's transport."""
import base64
import json
import urllib.parse

import numpy as np
import pandas as pd
import pytest
import yaml
from conftest import make_raw

from margingraph import connectors as c
from margingraph.cli import main
from margingraph.connectors.http import HttpClient, HttpError, next_link
from margingraph.pipeline import run


class FakeHttp:
    """Routes GET requests to a handler(path, params) -> (status, headers, payload)."""

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def __call__(self, method, url, headers, timeout):
        u = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(u.query))
        self.calls.append((u.path, params, dict(headers)))
        status, hdrs, payload = self.handler(u.path, params)
        return status, hdrs, json.dumps(payload).encode()


def client(handler):
    fake = FakeHttp(handler)
    return HttpClient(transport=fake, sleep=lambda s: None), fake


# ---------------------------------------------------------------- http


def test_http_retries_429_then_succeeds():
    n = {"i": 0}
    slept = []

    def h(path, params):
        n["i"] += 1
        return (429, {"Retry-After": "1.5"}, {}) if n["i"] < 3 else (200, {}, {"ok": True})

    fake = FakeHttp(h)
    cl = HttpClient(transport=fake, sleep=slept.append)
    assert cl.get("https://x.test/a", {"q": 1}).data == {"ok": True}
    assert slept == [1.5, 1.5] and len(fake.calls) == 3


def test_http_raises_on_401_and_redacts_secret():
    cl, _ = client(lambda p, q: (401, {}, {"error": "bad key"}))
    with pytest.raises(HttpError) as e:
        cl.get("https://x.test/a", {"consumer_secret": "cs_secret"})
    assert "cs_secret" not in str(e.value)


def test_next_link():
    h = '<https://s/a.json?page_info=p1&limit=250>; rel="previous", <https://s/a.json?page_info=p2&limit=250>; rel="next"'
    assert next_link(h) == "https://s/a.json?page_info=p2&limit=250"
    assert next_link('<https://s/a.json?page_info=p1>; rel="previous"') is None


# ---------------------------------------------------------------- csv


def test_csv_mapping_validation_and_cancellations(tmp_path):
    df = pd.DataFrame({
        "Order #": ["1001", "1001", "1002", "C1003", "1004"],
        "SKU": ["A", "B", "A", "A", "B"],
        "Qty": ["1", "2", "1", "-1", "3"],
        "Unit Price": ["$10.00", "$4.50", "$10.00", "$10.00", "$1,200.00"],
        "Date": ["2024-01-01 10:00", "2024-01-01 10:00", "2024-01-02", "2024-01-03", "2024-01-04"],
    })
    df.to_csv(tmp_path / "o.csv", index=False)
    with pytest.raises(ValueError, match="order_id"):
        c.load_csv_store(str(tmp_path / "o.csv"), None, c.load_mapping())

    m = c.load_mapping(overrides=["order_id=Order #", "product_id=SKU", "quantity=Qty",
                                  "unit_price=Unit Price", "ordered_at=Date"])
    m["cancelled_order_prefixes"] = ["C"]
    store = c.load_csv_store(str(tmp_path / "o.csv"), None, m)
    assert store.order_lines["unit_price"].tolist() == [10.0, 4.5, 10.0, 10.0, 1200.0]
    assert store.orders.set_index("order_id").loc["C1003", "status"] == "cancelled"
    rep = c.validate(store, min_orders=5)
    assert rep.ok and any("2+ products" in w for w in rep.warnings)
    lines, catalog, erp, log = c.to_pipeline(store)
    assert "C1003" not in set(lines["invoice"]) and log["dropped_cancelled_orders"] == 1
    assert erp["unit_cost"].isna().all()  # no cost anywhere -> pipeline will assume
    assert set(catalog["item"]) == {"A", "B"}


def test_validate_blocks_unusable_files():
    store = c.StoreData(orders=pd.DataFrame({"order_id": ["1"], "ordered_at": ["not a date"]}),
                        order_lines=pd.DataFrame({"order_id": ["1"], "product_id": ["A"], "quantity": [1], "unit_price": [2]}))
    rep = c.validate(store.normalised())
    assert not rep.ok and "ordered_at" in rep.errors[0]


# ---------------------------------------------------------------- shopify


def shopify_handler(orders_by_call):
    state = {"orders_call": 0}

    def h(path, params):
        if path.endswith("/products.json"):
            if params.get("page_info") == "p2":
                return 200, {}, {"products": [{"id": 2, "title": "Mug", "product_type": "Kitchen", "updated_at": "2024-01-01T00:00:00Z",
                                               "variants": [{"id": 21, "title": "Default Title", "price": "8.00",
                                                             "inventory_quantity": 40, "inventory_item_id": 921}]}]}
            assert params["limit"] == "250"
            return 200, {"Link": '<https://demo.myshopify.com/admin/api/2024-10/products.json?limit=250&page_info=p2>; rel="next"'}, {
                "products": [{"id": 1, "title": "Tee", "product_type": "Apparel", "updated_at": "2024-01-01T00:00:00Z",
                              "variants": [{"id": 11, "title": "S", "price": "20.00", "inventory_quantity": 5, "inventory_item_id": 911},
                                           {"id": 12, "title": "M", "price": "20.00", "inventory_quantity": -2, "inventory_item_id": 912}]}]}
        if path.endswith("/inventory_items.json"):
            assert set(params["ids"].split(",")) == {"911", "912", "921"}
            return 200, {}, {"inventory_items": [{"id": 911, "cost": "7.50"}, {"id": 912, "cost": None}, {"id": 921, "cost": "3.00"}]}
        if path.endswith("/orders.json"):
            assert params["status"] == "any"
            i = state["orders_call"]
            state["orders_call"] += 1
            return 200, {}, {"orders": orders_by_call[i](params)}
        return 404, {}, {}

    return h


def sh_order(oid, created, updated, items, cancelled=False):
    return {"id": oid, "created_at": created, "updated_at": updated, "cancelled_at": "x" if cancelled else None,
            "financial_status": "paid", "customer": {"id": 77}, "shipping_address": {"country_code": "GB"},
            "line_items": [{"variant_id": v, "product_id": 1, "name": f"v{v}", "quantity": q, "price": p,
                            "discount_allocations": [{"amount": "2.00"}] if v == 11 else []} for v, q, p in items]}


def test_shopify_full_then_incremental(tmp_path, tiny_cfg):
    cfg, _ = tiny_cfg
    first = [sh_order(i, f"2024-0{1 + i % 6}-1{i % 9}T10:00:00+01:00", "2024-07-01T00:00:00Z",
                      [(11, 1, "20.00"), (21, 2, "8.00")]) for i in range(1, 40)]

    def call1(params):
        assert "updated_at_min" not in params
        return first

    def call2(params):
        assert params["updated_at_min"] == "2024-07-01T00:00:00Z"
        return [sh_order(5, "2024-06-15T10:00:00Z", "2024-07-02T00:00:00Z", [(11, 1, "20.00")], cancelled=True),
                sh_order(500, "2024-07-02T09:00:00Z", "2024-07-02T09:00:00Z", [(12, 1, "20.00"), (21, 1, "8.00")])]

    cl, fake = client(shopify_handler([call1, call2]))
    src = c.ShopifySource("demo", "shpat_test", client=cl)
    res = c.sync(src, tmp_path / "s", cfg, min_orders=1)
    assert res["state"]["mode"] == "full" and res["state"]["orders_watermark"] == "2024-07-01T00:00:00Z"
    assert all(h["X-Shopify-Access-Token"] == "shpat_test" for _, _, h in fake.calls)

    erp = pd.read_parquet(tmp_path / "s/pipeline/erp.parquet").set_index("item")
    assert erp.loc["11", "unit_cost"] == 7.5 and "12" not in erp.index  # 12 not sold yet
    assert erp.loc["21", "stock"] == 40
    lines = pd.read_parquet(tmp_path / "s/pipeline/lines.parquet")
    assert lines.query("item == '11'")["price"].iloc[0] == 18.0  # 20 minus a 2.00 discount
    # +01:00 converted to UTC
    assert pd.read_parquet(tmp_path / "s/raw/orders.parquet").set_index("order_id").loc["1", "ordered_at"].hour == 9

    res2 = c.sync(src, tmp_path / "s", cfg, min_orders=1)
    assert res2["state"]["mode"] == "incremental" and res2["state"]["fetched_orders"] == 2
    orders = pd.read_parquet(tmp_path / "s/raw/orders.parquet").set_index("order_id")
    assert len(orders) == 40 and orders.loc["5", "status"] == "cancelled"
    lines = pd.read_parquet(tmp_path / "s/pipeline/lines.parquet")
    assert "5" not in set(lines["invoice"]) and "500" in set(lines["invoice"])
    erp = pd.read_parquet(tmp_path / "s/pipeline/erp.parquet").set_index("item")
    assert erp.loc["12", "stock"] == 0  # oversold variant clipped at zero
    assert np.isnan(erp.loc["12", "unit_cost"])  # no cost in Shopify -> assumed later


# ---------------------------------------------------------------- woocommerce


def woo_handler(path, params):
    page = int(params.get("page", 1))
    if path.endswith("/products"):
        data = {
            1: [{"id": 10, "type": "simple", "name": "Candle", "price": "12.00", "stock_quantity": 30,
                 "categories": [{"name": "Home"}], "meta_data": [{"key": "_wc_cog_cost", "value": "4.00"}],
                 "date_modified_gmt": "2024-01-01T00:00:00"}],
            2: [{"id": 20, "type": "variable", "name": "Scarf", "price": "15.00", "categories": [],
                 "meta_data": [{"key": "_wc_cog_cost", "value": "6.00"}]}],
        }[page]
        return 200, {"X-WP-TotalPages": "2"}, data
    if path.endswith("/products/20/variations"):
        return 200, {"X-WP-TotalPages": "1"}, [
            {"id": 21, "price": "15.00", "stock_quantity": None, "attributes": [{"option": "Red"}], "meta_data": []},
            {"id": 22, "price": "16.00", "stock_quantity": 3, "attributes": [{"option": "Blue"}],
             "meta_data": [{"key": "_wc_cog_cost", "value": "7.00"}]},
        ]
    if path.endswith("/orders"):
        orders = [{"id": 100 + i, "status": ["completed", "processing", "refunded"][i % 3],
                   "date_created_gmt": f"2024-0{1 + i % 6}-0{1 + i % 9}T12:00:00",
                   "date_modified_gmt": "2024-07-01T00:00:00", "customer_id": i % 4,
                   "billing": {"country": "US", "email": f"g{i}@x.test"}, "shipping": {},
                   "line_items": [{"product_id": 10, "variation_id": 0, "quantity": 2, "total": "20.00", "name": "Candle"},
                                  {"product_id": 20, "variation_id": 21 + i % 2, "quantity": 1, "total": "15.00", "name": "Scarf"}]}
                  for i in range(30)]
        chunks = [orders[:100]]
        return 200, {"X-WP-TotalPages": "1"}, chunks[page - 1]
    return 404, {}, {}


def test_woocommerce_pagination_variations_cost_meta(tmp_path, tiny_cfg):
    cfg, _ = tiny_cfg
    cl, fake = client(woo_handler)
    src = c.WooCommerceSource("shop.example.com", "ck_1", "cs_2", client=cl)
    c.sync(src, tmp_path / "w", cfg, min_orders=1)
    auth = fake.calls[0][2]["Authorization"]
    assert base64.b64decode(auth.split()[1]).decode() == "ck_1:cs_2"
    assert [p for p, q, _ in fake.calls if p.endswith("/products")] == ["/wp-json/wc/v3/products"] * 2

    erp = pd.read_parquet(tmp_path / "w/pipeline/erp.parquet").set_index("item")
    assert erp.loc["10", "unit_cost"] == 4.0
    assert erp.loc["21", "unit_cost"] == 6.0  # inherits the parent's cost
    assert erp.loc["22", "unit_cost"] == 7.0 and erp.loc["22", "stock"] == 3
    assert np.isnan(erp.loc["21", "stock"])
    lines = pd.read_parquet(tmp_path / "w/pipeline/lines.parquet")
    assert lines["invoice"].nunique() == 20  # refunded orders dropped
    assert lines.query("item == '10'")["price"].iloc[0] == 10.0
    cat = pd.read_parquet(tmp_path / "w/pipeline/catalog.parquet").set_index("item")
    assert cat.loc["22", "description"] == "Scarf - Blue" and cat.loc["10", "category"] == "HOME"

    res2 = c.sync(src, tmp_path / "w", cfg, min_orders=1)
    assert res2["state"]["mode"] == "incremental"
    last_orders = [q for p, q, _ in fake.calls if p.endswith("/orders")][-1]
    assert last_orders["modified_after"] == "2024-07-01T00:00:00Z" and last_orders["dates_are_gmt"] == "true"


def test_woocommerce_query_auth():
    cl, fake = client(lambda p, q: (200, {"X-WP-TotalPages": "1"}, []))
    c.WooCommerceSource("https://s.test", "ck_1", "cs_2", query_auth=True, client=cl).fetch()
    path, params, headers = fake.calls[0]
    assert params["consumer_key"] == "ck_1" and "Authorization" not in headers


def test_from_env_requires_credentials(monkeypatch):
    for k in ("SHOPIFY_SHOP", "SHOPIFY_ACCESS_TOKEN", "WC_STORE_URL", "WC_CONSUMER_KEY", "WC_CONSUMER_SECRET"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="SHOPIFY_SHOP"):
        c.ShopifySource.from_env()
    with pytest.raises(RuntimeError, match="WC_STORE_URL"):
        c.WooCommerceSource.from_env()


# ---------------------------------------------------------------- end to end


def test_cli_sync_csv_then_run_uses_store_costs(tmp_path, tiny_cfg):
    """Retail-style export + a products file with cost for half the items:
    sync via the CLI, then the full pipeline trains on it with real costs."""
    cfg, _ = tiny_cfg
    raw = make_raw(seed=3)
    raw.to_csv(tmp_path / "orders.csv", index=False)
    items = sorted(raw["StockCode"].unique())
    prods = pd.DataFrame({"SKU": items, "Unit Cost": [f"{2 + i % 5}.00" if i % 2 == 0 else "" for i in range(len(items))],
                          "On Hand": [str(10 * (i % 7)) for i in range(len(items))], "Type": "Gifts"})
    prods.to_csv(tmp_path / "products.csv", index=False)
    base = tmp_path / "base.yaml"
    base.write_text(yaml.safe_dump(cfg))

    main(["--config", str(base), "sync", "csv", "--out", str(tmp_path / "store"),
          "--orders", str(tmp_path / "orders.csv"), "--products", str(tmp_path / "products.csv"),
          "--preset", "online_retail_ii", "--map", "products.product_id=SKU", "--map", "products.cost=Unit Cost",
          "--map", "products.stock=On Hand", "--map", "products.category=Type"])
    log = json.loads((tmp_path / "store/pipeline/clean_log.json").read_text())
    assert log["dropped_cancelled_orders"] >= 1 and log["dropped_non_product_codes"] >= 1

    scfg = yaml.safe_load((tmp_path / "store/config.yaml").read_text())
    assert scfg["data"]["source"] == "csv" and scfg["split"]["val_start"] < scfg["split"]["test_start"]
    summary = run(scfg, str(tmp_path / "res"), str(tmp_path / "art"))
    assert summary["erp"]["source"] == "csv"
    assert 0.4 < summary["erp"]["cost_from_store_share"] < 0.6
    assert summary["erp"]["stock_from_store_share"] == 1.0
    erp = pd.read_csv(tmp_path / "res/erp_store.csv", dtype={"item": str}).set_index("item")
    assumed = erp[erp["cost_source"] == "assumed"]
    assert np.allclose(assumed["unit_cost"], assumed["price"] * 0.6)
    assert (tmp_path / "res/e8_strategies_store_erp.csv").exists()
    assert not (tmp_path / "res/e11_erp_sensitivity_milp_vs_ranker.csv").exists()

    import os

    from fastapi.testclient import TestClient

    os.environ["MARGINGRAPH_ARTIFACTS"] = str(tmp_path / "art")
    from margingraph import api

    api.bundle.cache_clear()
    r = TestClient(api.app).post("/recommend", json={"basket": [items[0], items[60]]})
    assert r.status_code == 200 and "store data" in r.json()["note"]
    assert {"cost_source", "stock_source"} <= set(r.json()["ranked_candidates"][0])
    api.bundle.cache_clear()
