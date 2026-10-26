"""KPIs and A/B statistics from the event log.

Unit of analysis is the recommendation request (one shown slate of add-ons):
a request converts if any shown add-on is bought, and its profit is the sum of
(price - unit_cost) * qty over bought add-ons. Variants are compared with
Welch normal-approximation 95% CIs on per-request means, which is what most
A/B tools report and needs no bootstrap loop (cheap on a laptop).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

Z = 1.959964


def per_request(ev: pd.DataFrame) -> pd.DataFrame:
    """One row per request: variant, day, shown, clicked, bought, revenue, profit, overstock units."""
    if ev.empty:
        return pd.DataFrame(columns=["request_id", "variant", "day", "shown", "clicked", "bought",
                                     "revenue", "profit", "overstock_units"])
    ev = ev.copy()
    buy = ev["event"] == "purchase"
    ev["revenue"] = np.where(buy, ev["price"].fillna(0) * ev["qty"], 0.0)
    ev["profit"] = np.where(buy, (ev["price"].fillna(0) - ev["unit_cost"].fillna(ev["price"])) * ev["qty"], 0.0)
    ev["ov_units"] = np.where(buy & (ev["overstock"] == 1), ev["qty"], 0)
    ev["is_imp"] = (ev["event"] == "impression").astype(int)
    ev["is_click"] = (ev["event"] == "click").astype(int)
    ev["is_buy"] = buy.astype(int)
    g = ev.groupby("request_id")
    out = pd.DataFrame({
        "variant": g["variant"].first(),
        "day": g["ts"].min().dt.strftime("%Y-%m-%d"),
        "shown": g["is_imp"].sum(),
        "clicked": (g["is_click"].sum() > 0).astype(int),
        "bought": (g["is_buy"].sum() > 0).astype(int),
        "revenue": g["revenue"].sum(),
        "profit": g["profit"].sum(),
        "overstock_units": g["ov_units"].sum(),
    }).reset_index()
    return out


def summary(req: pd.DataFrame) -> dict:
    n = len(req)
    rev, prof = float(req["revenue"].sum()), float(req["profit"].sum())
    return {
        "requests": n,
        "impressions": int(req["shown"].sum()),
        "clicks": int(req["clicked"].sum()),
        "purchases": int(req["bought"].sum()),
        "ctr": float(req["clicked"].mean()) if n else 0.0,
        "conversion": float(req["bought"].mean()) if n else 0.0,
        "revenue": rev,
        "profit": prof,
        "margin": prof / rev if rev > 0 else 0.0,
        "profit_per_request": prof / n if n else 0.0,
        "overstock_units": int(req["overstock_units"].sum()),
    }


def _welch(a: np.ndarray, b: np.ndarray) -> dict:
    """Difference mean(b) - mean(a), its 95% CI, two-sided p, and relative uplift with delta-method CI."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"control": float(a.mean()) if na else 0.0, "treatment": float(b.mean()) if nb else 0.0,
                "diff": 0.0, "lo": 0.0, "hi": 0.0, "p": 1.0, "rel": 0.0, "rel_lo": 0.0, "rel_hi": 0.0}
    ma, mb = a.mean(), b.mean()
    va, vb = a.var(ddof=1) / na, b.var(ddof=1) / nb
    se = math.sqrt(va + vb)
    d = mb - ma
    p = math.erfc(abs(d) / se / math.sqrt(2)) if se > 0 else (1.0 if d == 0 else 0.0)
    rel = rel_lo = rel_hi = 0.0
    if ma > 0:
        rel = mb / ma - 1
        se_rel = math.sqrt(vb / ma**2 + mb**2 * va / ma**4)
        rel_lo, rel_hi = rel - Z * se_rel, rel + Z * se_rel
    return {"control": float(ma), "treatment": float(mb), "diff": float(d), "lo": float(d - Z * se),
            "hi": float(d + Z * se), "p": float(p), "rel": float(rel), "rel_lo": float(rel_lo), "rel_hi": float(rel_hi)}


def srm_p(n_control: int, n_treatment: int, treatment_share: float) -> float:
    """Chi-square (1 df) p-value for sample ratio mismatch against the configured split."""
    n = n_control + n_treatment
    if n == 0 or not 0 < treatment_share < 1:
        return 1.0
    ec, et = n * (1 - treatment_share), n * treatment_share
    chi = (n_control - ec) ** 2 / ec + (n_treatment - et) ** 2 / et
    return float(math.erfc(math.sqrt(chi / 2)))


def mde(p: float, n_per_arm: int) -> float:
    """Minimum detectable absolute change in a rate at 95% confidence, 80% power."""
    if n_per_arm <= 0:
        return float("nan")
    return (Z + 0.841621) * math.sqrt(2 * p * (1 - p) / n_per_arm)


AB_METRICS = [
    ("profit", "Add-on profit per request", "money"),
    ("revenue", "Add-on revenue per request", "money"),
    ("bought", "Conversion (any add-on bought)", "pct"),
    ("clicked", "Click-through (any add-on clicked)", "pct"),
    ("overstock_units", "Overstock units per request", "num"),
]


def ab_test(req: pd.DataFrame, treatment_share: float = 0.5) -> dict:
    c = req[req["variant"] == "control"]
    t = req[req["variant"] == "treatment"]
    rows = []
    for col, label, fmt in AB_METRICS:
        r = _welch(c[col].to_numpy(float), t[col].to_numpy(float))
        r.update(metric=col, label=label, fmt=fmt)
        rows.append(r)
    cm = summary(c)["margin"] if len(c) else 0.0
    tm = summary(t)["margin"] if len(t) else 0.0
    conv = float(req["bought"].mean()) if len(req) else 0.0
    return {
        "n_control": len(c), "n_treatment": len(t),
        "rows": rows,
        "margin_control": cm, "margin_treatment": tm,
        "srm_p": srm_p(len(c), len(t), treatment_share),
        "mde_conversion": mde(conv, min(len(c), len(t))),
    }


def daily(req: pd.DataFrame) -> pd.DataFrame:
    if req.empty:
        return pd.DataFrame(columns=["day", "variant", "requests", "profit", "profit_per_request"])
    d = req.groupby(["day", "variant"]).agg(requests=("request_id", "size"), profit=("profit", "sum")).reset_index()
    d["profit_per_request"] = d["profit"] / d["requests"]
    return d


def top_items(ev: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    b = ev[ev["event"] == "purchase"].copy()
    if b.empty:
        return pd.DataFrame(columns=["item", "units", "revenue", "profit", "overstock"])
    b["revenue"] = b["price"] * b["qty"]
    b["profit"] = (b["price"] - b["unit_cost"].fillna(b["price"])) * b["qty"]
    out = b.groupby("item").agg(units=("qty", "sum"), revenue=("revenue", "sum"), profit=("profit", "sum"),
                                overstock=("overstock", "max")).reset_index()
    return out.sort_values("profit", ascending=False).head(n)


def policy_preview(catalog: pd.DataFrame, settings, rules: dict) -> dict:
    """What the current settings do to the catalog: how many items are eligible to be offered."""
    if catalog.empty:
        return {"items": 0, "below_floor": 0, "excluded": 0, "out_of_stock": 0, "eligible": 0, "overstock": 0}
    m = (catalog["price"] - catalog["unit_cost"]) / catalog["price"]
    below = m < settings.margin_floor - 1e-9
    excl = catalog["item"].isin([k for k, v in rules.items() if v["excluded"]])
    oos = catalog["stock"].fillna(1) <= 0
    return {
        "items": int(len(catalog)),
        "below_floor": int(below.sum()),
        "excluded": int(excl.sum()),
        "out_of_stock": int(oos.sum()),
        "eligible": int((~below & ~excl & ~oos).sum()),
        "overstock": int(catalog["overstock"].astype(bool).sum()),
    }
