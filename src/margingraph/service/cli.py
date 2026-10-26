"""Service commands: ``margingraph {api,init-db,create-store,import-catalog,import-orders,import-sync,bootstrap-demo,batch,scheduler}``."""
from __future__ import annotations

import argparse
import json
import logging
import secrets
import time

import pandas as pd


def add_parsers(sub) -> None:
    a = sub.add_parser("api", help="start the production API")
    a.add_argument("--host", default="0.0.0.0")
    a.add_argument("--port", type=int, default=8000)
    a.add_argument("--workers", type=int, default=1)
    sub.add_parser("init-db", help="create database tables")
    c = sub.add_parser("create-store", help="create a store and print its API key")
    c.add_argument("store_id")
    c.add_argument("--name", default="")
    c.add_argument("--settings", default="{}", help="JSON of StoreSettings fields")
    ic = sub.add_parser("import-catalog", help="CSV: item,price,unit_cost,stock[,description,category,overstock,active]")
    ic.add_argument("store_id")
    ic.add_argument("csv")
    io_ = sub.add_parser("import-orders", help="CSV: order_id,item,quantity,price,ts[,customer_id]")
    io_.add_argument("store_id")
    io_.add_argument("csv")
    sy = sub.add_parser("import-sync", help="load a `margingraph sync` output folder into a store")
    sy.add_argument("store_id")
    sy.add_argument("--folder", default="data/store")
    sy.add_argument("--create", action="store_true", help="create the store first and print its key")
    d = sub.add_parser("bootstrap-demo", help="load Online Retail II as a demo store and train it")
    d.add_argument("--store", default="demo")
    d.add_argument("--country", default="", help="only this country's orders (e.g. 'United Kingdom')")
    d.add_argument("--exclude-country", default="", help="all countries except this one")
    d.add_argument("--replay-days", type=int, default=14, help="hold back the last N days to replay as live traffic")
    d.add_argument("--no-train", action="store_true")
    b = sub.add_parser("batch", help="nightly job: retrain every store (or --store)")
    b.add_argument("--store", action="append")
    b.add_argument("--force", action="store_true", help="activate even if the quality gate fails")
    sc = sub.add_parser("scheduler", help="run the batch job every day at --hour (UTC)")
    sc.add_argument("--hour", type=int, default=3)


def _engine():
    from . import db
    from .settings import get_settings

    eng = db.make_engine(get_settings().database_url)
    db.init_db(eng)
    return eng


def create_store(eng, store_id: str, name: str, settings: dict) -> dict:
    from . import db
    from .app import hash_key
    from .schemas import StoreSettings

    key, secret = "mg_" + secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    db.create_store(eng, store_id, name, hash_key(key), secret, StoreSettings(**settings).model_dump())
    return {"store_id": store_id, "api_key": key, "webhook_secret": secret}


def bootstrap_demo(eng, cfg: dict, store: str, country: str, exclude_country: str, replay_days: int, train: bool) -> dict:
    """Online Retail II as a store. Cost and stock are SIMULATED (the dataset has neither)."""
    from .. import data
    from . import db

    lines, catalog, _ = data.load_or_build(cfg)
    if country:
        lines = lines[lines["country"] == country]
    if exclude_country:
        lines = lines[lines["country"] != exclude_country]
    cutoff = lines["ts"].max() - pd.Timedelta(days=replay_days)
    hist, replay = lines[lines["ts"] < cutoff], lines[lines["ts"] >= cutoff]
    cat = catalog[catalog["item"].isin(set(lines["item"]))].reset_index(drop=True)
    erp = data.simulate_erp(hist, cat, cfg, cfg["seed"])
    prods = cat.merge(erp[["item", "unit_cost", "stock", "overstock"]], on="item")
    out = {"store_id": store, "products": len(prods), "history_lines": len(hist), "replay_lines": len(replay), "cutoff": str(cutoff)}
    if db.get_store(eng, store) is None:
        out.update(create_store(eng, store, f"Online Retail II demo {country or 'all'}", {}))
    db.upsert_products(
        eng,
        store,
        [
            {"item": r.item, "description": r.description, "category": r.category, "price": float(r.price),
             "unit_cost": float(r.unit_cost), "stock": int(r.stock), "overstock": bool(r.overstock), "active": True}
            for r in prods.itertuples()
        ],
    )
    h = hist.rename(columns={"invoice": "order_id", "customer": "customer_id"})[["order_id", "item", "quantity", "price", "ts", "customer_id"]]
    t0 = time.time()
    out["imported_lines"] = db.bulk_import_lines(eng, store, h)
    out["import_seconds"] = round(time.time() - t0, 1)
    db.bump_catalog_version(eng, store)
    rp = replay.rename(columns={"invoice": "order_id", "customer": "customer_id"})[["order_id", "item", "quantity", "price", "ts", "customer_id"]]
    out["replay_csv"] = f"data/replay_{store}.csv"
    rp.to_csv(out["replay_csv"], index=False)
    if train:
        from .settings import get_settings
        from .train import train_store

        meta = train_store(eng, store, cfg, get_settings().artifacts_dir)
        out["model"] = {k: meta[k] for k in ("version", "status", "bundle_mb", "train_seconds", "peak_rss_mb")}
        out["model"]["metrics"] = {k: meta["metrics"][k] for k in ("lightgbm", "best_baseline", "gate", "pool_recall", "n_holdout_events")}
        out["model"]["best_baseline_metrics"] = meta["metrics"][meta["metrics"]["best_baseline"]]
    return out


def import_sync(eng, store_id: str, folder: str) -> dict:
    """Catalog, cost, stock and order history from a connector folder (docs/CONNECTORS.md).

    Items whose cost the store did not provide keep unit_cost NULL, so the
    service never recommends them: the margin floor cannot be checked.
    """
    from pathlib import Path

    from . import db

    p = Path(folder) / "pipeline"
    lines, cat, erp = (pd.read_parquet(p / f) for f in ("lines.parquet", "catalog.parquet", "erp.parquet"))
    prods = cat.merge(erp, on="item", how="left")
    rows = []
    for r in prods.itertuples():
        rows.append({
            "item": r.item, "description": r.description, "category": r.category, "price": float(r.price),
            "unit_cost": None if pd.isna(r.unit_cost) else float(r.unit_cost),
            "stock": 0 if pd.isna(r.stock) else int(r.stock), "active": True,
        })
    db.upsert_products(eng, store_id, rows)
    h = lines.rename(columns={"invoice": "order_id", "customer": "customer_id"})[["order_id", "item", "quantity", "price", "ts", "customer_id"]]
    n = db.bulk_import_lines(eng, store_id, h)
    db.bump_catalog_version(eng, store_id)
    return {"products": len(rows), "products_with_cost": int(prods["unit_cost"].notna().sum()), "imported_lines": n}


def run(args, cfg: dict) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from . import db
    from .settings import get_settings

    st = get_settings()
    if args.cmd == "api":
        import uvicorn

        uvicorn.run("margingraph.service.app:app", host=args.host, port=args.port, workers=args.workers)
        return
    eng = _engine()
    if args.cmd == "init-db":
        print(json.dumps({"ok": True, "database": eng.dialect.name}))
    elif args.cmd == "create-store":
        print(json.dumps(create_store(eng, args.store_id, args.name, json.loads(args.settings)), indent=2))
    elif args.cmd == "import-catalog":
        df = pd.read_csv(args.csv, dtype={"item": str})
        rows = [{k: v for k, v in r.items() if pd.notna(v)} for r in df.to_dict("records")]
        n = db.upsert_products(eng, args.store_id, rows)
        db.bump_catalog_version(eng, args.store_id)
        print(json.dumps({"upserted": n}))
    elif args.cmd == "import-orders":
        df = pd.read_csv(args.csv, dtype={"order_id": str, "item": str, "customer_id": str})
        print(json.dumps({"imported_lines": db.bulk_import_lines(eng, args.store_id, df)}))
    elif args.cmd == "import-sync":
        out = create_store(eng, args.store_id, args.store_id, {}) if args.create else {}
        out.update(import_sync(eng, args.store_id, args.folder))
        print(json.dumps(out, indent=2))
    elif args.cmd == "bootstrap-demo":
        out = bootstrap_demo(eng, cfg, args.store, args.country, args.exclude_country, args.replay_days, not args.no_train)
        print(json.dumps(out, indent=2, default=str))
    elif args.cmd == "batch":
        from .train import nightly, train_store

        if args.force and args.store:
            res = [train_store(eng, s, cfg, st.artifacts_dir, force=True)["status"] for s in args.store]
        else:
            res = nightly(eng, cfg, st.artifacts_dir, args.store)
        print(json.dumps(res, indent=2, default=str))
    elif args.cmd == "scheduler":
        from .train import nightly

        last = None
        logging.getLogger("margingraph").info("scheduler: daily batch at %02d:00 UTC", args.hour)
        while True:
            now = time.gmtime()
            if now.tm_hour == args.hour and last != now.tm_yday:
                last = now.tm_yday
                logging.getLogger("margingraph").info("nightly: %s", nightly(eng, cfg, st.artifacts_dir))
            time.sleep(60)
