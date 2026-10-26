"""Sample size for the pilot A/B test (two arms, 50/50, two-sided test).

Conversion (did the shopper buy a shown add-on):
    python scripts/ab_sample_size.py conversion --base 0.03 --rel-mde 0.10 --daily 400

Profit per visitor (continuous; take mean and sd from the store's own
pre-period data, e.g. profit of add-on lines per checkout over 4 weeks):
    python scripts/ab_sample_size.py profit --mean 0.20 --sd 1.5 --rel-mde 0.10 --daily 400
    python scripts/ab_sample_size.py profit --csv per_visitor_profit.csv --column profit --rel-mde 0.10 --daily 400

`--daily` is checkouts (or visitors) per day across both arms. The answer
is per arm; the test needs twice that in total. Round the length up to whole
weeks so every weekday is covered equally, and decide it before starting.
"""
from __future__ import annotations

import argparse
import math

from scipy.stats import norm


def n_conversion(base: float, rel_mde: float, alpha: float = 0.05, power: float = 0.8) -> int:
    p1, p2 = base, base * (1 + rel_mde)
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return math.ceil(z**2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2)


def n_mean(sd: float, delta: float, alpha: float = 0.05, power: float = 0.8) -> int:
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return math.ceil(2 * z**2 * sd**2 / delta**2)


def report(n: int, daily: float | None) -> None:
    print(f"per arm: {n:,}   total: {2 * n:,}")
    if daily:
        days = 2 * n / daily
        weeks = max(2, math.ceil(days / 7))
        print(f"at {daily:,.0f}/day: {days:,.1f} days -> run {weeks} full weeks")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.8)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("conversion")
    c.add_argument("--base", type=float, required=True, help="control conversion rate, e.g. 0.03")
    c.add_argument("--rel-mde", type=float, required=True, help="smallest relative change worth detecting, e.g. 0.10")
    c.add_argument("--daily", type=float)
    p = sub.add_parser("profit")
    p.add_argument("--mean", type=float)
    p.add_argument("--sd", type=float)
    p.add_argument("--csv", help="one row per visitor/checkout from the pre-period")
    p.add_argument("--column", default="profit")
    p.add_argument("--rel-mde", type=float, required=True)
    p.add_argument("--daily", type=float)
    a = ap.parse_args()
    if a.cmd == "conversion":
        report(n_conversion(a.base, a.rel_mde, a.alpha, a.power), a.daily)
        return
    if a.csv:
        import pandas as pd

        x = pd.read_csv(a.csv)[a.column].astype(float)
        a.mean, a.sd = float(x.mean()), float(x.std())
        print(f"from {a.csv}: n={len(x):,} mean={a.mean:.4f} sd={a.sd:.4f} (sd/mean={a.sd / a.mean:.1f})")
    if a.mean is None or a.sd is None:
        ap.error("profit needs --mean and --sd, or --csv")
    report(n_mean(a.sd, a.mean * a.rel_mde, a.alpha, a.power), a.daily)


if __name__ == "__main__":
    main()
