"""Small server-side SVG charts (no JS chart library, nothing to download).

Colors are CSS custom properties defined in the page, so light/dark mode
swap in one place. Hover tooltips use native SVG <title> plus enlarged
invisible hit targets.
"""
from __future__ import annotations

from html import escape

import pandas as pd

SERIES = {"control": "var(--series-1)", "treatment": "var(--series-2)"}


def _ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi <= lo:
        return [lo]
    step = (hi - lo) / n
    return [lo + i * step for i in range(n + 1)]


def line_chart(daily: pd.DataFrame, value: str, money: str = "£", width: int = 720, height: int = 240) -> str:
    """One line per variant over days. Direct labels at the line ends plus a legend."""
    if daily.empty:
        return '<p class="muted">No events in this period.</p>'
    days = sorted(daily["day"].unique())
    pad_l, pad_r, pad_t, pad_b = 56, 96, 12, 28
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    ymax = float(daily[value].max()) * 1.1 or 1.0
    x = {d: pad_l + (iw * i / max(1, len(days) - 1)) for i, d in enumerate(days)}

    def y(v: float) -> float:
        return pad_t + ih - ih * v / ymax

    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{escape(value)} by day">']
    for t in _ticks(0, ymax):
        out.append(f'<line x1="{pad_l}" x2="{pad_l + iw}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 6}" y="{y(t) + 4:.1f}" class="axis" text-anchor="end">{money}{t:.2f}</text>')
    for i, d in enumerate(days):
        if i % max(1, len(days) // 6) == 0 or i == len(days) - 1:
            out.append(f'<text x="{x[d]:.1f}" y="{height - 8}" class="axis" text-anchor="middle">{d[5:]}</text>')
    for var in ("control", "treatment"):
        s = daily[daily["variant"] == var].sort_values("day")
        if s.empty:
            continue
        pts = " ".join(f"{x[r.day]:.1f},{y(getattr(r, value)):.1f}" for r in s.itertuples())
        out.append(f'<polyline points="{pts}" fill="none" stroke="{SERIES[var]}" stroke-width="2" '
                   'stroke-linejoin="round" stroke-linecap="round"/>')
        for r in s.itertuples():
            v = getattr(r, value)
            out.append(f'<g class="pt"><circle cx="{x[r.day]:.1f}" cy="{y(v):.1f}" r="9" fill="transparent"/>'
                       f'<circle cx="{x[r.day]:.1f}" cy="{y(v):.1f}" r="2.5" fill="{SERIES[var]}"/>'
                       f'<title>{r.day} · {var}: {money}{v:.3f} per request ({r.requests} requests)</title></g>')
        last = s.iloc[-1]
        out.append(f'<text x="{x[last.day] + 8:.1f}" y="{y(last[value]) + 4:.1f}" class="label">{var}</text>')
    out.append("</svg>")
    return "".join(out)


def forest(rows: list[dict], width: int = 720) -> str:
    """Relative uplift (treatment vs control) with 95% CI per metric, zero line in the middle."""
    rows = [r for r in rows if r["control"] > 0]
    if not rows:
        return '<p class="muted">Not enough data for an A/B comparison yet.</p>'
    row_h, pad_l, pad_r, pad_t = 34, 250, 110, 22
    height = pad_t + row_h * len(rows) + 24
    lim = max(0.05, max(max(abs(r["rel_lo"]), abs(r["rel_hi"])) for r in rows)) * 1.1
    iw = width - pad_l - pad_r

    def x(v: float) -> float:
        return pad_l + iw * (v + lim) / (2 * lim)

    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="A/B uplift with 95% CIs">']
    for t in (-lim, -lim / 2, 0, lim / 2, lim):
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{pad_t - 6}" y2="{height - 22}" '
                   f'class="{"zero" if t == 0 else "grid"}"/>')
        out.append(f'<text x="{x(t):.1f}" y="{height - 6}" class="axis" text-anchor="middle">{t:+.0%}</text>')
    for i, r in enumerate(rows):
        cy = pad_t + row_h * i + row_h / 2
        sig = r["rel_lo"] > 0 or r["rel_hi"] < 0
        color = "var(--good)" if r["rel_lo"] > 0 else "var(--bad)" if r["rel_hi"] < 0 else "var(--text-muted)"
        out.append(f'<text x="{pad_l - 12}" y="{cy + 4:.1f}" class="label" text-anchor="end">{escape(r["label"])}</text>')
        out.append(f'<g class="pt"><rect x="{pad_l}" y="{cy - row_h / 2:.1f}" width="{iw}" height="{row_h}" fill="transparent"/>'
                   f'<line x1="{x(max(-lim, r["rel_lo"])):.1f}" x2="{x(min(lim, r["rel_hi"])):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" '
                   f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
                   f'<circle cx="{x(max(-lim, min(lim, r["rel"]))):.1f}" cy="{cy:.1f}" r="5" fill="{color}" '
                   'stroke="var(--surface)" stroke-width="2"/>'
                   f'<title>{escape(r["label"])}: {r["rel"]:+.1%} (95% CI {r["rel_lo"]:+.1%} to {r["rel_hi"]:+.1%}), '
                   f'p={r["p"]:.3f}</title></g>')
        out.append(f'<text x="{width - pad_r + 10}" y="{cy + 4:.1f}" class="value">{r["rel"]:+.1%}{" ✓" if sig else ""}</text>')
    out.append("</svg>")
    return "".join(out)
