"""Command line entry point: ``margingraph {prepare,run,serve,sync}``."""
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
    y = sub.add_parser("sync", help="pull a store's products and orders into a folder `run` can train on")
    y.add_argument("source", choices=["csv", "shopify", "woocommerce"])
    y.add_argument("--out", default="data/store", help="output folder (default data/store)")
    y.add_argument("--full", action="store_true", help="ignore the saved watermark and refetch every order")
    y.add_argument("--orders", help="csv: orders file, one row per order line (.csv/.tsv/.xlsx)")
    y.add_argument("--products", help="csv: optional products file with price/cost/stock/category")
    y.add_argument("--mapping", help="csv: YAML column mapping (see docs/CONNECTORS.md)")
    y.add_argument("--preset", help="csv: built-in mapping, e.g. online_retail_ii or shopify_orders_export")
    y.add_argument("--map", action="append", default=[], metavar="FIELD=COLUMN",
                   help="csv: map one field, e.g. --map order_id=Invoice or --map products.cost='Unit Cost'")
    y.add_argument("--product-id-regex", help="keep only product ids matching this pattern")
    y.add_argument("--min-orders", type=int, default=200, help="warn below this many orders with 2+ products")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "prepare":
        from .data import load_or_build

        _, _, log = load_or_build(cfg)
        print(json.dumps(log, indent=2))
    elif args.cmd == "run":
        from .pipeline import run

        run(cfg, args.results, args.artifacts)
    elif args.cmd == "sync":
        _sync(args, cfg)
    elif args.cmd == "serve":
        import uvicorn

        os.environ["MARGINGRAPH_ARTIFACTS"] = args.artifacts
        uvicorn.run("margingraph.api:app", host="0.0.0.0", port=args.port)


def _sync(args, cfg: dict) -> None:
    import sys

    from . import connectors as c

    regex = args.product_id_regex
    if args.source == "csv":
        if not args.orders:
            sys.exit("sync csv needs --orders FILE")
        mapping = c.load_mapping(args.mapping, args.preset, args.map)
        regex = regex or mapping.get("product_id_regex")
        source = c.load_csv_store(args.orders, args.products, mapping)
    elif args.source == "shopify":
        source = c.ShopifySource.from_env()
    else:
        source = c.WooCommerceSource.from_env()
    try:
        res = c.sync(source, args.out, cfg, full=args.full, product_id_regex=regex, min_orders=args.min_orders)
    except c.SyncError as e:
        print(json.dumps(e.report, indent=2), file=sys.stderr)
        sys.exit(f"sync failed: {e}")
    v = res["clean"].pop("validation")
    for w in v["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    print(json.dumps({**res, "validation_stats": v["stats"]}, indent=2, default=str))
    print(f"\nnext: margingraph --config {res['config']} run", file=sys.stderr)


if __name__ == "__main__":
    main()
