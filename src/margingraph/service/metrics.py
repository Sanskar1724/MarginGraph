"""Prometheus text-format metrics without extra dependencies.

Counters live per process; Prometheus (or Grafana Cloud's free tier) scrapes
each instance's /metrics and sums them.
"""
from __future__ import annotations

import threading
from collections import defaultdict

BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[tuple[str, tuple], float] = defaultdict(float)
        self.hist: dict[tuple, list[float]] = {}
        self.hist_sum: dict[tuple, float] = defaultdict(float)
        self.hist_n: dict[tuple, int] = defaultdict(int)

    def inc(self, name: str, value: float = 1.0, **labels) -> None:
        with self._lock:
            self.counters[(name, tuple(sorted(labels.items())))] += value

    def observe_ms(self, ms: float, **labels) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            b = self.hist.setdefault(key, [0.0] * (len(BUCKETS_MS) + 1))
            for i, edge in enumerate(BUCKETS_MS):
                if ms <= edge:
                    b[i] += 1
            b[-1] += 1
            self.hist_sum[key] += ms
            self.hist_n[key] += 1

    @staticmethod
    def _fmt(labels: tuple) -> str:
        if not labels:
            return ""
        inner = ",".join(f'{k}="{str(v)}"' for k, v in labels)
        return "{" + inner + "}"

    def render(self, gauges: dict[str, float] | None = None) -> str:
        out: list[str] = []
        with self._lock:
            names = sorted({n for n, _ in self.counters})
            for n in names:
                out.append(f"# TYPE {n} counter")
                for (m, labels), v in sorted(self.counters.items()):
                    if m == n:
                        out.append(f"{n}{self._fmt(labels)} {v}")
            if self.hist:
                n = "margingraph_recommend_latency_ms"
                out.append(f"# TYPE {n} histogram")
                for key, b in sorted(self.hist.items()):
                    for i, edge in enumerate(BUCKETS_MS):
                        out.append(f"{n}_bucket{self._fmt(key + (('le', edge),))} {b[i]}")
                    out.append(f"{n}_bucket{self._fmt(key + (('le', '+Inf'),))} {b[-1]}")
                    out.append(f"{n}_sum{self._fmt(key)} {self.hist_sum[key]}")
                    out.append(f"{n}_count{self._fmt(key)} {self.hist_n[key]}")
        for g, v in (gauges or {}).items():
            out.append(f"# TYPE {g} gauge")
            out.append(f"{g} {v}")
        return "\n".join(out) + "\n"


METRICS = Metrics()
