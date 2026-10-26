"""Command line entry point: ``margingraph {prepare,run,serve}``."""
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


if __name__ == "__main__":
    main()
