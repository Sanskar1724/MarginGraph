"""MarginGraph live demo (Gradio, CPU only, ~150 MB RAM).

Tab 1  Demo store: build a basket from 2,000 real Online Retail II products,
       compare plain top-2 add-ons with MarginGraph's margin-safe pick.
Tab 2  Your store: upload your products (price, cost, stock) and optionally
       your order history; get recommendations for one basket or a whole CSV.
Tab 3  Backtest: measured numbers on held-out Oct-Dec 2011 baskets.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import core
import gradio as gr
import numpy as np
import pandas as pd

ART = Path(__file__).resolve().parent / "artifacts"
META = json.loads((ART / "meta.json").read_text())
_npz = np.load(ART / "ease.npz")
DEMO = core.Model(
    items=[str(s) for s in _npz["items"]],
    B=_npz["B"].astype(np.float32),
    calib=META["calibration"],
    catalog=pd.read_csv(ART / "catalog.csv", dtype={"item": str}),
)
del _npz

PRODUCT_COLS = ["item", "description", "price", "unit_cost", "stock", "overstock"]
ALIASES = {
    "item": ["item", "stock_code", "stockcode", "sku", "product_id", "product", "code", "id"],
    "description": ["description", "name", "title", "product_name"],
    "price": ["price", "unit_price", "sell_price", "retail_price"],
    "unit_cost": ["unit_cost", "cost", "cogs", "buy_price", "purchase_price"],
    "stock": ["stock", "qty", "quantity", "on_hand", "inventory", "stock_level"],
    "overstock": ["overstock", "overstocked", "clearance", "excess"],
    "basket": ["basket", "basket_id", "order", "order_id", "invoice", "invoice_no", "transaction_id", "cart_id"],
}
SIM_NOTE = ("Demo store costs and stock are **simulated** (Online Retail II publishes prices but not costs "
            "or inventory). Upload your own numbers in *Your store* to use real ones.")


# ---------------------------------------------------------------- helpers

def label(model: core.Model, code: str) -> str:
    i = model.pos.get(code)
    return f"{code} · {model.catalog['description'].iat[i]}" if i is not None else code


def choices(model: core.Model) -> list[str]:
    return [label(model, c) for c in model.items if model.catalog["stock"].iat[model.pos[c]] >= 0]


def codes_from(sel) -> list[str]:
    if isinstance(sel, str):
        sel = [s for s in sel.replace("\n", ",").split(",")]
    return [s.split("·")[0].strip().upper() for s in (sel or []) if s and s.strip()]


def policy(floor, overstock_w, lam, discounts, k) -> core.Policy:
    return core.Policy(lam=float(lam), overstock_weight=float(overstock_w), floor=float(floor),
                       discounts=(0.0, 0.10, 0.20) if discounts else (0.0,), max_addons=int(k))


def money(x: float) -> str:
    return f"£{x:,.2f}"


def card(title: str, cand: pd.DataFrame, chosen, pol: core.Policy, accent: str) -> str:
    st = core.offer_stats(cand, chosen, pol)
    rows = []
    for j, d in chosen:
        r = cand.loc[j]
        price = r.price * (1 - d)
        m = (price - r.unit_cost) / price if price else 0
        tags = []
        if r.overstock:
            tags.append('<span class="mg-tag mg-over">overstock</span>')
        if d:
            tags.append(f'<span class="mg-tag">-{int(d*100)}%</span>')
        if m < pol.floor:
            tags.append('<span class="mg-tag mg-bad">below margin floor</span>')
        rows.append(
            f'<div class="mg-item"><div class="mg-name">{r.description.title()} '
            f'<span class="mg-code">{r["item"]}</span> {"".join(tags)}</div>'
            f'<div class="mg-meta">{money(price)} · margin {m:.0%} · p(buy) {min(1, r.p_accept*(1+pol.elasticity*d)):.1%}'
            f' · stock {int(r.stock)}</div>'
            f'<div class="mg-why">bought with: {str(r.because_of).title()}</div></div>')
    body = "".join(rows) or '<div class="mg-meta">No add-on passes the rules for this basket.</div>'
    return (f'<div class="mg-card" style="border-top:4px solid {accent}"><div class="mg-h">{title}</div>{body}'
            f'<div class="mg-foot">Expected profit <b>{money(st["exp_profit"])}</b> · expected margin '
            f'{st["exp_margin"]:.0%} · chance of at least one sale ≈ {min(1, st["hit_prob"]):.0%}</div></div>')


def run(model: core.Model, codes: list[str], pol: core.Policy):
    res = model.recommend(codes, pol)
    if not res["known"]:
        msg = "Add at least one product the model knows."
        if res["unknown"]:
            msg += f" Unknown codes: {', '.join(res['unknown'][:10])}"
        return f'<div class="mg-note">{msg}</div>', "", "", None
    cand = res["candidates"]
    a = core.offer_stats(cand, res["top"], pol)
    b = core.offer_stats(cand, res["optimized"], pol)
    dp = (b["exp_profit"] / a["exp_profit"] - 1) * 100 if a["exp_profit"] > 0 else 0.0
    dh = (min(1, b["hit_prob"]) - min(1, a["hit_prob"])) * 100
    summary = (f'<div class="mg-sum"><div><span class="mg-big">{dp:+.0f}%</span><br>expected profit vs plain top-{pol.max_addons}</div>'
               f'<div><span class="mg-big">{dh:+.1f} pts</span><br>chance of an add-on sale</div>'
               f'<div><span class="mg-big">{a["floor_violations"]} → {b["floor_violations"]}</span><br>items below the {pol.floor:.0%} floor</div></div>')
    if res["unknown"]:
        summary += f'<div class="mg-note">Ignored codes not in the model: {", ".join(res["unknown"][:10])}</div>'
    tbl = cand.assign(
        p_accept=(cand.p_accept * 100).round(1), margin=(cand.margin * 100).round(0),
        exp_profit=cand.exp_profit.round(3), price=cand.price.round(2), unit_cost=cand.unit_cost.round(2),
        picked=["✓" if j in {x for x, _ in res["optimized"]} else "" for j in range(len(cand))],
    ).rename(columns={"p_accept": "p(buy) %", "margin": "margin %", "exp_profit": "exp. profit £"})
    return (summary, card(f"Plain top-{pol.max_addons} (relevance only)", cand, res["top"], pol, "#9aa0a6"),
            card("MarginGraph pick", cand, res["optimized"], pol, "#0f9d58"), tbl)


# ---------------------------------------------------------------- merchant

def _rename(df: pd.DataFrame, wanted: list[str]) -> pd.DataFrame:
    low = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    m = {}
    for w in wanted:
        for a in ALIASES[w]:
            if a in low:
                m[low[a]] = w
                break
    return df.rename(columns=m)


def read_products(path) -> pd.DataFrame:
    df = _rename(pd.read_csv(path, dtype=str), PRODUCT_COLS)
    miss = [c for c in ["item", "price", "unit_cost", "stock"] if c not in df.columns]
    if miss:
        raise gr.Error(f"Products CSV is missing column(s): {', '.join(miss)}. Download the template.")
    df["item"] = df["item"].astype(str).str.strip().str.upper()
    if "description" not in df:
        df["description"] = df["item"]
    if "overstock" not in df:
        df["overstock"] = "false"
    df["overstock"] = df["overstock"].astype(str).str.strip().str.lower().isin(["1", "true", "yes", "y", "x"])
    for c in ["price", "unit_cost", "stock"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[£$€,\s]", "", regex=True), errors="coerce")
    bad = df[["price", "unit_cost", "stock"]].isna().any(axis=1).sum()
    df = df.dropna(subset=["price", "unit_cost", "stock"])
    df.attrs["dropped"] = int(bad)
    return df[PRODUCT_COLS]


def read_baskets(path) -> list[list[str]]:
    df = _rename(pd.read_csv(path, dtype=str), ["basket", "item"])
    if not {"basket", "item"} <= set(df.columns):
        raise gr.Error("Orders CSV needs two columns: order_id (or invoice/basket_id) and item (or sku/stock_code).")
    return core.baskets_from_lines(df, "basket", "item")


def load_store(products_file, orders_file):
    if products_file is None:
        raise gr.Error("Upload a products CSV first (use the template).")
    prods = read_products(products_file)
    notes = [f"Loaded **{len(prods):,}** products"
             + (f" ({prods.attrs['dropped']} rows skipped: missing price, cost or stock)." if prods.attrs["dropped"] else ".")]
    if orders_file is not None:
        baskets = read_baskets(orders_file)
        try:
            model = core.train_from_baskets(baskets, prods)
        except ValueError as e:
            raise gr.Error(str(e)) from e
        h = model.calib["hit"]
        notes.append(f"Trained on **{len(baskets):,}** of your orders ({len(model.items):,} products). "
                     f"Backtest on your most recent 20% of orders: the hidden item is in our top-2 "
                     f"**{h['hit@2']:.1%}** of the time, top-10 **{h['hit@10']:.1%}** "
                     f"({model.calib['n_events']:,} test baskets).")
    else:
        model = core.Model(DEMO.items, DEMO.B, DEMO.calib, prods)
        n = int(model.catalog["price"].gt(0).sum())
        notes.append(f"No order history uploaded, so the demo model (Online Retail II co-purchases) is used. "
                     f"**{n:,}** of your products match its item codes and can be recommended. "
                     f"Upload orders to train on your own data.")
        if n == 0:
            notes.append("⚠️ None of your codes match. Upload your order history so the model can learn your catalog.")
    sold = model.catalog[model.catalog["price"] > 0]
    return model, "\n\n".join(notes), gr.Dropdown(choices=[label(model, c) for c in sold["item"]], value=[])


def store_recommend(model, sel, floor, ow, lam, disc, k):
    if model is None:
        raise gr.Error("Load your store first.")
    return run(model, codes_from(sel), policy(floor, ow, lam, disc, k))


def batch(model, baskets_file, floor, ow, lam, disc, k):
    if model is None:
        model = DEMO
    if baskets_file is None:
        raise gr.Error("Upload a CSV of open baskets (basket_id, item).")
    df = _rename(pd.read_csv(baskets_file, dtype=str), ["basket", "item"])
    if not {"basket", "item"} <= set(df.columns):
        raise gr.Error("Baskets CSV needs columns basket_id and item.")
    pol = policy(floor, ow, lam, disc, k)
    out = []
    for bid, g in df.groupby("basket", sort=False):
        res = model.recommend(g["item"].tolist(), pol)
        if not res["known"]:
            out.append({"basket_id": bid, "slot": 0, "item": "", "description": "no known items"})
            continue
        cand = res["candidates"]
        for slot, (j, d) in enumerate(res["optimized"], 1):
            r = cand.loc[j]
            price = r.price * (1 - d)
            out.append({"basket_id": bid, "slot": slot, "item": r["item"], "description": r.description,
                        "price": round(price, 2), "discount": d, "margin": round((price - r.unit_cost) / price, 3),
                        "p_accept": round(r.p_accept * (1 + pol.elasticity * d), 4),
                        "expected_profit": round(r.p_accept * (1 + pol.elasticity * d) * (price - r.unit_cost), 4),
                        "overstock": bool(r.overstock), "because_of": r.because_of})
    res = pd.DataFrame(out)
    path = Path(tempfile.mkdtemp()) / "margingraph_recommendations.csv"
    res.to_csv(path, index=False)
    return res.head(50), str(path)


def template() -> str:
    path = Path(tempfile.mkdtemp()) / "products_template.csv"
    DEMO.catalog[PRODUCT_COLS].head(300).to_csv(path, index=False)
    return str(path)


def orders_template() -> str:
    path = Path(tempfile.mkdtemp()) / "orders_template.csv"
    rows = [(f"ORD{i:05d}", c) for i, b in enumerate(META["examples"]) for c in b]
    pd.DataFrame(rows, columns=["order_id", "item"]).to_csv(path, index=False)
    return str(path)


# ---------------------------------------------------------------- backtest tab

def backtest_md() -> str:
    bt, tr = META["backtest"], META["test_ranking"]
    names = {"top2_relevance": "Plain top-2 (relevance only)",
             "margingraph_lam0.5": "MarginGraph, balance 0.5",
             "margingraph_lam1.0": "MarginGraph, balance 1.0 (profit)",
             "margingraph_lam1.0_overstock2x": "MarginGraph, balance 1.0, overstock 2x"}
    lines = ["| Strategy | Hit@2 | Realized profit / basket | vs top-2 (95% CI, £/basket) | Below 15% floor | Overstock share |",
             "|---|---|---|---|---|---|"]
    for k, v in bt.items():
        ci = v["realized_profit_diff_ci95"]
        lines.append(f"| {names.get(k, k)} | {v['hit@2']:.1%} | £{v['realized_profit_per_basket']:.4f} | "
                     f"{v['realized_profit_vs_top2_pct']:+.1f}% ([{ci[0]:+.4f}, {ci[1]:+.4f}]) | "
                     f"{v['margin_floor_violations_per_basket']:.3f} | {v['overstock_share_of_offers']:.1%} |")
    return f"""
### Measured on real held-out baskets (not targets)

**Protocol.** Model fit on Dec 2009 to Sep 2011, tested on {META['n_test_events']:,} invoices from Oct to Dec 2011.
In each test invoice one product is hidden; a strategy *hits* if one of its 2 add-ons is that product.
*Realized profit* only counts the hidden product, so it is grounded in what customers really bought.

**Stage 1 (EASE, {META['n_items']:,} products, {META['test_line_coverage']:.0%} of test lines covered):**
Hit@2 {tr['hit']['hit@2']:.1%} · Hit@5 {tr['hit']['hit@5']:.1%} · Hit@10 {tr['hit']['hit@10']:.1%}.
Picking at random from {META['n_items']:,} products would hit about {2/META['n_items']:.2%} at 2.

**Stage 2:**

{chr(10).join(lines)}

Costs and stock in this table are **simulated** (Beta(4,6) margins, mean 40%; 15% of items overstocked),
so profit numbers show how the optimizer behaves, not what a real store would earn.
The full research pipeline (LightGBM reranker, Hit@10 35.6%) lives in the main repo.
"""


# ---------------------------------------------------------------- UI

CSS = """
.mg-card{background:var(--block-background-fill);border:1px solid var(--border-color-primary);border-radius:10px;padding:14px;min-height:210px}
.mg-h{font-weight:700;font-size:1.05em;margin-bottom:8px}
.mg-item{padding:8px 0;border-bottom:1px dashed var(--border-color-primary)}
.mg-name{font-weight:600}.mg-code{opacity:.6;font-size:.85em;font-weight:400}
.mg-meta,.mg-why{font-size:.9em;opacity:.85}.mg-why{font-style:italic}
.mg-foot{margin-top:10px;font-size:.95em}
.mg-tag{display:inline-block;font-size:.75em;padding:1px 6px;border-radius:8px;background:#e8eaed;color:#333;margin-left:4px}
.mg-over{background:#fde293}.mg-bad{background:#f6aea9}
.mg-sum{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0}.mg-sum>div{flex:1;min-width:150px;text-align:center;padding:8px;border-radius:10px;background:var(--block-background-fill);border:1px solid var(--border-color-primary)}
.mg-big{font-size:1.8em;font-weight:700}
.mg-note{padding:8px;border-radius:8px;background:#fef7e0;color:#5f4b00;margin-top:6px}
"""

DEMO_CHOICES = choices(DEMO)


def controls():
    with gr.Row():
        floor = gr.Slider(0, 0.5, 0.15, step=0.01, label="Margin floor (min margin per add-on)")
        ow = gr.Slider(1.0, 2.0, 1.0, step=0.05, label="Overstock weight (push excess stock)")
        lam = gr.Slider(0, 1, 1.0, step=0.05, label="Balance: 0 = most likely to sell, 1 = most profit")
    with gr.Row():
        disc = gr.Checkbox(False, label="Allow 10% / 20% discounts (assumed demand response)")
        k = gr.Radio([1, 2], value=2, label="Add-ons to show")
    return floor, ow, lam, disc, k


with gr.Blocks(title="MarginGraph: profit-aware add-on recommendations") as demo:
    gr.Markdown("""# MarginGraph
**Checkout add-ons that customers want *and* that keep your margin.** Stage 1 learns what is bought together
from real orders. Stage 2 picks the best 2 add-ons under hard business rules: a minimum margin,
in-stock only, and an optional push for overstocked items.""")

    with gr.Tab("Demo store"):
        gr.Markdown(SIM_NOTE)
        with gr.Row():
            basket = gr.Dropdown(DEMO_CHOICES, value=[label(DEMO, c) for c in META["examples"][0]],
                                 multiselect=True, label="Basket (type to search 2,000 products)", scale=4)
            ex_btn = gr.Button("🎲 Real basket", scale=1)
        floor, ow, lam, disc, k = controls()
        go = gr.Button("Recommend add-ons", variant="primary")
        summary = gr.HTML()
        with gr.Row():
            left, right = gr.HTML(), gr.HTML()
        with gr.Accordion("All 20 candidates the optimizer looked at", open=False):
            table = gr.Dataframe(wrap=True)
        ins = [basket, floor, ow, lam, disc, k]
        outs = [summary, left, right, table]
        fn = lambda sel, *a: run(DEMO, codes_from(sel), policy(*a))  # noqa: E731
        go.click(fn, ins, outs)
        for c in [floor, ow, lam, disc, k]:
            c.release(fn, ins, outs) if isinstance(c, gr.Slider) else c.change(fn, ins, outs)

        def random_basket():
            b = META["examples"][np.random.randint(len(META["examples"]))]
            return [label(DEMO, c) for c in b]
        ex_btn.click(random_basket, None, basket).then(fn, ins, outs)
        demo.load(fn, ins, outs)

    with gr.Tab("Your store"):
        gr.Markdown("""**Use your own catalog.** 1) Upload products with `item, description, price, unit_cost, stock`
(optional `overstock` = yes/no). 2) Optionally upload order history (`order_id, item`, one row per item, oldest first)
so the model learns *your* customers; without it the demo model is used for matching item codes.
Files stay in this session only and are not stored.""")
        store = gr.State(None)
        with gr.Row():
            with gr.Column():
                pf = gr.File(label="Products CSV", file_types=[".csv"], elem_id="products-file")
                gr.DownloadButton("Products template", value=template)
            with gr.Column():
                of = gr.File(label="Order history CSV (optional)", file_types=[".csv"], elem_id="orders-file")
                gr.DownloadButton("Orders template", value=orders_template)
        load_btn = gr.Button("Load my store", variant="primary")
        status = gr.Markdown()
        s_basket = gr.Dropdown([], multiselect=True, label="Basket from your catalog")
        sfloor, sow, slam, sdisc, sk = controls()
        s_go = gr.Button("Recommend", variant="primary")
        s_sum = gr.HTML()
        with gr.Row():
            s_left, s_right = gr.HTML(), gr.HTML()
        with gr.Accordion("Candidates", open=False):
            s_tbl = gr.Dataframe(wrap=True)
        load_btn.click(load_store, [pf, of], [store, status, s_basket])
        s_go.click(store_recommend, [store, s_basket, sfloor, sow, slam, sdisc, sk], [s_sum, s_left, s_right, s_tbl])

        gr.Markdown("### Batch: recommendations for many open baskets\nUpload `basket_id, item` rows; "
                    "uses your store if loaded, otherwise the demo store.")
        bf = gr.File(label="Open baskets CSV", file_types=[".csv"], elem_id="baskets-file")
        b_go = gr.Button("Run batch")
        b_tbl = gr.Dataframe(label="First 50 rows")
        b_dl = gr.File(label="Download all recommendations")
        b_go.click(batch, [store, bf, sfloor, sow, slam, sdisc, sk], [b_tbl, b_dl])

    with gr.Tab("Backtest"):
        gr.Markdown(backtest_md())

    with gr.Tab("How it works / API"):
        gr.Markdown("""
**Pipeline.** Basket → EASE co-purchase model scores every product → top 20 candidates →
p(buy) calibrated on held-out baskets → exact optimizer picks ≤ 2 add-ons that maximize
`p(buy) × ((1 − balance) × avg p + balance × overstock_weight × unit profit)`
subject to margin ≥ floor, stock > 0, one discount per item. Rules are enforced in code; nothing is guessed by an LLM.

**Call it from code** (every button is also an API endpoint):
```python
from gradio_client import Client
c = Client("YOUR-HF-USERNAME/margingraph")
print(c.view_api())
```
Source and research pipeline: [github.com/Sanskar1724/MarginGraph](https://github.com/Sanskar1724/MarginGraph)
""")

if __name__ == "__main__":
    demo.launch(css=CSS, theme=gr.themes.Soft())
