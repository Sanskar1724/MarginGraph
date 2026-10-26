"""Merchant dashboard web app (FastAPI + server-rendered HTML, no JS build).

Run:  margingraph dashboard --db margingraph.db --sample
HTML: /store/{id} (KPIs, A/B), /store/{id}/settings (policy, item rules, history)
JSON: /api/stores/{id}/settings (GET/PUT), /api/stores/{id}/kpis, POST /api/events

Set MARGINGRAPH_DASHBOARD_TOKEN to require it as the HTTP Basic password
(any user name) or as a Bearer token.
"""
from __future__ import annotations

import base64
import hmac
import io
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from html import escape
from urllib.parse import parse_qs, quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import adapter, charts, db, kpis

PERIODS = {"7": 7, "28": 28, "90": 90, "all": None}


@lru_cache(maxsize=1)
def con():
    return db.connect(os.environ.get("MARGINGRAPH_DB", "margingraph.db"))


def auth(request: Request) -> None:
    token = os.environ.get("MARGINGRAPH_DASHBOARD_TOKEN")
    if not token:
        return
    h = request.headers.get("authorization", "")
    given = ""
    if h.lower().startswith("bearer "):
        given = h[7:]
    elif h.lower().startswith("basic "):
        try:
            given = base64.b64decode(h[6:]).decode().split(":", 1)[1]
        except Exception:
            given = ""
    if not hmac.compare_digest(given, token):
        raise HTTPException(401, "unauthorized", headers={"WWW-Authenticate": 'Basic realm="MarginGraph"'})


app = FastAPI(title="MarginGraph merchant dashboard", version="0.1.0", dependencies=[Depends(auth)])


def window(days: str) -> tuple[str | None, str]:
    n = PERIODS.get(days, 28)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = None if n is None else (end - timedelta(days=n + 1)).strftime("%Y-%m-%d")
    return start, end.strftime("%Y-%m-%d")


def compute(store_id: str, days: str = "28") -> dict:
    c = con()
    s = db.get_settings(c, store_id)
    start, end = window(days)
    ev = adapter.load_events(c, store_id, start, end)
    req = kpis.per_request(ev)
    return {
        "store_id": store_id,
        "period_days": days,
        "settings": asdict(s),
        "sample_data": bool(len(ev)) and bool((ev["source"] == "sample").all()),
        "totals": kpis.summary(req),
        "by_variant": {v: kpis.summary(req[req["variant"] == v]) for v in db.VARIANTS},
        "ab": kpis.ab_test(req, s.treatment_share),
        "daily": kpis.daily(req),
        "top_items": kpis.top_items(ev),
    }


# ---------------------------------------------------------------- JSON API

@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/stores")
def api_stores() -> list[str]:
    return db.stores(con())


@app.get("/api/stores/{store_id}/settings")
def api_get_settings(store_id: str) -> dict:
    """What the recommendation service reads before solving: policy plus per-item rules."""
    c = con()
    return {"store_id": store_id, **asdict(db.get_settings(c, store_id)), "items": db.item_rules(c, store_id)}


@app.put("/api/stores/{store_id}/settings")
async def api_put_settings(store_id: str, request: Request) -> dict:
    body = await request.json()
    c = con()
    cur = asdict(db.get_settings(c, store_id))
    unknown = set(body) - set(cur) - {"items", "store_id"}
    if unknown:
        raise HTTPException(422, f"unknown fields: {sorted(unknown)}")
    cur.update({k: v for k, v in body.items() if k in cur})
    try:
        s = db.Settings(**cur)
        s.max_addons = int(s.max_addons)
        s.allow_discounts = bool(s.allow_discounts)
    except (TypeError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    err = db.save_settings(c, store_id, s)
    for item, r in (body.get("items") or {}).items():
        err += db.set_item_rule(c, store_id, item, excluded=r.get("excluded"),
                                overstock_weight=r.get("overstock_weight"),
                                clear_weight="overstock_weight" in r and r["overstock_weight"] is None)
    if err:
        raise HTTPException(422, "; ".join(err))
    return api_get_settings(store_id)


@app.get("/api/stores/{store_id}/kpis")
def api_kpis(store_id: str, days: str = "28") -> dict:
    k = compute(store_id, days)
    k["daily"] = k["daily"].to_dict("records")
    k["top_items"] = k["top_items"].to_dict("records")
    return k


@app.post("/api/events")
async def api_events(request: Request) -> dict:
    """Log impressions/clicks/purchases: a JSON object or a list of them (see db.events)."""
    body = await request.json()
    rows = body if isinstance(body, list) else [body]
    try:
        n = db.insert_events(con(), rows)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, f"bad event: {e}") from e
    return {"inserted": n}


@app.post("/api/stores/{store_id}/catalog")
async def api_catalog(store_id: str, request: Request) -> dict:
    """Replace the store's catalog from CSV text: item,price[,description,unit_cost,stock,overstock]."""
    import pandas as pd

    try:
        df = pd.read_csv(io.StringIO((await request.body()).decode()), dtype={"item": str})
        n = db.import_catalog(con(), store_id, df)
    except (ValueError, pd.errors.ParserError) as e:
        raise HTTPException(422, str(e)) from e
    return {"store_id": store_id, "items": n}


@app.get("/api/stores/{store_id}/events.csv")
def api_events_csv(store_id: str, days: str = "all") -> Response:
    start, end = window(days)
    buf = io.StringIO()
    adapter.load_events(con(), store_id, start, end).to_csv(buf, index=False)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{store_id}_events.csv"'})


# ---------------------------------------------------------------- HTML

CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--panel:#ffffff;--border:#e4e3df;--text:#0b0b0b;--text-2:#52514e;
--text-muted:#8a8984;--series-1:#2a78d6;--series-2:#eb6834;--good:#0a7d32;--bad:#c22b2b;--accent:#2a78d6}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface:#1a1a19;
--panel:#232322;--border:#3a3a38;--text:#f0efec;--text-2:#c3c2b7;--text-muted:#8f8e88;--series-1:#3987e5;
--series-2:#d95926;--good:#4cc27a;--bad:#ff7a7a;--accent:#3987e5}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--panel:#232322;--border:#3a3a38;--text:#f0efec;
--text-2:#c3c2b7;--text-muted:#8f8e88;--series-1:#3987e5;--series-2:#d95926;--good:#4cc27a;--bad:#ff7a7a;--accent:#3987e5}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--text);
font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:14px 16px;
border-bottom:1px solid var(--border);background:var(--panel)}
header h1{font-size:18px;margin:0}header nav a{margin-left:14px}
main{max-width:1080px;margin:0 auto;padding:16px}
a{color:var(--accent)}h2{font-size:16px;margin:28px 0 10px}
.muted{color:var(--text-muted)}.note{color:var(--text-2);font-size:13px}
.banner{border:1px solid var(--series-2);border-radius:8px;padding:10px 12px;margin:10px 0;font-size:14px}
.ok{border-color:var(--good)}.err{border-color:var(--bad)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.tile{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px}
.tile .k{font-size:12px;color:var(--text-2)}.tile .v{font-size:24px;font-weight:600;margin-top:2px}
.tile .s{font-size:12px;color:var(--text-muted);margin-top:2px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:6px 8px;
border-bottom:1px solid var(--border);white-space:nowrap}th{color:var(--text-2);font-weight:500}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.pos{color:var(--good)}.neg{color:var(--bad)}
.chart{width:100%;min-width:560px;height:auto;display:block}.chart .grid{stroke:var(--border);stroke-width:1}
.chart .zero{stroke:var(--text-muted);stroke-width:1}.chart .axis{fill:var(--text-muted);font-size:11px}
.chart .label{fill:var(--text-2);font-size:12px}.chart .value{fill:var(--text);font-size:12px}
.legend{display:flex;gap:16px;font-size:13px;color:var(--text-2);margin-bottom:6px}
.sw{display:inline-block;width:12px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
form.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
label{display:block;font-size:13px;color:var(--text-2)}
input,select,button{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--border);
border-radius:6px;padding:6px 8px;width:100%;margin-top:4px}
input[type=checkbox]{width:auto}button{background:var(--accent);color:#fff;border:0;cursor:pointer;width:auto;padding:8px 16px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:end}.row>*{flex:1 1 140px}
.periods a{margin-right:10px}.periods a.on{font-weight:600;color:var(--text);text-decoration:none}
@media (max-width:600px){.tile .v{font-size:20px}}
"""


def page(title: str, store_id: str | None, body: str) -> HTMLResponse:
    nav = ""
    if store_id:
        sid = quote(store_id)
        nav = (f'<nav><a href="/store/{sid}">Dashboard</a><a href="/store/{sid}/settings">Settings</a>'
               f'<a href="/api/stores/{sid}/events.csv">Export CSV</a></nav>')
    stores = db.stores(con())
    picker = ""
    if len(stores) > 1:
        opts = "".join(f'<option value="{escape(s)}"{" selected" if s == store_id else ""}>{escape(s)}</option>'
                       for s in stores)
        picker = (f'<form method="get" action="/go" style="width:160px"><select name="store" '
                  f'onchange="this.form.submit()" aria-label="Store">{opts}</select></form>')
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{CSS}</style></head><body>'
            f'<header><h1>MarginGraph · {escape(store_id or "")}</h1>{picker}{nav}</header><main>{body}</main></body></html>')
    return HTMLResponse(html)


def money(v: float) -> str:
    return f"£{v:,.2f}"


def fmt(v: float, kind: str) -> str:
    if kind == "money":
        return f"{'-' if v < 0 else ''}£{abs(v):,.3f}"
    if kind == "pct":
        return f"{v:.2%}"
    return f"{v:,.3f}"


def weight_str(w: float | None) -> str:
    return "" if w is None else f"{w:.2f}"


def tile(k: str, v: str, s: str = "") -> str:
    return f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>'


@app.get("/", include_in_schema=False)
def root():
    s = db.stores(con())
    return RedirectResponse(f"/store/{quote(s[0])}" if s else "/store/demo")


@app.get("/go", include_in_schema=False)
def go(store: str):
    return RedirectResponse(f"/store/{quote(store)}")


@app.get("/store/{store_id}", response_class=HTMLResponse, include_in_schema=False)
def dashboard(store_id: str, days: str = "28"):
    k = compute(store_id, days)
    t, ab = k["totals"], k["ab"]
    periods = "".join(f'<a class="{"on" if p == days else ""}" href="?days={p}">{"All" if p == "all" else p + " days"}</a>'
                      for p in PERIODS)
    parts = [f'<div class="periods">{periods}</div>']
    if k["sample_data"]:
        parts.append('<div class="banner">Showing <b>sample data</b>: real product prices with simulated cost, stock '
                     'and shopper behaviour. Connect the recommendation service (see docs/DASHBOARD.md) to see live '
                     'numbers.</div>')
    if t["requests"] == 0:
        parts.append('<p class="muted">No recommendation events in this period yet. Run '
                     '<code>margingraph dashboard --sample</code> for demo data, or send events to '
                     '<code>POST /api/events</code>.</p>')
        return page("MarginGraph dashboard", store_id, "".join(parts))
    prof = next(r for r in ab["rows"] if r["metric"] == "profit")
    uplift = (f'{prof["rel"]:+.1%}', f'95% CI {prof["rel_lo"]:+.1%} to {prof["rel_hi"]:+.1%}') if prof["control"] > 0 \
        else ("n/a", "needs control traffic")
    parts.append('<h2>Overview</h2><div class="tiles">' + "".join([
        tile("Profit uplift (A/B)", uplift[0], uplift[1]),
        tile("Add-on profit", money(t["profit"]), f'revenue {money(t["revenue"])}'),
        tile("Add-on margin", f'{t["margin"]:.1%}', f'floor {k["settings"]["margin_floor"]:.0%}'),
        tile("Overstock units cleared", f'{t["overstock_units"]:,}', "bought as add-ons"),
        tile("Recommendation clicks", f'{t["clicks"]:,}', f'CTR {t["ctr"]:.1%} of {t["requests"]:,} requests'),
        tile("Add-on buys", f'{t["purchases"]:,}', f'conversion {t["conversion"]:.1%}'),
    ]) + "</div>")

    legend = ('<div class="legend"><span><i class="sw" style="background:var(--series-1)"></i>control (relevance only)'
              '</span><span><i class="sw" style="background:var(--series-2)"></i>treatment (margin-aware)</span></div>')
    parts.append(f'<h2>Add-on profit per request, by day</h2><div class="card">{legend}'
                 f'{charts.line_chart(k["daily"], "profit_per_request")}</div>')

    parts.append('<h2>A/B test: treatment vs control</h2>')
    srm = ab["srm_p"]
    if srm < 0.001:
        parts.append(f'<div class="banner err">Sample ratio mismatch (p={srm:.4f}): traffic split does not match the '
                     f'configured {k["settings"]["treatment_share"]:.0%}. Check assignment before trusting results.</div>')
    rows = "".join(
        f'<tr><td>{escape(r["label"])}</td><td class="n">{fmt(r["control"], r["fmt"])}</td>'
        f'<td class="n">{fmt(r["treatment"], r["fmt"])}</td>'
        f'<td class="n {"pos" if r["lo"] > 0 else "neg" if r["hi"] < 0 else ""}">{fmt(r["diff"], r["fmt"])}</td>'
        f'<td class="n">[{fmt(r["lo"], r["fmt"])}, {fmt(r["hi"], r["fmt"])}]</td>'
        f'<td class="n">{r["rel"]:+.1%}</td><td class="n">{r["p"]:.3f}</td></tr>' for r in ab["rows"])
    parts.append(
        f'<div class="card"><p class="note">{ab["n_control"]:,} control and {ab["n_treatment"]:,} treatment requests. '
        f'Add-on margin: control {ab["margin_control"]:.1%}, treatment {ab["margin_treatment"]:.1%}. '
        f'95% CIs use a Welch normal approximation per request; ✓ marks a CI that excludes zero. With this traffic '
        f'the smallest conversion change you can reliably detect is about {ab["mde_conversion"]:.2%} points.</p>'
        f'{charts.forest(ab["rows"])}'
        f'<table><tr><th>Metric</th><th class="n">Control</th><th class="n">Treatment</th><th class="n">Diff</th>'
        f'<th class="n">95% CI</th><th class="n">Relative</th><th class="n">p</th></tr>{rows}</table></div>')

    ti = k["top_items"]
    desc = adapter.load_catalog(con(), store_id).set_index("item")["description"].dropna().to_dict()
    trs = "".join(f'<tr><td>{escape(str(r.item))}</td><td>{escape(desc.get(r.item, ""))}</td>'
                  f'<td>{"overstock" if r.overstock else ""}</td>'
                  f'<td class="n">{int(r.units)}</td>'
                  f'<td class="n">{money(r.revenue)}</td><td class="n">{money(r.profit)}</td></tr>' for r in ti.itertuples())
    parts.append(f'<h2>Top add-ons by profit</h2><div class="card"><table><tr><th>Item</th><th>Description</th><th></th><th class="n">Units</th>'
                 f'<th class="n">Revenue</th><th class="n">Profit</th></tr>{trs}</table></div>')
    bv = k["by_variant"]
    vrows = "".join(f'<tr><td>{v}</td><td class="n">{x["requests"]:,}</td><td class="n">{x["clicks"]:,}</td>'
                    f'<td class="n">{x["purchases"]:,}</td><td class="n">{money(x["profit"])}</td>'
                    f'<td class="n">{x["margin"]:.1%}</td><td class="n">{x["overstock_units"]:,}</td></tr>'
                    for v, x in bv.items())
    parts.append(f'<h2>Totals by variant</h2><div class="card"><table><tr><th>Variant</th><th class="n">Requests</th>'
                 f'<th class="n">Clicks</th><th class="n">Buys</th><th class="n">Profit</th><th class="n">Margin</th>'
                 f'<th class="n">Overstock units</th></tr>{vrows}</table></div>')
    return page("MarginGraph dashboard", store_id, "".join(parts))


@app.get("/store/{store_id}/settings", response_class=HTMLResponse, include_in_schema=False)
def settings_page(store_id: str, saved: str = "", error: str = ""):
    c = con()
    s = db.get_settings(c, store_id)
    rules = db.item_rules(c, store_id)
    prev = kpis.policy_preview(adapter.load_catalog(c, store_id), s, rules)
    parts = []
    if saved:
        parts.append('<div class="banner ok">Saved. The recommendation service picks this up on its next request.</div>')
    if error:
        parts.append(f'<div class="banner err">{escape(error)}</div>')
    parts.append(f'''<h2>Recommendation policy</h2><div class="card">
<form method="post" class="grid">
<label>Margin floor (%)<input type="number" name="margin_floor" min="0" max="90" step="1" value="{s.margin_floor * 100:.0f}">
<span class="note">No add-on is offered below this gross margin.</span></label>
<label>Max add-ons per checkout<input type="number" name="max_addons" min="1" max="5" step="1" value="{s.max_addons}"></label>
<label>Profit weight λ (0 = pure relevance, 1 = pure profit)<input type="number" name="lam" min="0" max="1" step="0.05" value="{s.lam}"></label>
<label>Overstock weight (1.0 to 2.0)<input type="number" name="overstock_weight" min="1" max="2" step="0.05" value="{s.overstock_weight}">
<span class="note">How much extra value clearing overstock is worth.</span></label>
<label>Traffic on margin-aware policy (%)<input type="number" name="treatment_share" min="0" max="100" step="5" value="{s.treatment_share * 100:.0f}">
<span class="note">The rest is the control group for the A/B test.</span></label>
<label><input type="checkbox" name="allow_discounts" value="1"{" checked" if s.allow_discounts else ""}> Allow 10% / 20% discounts on add-ons</label>
<div><button type="submit">Save policy</button></div>
</form></div>''')
    if prev["items"]:
        parts.append('<h2>What this policy allows</h2><div class="tiles">' + "".join([
            tile("Catalog items", f'{prev["items"]:,}'),
            tile("Eligible to offer", f'{prev["eligible"]:,}', f'{prev["eligible"] / prev["items"]:.0%} of catalog'),
            tile("Blocked by margin floor", f'{prev["below_floor"]:,}'),
            tile("Excluded by you", f'{prev["excluded"]:,}'),
            tile("Out of stock", f'{prev["out_of_stock"]:,}'),
            tile("Flagged overstock", f'{prev["overstock"]:,}'),
        ]) + "</div>")
    trs = "".join(
        f'<tr><td>{escape(i)}</td><td>{"excluded" if r["excluded"] else ""}</td>'
        f'<td class="n">{weight_str(r["overstock_weight"])}</td>'
        f'<td><form method="post" action="items" style="display:inline"><input type="hidden" name="item" value="{escape(i)}">'
        f'<input type="hidden" name="action" value="reset"><button type="submit">Reset</button></form></td></tr>'
        for i, r in sorted(rules.items()))
    parts.append(f'''<h2>Per-product rules</h2><div class="card">
<form method="post" action="items" class="row">
<label>Product code<input name="item" required placeholder="e.g. 85123A"></label>
<label>Action<select name="action"><option value="exclude">Never recommend</option><option value="include">Allow again</option>
<option value="weight">Set overstock weight</option><option value="reset">Remove rule</option></select></label>
<label>Weight (for "set weight")<input type="number" name="weight" min="1" max="2" step="0.05" value="1.5"></label>
<div><button type="submit">Apply</button></div></form>
<table style="margin-top:12px"><tr><th>Product</th><th>Status</th><th class="n">Overstock weight</th><th></th></tr>
{trs or '<tr><td colspan="4" class="muted">No product rules yet.</td></tr>'}</table></div>''')
    hist = db.history(c, store_id)
    htr = "".join(f'<tr><td>{escape(h["ts"])}</td><td>{escape(h["field"])}</td><td>{escape(str(h["old"]))}</td>'
                  f'<td>{escape(str(h["new"]))}</td></tr>' for h in hist)
    parts.append(f'<h2>Change history</h2><div class="card"><table><tr><th>When (UTC)</th><th>Setting</th><th>From</th>'
                 f'<th>To</th></tr>{htr or "<tr><td colspan=4 class=muted>No changes yet.</td></tr>"}</table></div>')
    return page("MarginGraph settings", store_id, "".join(parts))


async def form(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode()
    return {k: v[-1] for k, v in parse_qs(raw, keep_blank_values=True).items()}


@app.post("/store/{store_id}/settings", include_in_schema=False)
async def settings_post(store_id: str, request: Request):
    f = await form(request)
    back = f"/store/{quote(store_id)}/settings"
    try:
        s = db.Settings(
            margin_floor=float(f.get("margin_floor", 15)) / 100,
            max_addons=int(f.get("max_addons", 2)),
            lam=float(f.get("lam", 0.5)),
            overstock_weight=float(f.get("overstock_weight", 1.5)),
            allow_discounts=f.get("allow_discounts") == "1",
            treatment_share=float(f.get("treatment_share", 50)) / 100,
        )
    except ValueError:
        return RedirectResponse(f"{back}?error={quote('Please enter numbers only.')}", status_code=303)
    err = db.save_settings(con(), store_id, s)
    if err:
        return RedirectResponse(f"{back}?error={quote('; '.join(err))}", status_code=303)
    return RedirectResponse(f"{back}?saved=1", status_code=303)


@app.post("/store/{store_id}/items", include_in_schema=False)
async def items_post(store_id: str, request: Request):
    f = await form(request)
    back = f"/store/{quote(store_id)}/settings"
    item, action = f.get("item", ""), f.get("action", "")
    c = con()
    if action == "exclude":
        err = db.set_item_rule(c, store_id, item, excluded=True)
    elif action == "include":
        err = db.set_item_rule(c, store_id, item, excluded=False)
    elif action == "weight":
        try:
            err = db.set_item_rule(c, store_id, item, overstock_weight=float(f.get("weight", "")))
        except ValueError:
            err = ["weight must be a number"]
    elif action == "reset":
        err = db.set_item_rule(c, store_id, item, excluded=False, clear_weight=True)
    else:
        err = ["unknown action"]
    if err:
        return RedirectResponse(f"{back}?error={quote('; '.join(err))}", status_code=303)
    return RedirectResponse(f"{back}?saved=1", status_code=303)
