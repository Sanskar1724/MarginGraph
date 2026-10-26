"""Merchant dashboard: settings storage, KPI math, A/B stats and HTTP routes."""
import base64

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from margingraph.dashboard import adapter, app as appmod, db, kpis, sample


@pytest.fixture
def con(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setenv("MARGINGRAPH_DB", path)
    monkeypatch.delenv("MARGINGRAPH_DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("MARGINGRAPH_EVENTS_SQL", raising=False)
    monkeypatch.delenv("MARGINGRAPH_EVENTS_DB", raising=False)
    appmod.con.cache_clear()
    yield appmod.con()
    appmod.con.cache_clear()


@pytest.fixture
def client(con):
    return TestClient(appmod.app)


def ev(rid, variant, event, item="A", price=10.0, cost=6.0, over=0, qty=1, ts="2026-10-20T10:00:00+00:00"):
    return dict(ts=ts, store_id="s1", request_id=rid, variant=variant, event=event, item=item,
                price=price, unit_cost=cost, overstock=over, qty=qty)


def test_settings_roundtrip_validation_and_history(con):
    assert db.get_settings(con, "s1") == db.Settings()
    assert db.save_settings(con, "s1", db.Settings(margin_floor=0.2, overstock_weight=1.8)) == []
    s = db.get_settings(con, "s1")
    assert s.margin_floor == 0.2 and s.overstock_weight == 1.8 and s.allow_discounts is False
    assert db.save_settings(con, "s1", db.Settings(overstock_weight=3.0))  # out of 1.0-2.0
    assert db.get_settings(con, "s1").overstock_weight == 1.8           # unchanged after rejected save
    changed = {h["field"] for h in db.history(con, "s1")}
    assert changed == {"margin_floor", "overstock_weight"}


def test_item_rules(con):
    assert db.set_item_rule(con, "s1", " 85123a ", excluded=True) == []
    assert db.item_rules(con, "s1") == {"85123A": {"excluded": True, "overstock_weight": None}}
    assert db.set_item_rule(con, "s1", "X", overstock_weight=2.5)  # rejected
    db.set_item_rule(con, "s1", "85123A", excluded=False, clear_weight=True)
    assert db.item_rules(con, "s1") == {}


def test_kpis_hand_computed(con):
    db.insert_events(con, [
        ev("r1", "control", "impression"), ev("r1", "control", "impression", item="B"),
        ev("r1", "control", "click"), ev("r1", "control", "purchase", qty=2),           # profit 8, rev 20
        ev("r2", "control", "impression"),
        ev("r3", "treatment", "impression", item="C", price=20, cost=10, over=1),
        ev("r3", "treatment", "click", item="C", price=20, cost=10, over=1),
        ev("r3", "treatment", "purchase", item="C", price=20, cost=10, over=1),          # profit 10, rev 20
    ])
    req = kpis.per_request(adapter.load_events(con, "s1"))
    t = kpis.summary(req)
    assert (t["requests"], t["impressions"], t["clicks"], t["purchases"]) == (3, 4, 2, 2)
    assert t["revenue"] == 40 and t["profit"] == 18 and t["margin"] == pytest.approx(0.45)
    assert t["overstock_units"] == 1
    c = kpis.summary(req[req.variant == "control"])
    assert c["profit_per_request"] == 4 and c["conversion"] == 0.5


def test_catalog_fills_missing_price_cost_overstock(con):
    db.import_catalog(con, "s1", pd.DataFrame({"item": ["a"], "price": [5.0], "unit_cost": [2.0], "overstock": [True]}))
    db.insert_events(con, [dict(store_id="s1", request_id="r", variant="treatment", event="purchase", item="A")])
    e = adapter.load_events(con, "s1")
    assert (e.price[0], e.unit_cost[0], e.overstock[0]) == (5.0, 2.0, 1)


def test_welch_ci_matches_known_values():
    rng = np.random.default_rng(0)
    a, b = rng.normal(1.0, 1, 20000), rng.normal(1.1, 1, 20000)
    r = kpis._welch(a, b)
    assert r["lo"] < 0.1 < r["hi"] and r["p"] < 1e-6
    assert r["rel_lo"] < r["rel"] < r["rel_hi"]
    same = kpis._welch(a, a.copy())
    assert same["diff"] == 0 and same["p"] == 1.0


def test_srm_and_mde():
    assert kpis.srm_p(5000, 5000, 0.5) == pytest.approx(1.0)
    assert kpis.srm_p(5000, 5600, 0.5) < 0.001
    assert kpis.mde(0.16, 5000) == pytest.approx(0.0205, abs=0.001)


def test_policy_preview(con):
    cat = pd.DataFrame({"item": ["A", "B", "C"], "price": [10, 10, 10], "unit_cost": [9.5, 5, 5],
                        "stock": [5, 0, 5], "overstock": [0, 0, 1]})
    p = kpis.policy_preview(cat, db.Settings(margin_floor=0.15), {"C": {"excluded": True, "overstock_weight": None}})
    assert p == {"items": 3, "below_floor": 1, "excluded": 1, "out_of_stock": 1, "eligible": 0, "overstock": 1}


def test_sample_seed_and_pages(con, client):
    info = sample.seed(con, days=5, requests_per_day=200)
    assert info["events"] > 1000
    k = client.get("/api/stores/demo/kpis?days=all").json()
    assert k["sample_data"] and k["totals"]["requests"] > 800
    assert {r["metric"] for r in k["ab"]["rows"]} >= {"profit", "bought", "clicked"}
    # treatment never shows an item under the margin floor
    e = adapter.load_events(con, "demo")
    t = e[(e.variant == "treatment") & (e.event == "impression")]
    assert ((t.price - t.unit_cost) / t.price >= 0.15 - 1e-9).all()
    for url in ["/", "/store/demo", "/store/demo?days=7", "/store/demo/settings", "/store/empty"]:
        assert client.get(url).status_code == 200, url
    assert "sample data" in client.get("/store/demo").text
    csv = client.get("/api/stores/demo/events.csv")
    assert csv.status_code == 200 and csv.text.startswith("ts,store_id")


def test_settings_form_and_api(client, con):
    r = client.post("/store/s1/settings", content="margin_floor=20&max_addons=3&lam=0.7&overstock_weight=1.25"
                    "&treatment_share=30&allow_discounts=1",
                    headers={"content-type": "application/x-www-form-urlencoded"}, follow_redirects=False)
    assert r.status_code == 303 and "saved=1" in r.headers["location"]
    s = client.get("/api/stores/s1/settings").json()
    assert s["margin_floor"] == 0.2 and s["max_addons"] == 3 and s["allow_discounts"] is True
    bad = client.post("/store/s1/settings", content="margin_floor=95", follow_redirects=False,
                      headers={"content-type": "application/x-www-form-urlencoded"})
    assert "error=" in bad.headers["location"]
    client.post("/store/s1/items", content="item=22423&action=exclude",
                headers={"content-type": "application/x-www-form-urlencoded"})
    assert client.get("/api/stores/s1/settings").json()["items"]["22423"]["excluded"] is True
    r = client.put("/api/stores/s1/settings", json={"margin_floor": 0.1, "items": {"22423": {"excluded": False}}})
    assert r.status_code == 200 and r.json()["margin_floor"] == 0.1 and r.json()["items"] == {}
    assert client.put("/api/stores/s1/settings", json={"lam": 2}).status_code == 422
    assert client.put("/api/stores/s1/settings", json={"bogus": 1}).status_code == 422
    assert "margin_floor" in client.get("/store/s1/settings").text


def test_event_ingest_and_catalog_upload(client):
    r = client.post("/api/events", json=[ev("r1", "control", "impression"), ev("r1", "control", "purchase")])
    assert r.json() == {"inserted": 2}
    assert client.post("/api/events", json=ev("r1", "nope", "impression")).status_code == 422
    r = client.post("/api/stores/s1/catalog", content="item,price,unit_cost,stock,overstock\nA,10,6,3,true\nB,0,1,1,0\n")
    assert r.json() == {"store_id": "s1", "items": 1}


def test_token_auth(client, monkeypatch):
    monkeypatch.setenv("MARGINGRAPH_DASHBOARD_TOKEN", "secret")
    assert client.get("/api/stores").status_code == 401
    assert client.get("/api/stores", headers={"authorization": "Bearer secret"}).status_code == 200
    basic = base64.b64encode(b"owner:secret").decode()
    assert client.get("/store/s1", headers={"authorization": f"Basic {basic}"}).status_code == 200
