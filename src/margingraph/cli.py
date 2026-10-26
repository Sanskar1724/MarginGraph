"""Command line entry point: ``margingraph {prepare,run,serve,dashboard}``."""
from __future__ import annotations

import argparse
import json
import os

# implicit's ALS is slow with a multi-threaded OpenBLAS pool
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import yaml


def load_config(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="margingraph")
    ap.add_argument("--config", default="configs/default.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare", help="clean the raw xlsx into Parquet")
    r = sub.add_parser("run", help="run E1-E11 and write results/")
    r.add_argument("--results", default="results")
    r.add_argument("--artifacts", default="artifacts")
    s = sub.add_parser("serve", help="start the FastAPI demo")
    s.add_argument("--artifacts", default="artifacts")
    s.add_argument("--port", type=int, default=8000)
    d = sub.add_parser("dashboard", help="start the merchant dashboard")
    d.add_argument("--db", default="margingraph.db")
    d.add_argument("--port", type=int, default=8501)
    d.add_argument("--host", default="127.0.0.1")
    d.add_argument("--sample", action="store_true", help="(re)seed the 'demo' store with sample data first")
    d.add_argument("--catalog", help="CSV (item,price,unit_cost,stock,overstock,description) to load for --store")
    d.add_argument("--store", default="demo")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "prepare":
        from .data import load_or_build

        _, _, log = load_or_build(cfg)
        print(json.dumps(log, indent=2))
    elif args.cmd == "run":
        from .pipeline import run

        run(cfg, args.results, args.artifacts)
    elif args.cmd == "serve":
        import uvicorn

        os.environ["MARGINGRAPH_ARTIFACTS"] = args.artifacts
        uvicorn.run("margingraph.api:app", host="0.0.0.0", port=args.port)
    elif args.cmd == "dashboard":
        import uvicorn

        from .dashboard import db, sample

        os.environ["MARGINGRAPH_DB"] = args.db
        if args.sample:
            print(json.dumps(sample.seed(db.connect(args.db))))
        if args.catalog:
            import pandas as pd

            n = db.import_catalog(db.connect(args.db), args.store, pd.read_csv(args.catalog, dtype={"item": str}))
            print(f"loaded {n} catalog items into store {args.store!r}")
        uvicorn.run("margingraph.dashboard.app:app", host=args.host, port=args.port)

if __name__ == "__main__":
    main()
