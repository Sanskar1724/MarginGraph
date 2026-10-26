"""Storage for stores, catalog, stock, orders, request logs and model versions.

SQLAlchemy Core keeps one code path for SQLite (default, zero setup) and
Postgres (set DATABASE_URL=postgresql+psycopg://...). JSON fields are stored as
text so both backends behave the same.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    func,
    select,
    update,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

stores = Table(
    "stores",
    metadata,
    Column("store_id", String(64), primary_key=True),
    Column("name", String(200), nullable=False, default=""),
    Column("api_key_hash", String(64), nullable=False, unique=True),
    Column("webhook_secret", String(128), nullable=False, default=""),
    Column("settings", Text, nullable=False, default="{}"),
    Column("catalog_version", Integer, nullable=False, default=1),
    Column("created_at", DateTime, nullable=False),
)

products = Table(
    "products",
    metadata,
    Column("store_id", String(64), primary_key=True),
    Column("item", String(64), primary_key=True),
    Column("description", Text, nullable=False, default=""),
    Column("category", String(100), nullable=False, default=""),
    Column("price", Float, nullable=False),
    Column("unit_cost", Float, nullable=True),  # NULL = unknown margin, never recommended
    Column("stock", Integer, nullable=False, default=0),
    Column("overstock", Boolean, nullable=False, default=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("updated_at", DateTime, nullable=False),
)

orders = Table(
    "orders",
    metadata,
    Column("store_id", String(64), primary_key=True),
    Column("order_id", String(128), primary_key=True),
    Column("customer_id", String(128), nullable=False, default=""),
    Column("session_id", String(128), nullable=False, default=""),
    Column("recommendation_id", String(64), nullable=False, default=""),
    Column("ts", DateTime, nullable=False),
)

order_lines = Table(
    "order_lines",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("store_id", String(64), nullable=False),
    Column("order_id", String(128), nullable=False),
    Column("item", String(64), nullable=False),
    Column("quantity", Float, nullable=False),
    Column("price", Float, nullable=False),
    Column("customer_id", String(128), nullable=False, default=""),
    Column("ts", DateTime, nullable=False),
    Index("ix_order_lines_store_ts", "store_id", "ts"),
)

recommendations = Table(
    "recommendations",
    metadata,
    Column("request_id", String(64), primary_key=True),
    Column("store_id", String(64), nullable=False),
    Column("ts", DateTime, nullable=False),
    Column("customer_id", String(128), nullable=False, default=""),
    Column("session_id", String(128), nullable=False, default=""),
    Column("variant", String(64), nullable=False, default=""),
    Column("source", String(32), nullable=False),
    Column("model_version", String(64), nullable=False, default=""),
    Column("basket", Text, nullable=False),
    Column("addons", Text, nullable=False),
    Column("expected_profit", Float, nullable=False, default=0.0),
    Column("latency_ms", Float, nullable=False),
    Index("ix_recs_store_ts", "store_id", "ts"),
    Index("ix_recs_store_customer", "store_id", "customer_id"),
    Index("ix_recs_store_session", "store_id", "session_id"),
)

rec_events = Table(
    "rec_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("store_id", String(64), nullable=False),
    Column("request_id", String(64), nullable=False),
    Column("item", String(64), nullable=False),
    Column("event_type", String(32), nullable=False),  # click | add_to_cart | purchase
    Column("quantity", Float, nullable=False, default=0.0),
    Column("revenue", Float, nullable=False, default=0.0),
    Column("profit", Float, nullable=False, default=0.0),
    Column("order_id", String(128), nullable=False, default=""),
    Column("ts", DateTime, nullable=False),
    Index("ix_rec_events_request", "request_id"),
    Index("ix_rec_events_store_ts", "store_id", "ts"),
)

models = Table(
    "models",
    metadata,
    Column("store_id", String(64), primary_key=True),
    Column("version", String(64), primary_key=True),
    Column("created_at", DateTime, nullable=False),
    Column("status", String(16), nullable=False),  # active | rejected | archived
    Column("path", Text, nullable=False),
    Column("metrics", Text, nullable=False, default="{}"),
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    kw: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False, "timeout": 30}
    eng = create_engine(url, **kw)
    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _pragmas(conn, _):  # WAL lets the API read while the batch job writes
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

    return eng


# Event view in the shape the merchant dashboard reads (docs/DASHBOARD.md):
# MARGINGRAPH_EVENTS_SQL="SELECT * FROM svc.dashboard_events"
DASHBOARD_VIEW = """
SELECT e.ts AS ts, e.store_id AS store_id, e.request_id AS request_id, r.variant AS variant,
       e.event_type AS event, e.item AS item,
       CASE WHEN e.quantity > 0 THEN e.revenue / e.quantity ELSE p.price END AS price,
       p.unit_cost AS unit_cost, p.overstock AS overstock, e.quantity AS qty, 'live' AS source
FROM rec_events e
JOIN recommendations r ON r.request_id = e.request_id
LEFT JOIN products p ON p.store_id = e.store_id AND p.item = e.item
"""


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql("CREATE OR REPLACE VIEW dashboard_events AS " + DASHBOARD_VIEW)
        else:
            conn.exec_driver_sql("CREATE VIEW IF NOT EXISTS dashboard_events AS " + DASHBOARD_VIEW)


def _upsert(engine: Engine, table: Table, rows: list[dict], keys: list[str], update_cols=None, chunk: int = 2000) -> None:
    """Dialect-aware INSERT ... ON CONFLICT DO UPDATE for SQLite and Postgres.

    ``update_cols`` limits which columns an existing row gets overwritten with,
    so a partial update (say, only ``unit_cost``) keeps the stored stock.
    """
    if not rows:
        return
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    with engine.begin() as conn:
        for s in range(0, len(rows), chunk):
            part = rows[s : s + chunk]
            stmt = insert(table).values(part)
            names = update_cols if update_cols is not None else [c for c in part[0] if c not in keys]
            cols = {c: stmt.excluded[c] for c in names}
            stmt = stmt.on_conflict_do_update(index_elements=keys, set_=cols) if cols else stmt.on_conflict_do_nothing()
            conn.execute(stmt)


# ---- stores --------------------------------------------------------------
def create_store(engine: Engine, store_id: str, name: str, api_key_hash: str, webhook_secret: str, settings: dict) -> None:
    with engine.begin() as conn:
        conn.execute(
            stores.insert().values(
                store_id=store_id,
                name=name,
                api_key_hash=api_key_hash,
                webhook_secret=webhook_secret,
                settings=json.dumps(settings),
                catalog_version=1,
                created_at=utcnow(),
            )
        )


def get_store(engine: Engine, store_id: str) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(select(stores).where(stores.c.store_id == store_id)).mappings().first()
    return _store_row(r)


def get_store_by_key_hash(engine: Engine, key_hash: str) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(select(stores).where(stores.c.api_key_hash == key_hash)).mappings().first()
    return _store_row(r)


def _store_row(r) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["settings"] = json.loads(d["settings"] or "{}")
    return d


def list_stores(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(stores).order_by(stores.c.store_id)).mappings().all()
    return [_store_row(r) for r in rows]


def update_store(engine: Engine, store_id: str, **values) -> None:
    if "settings" in values:
        values["settings"] = json.dumps(values["settings"])
    with engine.begin() as conn:
        conn.execute(update(stores).where(stores.c.store_id == store_id).values(**values))


def bump_catalog_version(engine: Engine, store_id: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            update(stores).where(stores.c.store_id == store_id).values(catalog_version=stores.c.catalog_version + 1)
        )
        return int(conn.execute(select(stores.c.catalog_version).where(stores.c.store_id == store_id)).scalar_one())


def catalog_version(engine: Engine, store_id: str) -> int:
    with engine.connect() as conn:
        v = conn.execute(select(stores.c.catalog_version).where(stores.c.store_id == store_id)).scalar()
    return int(v or 0)


# ---- catalog and stock ---------------------------------------------------
PRODUCT_FIELDS = ("description", "category", "price", "unit_cost", "stock", "overstock", "active")


PRODUCT_DEFAULTS = {"description": "", "category": "", "unit_cost": None, "stock": 0, "overstock": False, "active": True}


def upsert_products(engine: Engine, store_id: str, rows: Iterable[dict]) -> int:
    """Insert new products; for existing ones overwrite only the fields given."""
    now = utcnow()
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        given = tuple(sorted(f for f in PRODUCT_FIELDS if f in r and (r[f] is not None or f == "unit_cost")))
        d = {**PRODUCT_DEFAULTS, **{f: r[f] for f in given}}
        d.update(store_id=store_id, item=str(r["item"]).strip().upper(), updated_at=now)
        if d.get("price") is None:
            # update of an existing product without a price: keep the stored price
            d["price"] = 0.0
            given = tuple(f for f in given if f != "price")
        groups.setdefault(given, []).append(d)
    n = 0
    for given, part in groups.items():
        _upsert(engine, products, part, ["store_id", "item"], update_cols=list(given) + ["updated_at"])
        n += len(part)
    return n


def set_stock(engine: Engine, store_id: str, changes: list[dict]) -> dict:
    """Apply absolute (``stock``) or relative (``delta``) stock changes."""
    now, updated, missing = utcnow(), 0, []
    with engine.begin() as conn:
        for c in changes:
            item = str(c["item"]).strip().upper()
            where = (products.c.store_id == store_id) & (products.c.item == item)
            if c.get("stock") is not None:
                val = int(c["stock"])
            else:
                val = func.max(products.c.stock + int(c["delta"]), 0) if engine.dialect.name == "sqlite" else func.greatest(
                    products.c.stock + int(c["delta"]), 0
                )
            res = conn.execute(update(products).where(where).values(stock=val, updated_at=now))
            if res.rowcount:
                updated += 1
            else:
                missing.append(item)
    return {"updated": updated, "missing": missing}


def load_products(engine: Engine, store_id: str, since: datetime | None = None) -> pd.DataFrame:
    q = select(products).where(products.c.store_id == store_id)
    if since is not None:
        q = q.where(products.c.updated_at >= since)
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    return df


def unit_costs(engine: Engine, store_id: str, items: list[str]) -> dict[str, float | None]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(products.c.item, products.c.unit_cost).where((products.c.store_id == store_id) & products.c.item.in_(items))
        ).all()
    return {r[0]: r[1] for r in rows}


def count_rows(engine: Engine, table: Table, store_id: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table).where(table.c.store_id == store_id)).scalar_one())


# ---- orders --------------------------------------------------------------
def insert_order(engine: Engine, store_id: str, order: dict, lines: list[dict]) -> bool:
    """Insert one order and its lines. Returns False if the order id was already seen."""
    with engine.begin() as conn:
        seen = conn.execute(
            select(orders.c.order_id).where((orders.c.store_id == store_id) & (orders.c.order_id == order["order_id"]))
        ).first()
        if seen:
            return False
        conn.execute(orders.insert().values(store_id=store_id, **order))
        if lines:
            conn.execute(
                order_lines.insert(),
                [{"store_id": store_id, "order_id": order["order_id"], "customer_id": order["customer_id"], "ts": order["ts"], **l} for l in lines],
            )
    return True


def bulk_import_lines(engine: Engine, store_id: str, df: pd.DataFrame, chunk: int = 20000) -> int:
    """Fast historical import (no stock changes, no attribution).

    ``df`` needs order_id, item, quantity, price, ts and optionally customer_id.
    """
    df = df.copy()
    df["store_id"] = store_id
    if "customer_id" not in df:
        df["customer_id"] = ""
    df["customer_id"] = df["customer_id"].fillna("").astype(str)
    df["item"] = df["item"].astype(str).str.strip().str.upper()
    df["order_id"] = df["order_id"].astype(str)
    df["ts"] = pd.to_datetime(df["ts"])
    heads = df.groupby("order_id", sort=False).agg(ts=("ts", "min"), customer_id=("customer_id", "first")).reset_index()
    heads["store_id"] = store_id
    heads["session_id"] = ""
    heads["recommendation_id"] = ""
    with engine.connect() as conn:
        known = set(
            r[0] for r in conn.execute(select(orders.c.order_id).where(orders.c.store_id == store_id))
        )
    heads = heads[~heads["order_id"].isin(known)]
    df = df[df["order_id"].isin(set(heads["order_id"]))]
    cols = ["store_id", "order_id", "item", "quantity", "price", "customer_id", "ts"]
    with engine.begin() as conn:
        for s in range(0, len(heads), chunk):
            conn.execute(orders.insert(), heads.iloc[s : s + chunk].to_dict("records"))
        recs = df[cols]
        for s in range(0, len(recs), chunk):
            conn.execute(order_lines.insert(), recs.iloc[s : s + chunk].to_dict("records"))
    return len(df)


def load_order_lines(engine: Engine, store_id: str, since: datetime | None = None) -> pd.DataFrame:
    q = select(
        order_lines.c.order_id.label("invoice"),
        order_lines.c.item,
        order_lines.c.quantity,
        order_lines.c.price,
        order_lines.c.customer_id.label("customer"),
        order_lines.c.ts,
    ).where(order_lines.c.store_id == store_id)
    if since is not None:
        q = q.where(order_lines.c.ts >= since)
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def top_sellers(engine: Engine, store_id: str, days: int = 90, limit: int = 200) -> list[tuple[str, int]]:
    """Items by number of distinct orders in the last ``days`` of order history."""
    with engine.connect() as conn:
        last = conn.execute(select(func.max(order_lines.c.ts)).where(order_lines.c.store_id == store_id)).scalar()
        if last is None:
            return []
        if isinstance(last, str):
            last = pd.Timestamp(last).to_pydatetime()
        rows = conn.execute(
            select(order_lines.c.item, func.count(func.distinct(order_lines.c.order_id)).label("n"))
            .where((order_lines.c.store_id == store_id) & (order_lines.c.ts >= last - timedelta(days=days)))
            .group_by(order_lines.c.item)
            .order_by(func.count(func.distinct(order_lines.c.order_id)).desc())
            .limit(limit)
        ).all()
    return [(r[0], int(r[1])) for r in rows]


# ---- request log and attribution ------------------------------------------
def log_recommendation(engine: Engine, row: dict) -> None:
    row = {**row, "basket": json.dumps(row["basket"]), "addons": json.dumps(row["addons"])}
    with engine.begin() as conn:
        conn.execute(recommendations.insert().values(**row))


def get_recommendation(engine: Engine, store_id: str, request_id: str) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(
            select(recommendations).where(
                (recommendations.c.store_id == store_id) & (recommendations.c.request_id == request_id)
            )
        ).mappings().first()
    if r is None:
        return None
    d = dict(r)
    d["basket"], d["addons"] = json.loads(d["basket"]), json.loads(d["addons"])
    return d


def recent_recommendations(
    engine: Engine, store_id: str, customer_id: str, session_id: str, since: datetime, until: datetime
) -> list[dict]:
    conds = []
    if customer_id:
        conds.append(recommendations.c.customer_id == customer_id)
    if session_id:
        conds.append(recommendations.c.session_id == session_id)
    if not conds:
        return []
    from sqlalchemy import or_

    with engine.connect() as conn:
        rows = conn.execute(
            select(recommendations)
            .where(
                (recommendations.c.store_id == store_id)
                & (recommendations.c.ts >= since)
                & (recommendations.c.ts <= until)
                & or_(*conds)
            )
            .order_by(recommendations.c.ts.desc())
            .limit(50)
        ).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["addons"] = json.loads(d["addons"])
        out.append(d)
    return out


def add_rec_events(engine: Engine, rows: list[dict]) -> None:
    if rows:
        with engine.begin() as conn:
            conn.execute(rec_events.insert(), rows)


def report(engine: Engine, store_id: str, since: datetime) -> pd.DataFrame:
    """Per-variant A/B summary since ``since``."""
    with engine.connect() as conn:
        recs = pd.read_sql(
            select(
                recommendations.c.request_id,
                recommendations.c.variant,
                recommendations.c.source,
                recommendations.c.addons,
                recommendations.c.expected_profit,
                recommendations.c.latency_ms,
            ).where((recommendations.c.store_id == store_id) & (recommendations.c.ts >= since)),
            conn,
        )
        # events are matched to recommendations in the window (an order's own
        # timestamp can be older than when it reached us, e.g. on replays)
        evs = pd.read_sql(
            select(rec_events)
            .join(recommendations, recommendations.c.request_id == rec_events.c.request_id)
            .where((rec_events.c.store_id == store_id) & (recommendations.c.ts >= since)),
            conn,
        )
    if recs.empty:
        return pd.DataFrame()
    recs["n_addons"] = recs["addons"].map(lambda s: len(json.loads(s)))
    recs["fallback"] = (recs["source"] == "fallback").astype(float)
    g = recs.groupby("variant").agg(
        requests=("request_id", "size"),
        addons_shown=("n_addons", "sum"),
        fallback_share=("fallback", "mean"),
        expected_profit=("expected_profit", "sum"),
        p50_latency_ms=("latency_ms", "median"),
        p95_latency_ms=("latency_ms", lambda s: s.quantile(0.95)),
    )
    if not evs.empty:
        evs = evs.merge(recs[["request_id", "variant"]], on="request_id", how="inner")
        for t in ("click", "add_to_cart", "purchase"):
            e = evs[evs["event_type"] == t]
            g[f"{t}s"] = e.groupby("variant").size()
            if t == "purchase":
                g["purchased_revenue"] = e.groupby("variant")["revenue"].sum()
                g["purchased_profit"] = e.groupby("variant")["profit"].sum()
                g["requests_with_purchase"] = e.groupby("variant")["request_id"].nunique()
    g = g.fillna(0.0)
    for c in ("clicks", "add_to_carts", "purchases", "purchased_revenue", "purchased_profit", "requests_with_purchase"):
        if c not in g:
            g[c] = 0.0
    g["conversion_rate"] = g["requests_with_purchase"] / g["requests"]
    g["profit_per_request"] = g["purchased_profit"] / g["requests"]
    return g.reset_index()


# ---- model registry ------------------------------------------------------
def register_model(engine: Engine, store_id: str, version: str, path: str, status: str, metrics: dict) -> None:
    with engine.begin() as conn:
        if status == "active":
            conn.execute(
                update(models)
                .where((models.c.store_id == store_id) & (models.c.status == "active"))
                .values(status="archived")
            )
        conn.execute(
            models.insert().values(
                store_id=store_id, version=version, path=path, status=status, metrics=json.dumps(metrics), created_at=utcnow()
            )
        )


def active_model(engine: Engine, store_id: str) -> dict | None:
    with engine.connect() as conn:
        r = conn.execute(
            select(models)
            .where((models.c.store_id == store_id) & (models.c.status == "active"))
            .order_by(models.c.created_at.desc())
        ).mappings().first()
    if r is None:
        return None
    d = dict(r)
    d["metrics"] = json.loads(d["metrics"] or "{}")
    return d


def list_models(engine: Engine, store_id: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(models).where(models.c.store_id == store_id).order_by(models.c.created_at.desc())
        ).mappings().all()
    return [{**dict(r), "metrics": json.loads(r["metrics"] or "{}")} for r in rows]


def set_model_status(engine: Engine, store_id: str, version: str, status: str) -> None:
    with engine.begin() as conn:
        if status == "active":
            conn.execute(
                update(models)
                .where((models.c.store_id == store_id) & (models.c.status == "active"))
                .values(status="archived")
            )
        conn.execute(
            update(models).where((models.c.store_id == store_id) & (models.c.version == version)).values(status=status)
        )
