"""Production service tests on the tiny synthetic fixture (code checks only)."""
import hashlib
import hmac
import io
import json
import os

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from margingraph import data
from margingraph.service import db
from margingraph.service.app import apply_dashboard_settings, create_app
from margingraph.service.cache import MemoryCache, RedisCache
from margingraph.service.engine import assign_variant
from margingraph.service.schemas import StoreSettings
from margingraph.service.settings import Settings
from margingraph.service.train import train_store

ADMIN = {"X-Admin-Key": "test-admin"}


def _settings(tmp, url=None):
    return Settings(
        database_url=url or f"sqlite:///{tmp}/svc.db",
        artifacts_dir=str(tmp / "artifacts"),
        admin_key="test-admin",
        version_ttl_s=0.0,
        preload_models=False,
    )


@pytest.fixture(scope="module")
def world(tiny_cfg, tmp_path_factory):
    """A trained store 'shop' behind a TestClient, plus the raw tables it was built from."""
    cfg, _ = tiny_cfg
    tmp = tmp_path_factory.mktemp("svc")
    url = os.environ.get("MARGINGRAPH_TEST_DATABASE_URL")  # e.g. a local Postgres
    st = _settings(tmp, url)
    if url:
        eng = db.make_engine(url)
        db.metadata.drop_all(eng)
    app = create_app(st)
    client = TestClient(app)
    lines, catalog, _ = data.load_or_build(cfg)
    erp = data.simulate_erp(lines, catalog, cfg, 0)
    prods = catalog.merge(erp[["item", "unit_cost", "stock", "overstock"]], on="item")

    r = client.post("/v1/admin/stores", headers=ADMIN, json={"store_id": "shop", "name": "Test shop"})
    assert r.status_code == 201, r.text
    creds = r.json()
    h = {"X-API-Key": creds["api_key"]}
    buf = io.StringIO()
    prods[["item", "price", "unit_cost", "stock", "overstock", "description", "category"]].to_csv(buf, index=False)
    r = client.post("/v1/catalog/csv", headers={**h, "content-type": "text/csv"}, content=buf.getvalue())
    assert r.status_code == 200 and r.json()["upserted"] == len(prods), r.text
    buf = io.StringIO()
    lines.rename(columns={"invoice": "order_id", "customer": "customer_id"})[
        ["order_id", "item", "quantity", "price", "ts", "customer_id"]
    ].to_csv(buf, index=False)
    r = client.post("/v1/orders/import", headers={**h, "content-type": "text/csv"}, content=buf.getvalue())
    assert r.json()["imported_lines"] == len(lines)
    r = client.patch("/v1/settings", headers=h, json={"min_train_orders": 50, "rate_limit_per_minute": 0})
    assert r.status_code == 200, r.text

    meta = train_store(app.state.svc.engine, "shop", cfg, st.artifacts_dir, holdout_days=200, min_events=100)
    return {"client": client, "h": h, "creds": creds, "meta": meta, "lines": lines, "prods": prods, "app": app, "cfg": cfg, "st": st}


def _basket(world):
    inv = world["lines"].groupby("invoice")["item"].apply(list)
    return next(b for b in inv if len(b) >= 3)[:2]


def test_training_publishes_an_active_model(world):
    meta = world["meta"]
    assert meta["status"] == "active"
    m = meta["metrics"]
    hits = {k: v["hit@10"] for k, v in m.items() if isinstance(v, dict) and "hit@10" in v}
    assert hits["lightgbm"] > hits["popularity"], hits  # planted pairs are learnable
    assert m["gate"]["passed"] == (hits["lightgbm"] >= hits[m["best_baseline"]])
    r = world["client"].get("/v1/models", headers=world["h"])
    assert r.json()[0]["status"] == "active"


def test_quality_gate_keeps_the_serving_model(world):
    """A retrain that fails the gate is stored as rejected; the active model stays."""
    import margingraph.service.train as T

    app, eng = world["app"], world["app"].state.svc.engine
    real = T.ranking_metrics
    calls = {"n": 0}

    def rigged(rank, *a, **k):  # first call is LightGBM: make it look terrible
        calls["n"] += 1
        return real(rank + 1000 if calls["n"] == 1 else rank, *a, **k)

    T.ranking_metrics = rigged
    try:
        meta = train_store(eng, "shop", world["cfg"], world["st"].artifacts_dir, holdout_days=200, min_events=100)
    finally:
        T.ranking_metrics = real
    assert meta["status"] == "rejected" and not meta["metrics"]["gate"]["passed"]
    assert db.active_model(eng, "shop")["version"] == world["meta"]["version"]


def test_recommend_obeys_business_rules(world):
    c, h = world["client"], world["h"]
    basket = _basket(world)
    r = c.post("/v1/recommend", headers=h, json={"basket": basket, "customer_id": "7"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "model" and d["model_version"] == world["meta"]["version"]
    assert 1 <= len(d["addons"]) <= 2
    for a in d["addons"]:
        assert a["item"] not in basket
        assert a["margin_pct"] >= 0.15 - 1e-9
        assert a["stock"] > 0
        assert 0 <= a["p_accept"] <= 1
    # identical request is served from cache
    assert c.post("/v1/recommend", headers=h, json={"basket": basket, "customer_id": "7"}).json()["source"] == "cache"


def test_margin_floor_setting_is_hard(world):
    c, h = world["client"], world["h"]
    c.patch("/v1/settings", headers=h, json={"margin_floor": 0.55})
    try:
        for b in world["lines"].groupby("invoice")["item"].apply(list).head(30):
            d = c.post("/v1/recommend", headers=h, json={"basket": b[:2]}).json()
            assert all(a["margin_pct"] >= 0.55 - 1e-9 for a in d["addons"]), d
    finally:
        c.patch("/v1/settings", headers=h, json={"margin_floor": 0.15})


def test_stock_update_takes_effect_immediately(world):
    c, h = world["client"], world["h"]
    basket = _basket(world)
    first = c.post("/v1/recommend", headers=h, json={"basket": basket}).json()["addons"][0]["item"]
    r = c.post("/v1/inventory", headers=h, json={"changes": [{"item": first, "stock": 0}]})
    assert r.json()["updated"] == 1
    again = c.post("/v1/recommend", headers=h, json={"basket": basket}).json()
    assert first not in [a["item"] for a in again["addons"]]
    c.post("/v1/inventory", headers=h, json={"changes": [{"item": first, "stock": 50}]})
    assert c.get(f"/v1/catalog/{first}", headers=h).json()["stock"] == 50


def test_unknown_basket_falls_back_within_floor(world):
    c, h = world["client"], world["h"]
    d = c.post("/v1/recommend", headers=h, json={"basket": ["NOT-A-PRODUCT"]}).json()
    assert d["source"] == "fallback" and d["fallback_reason"] == "unknown_basket"
    assert d["basket_unknown"] == ["NOT-A-PRODUCT"]
    assert d["addons"] and all(a["margin_pct"] >= 0.15 - 1e-9 for a in d["addons"])


def test_store_without_model_uses_fallback(world):
    c = world["client"]
    creds = c.post("/v1/admin/stores", headers=ADMIN, json={"store_id": "newshop"}).json()
    h = {"X-API-Key": creds["api_key"]}
    c.post("/v1/catalog", headers=h, json={"products": [
        {"item": "A1", "price": 10, "unit_cost": 5, "stock": 3},
        {"item": "B2", "price": 10, "unit_cost": 9.5, "stock": 3},  # 5% margin: below floor
        {"item": "C3", "price": 10, "unit_cost": 2, "stock": 0},    # out of stock
    ]})
    d = c.post("/v1/recommend", headers=h, json={"basket": ["Z9"]}).json()
    assert d["fallback_reason"] == "no_model"
    assert [a["item"] for a in d["addons"]] == ["A1"]
    # stores are isolated: the other store's key cannot see this catalog
    assert c.get("/v1/catalog/A1", headers=world["h"]).status_code == 404


def test_partial_catalog_update_keeps_other_fields(world):
    c, h = world["client"], world["h"]
    item = world["prods"]["item"].iloc[0]
    before = c.get(f"/v1/catalog/{item}", headers=h).json()
    c.post("/v1/catalog", headers=h, json={"products": [{"item": item, "unit_cost": round(before["price"] * 0.5, 2)}]})
    after = c.get(f"/v1/catalog/{item}", headers=h).json()
    assert after["stock"] == before["stock"] and after["price"] == before["price"]
    assert after["unit_cost"] == round(before["price"] * 0.5, 2)


def test_order_attribution_stock_and_idempotency(world):
    c, h = world["client"], world["h"]
    rec = c.post("/v1/recommend", headers=h, json={"basket": _basket(world), "customer_id": "c-1", "session_id": "s-1"}).json()
    item = rec["addons"][0]["item"]
    stock0 = c.get(f"/v1/catalog/{item}", headers=h).json()["stock"]
    order = {"order_id": "o-1", "customer_id": "c-1", "lines": [{"item": item, "quantity": 2, "price": rec["addons"][0]["price"]}]}
    r = c.post("/v1/orders", headers=h, json=order).json()
    assert r == {"order_id": "o-1", "duplicate": False, "attributed": 1}
    assert c.get(f"/v1/catalog/{item}", headers=h).json()["stock"] == max(stock0 - 2, 0)
    assert c.post("/v1/orders", headers=h, json=order).json()["duplicate"] is True
    assert c.post("/v1/events", headers=h, json={"request_id": rec["request_id"], "item": item, "event_type": "click"}).json()["ok"]
    rep = c.get("/v1/report", headers=h).json()["variants"]
    assert sum(v["purchases"] for v in rep) >= 1 and sum(v["clicks"] for v in rep) >= 1


def test_signed_webhook(world):
    c, creds = world["client"], world["creds"]
    body = json.dumps({"order_id": "w-1", "lines": [{"item": "NOPE", "quantity": 1, "price": 1.0}]}).encode()
    sig = hmac.new(creds["webhook_secret"].encode(), body, hashlib.sha256).hexdigest()
    url = "/v1/webhooks/shop/orders"
    assert c.post(url, content=body, headers={"X-MarginGraph-Signature": "00" * 32}).status_code == 401
    r = c.post(url, content=body, headers={"X-MarginGraph-Signature": sig, "content-type": "application/json"})
    assert r.status_code == 200 and r.json()["duplicate"] is False


def test_auth_and_rate_limit(world):
    c = world["client"]
    assert c.post("/v1/recommend", json={"basket": ["A"]}).status_code == 401
    assert c.post("/v1/recommend", headers={"X-API-Key": "nope"}, json={"basket": ["A"]}).status_code == 401
    assert c.get("/v1/admin/stores", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert c.get("/v1/admin/stores", headers=ADMIN).status_code == 200
    creds = c.post("/v1/admin/stores", headers=ADMIN, json={"store_id": "tiny", "settings": {"rate_limit_per_minute": 2}}).json()
    h = {"X-API-Key": creds["api_key"]}
    codes = [c.post("/v1/recommend", headers=h, json={"basket": ["A"]}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_experiment_assignment_is_sticky_and_split(world):
    c, h = world["client"], world["h"]
    c.patch("/v1/settings", headers=h, json={"experiment": {"enabled": True}})
    try:
        seen = {}
        for i in range(40):
            v = c.post("/v1/recommend", headers=h, json={"basket": _basket(world), "customer_id": f"u{i}"}).json()["variant"]
            seen[f"u{i}"] = v
        assert set(seen.values()) == {"control", "treatment"}
        assert c.post("/v1/recommend", headers=h, json={"basket": _basket(world), "customer_id": "u3"}).json()["variant"] == seen["u3"]
        names = {v["variant"] for v in c.get("/v1/report", headers=h).json()["variants"]}
        assert {"control", "treatment"} <= names
    finally:
        c.patch("/v1/settings", headers=h, json={"experiment": {"enabled": False}})


def test_bad_settings_rejected(world):
    c, h = world["client"], world["h"]
    assert c.patch("/v1/settings", headers=h, json={"margin_floor": 2}).status_code == 422
    bad = {"experiment": {"enabled": True, "variants": [{"name": "x", "overrides": {"api_key_hash": "y"}}]}}
    assert c.patch("/v1/settings", headers=h, json=bad).status_code == 422


def test_rollback_and_ops_endpoints(world):
    c, h = world["client"], world["h"]
    v = world["meta"]["version"]
    assert c.post(f"/v1/models/{v}/activate", headers=h).json() == {"active": v}
    assert c.post("/v1/models/nope/activate", headers=h).status_code == 404
    assert c.get("/health").json()["ok"]
    assert c.get("/ready").json()["database_ok"]
    m = c.get("/metrics").text
    assert "margingraph_recommendations_total" in m and "margingraph_recommend_latency_ms_bucket" in m


def test_dashboard_event_view(world):
    with world["app"].state.svc.engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT event, COUNT(*) FROM dashboard_events GROUP BY event").all()
    kinds = dict(rows)
    assert kinds.get("impression", 0) > 0 and kinds.get("purchase", 0) >= 1


def test_dashboard_settings_mapping():
    s = apply_dashboard_settings(
        StoreSettings(),
        {"margin_floor": 0.2, "lam": 0.5, "allow_discounts": True, "treatment_share": 0.3,
         "items": {"22423": {"excluded": True}, "X": {"excluded": False}}},
    )
    assert s.margin_floor == 0.2 and s.discounts == [0.0, 0.1, 0.2] and s.excluded_items == ["22423"]
    v = {x.name: x for x in s.experiment.variants}
    assert v["control"].weight == pytest.approx(0.7) and v["treatment"].overrides == {"lam": 0.5}
    assert s.for_variant("control").lam == 0.0 and s.for_variant("treatment").margin_floor == 0.2
    # garbage from the dashboard never replaces valid settings
    assert apply_dashboard_settings(StoreSettings(), {"margin_floor": 7}).margin_floor == 0.15


def test_variant_hash_is_balanced():
    s = StoreSettings(experiment={"enabled": True})
    share = sum(assign_variant(s, "st", f"c{i}") == "treatment" for i in range(4000)) / 4000
    assert 0.46 < share < 0.54


def test_caches(monkeypatch):
    m = MemoryCache(max_items=2)
    m.set("a", 1); m.set("b", 2); m.set("c", 3)
    assert m.get("a") is None and m.get("c") == 3
    assert [m.incr("n", 60) for _ in range(3)] == [1, 2, 3]
    fakeredis = pytest.importorskip("fakeredis")
    import redis

    srv = fakeredis.FakeServer()
    monkeypatch.setattr(redis.Redis, "from_url", classmethod(lambda cls, *a, **k: fakeredis.FakeRedis(server=srv, decode_responses=True)))
    r = RedisCache("redis://fake")
    r.set("k", {"x": [1, 2]}, ttl=10)
    assert r.get("k") == {"x": [1, 2]} and r.ping()
    assert [r.incr("n", 60) for _ in range(2)] == [1, 2]


def test_import_sync_folder_keeps_unknown_costs_unrecommendable(tmp_path, tiny_cfg):
    """Connector output -> service store: items without a store cost are never offered."""
    import yaml

    from conftest import make_raw
    from margingraph.cli import main
    from margingraph.service.cli import import_sync

    cfg, _ = tiny_cfg
    raw = make_raw(seed=5)
    raw.to_csv(tmp_path / "orders.csv", index=False)
    items = sorted(raw["StockCode"].unique())
    pd.DataFrame({"SKU": items, "Unit Cost": [1.0 if i % 2 == 0 else None for i in range(len(items))], "On Hand": 5}).to_csv(
        tmp_path / "products.csv", index=False
    )
    (tmp_path / "base.yaml").write_text(yaml.safe_dump(cfg))
    main(["--config", str(tmp_path / "base.yaml"), "sync", "csv", "--out", str(tmp_path / "store"),
          "--orders", str(tmp_path / "orders.csv"), "--products", str(tmp_path / "products.csv"),
          "--preset", "online_retail_ii", "--map", "products.product_id=SKU", "--map", "products.cost=Unit Cost",
          "--map", "products.stock=On Hand"])
    st = _settings(tmp_path)
    app = create_app(st)
    c = TestClient(app)
    creds = c.post("/v1/admin/stores", headers=ADMIN, json={"store_id": "synced"}).json()
    out = import_sync(app.state.svc.engine, "synced", str(tmp_path / "store"))
    assert out["imported_lines"] > 0 and 0 < out["products_with_cost"] < out["products"]
    d = c.post("/v1/recommend", headers={"X-API-Key": creds["api_key"]}, json={"basket": [items[0]]}).json()
    costed = set(db.load_products(app.state.svc.engine, "synced").dropna(subset=["unit_cost"])["item"])
    assert d["addons"] and all(a["item"] in costed for a in d["addons"])
