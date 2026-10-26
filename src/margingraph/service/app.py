"""MarginGraph production API (FastAPI). See docs/API.md for the contract.

Stateless by design: every piece of state lives in the database (stores,
catalog, stock, orders, logs, model registry), the cache (Redis or memory) or
the artifacts directory, so any number of copies can run behind a load
balancer. Start with ``margingraph api`` or ``uvicorn margingraph.service.app:app``.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import logging
import os
import secrets
import threading
import time
import uuid
from datetime import timedelta
from typing import Any

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from .. import __version__
from . import db
from .cache import make_cache
from .engine import (
    ModelRegistry,
    StoreCache,
    assign_variant,
    cache_key,
    fallback_recommend,
    model_recommend,
)
from .metrics import METRICS
from .schemas import (
    CatalogUpsert,
    FeedbackEvent,
    InventoryUpdate,
    Order,
    RecommendRequest,
    RecommendResponse,
    StoreCreate,
    StoreCreated,
    StoreSettings,
)
from .settings import DEV_ADMIN_KEY, Settings, get_settings

log = logging.getLogger("margingraph.api")


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class Service:
    """Shared, thread-safe state of one API process."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = db.make_engine(settings.database_url)
        db.init_db(self.engine)
        self.cache = make_cache(settings.redis_url)
        self.registry = ModelRegistry(settings.max_loaded_models)
        self.snapshots = StoreCache()
        self._auth: dict[str, tuple[float, dict | None]] = {}
        self._train_lock = threading.Lock()
        self.started = time.time()

    # ---- cached lookups ---------------------------------------------------
    def store_for_key(self, key: str) -> dict | None:
        h = hash_key(key)
        hit = self._auth.get(h)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        store = db.get_store_by_key_hash(self.engine, h)
        self._auth[h] = (time.monotonic() + self.settings.version_ttl_s, store)
        return store

    def forget_store(self, store_id: str) -> None:
        self._auth = {h: v for h, v in self._auth.items() if not (v[1] and v[1]["store_id"] == store_id)}

    def catalog_version(self, store_id: str) -> int:
        k = f"cv:{store_id}"
        v = self.cache.get(k)
        if v is None:
            v = db.catalog_version(self.engine, store_id)
            self.cache.set(k, v, self.settings.version_ttl_s)
        return int(v)

    def bump_catalog(self, store_id: str) -> int:
        v = db.bump_catalog_version(self.engine, store_id)
        self.cache.set(f"cv:{store_id}", v, self.settings.version_ttl_s)
        return v

    def model_info(self, store_id: str) -> dict | None:
        k = f"mv:{store_id}"
        v = self.cache.get(k)
        if v is None:
            m = db.active_model(self.engine, store_id)
            path = ""
            if m:
                path = m["path"] if os.path.isabs(m["path"]) else os.path.join(self.settings.artifacts_dir, m["path"])
            v = {"version": m["version"], "path": path} if m else {"version": "", "path": ""}
            self.cache.set(k, v, max(self.settings.version_ttl_s, 30))
        return v if v["version"] else None

    def store_settings(self, store: dict) -> StoreSettings:
        """Stored settings, overlaid with the merchant dashboard's when it is connected."""
        s = StoreSettings(**store["settings"])
        if not self.settings.dashboard_url:
            return s
        k = f"dash:{store['store_id']}"
        d = self.cache.get(k)
        if d is None:
            d = fetch_dashboard_settings(self.settings, store["store_id"])
            self.cache.set(k, d or {}, 30)
        return apply_dashboard_settings(s, d) if d else s

    def top_sellers(self, store_id: str, cv: int, days: int) -> list:
        k = f"pop:{store_id}:{cv}:{days}"
        v = self.cache.get(k)
        if v is None:
            v = db.top_sellers(self.engine, store_id, days)
            self.cache.set(k, v, 3600)
        return [tuple(x) for x in v]


def fetch_dashboard_settings(settings: Settings, store_id: str) -> dict | None:
    import httpx

    h = {"Authorization": f"Bearer {settings.dashboard_token}"} if settings.dashboard_token else {}
    try:
        r = httpx.get(f"{settings.dashboard_url.rstrip('/')}/api/stores/{store_id}/settings", headers=h, timeout=1.0)
        return r.json() if r.status_code == 200 else None
    except Exception as e:  # noqa: BLE001 - dashboard down: keep serving stored settings
        log.warning("dashboard settings unavailable for %s: %s", store_id, e)
        return None


def apply_dashboard_settings(s: StoreSettings, d: dict) -> StoreSettings:
    """Map the dashboard contract (docs/DASHBOARD.md) onto StoreSettings.

    control = pure relevance (lam 0); treatment = the dashboard's lam. Both keep
    the margin floor, so the floor is never part of what is being tested.
    """
    new = s.model_dump()
    for f in ("margin_floor", "max_addons", "lam", "overstock_weight"):
        if d.get(f) is not None:
            new[f] = d[f]
    if "allow_discounts" in d:
        new["discounts"] = [0.0, 0.1, 0.2] if d["allow_discounts"] else [0.0]
    items = d.get("items") or {}
    new["excluded_items"] = sorted(set(new["excluded_items"]) | {i for i, r in items.items() if r and r.get("excluded")})
    share = d.get("treatment_share")
    if share is not None:
        share = min(max(float(share), 0.0), 1.0)
        variants = []
        if share < 1:
            variants.append({"name": "control", "weight": 1 - share, "overrides": {"lam": 0.0}})
        if share > 0:
            variants.append({"name": "treatment", "weight": share, "overrides": {"lam": new["lam"]}})
        new["experiment"] = {"enabled": True, "name": "dashboard", "variants": variants}
    try:
        return StoreSettings(**new)
    except ValidationError as e:
        log.warning("ignoring invalid dashboard settings: %s", e)
        return s


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.admin_key == DEV_ADMIN_KEY:
        log.warning("using the development admin key; set MARGINGRAPH_ADMIN_KEY before going live")
    svc = Service(settings)
    app = FastAPI(
        title="MarginGraph",
        version=__version__,
        description="Margin-aware checkout add-on recommendations for retail stores.",
    )
    app.state.svc = svc
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    @app.on_event("startup")
    def preload() -> None:
        # load active models in the background so the first checkout isn't a cold start
        def job():
            for st in db.list_stores(svc.engine)[: settings.max_loaded_models]:
                m = svc.model_info(st["store_id"])
                if m:
                    try:
                        svc.registry.get(st["store_id"], m["version"], m["path"])
                    except Exception:  # noqa: BLE001
                        log.exception("preload failed for %s", st["store_id"])

        if settings.preload_models:
            threading.Thread(target=job, daemon=True).start()

    @app.middleware("http")
    async def count_requests(request: Request, call_next):
        t0 = time.perf_counter()
        try:
            resp = await call_next(request)
        except Exception:
            METRICS.inc("margingraph_http_requests_total", path=request.url.path, status=500)
            raise
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        METRICS.inc("margingraph_http_requests_total", path=path, status=resp.status_code)
        resp.headers["X-Response-Time-ms"] = f"{1000 * (time.perf_counter() - t0):.1f}"
        return resp

    # ---- auth -----------------------------------------------------------
    def store_auth(
        x_api_key: str | None = Header(None),
        authorization: str | None = Header(None),
    ) -> dict:
        key = x_api_key or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None)
        if not key:
            raise HTTPException(401, "missing API key (X-API-Key header)")
        store = svc.store_for_key(key)
        if store is None:
            raise HTTPException(401, "invalid API key")
        s = StoreSettings(**store["settings"])
        if s.rate_limit_per_minute:
            n = svc.cache.incr(f"rl:{store['store_id']}:{int(time.time() // 60)}", 60)
            if n > s.rate_limit_per_minute:
                METRICS.inc("margingraph_rate_limited_total", store=store["store_id"])
                raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": "60"})
        return store

    def admin_auth(x_admin_key: str | None = Header(None)) -> None:
        if not x_admin_key or not hmac.compare_digest(x_admin_key, settings.admin_key):
            raise HTTPException(401, "invalid admin key (X-Admin-Key header)")

    # ---- ops --------------------------------------------------------------
    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"ok": True, "version": __version__}

    @app.get("/ready", tags=["ops"])
    def ready() -> JSONResponse:
        checks: dict[str, Any] = {"cache": svc.cache.backend, "cache_ok": svc.cache.ping()}
        try:
            with svc.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            checks["database_ok"] = True
        except Exception as e:  # noqa: BLE001
            checks["database_ok"] = False
            checks["database_error"] = str(e)[:200]
        checks["database"] = svc.engine.dialect.name
        checks["models_loaded"] = [f"{s}:{v}" for s, v in svc.registry.loaded()]
        ok = checks["database_ok"] and checks["cache_ok"]
        return JSONResponse({"ok": ok, **checks}, status_code=200 if ok else 503)

    @app.get("/metrics", tags=["ops"], response_class=PlainTextResponse)
    def metrics() -> str:
        return METRICS.render(
            {"margingraph_uptime_seconds": round(time.time() - svc.started, 1), "margingraph_models_loaded": len(svc.registry.loaded())}
        )

    # ---- admin ------------------------------------------------------------
    @app.post("/v1/admin/stores", tags=["admin"], response_model=StoreCreated, status_code=201, dependencies=[Depends(admin_auth)])
    def create_store(body: StoreCreate) -> dict:
        if db.get_store(svc.engine, body.store_id):
            raise HTTPException(409, "store exists")
        key, secret = "mg_" + secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        db.create_store(svc.engine, body.store_id, body.name, hash_key(key), secret, body.settings.model_dump())
        return {"store_id": body.store_id, "api_key": key, "webhook_secret": secret}

    @app.get("/v1/admin/stores", tags=["admin"], dependencies=[Depends(admin_auth)])
    def list_stores() -> list[dict]:
        out = []
        for s in db.list_stores(svc.engine):
            m = db.active_model(svc.engine, s["store_id"])
            out.append(
                {
                    "store_id": s["store_id"],
                    "name": s["name"],
                    "catalog_version": s["catalog_version"],
                    "products": db.count_rows(svc.engine, db.products, s["store_id"]),
                    "orders": db.count_rows(svc.engine, db.orders, s["store_id"]),
                    "active_model": m["version"] if m else None,
                }
            )
        return out

    @app.post("/v1/admin/stores/{store_id}/rotate-key", tags=["admin"], response_model=StoreCreated, dependencies=[Depends(admin_auth)])
    def rotate_key(store_id: str) -> dict:
        if not db.get_store(svc.engine, store_id):
            raise HTTPException(404, "unknown store")
        key, secret = "mg_" + secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        db.update_store(svc.engine, store_id, api_key_hash=hash_key(key), webhook_secret=secret)
        svc.forget_store(store_id)
        return {"store_id": store_id, "api_key": key, "webhook_secret": secret}

    @app.post("/v1/admin/stores/{store_id}/train", tags=["admin"], status_code=202, dependencies=[Depends(admin_auth)])
    def train(store_id: str, background: BackgroundTasks) -> dict:
        """Run the batch job inside this process (handy on a single free instance).

        For bigger stores prefer ``margingraph batch`` on a schedule, so the
        training memory peak never sits next to live traffic.
        """
        if not db.get_store(svc.engine, store_id):
            raise HTTPException(404, "unknown store")
        if not svc._train_lock.acquire(blocking=False):
            raise HTTPException(409, "a training job is already running in this instance")

        def job():
            from ..cli import load_config
            from .train import train_store

            try:
                train_store(svc.engine, store_id, load_config(settings.config_path), settings.artifacts_dir)
                svc.cache.delete(f"mv:{store_id}")
            except Exception:  # noqa: BLE001
                log.exception("training failed for %s", store_id)
            finally:
                svc._train_lock.release()

        background.add_task(job)
        return {"accepted": True, "store_id": store_id}

    # ---- store settings ---------------------------------------------------
    @app.get("/v1/settings", tags=["store"])
    def get_store_settings(store: dict = Depends(store_auth)) -> dict:
        out = {"store_id": store["store_id"], "name": store["name"], "settings": StoreSettings(**store["settings"]).model_dump()}
        if settings.dashboard_url:
            out["effective"] = svc.store_settings(store).model_dump()  # after the dashboard overlay
        return out

    @app.patch("/v1/settings", tags=["store"])
    def patch_settings(patch: dict, store: dict = Depends(store_auth)) -> dict:
        merged = {**StoreSettings(**store["settings"]).model_dump(), **patch}
        try:
            new = StoreSettings(**merged)
            for v in new.experiment.variants:  # validate overrides now, not at request time
                new.for_variant(v.name)
        except (ValidationError, ValueError) as e:
            raise HTTPException(422, str(e)) from e
        db.update_store(svc.engine, store["store_id"], settings=new.model_dump())
        svc.forget_store(store["store_id"])
        return {"store_id": store["store_id"], "settings": new.model_dump()}

    # ---- catalog and inventory --------------------------------------------
    @app.post("/v1/catalog", tags=["catalog"])
    def upsert_catalog(body: CatalogUpsert, store: dict = Depends(store_auth)) -> dict:
        n = db.upsert_products(svc.engine, store["store_id"], [p.model_dump(exclude_unset=True) for p in body.products])
        return {"upserted": n, "catalog_version": svc.bump_catalog(store["store_id"])}

    @app.post("/v1/catalog/csv", tags=["catalog"])
    async def upsert_catalog_csv(request: Request, store: dict = Depends(store_auth)) -> dict:
        """CSV body with header item,price[,unit_cost,stock,description,category,overstock,active]."""
        raw = await request.body()
        try:
            df = pd.read_csv(io.BytesIO(raw), dtype={"item": str})
            body = CatalogUpsert(products=[{k: v for k, v in r.items() if pd.notna(v)} for r in df.to_dict("records")])
        except (ValidationError, ValueError, KeyError) as e:
            raise HTTPException(422, f"bad catalog csv: {e}") from e
        return upsert_catalog(body, store)

    @app.get("/v1/catalog/{item}", tags=["catalog"])
    def get_product(item: str, store: dict = Depends(store_auth)) -> dict:
        p = db.load_products(svc.engine, store["store_id"])
        r = p[p["item"] == item.strip().upper()]
        if r.empty:
            raise HTTPException(404, "unknown item")
        d = r.iloc[0].to_dict()
        d["updated_at"] = str(d["updated_at"])
        return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in d.items()}

    @app.post("/v1/inventory", tags=["catalog"])
    def inventory(body: InventoryUpdate, store: dict = Depends(store_auth)) -> dict:
        res = db.set_stock(svc.engine, store["store_id"], [c.model_dump() for c in body.changes])
        res["catalog_version"] = svc.bump_catalog(store["store_id"])
        return res

    # ---- recommend --------------------------------------------------------
    @app.post("/v1/recommend", tags=["recommend"], response_model=RecommendResponse)
    async def recommend(req: RecommendRequest, background: BackgroundTasks, store: dict = Depends(store_auth)) -> dict:
        t0 = time.perf_counter()
        sid = store["store_id"]
        rid = uuid.uuid4().hex
        base = svc.store_settings(store)
        variant = assign_variant(base, sid, req.customer_id or req.session_id or rid)
        s = base.for_variant(variant)
        basket = req.items()
        exclude = {e.strip().upper() for e in req.exclude} | {e.strip().upper() for e in s.excluded_items}
        cv = svc.catalog_version(sid)
        m = svc.model_info(sid)
        mv = m["version"] if m else ""
        key = cache_key(sid, cv, mv, variant, basket, req.customer_id, req.max_addons, exclude)

        source, reason, addons, known = "model", "", None, []
        hit = svc.cache.get(key)
        if hit is not None:
            source, addons, known = "cache", hit["addons"], hit["known"]
        elif m is None:
            reason = "no_model"
        else:

            def run():
                bundle = svc.registry.get(sid, mv, m["path"])
                snap = svc.snapshots.snapshot(svc.engine, sid, cv, mv, bundle.generator.index.items)
                return model_recommend(bundle, snap, basket, req.customer_id, s, req.max_addons, exclude)

            try:
                addons, known = await asyncio.wait_for(asyncio.to_thread(run), s.latency_budget_ms / 1000)
                if not known:
                    reason, addons = "unknown_basket", None
                elif not addons:
                    reason, addons = "no_eligible_candidates", None
                else:
                    svc.cache.set(key, {"addons": addons, "known": known}, settings.response_cache_ttl_s)
            except asyncio.TimeoutError:
                reason = "timeout"
            except Exception:  # noqa: BLE001 - the shop page must never break
                log.exception("model path failed for store %s", sid)
                reason = "error"
                METRICS.inc("margingraph_model_errors_total", store=sid)

        if addons is None:
            source = "fallback"
            snap = _catalog_only(svc, sid, cv)
            addons = fallback_recommend(svc.top_sellers(sid, cv, s.fallback_days), snap, basket, s, req.max_addons, exclude)
            known = [b for b in basket if b in snap.pos]

        latency = round(1000 * (time.perf_counter() - t0), 2)
        METRICS.inc("margingraph_recommendations_total", store=sid, source=source, variant=variant)
        if reason:
            METRICS.inc("margingraph_fallbacks_total", store=sid, reason=reason)
        METRICS.observe_ms(latency, source=source)
        exp_profit = sum(a["expected_profit"] or 0.0 for a in addons)
        if settings.log_requests:
            background.add_task(
                _log_rec,
                svc,
                {
                    "request_id": rid,
                    "store_id": sid,
                    "ts": db.utcnow(),
                    "customer_id": req.customer_id,
                    "session_id": req.session_id,
                    "variant": variant,
                    "source": source,
                    "model_version": mv,
                    "basket": basket,
                    "addons": [{k: a[k] for k in ("item", "price", "discount", "margin_pct", "p_accept")} for a in addons],
                    "expected_profit": exp_profit,
                    "latency_ms": latency,
                },
            )
        return {
            "request_id": rid,
            "store_id": sid,
            "variant": variant,
            "source": source,
            "model_version": mv,
            "addons": addons,
            "basket_known": known,
            "basket_unknown": [b for b in basket if b not in set(known)],
            "latency_ms": latency,
            "fallback_reason": reason,
        }

    # ---- orders, feedback and reporting -----------------------------------
    def _ingest_order(store: dict, order: Order) -> dict:
        sid = store["store_id"]
        s = StoreSettings(**store["settings"])
        ts = (order.ts.replace(tzinfo=None) if order.ts else db.utcnow())
        head = {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "session_id": order.session_id,
            "recommendation_id": order.recommendation_id,
            "ts": ts,
        }
        lines = [{"item": l.item.strip().upper(), "quantity": l.quantity, "price": l.price} for l in order.lines]
        if not db.insert_order(svc.engine, sid, head, lines):
            return {"order_id": order.order_id, "duplicate": True, "attributed": 0}
        if order.decrement_stock:
            qty: dict[str, int] = {}
            for l in lines:
                qty[l["item"]] = qty.get(l["item"], 0) + int(round(l["quantity"]))
            db.set_stock(svc.engine, sid, [{"item": i, "delta": -q} for i, q in qty.items()])
            svc.bump_catalog(sid)

        # attribution: the given recommendation, else the latest ones shown to
        # this customer/session within the window before the order
        if order.recommendation_id:
            r = db.get_recommendation(svc.engine, sid, order.recommendation_id)
            recs = [r] if r else []
        else:
            recs = db.recent_recommendations(
                svc.engine, sid, order.customer_id, order.session_id, ts - timedelta(hours=s.attribution_hours), ts
            )
        cost = db.unit_costs(svc.engine, sid, [l["item"] for l in lines]) if recs else {}
        events, done = [], set()
        for r in recs:  # newest first, one credit per item
            shown = {a["item"] for a in r["addons"]}
            for l in lines:
                if l["item"] in shown and l["item"] not in done:
                    c = cost.get(l["item"])
                    c = 0.0 if c is None or pd.isna(c) else float(c)
                    events.append(
                        {
                            "store_id": sid,
                            "request_id": r["request_id"],
                            "item": l["item"],
                            "event_type": "purchase",
                            "quantity": l["quantity"],
                            "revenue": l["quantity"] * l["price"],
                            "profit": l["quantity"] * (l["price"] - c),
                            "order_id": order.order_id,
                            # never before the slate was shown (replayed orders carry old timestamps)
                            "ts": max(ts, r["ts"]) if isinstance(r["ts"], type(ts)) else ts,
                        }
                    )
                    done.add(l["item"])
        db.add_rec_events(svc.engine, events)
        METRICS.inc("margingraph_orders_total", store=sid)
        METRICS.inc("margingraph_attributed_addons_total", len(events), store=sid)
        return {"order_id": order.order_id, "duplicate": False, "attributed": len(events)}

    @app.post("/v1/orders", tags=["orders"])
    def post_order(order: Order, store: dict = Depends(store_auth)) -> dict:
        return _ingest_order(store, order)

    @app.post("/v1/webhooks/{store_id}/orders", tags=["orders"])
    async def order_webhook(store_id: str, request: Request, x_margingraph_signature: str | None = Header(None)) -> dict:
        """Signed webhook: X-MarginGraph-Signature = hex HMAC-SHA256(webhook_secret, raw body)."""
        store = db.get_store(svc.engine, store_id)
        raw = await request.body()
        if store is None or not x_margingraph_signature:
            raise HTTPException(401, "unknown store or missing signature")
        want = hmac.new(store["webhook_secret"].encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, x_margingraph_signature.strip().lower()):
            raise HTTPException(401, "bad signature")
        try:
            order = Order.model_validate_json(raw)
        except ValidationError as e:
            raise HTTPException(422, str(e)) from e
        return _ingest_order(store, order)

    @app.post("/v1/orders/import", tags=["orders"])
    async def import_orders(request: Request, store: dict = Depends(store_auth)) -> dict:
        """Bulk history import, CSV body: order_id,item,quantity,price,ts[,customer_id].

        Used once when a store joins, so the first model has history to learn
        from. It does not touch stock or attribution.
        """
        raw = await request.body()
        try:
            df = pd.read_csv(io.BytesIO(raw), dtype={"order_id": str, "item": str, "customer_id": str})
            need = {"order_id", "item", "quantity", "price", "ts"}
            if need - set(df.columns):
                raise ValueError(f"missing columns {sorted(need - set(df.columns))}")
            df = df[(df["quantity"] > 0) & (df["price"] >= 0)]
        except (ValueError, KeyError) as e:
            raise HTTPException(422, f"bad orders csv: {e}") from e
        n = db.bulk_import_lines(svc.engine, store["store_id"], df)
        svc.bump_catalog(store["store_id"])
        return {"imported_lines": n}

    @app.post("/v1/events", tags=["orders"])
    def feedback(ev: FeedbackEvent, store: dict = Depends(store_auth)) -> dict:
        r = db.get_recommendation(svc.engine, store["store_id"], ev.request_id)
        if r is None:
            raise HTTPException(404, "unknown request_id")
        db.add_rec_events(
            svc.engine,
            [{"store_id": store["store_id"], "request_id": ev.request_id, "item": ev.item.strip().upper(), "event_type": ev.event_type, "ts": db.utcnow()}],
        )
        return {"ok": True}

    @app.get("/v1/report", tags=["orders"])
    def get_report(days: int = Query(30, ge=1, le=365), store: dict = Depends(store_auth)) -> dict:
        rep = db.report(svc.engine, store["store_id"], db.utcnow() - timedelta(days=days))
        return {"store_id": store["store_id"], "days": days, "variants": rep.to_dict("records")}

    @app.get("/v1/models", tags=["models"])
    def models(store: dict = Depends(store_auth)) -> list[dict]:
        return [
            {"version": m["version"], "status": m["status"], "created_at": str(m["created_at"]), "metrics": m["metrics"].get("metrics", {})}
            for m in db.list_models(svc.engine, store["store_id"])
        ]

    @app.post("/v1/models/{version}/activate", tags=["models"])
    def activate(version: str, store: dict = Depends(store_auth)) -> dict:
        """Roll back (or forward) to any trained version."""
        if version not in {m["version"] for m in db.list_models(svc.engine, store["store_id"])}:
            raise HTTPException(404, "unknown version")
        db.set_model_status(svc.engine, store["store_id"], version, "active")
        svc.cache.delete(f"mv:{store['store_id']}")
        return {"active": version}

    return app


def _catalog_only(svc: Service, store_id: str, cv: int):
    """Snapshot of the whole catalog (no model index), for the fallback path."""
    return svc.snapshots.snapshot(svc.engine, store_id, cv, "#catalog", None)


def _log_rec(svc: Service, row: dict) -> None:
    try:
        db.log_recommendation(svc.engine, row)
        # one impression per shown add-on, so event-level tools (the dashboard) see slates
        db.add_rec_events(
            svc.engine,
            [
                {"store_id": row["store_id"], "request_id": row["request_id"], "item": a["item"], "event_type": "impression",
                 "quantity": 0.0, "revenue": 0.0, "profit": 0.0, "order_id": "", "ts": row["ts"]}
                for a in row["addons"]
            ],
        )
    except Exception:  # noqa: BLE001 - logging must not fail the request
        log.exception("could not log recommendation")


def __getattr__(name: str):
    # `uvicorn margingraph.service.app:app` builds the app lazily from env settings
    if name == "app":
        return create_app()
    raise AttributeError(name)
