"""Release gate: the reranker must beat the popularity baseline on test.

Reads the CSVs that ``margingraph run`` writes (E3 baselines, E5 rerank) and
fails when LightGBM Hit@K on the test split is below popularity Hit@K. With
``strict`` the lower end of the ranker's 95% CI must clear popularity's mean.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def check(results_dir: str | Path, metric: str = "hit@10", ranker: str = "lightgbm", strict: bool = False) -> dict:
    d = Path(results_dir)
    e3 = pd.read_csv(d / "e3_baselines.csv")
    e5 = pd.read_csv(d / "e5_rerank.csv")
    base = e3[(e3.model == "popularity") & (e3.metric == metric) & (e3.split == "test")]
    rank = e5[(e5.model == ranker) & (e5.metric == metric)]
    if base.empty or rank.empty:
        raise ValueError(f"missing {metric} rows for popularity (E3 test) or {ranker} (E5)")
    b, r = base.iloc[0], rank.iloc[0]
    score = float(r.ci_low if strict else r["mean"])
    return {
        "metric": metric,
        "ranker": ranker,
        "ranker_mean": float(r["mean"]),
        "ranker_ci_low": float(r.ci_low),
        "popularity_mean": float(b["mean"]),
        "strict": strict,
        "passed": score >= float(b["mean"]),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="margingraph-gate", description=__doc__)
    ap.add_argument("results", nargs="?", default="results")
    ap.add_argument("--metric", default="hit@10")
    ap.add_argument("--strict", action="store_true", help="compare the CI lower bound, not the mean")
    args = ap.parse_args(argv)
    out = check(args.results, args.metric, strict=args.strict)
    print(json.dumps(out, indent=2))
    if not out["passed"]:
        print(f"GATE FAILED: {out['ranker']} {args.metric} is below popularity", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
