"""Load and latency test for POST /recommend. Standard library only.

Sends N requests at a fixed concurrency to a running server and reports
client-side p50/p95/p99, throughput and error rate, plus the server's own
``latency_ms`` (model + solver time, no HTTP). Baskets are sampled from the
catalog in the model bundle so every request exercises the full path.

    margingraph serve --artifacts artifacts &
    python scripts/loadtest.py --artifacts artifacts -n 2000 -c 8 --out loadtest.json

``--max-p95-ms`` makes it exit 1 when client p95 is above the budget (CI).
"""
from __future__ import annotations

import argparse
import json
import pickle
import platform
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np


def pct(xs: list[float], q: float) -> float:
    return float(np.percentile(xs, q)) if xs else float("nan")


def sample_baskets(artifacts: str, n: int, seed: int) -> list[list[str]]:
    with open(Path(artifacts) / "bundle.pkl", "rb") as fh:
        items = list(pickle.load(fh)["generator"].index.items)
    rng = np.random.default_rng(seed)
    return [list(rng.choice(items, size=int(rng.integers(1, 5)), replace=False)) for _ in range(n)]


def call(url: str, basket: list[str], timeout: float) -> tuple[float, int, float | None]:
    body = json.dumps({"basket": basket}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read())
            return 1000 * (time.perf_counter() - t0), r.status, out.get("latency_ms")
    except urllib.error.HTTPError as e:
        return 1000 * (time.perf_counter() - t0), e.code, None
    except Exception:
        return 1000 * (time.perf_counter() - t0), 0, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("-n", "--requests", type=int, default=1000)
    ap.add_argument("-c", "--concurrency", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-p95-ms", type=float, default=None)
    ap.add_argument("--max-error-rate", type=float, default=0.0)
    ap.add_argument("--out", default=None, help="write the JSON report here")
    args = ap.parse_args(argv)

    url = args.url.rstrip("/") + "/recommend"
    baskets = sample_baskets(args.artifacts, args.requests + args.warmup, args.seed)
    for b in baskets[: args.warmup]:
        call(url, b, args.timeout)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as ex:
        res = list(ex.map(lambda b: call(url, b, args.timeout), baskets[args.warmup :]))
    wall = time.perf_counter() - t0

    ok = [r for r in res if r[1] == 200]
    lat = [r[0] for r in ok]
    srv = [r[2] for r in ok if r[2] is not None]
    report = {
        "requests": len(res),
        "concurrency": args.concurrency,
        "ok": len(ok),
        "status_counts": {str(s): sum(r[1] == s for r in res) for s in sorted({r[1] for r in res})},
        "error_rate": round(1 - len(ok) / len(res), 4),
        "throughput_rps": round(len(res) / wall, 1),
        "client_ms": {k: round(pct(lat, q), 1) for k, q in (("p50", 50), ("p95", 95), ("p99", 99))}
        | {"mean": round(statistics.fmean(lat), 1) if lat else None, "max": round(max(lat), 1) if lat else None},
        "server_ms": {k: round(pct(srv, q), 1) for k, q in (("p50", 50), ("p95", 95), ("p99", 99))},
        "machine": {"python": platform.python_version(), "cpu": platform.processor() or platform.machine()},
    }
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n")

    failed = report["error_rate"] > args.max_error_rate
    if args.max_p95_ms is not None and report["client_ms"]["p95"] > args.max_p95_ms:
        failed = True
    if failed:
        print("LOAD TEST FAILED: error rate or p95 over budget", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
