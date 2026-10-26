"""SQLite storage for the dashboard: settings, item rules, catalog and events.

Everything lives in one file (default ``margingraph.db``) so a store can run
the dashboard on a laptop. The recommendation service reads settings through
``get_settings`` (or ``GET /api/stores/{id}/settings``) and logs impressions,
clicks and purchases into ``events``. ``adapter.py`` maps other log tables in.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    store_id          TEXT PRIMARY KEY,
    margin_floor      REAL NOT NULL,
    max_addons        INTEGER NOT NULL,
    lam               REAL NOT NULL,
    overstock_weight  REAL NOT NULL,
    allow_discounts   INTEGER NOT NULL,
    treatment_share   REAL NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_rules (
    store_id          TEXT NOT NULL,
    item              TEXT NOT NULL,
    excluded          INTEGER NOT NULL DEFAULT 0,
    overstock_weight  REAL,
    PRIMARY KEY (store_id, item)
);
CREATE TABLE IF NOT EXISTS settings_history (
    ts       TEXT NOT NULL,
    store_id TEXT NOT NULL,
    field    TEXT NOT NULL,
    old      TEXT,
    new      TEXT
);
CREATE TABLE IF NOT EXISTS catalog (
    store_id    TEXT NOT NULL,
    item        TEXT NOT NULL,
    description TEXT,
    price       REAL NOT NULL,
    unit_cost   REAL,
    stock       INTEGER,
    overstock   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (store_id, item)
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    store_id    TEXT NOT NULL,
    request_id  TEXT NOT NULL,
    variant     TEXT NOT NULL,          -- 'control' | 'treatment'
    event       TEXT NOT NULL,          -- 'impression' | 'click' | 'purchase'
    item        TEXT NOT NULL,
    price       REAL,                   -- price actually charged (after discount)
    unit_cost   REAL,
    overstock   INTEGER,                -- NULL = look up in catalog
    qty         INTEGER NOT NULL DEFAULT 1,
    source      TEXT NOT NULL DEFAULT 'live'   -- 'live' | 'sample'
);
CREATE INDEX IF NOT EXISTS events_store_ts ON events (store_id, ts);
"""

EVENT_TYPES = ("impression", "click", "purchase")
VARIANTS = ("control", "treatment")


@dataclass
class Settings:
    """Per-store policy. Defaults are the plan's: 15% floor, max 2 add-ons."""

    margin_floor: float = 0.15
    max_addons: int = 2
    lam: float = 0.5
    overstock_weight: float = 1.5
    allow_discounts: bool = False
    treatment_share: float = 0.5   # share of traffic that gets the MILP policy

    def validate(self) -> list[str]:
        err = []
        if not 0.0 <= self.margin_floor <= 0.9:
            err.append("margin floor must be between 0% and 90%")
        if not 1 <= self.max_addons <= 5:
            err.append("max add-ons must be between 1 and 5")
        if not 0.0 <= self.lam <= 1.0:
            err.append("profit weight (lambda) must be between 0 and 1")
        if not 1.0 <= self.overstock_weight <= 2.0:
            err.append("overstock weight must be between 1.0 and 2.0")
        if not 0.0 <= self.treatment_share <= 1.0:
            err.append("treatment share must be between 0% and 100%")
        return err


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def stores(con) -> list[str]:
    rows = con.execute(
        "SELECT store_id FROM settings UNION SELECT store_id FROM catalog "
        "UNION SELECT DISTINCT store_id FROM events ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows]


def get_settings(con, store_id: str) -> Settings:
    r = con.execute("SELECT * FROM settings WHERE store_id = ?", (store_id,)).fetchone()
    if r is None:
        return Settings()
    return Settings(**{f.name: (bool(r[f.name]) if f.type in (bool, "bool") else r[f.name]) for f in fields(Settings)})


def save_settings(con, store_id: str, s: Settings) -> list[str]:
    """Validate, write, and record every changed field in settings_history."""
    err = s.validate()
    if err:
        return err
    old = asdict(get_settings(con, store_id))
    ts = now()
    with con:
        for k, v in asdict(s).items():
            if old[k] != v:
                con.execute(
                    "INSERT INTO settings_history VALUES (?,?,?,?,?)", (ts, store_id, k, str(old[k]), str(v))
                )
        cols = [f.name for f in fields(Settings)]
        con.execute(
            f"INSERT OR REPLACE INTO settings (store_id, {', '.join(cols)}, updated_at) "
            f"VALUES (?, {', '.join('?' * len(cols))}, ?)",
            (store_id, *[int(v) if isinstance(v, bool) else v for v in asdict(s).values()], ts),
        )
    return []


def item_rules(con, store_id: str) -> dict[str, dict]:
    rows = con.execute("SELECT * FROM item_rules WHERE store_id = ?", (store_id,)).fetchall()
    return {r["item"]: {"excluded": bool(r["excluded"]), "overstock_weight": r["overstock_weight"]} for r in rows}


def set_item_rule(con, store_id: str, item: str, excluded: bool | None = None, overstock_weight: float | None = None,
                  clear_weight: bool = False) -> list[str]:
    item = item.strip().upper()
    if not item:
        return ["item code is empty"]
    if overstock_weight is not None and not 1.0 <= overstock_weight <= 2.0:
        return ["overstock weight must be between 1.0 and 2.0"]
    cur = item_rules(con, store_id).get(item, {"excluded": False, "overstock_weight": None})
    new = dict(cur)
    if excluded is not None:
        new["excluded"] = bool(excluded)
    if overstock_weight is not None:
        new["overstock_weight"] = float(overstock_weight)
    if clear_weight:
        new["overstock_weight"] = None
    ts = now()
    with con:
        for k in ("excluded", "overstock_weight"):
            if cur[k] != new[k]:
                con.execute("INSERT INTO settings_history VALUES (?,?,?,?,?)",
                            (ts, store_id, f"item:{item}:{k}", str(cur[k]), str(new[k])))
        if not new["excluded"] and new["overstock_weight"] is None:
            con.execute("DELETE FROM item_rules WHERE store_id = ? AND item = ?", (store_id, item))
        else:
            con.execute("INSERT OR REPLACE INTO item_rules VALUES (?,?,?,?)",
                        (store_id, item, int(new["excluded"]), new["overstock_weight"]))
    return []


def history(con, store_id: str, limit: int = 50) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM settings_history WHERE store_id = ? ORDER BY ts DESC, rowid DESC LIMIT ?", (store_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def insert_events(con, rows: list[dict]) -> int:
    cols = ("ts", "store_id", "request_id", "variant", "event", "item", "price", "unit_cost", "overstock", "qty", "source")
    data = []
    for r in rows:
        if r.get("event") not in EVENT_TYPES:
            raise ValueError(f"event must be one of {EVENT_TYPES}")
        if r.get("variant") not in VARIANTS:
            raise ValueError(f"variant must be one of {VARIANTS}")
        data.append((r.get("ts") or now(), r["store_id"], r["request_id"], r["variant"], r["event"],
                     str(r["item"]).upper(), r.get("price"), r.get("unit_cost"),
                     None if r.get("overstock") is None else int(bool(r["overstock"])),
                     int(r.get("qty", 1)), r.get("source", "live")))
    with con:
        con.executemany(f"INSERT INTO events ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", data)
    return len(data)


CATALOG_COLUMNS = ("item", "description", "price", "unit_cost", "stock", "overstock")


def import_catalog(con, store_id: str, df) -> int:
    """Replace a store's catalog from a DataFrame with CATALOG_COLUMNS (description/stock/overstock optional)."""
    df = df.rename(columns=str.lower)
    for need in ("item", "price"):
        if need not in df.columns:
            raise ValueError(f"catalog needs an '{need}' column")
    for opt in ("description", "unit_cost", "stock", "overstock"):
        if opt not in df.columns:
            df[opt] = None
    rows = []
    for r in df.itertuples():
        if r.price is None or not float(r.price) > 0:
            continue
        rows.append((store_id, str(r.item).strip().upper(),
                     r.description if isinstance(r.description, str) else None, float(r.price),
                     None if r.unit_cost is None or r.unit_cost != r.unit_cost else float(r.unit_cost),
                     None if r.stock is None or r.stock != r.stock else int(r.stock),
                     int(str(r.overstock).strip().lower() in ("1", "true", "yes"))))
    with con:
        con.execute("DELETE FROM catalog WHERE store_id = ?", (store_id,))
        con.executemany("INSERT INTO catalog VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)
