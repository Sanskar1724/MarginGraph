# Merchant dashboard

A small web app where a store owner controls the recommendation policy and sees whether it pays off.
It runs on a laptop with 8 GB of RAM: FastAPI, server-rendered HTML, inline SVG charts and one SQLite file.
There is no JavaScript build, no chart library and no paid service.

```bash
pip install -e .
margingraph dashboard --sample          # seeds a 'demo' store, then serves http://127.0.0.1:8501
```

Measured on the container (Python 3.13, 28 days of sample data, about 11,000 requests and 28,000 events):
the server uses about 190 MB of RAM, and the dashboard page renders in about 0.33 s.

## What the store owner can do

**Settings page** (`/store/{id}/settings`)

| Setting | Range | What it does |
| --- | --- | --- |
| Margin floor | 0–90% | No add-on is offered below this gross margin (default 15%) |
| Max add-ons per checkout | 1–5 | Slate size (default 2) |
| Profit weight λ | 0–1 | 0 = pure relevance, 1 = pure expected profit (default 0.5) |
| Overstock weight | 1.0–2.0× | Extra value for items flagged overstock (default 1.5) |
| Traffic on margin-aware policy | 0–100% | The rest is the A/B control group (default 50%) |
| Allow discounts | on/off | Lets the optimizer offer 10% or 20% off |
| Per-product rules | | "Never recommend" an item, or set its own overstock weight |

The page also shows **what this policy allows**: how many catalog items are eligible, blocked by the margin floor, excluded, or out of stock.
Every change is written to a **change history** with old and new values.

**Dashboard page** (`/store/{id}`, periods 7 / 28 / 90 days / all)

* KPI tiles: profit uplift from the A/B test with its 95% CI, add-on profit and revenue, add-on margin, overstock units cleared, recommendation clicks (CTR) and add-on buys (conversion).
* Add-on profit per request by day, control vs treatment.
* A/B table and chart: profit, revenue, conversion, click-through and overstock units per request, with the difference, 95% CI, relative change and p-value.
* A sample ratio mismatch alarm if the traffic split does not match the configured share.
* The minimum detectable conversion change at the current traffic.
* Top add-ons by profit, with product descriptions, and totals by variant.
* `Export CSV` downloads the raw events.

## How the numbers are computed

The unit is one **recommendation request** (one slate shown at checkout).
A request *clicks* if any shown add-on was clicked and *converts* if any was bought.
Its profit is `(price - unit_cost) × qty` summed over bought add-ons.

Treatment and control are compared on per-request means with a Welch normal-approximation 95% CI. The relative uplift CI uses the delta method.
This is the standard method in commercial A/B tools, and it is cheap: no bootstrap loop.
The sample ratio check is a 1-df chi-square test against the configured split. The MDE assumes 95% confidence and 80% power.
Unit tests check these formulas against hand-computed values (`tests/test_dashboard.py`).

## Sample data is not evidence

`--sample` builds the `demo` store from two sources:
* **Catalog:** the 4,563 real Online Retail II products, with real prices and descriptions (`results/item_descriptions.csv`). Unit cost, stock and the overstock flag come from the pipeline's **simulated** ERP (`results/erp_simulated.csv`).
* **Events:** 28 days of a **simulated** 50/50 test. Control shows items sampled by real weekly demand. Treatment shows items picked by the store's policy (margin floor, exclusions, λ, overstock weight). Per-item buy rates come from the offline E8 result (ranker top-2 Hit@2 16.7% vs MILP λ=0.5 15.6%), so treatment converts *less*. Any profit gain comes only from which items get shown.

The page shows a "sample data" banner whenever every event in view is a sample event (`source='sample'`).
The +18.8% profit uplift you see on the demo store comes from this simulation. It is not a measured result.

## Connecting a real store

1. **Catalog.** Load a CSV with `item,price` and optionally `description,unit_cost,stock,overstock`:
   `margingraph dashboard --store shop1 --catalog my_products.csv`, or `POST /api/stores/shop1/catalog` with the CSV as the request body.
   Unit cost is what makes the margin floor and profit real. Without it, profit is counted as zero.
2. **Settings for the recommender.** The recommendation service reads `GET /api/stores/{id}/settings`, or calls `margingraph.dashboard.db.get_settings` / `item_rules` directly on the same SQLite file:
   ```json
   {"store_id": "shop1", "margin_floor": 0.15, "max_addons": 2, "lam": 0.5, "overstock_weight": 1.5,
    "allow_discounts": false, "treatment_share": 0.5, "items": {"22423": {"excluded": true, "overstock_weight": null}}}
   ```
   `PUT` the same shape (any subset of fields) to change settings from a script.
3. **Events.** For each slate shown, log one `impression` per item. Then log `click` and `purchase` events with the same `request_id` and `variant` (`control` or `treatment`):
   ```bash
   curl -X POST localhost:8501/api/events -H 'content-type: application/json' -d '[
     {"store_id":"shop1","request_id":"r-123","variant":"treatment","event":"impression","item":"22423"},
     {"store_id":"shop1","request_id":"r-123","variant":"treatment","event":"purchase","item":"22423","price":12.75,"qty":1}]'
   ```
   If `price`, `unit_cost` or `overstock` are left out, they are filled in from the catalog.
4. **The service already logs somewhere else?** The KPI code reads events only through `dashboard/adapter.py`. Point it at the other log without changing code:
   ```bash
   export MARGINGRAPH_EVENTS_DB=/path/to/service.db            # attached as "svc"
   export MARGINGRAPH_EVENTS_SQL="SELECT created_at AS ts, store_id, request_id, variant, event, item,
          price, unit_cost, overstock, qty, 'live' AS source FROM svc.request_log"
   ```
5. **Access.** Set `MARGINGRAPH_DASHBOARD_TOKEN=...`. The browser then asks for a password (any user name works), and API clients send `Authorization: Bearer ...`.
   Run it behind HTTPS (for example Caddy, or a free Cloudflare Tunnel) if it is reachable from the internet.

## Limits

* Settings forms have no CSRF token. Keep the dashboard on a private network or behind the token.
* One SQLite file handles a single store or a few small stores well. For many stores with heavy traffic, move `events` to Postgres and keep the same adapter query.
* A/B assignment is done by the recommendation service, not by the dashboard. The SRM alarm catches a broken split but cannot fix it.
* The dashboard does not run the optimizer itself. "What this policy allows" counts eligible items; it does not simulate profit.
