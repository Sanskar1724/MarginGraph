"""Replay held-back real orders through a running MarginGraph API.

For each order (in time order) one product is hidden, the rest is sent to
/v1/recommend as the checkout basket, then the full real order is posted to
/v1/orders with the recommendation id. An add-on "converts" only when it is
the product the customer really bought, so the A/B report measures real
behaviour; profit still uses the store's (here simulated) unit costs.

    python scripts/replay.py --url http://localhost:8000 --key mg_... --csv data/replay_demo.csv
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

import httpx
import numpy as np
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--key", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--max-orders", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    df = pd.read_csv(args.csv, dtype={"order_id": str, "item": str, "customer_id": str}, parse_dates=["ts"])
    df["customer_id"] = df["customer_id"].fillna("")
    orders = [g for _, g in sorted(df.groupby("order_id"), key=lambda kv: kv[1]["ts"].min())]
    orders = [g for g in orders if 2 <= len(g) <= 50][: args.max_orders]
    h = {"X-API-Key": args.key}
    lat, client_lat, sources, hits = [], [], {}, {}
    with httpx.Client(base_url=args.url, headers=h, timeout=10) as c:
        t_start = time.time()
        for g in orders:
            items = g["item"].tolist()
            k = int(rng.integers(len(items)))
            basket = items[:k] + items[k + 1 :]
            cust = str(g["customer_id"].iloc[0])
            t0 = time.perf_counter()
            r = c.post("/v1/recommend", json={"basket": basket, "customer_id": cust, "session_id": g["order_id"].iloc[0]})
            client_lat.append(1000 * (time.perf_counter() - t0))
            r.raise_for_status()
            rec = r.json()
            lat.append(rec["latency_ms"])
            sources[rec["source"]] = sources.get(rec["source"], 0) + 1
            v = rec["variant"]
            hits.setdefault(v, []).append(any(a["item"] == items[k] for a in rec["addons"]))
            o = {
                "order_id": g["order_id"].iloc[0],
                "customer_id": cust,
                "recommendation_id": rec["request_id"],
                "ts": g["ts"].min().isoformat(),
                "lines": [{"item": i, "quantity": float(q), "price": float(p)} for i, q, p in zip(g["item"], g["quantity"], g["price"], strict=True)],
            }
            c.post("/v1/orders", json=o).raise_for_status()
        wall = time.time() - t_start
        rep = c.get("/v1/report", params={"days": 365}).json()
    q = lambda xs, p: float(np.percentile(xs, p))
    out = {
        "orders_replayed": len(orders),
        "wall_seconds": round(wall, 1),
        "sources": sources,
        "server_latency_ms": {"p50": round(statistics.median(lat), 1), "p95": round(q(lat, 95), 1), "p99": round(q(lat, 99), 1)},
        "client_roundtrip_ms": {"p50": round(statistics.median(client_lat), 1), "p95": round(q(client_lat, 95), 1)},
        "hit_rate_by_variant": {v: round(float(np.mean(x)), 4) for v, x in hits.items()},
        "n_by_variant": {v: len(x) for v, x in hits.items()},
        "report": rep["variants"],
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
