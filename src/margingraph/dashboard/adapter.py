"""Thin adapter between whatever logs the events and the KPI code.

The KPI code only needs a DataFrame with these columns::

    ts, store_id, request_id, variant, event, item, price, unit_cost, overstock, qty, source

By default they come from the dashboard's own ``events`` table. If the
recommendation service logs to a different table or database, point the
dashboard at it without touching the KPI code:

* ``MARGINGRAPH_EVENTS_DB``  - path to the service's SQLite file (ATTACHed as ``svc``)
* ``MARGINGRAPH_EVENTS_SQL`` - a SELECT returning the columns above, e.g.
  ``SELECT created_at AS ts, store AS store_id, ... FROM svc.request_log``

Rows missing ``price``, ``unit_cost`` or ``overstock`` are filled from the
store's ``catalog`` table.
"""
from __future__ import annotations

import os

import pandas as pd

COLUMNS = ["ts", "store_id", "request_id", "variant", "event", "item", "price", "unit_cost", "overstock", "qty", "source"]
DEFAULT_SQL = f"SELECT {', '.join(COLUMNS)} FROM events"


def attach_service_db(con) -> None:
    path = os.environ.get("MARGINGRAPH_EVENTS_DB")
    if path and not any(r[1] == "svc" for r in con.execute("PRAGMA database_list")):
        con.execute("ATTACH DATABASE ? AS svc", (path,))


def load_events(con, store_id: str, start: str | None = None, end: str | None = None,
                sql: str | None = None) -> pd.DataFrame:
    """Events for one store with ts in [start, end) (ISO dates or timestamps)."""
    attach_service_db(con)
    base = sql or os.environ.get("MARGINGRAPH_EVENTS_SQL") or DEFAULT_SQL
    q = f"SELECT * FROM ({base}) WHERE store_id = ?"
    args: list = [store_id]
    if start:
        q += " AND ts >= ?"
        args.append(start)
    if end:
        q += " AND ts < ?"
        args.append(end)
    df = pd.read_sql_query(q, con, params=args)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"event source is missing columns {missing}; see dashboard/adapter.py")
    df = df[COLUMNS].copy()
    cat = pd.read_sql_query("SELECT item, price AS c_price, unit_cost AS c_cost, overstock AS c_over "
                            "FROM catalog WHERE store_id = ?", con, params=[store_id])
    if len(cat) and len(df):
        df["item"] = df["item"].astype(str).str.upper()
        df = df.merge(cat, on="item", how="left")
        df["price"] = df["price"].fillna(df["c_price"])
        df["unit_cost"] = df["unit_cost"].fillna(df["c_cost"])
        df["overstock"] = df["overstock"].fillna(df["c_over"])
        df = df.drop(columns=["c_price", "c_cost", "c_over"])
    df["overstock"] = df["overstock"].fillna(0).astype(int)
    df["qty"] = df["qty"].fillna(1).astype(int)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    return df


def load_catalog(con, store_id: str) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM catalog WHERE store_id = ? ORDER BY item", con, params=[store_id])
