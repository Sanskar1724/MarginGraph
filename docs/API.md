# MarginGraph API (v1)

The production service in `src/margingraph/service/`. Start it with `margingraph api` (default port 8000).
Interactive docs with every schema: `http://localhost:8000/docs` (OpenAPI JSON at `/openapi.json`).

All bodies are JSON unless marked CSV. Item ids are trimmed and upper-cased. Times are UTC.

## Authentication

| Header | Who | Used for |
| --- | --- | --- |
| `X-API-Key: mg_...` (or `Authorization: Bearer mg_...`) | one store | every `/v1/*` route except admin and the signed webhook |
| `X-Admin-Key: ...` | operator | `/v1/admin/*`; the value is `MARGINGRAPH_ADMIN_KEY` |
| `X-MarginGraph-Signature: <hex>` | the shop platform | `/v1/webhooks/{store_id}/orders`; hex HMAC-SHA256 of the raw body with the store's `webhook_secret` |

A store key only sees its own store. Keys are stored as SHA-256 hashes; the plain key is shown once, at creation or rotation.
Errors: `401` bad or missing key, `404` unknown thing, `409` conflict, `422` invalid body, `429` rate limit (`Retry-After: 60`).

## Recommend

`POST /v1/recommend`

```json
{"basket": ["85123A", {"item": "71053", "quantity": 2}],
 "customer_id": "13085", "session_id": "web-7f3a", "max_addons": 2, "exclude": ["22423"]}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `basket` | yes | 1–200 item ids, or `{item, quantity}` objects |
| `customer_id` | no | enables repeat-purchase features and sticky A/B buckets |
| `session_id` | no | A/B bucket and attribution when there is no customer id |
| `max_addons` | no | cap below the store's `max_addons` |
| `exclude` | no | items not to suggest in this call (adds to the store's `excluded_items`) |

Response:

```json
{
  "request_id": "7e22572c1b6242a08efaf3ca58ce1ad5",
  "store_id": "demo",
  "variant": "treatment",
  "source": "model",
  "model_version": "20261026-114841",
  "addons": [
    {"item": "21733", "description": "RED HANGING HEART T-LIGHT HOLDER", "price": 2.95, "discount": 0.0,
     "margin_pct": 0.5451, "p_accept": 0.0177, "expected_profit": 0.0285, "overstock": false, "stock": 412,
     "reason": "Often bought with White Hanging Heart T-Light Holder"}
  ],
  "basket_known": ["85123A", "71053"],
  "basket_unknown": [],
  "latency_ms": 24.6,
  "fallback_reason": ""
}
```

* `source`: `model` (LightGBM + optimizer), `cache` (same answer as a recent identical call), or `fallback`.
* `fallback_reason`: `no_model`, `unknown_basket`, `no_eligible_candidates`, `timeout` (model path took longer than `latency_budget_ms`), or `error`. A fallback answer is the store's best sellers that are active, in stock, have a known cost and clear the margin floor. `p_accept` and `expected_profit` are `null` there.
* Every add-on, from any source, is active, in stock, has a known unit cost, is not in the basket, and has `margin_pct >= margin_floor` (in `item` floor mode).
* Keep `request_id`: send it back with clicks and orders so the A/B report can credit the slate.

## Orders, feedback and reporting

`POST /v1/orders` (store key) or `POST /v1/webhooks/{store_id}/orders` (signature):

```json
{"order_id": "100234", "customer_id": "13085", "session_id": "web-7f3a",
 "recommendation_id": "7e22572c1b6242a08efaf3ca58ce1ad5", "ts": "2026-10-26T10:15:00Z",
 "lines": [{"item": "21733", "quantity": 1, "price": 2.95}], "decrement_stock": true}
```

* Idempotent on `order_id`: a repeat returns `{"duplicate": true}` and changes nothing.
* Stock of each line is decreased (never below 0) unless `decrement_stock` is false.
* Lines are stored as training history for the nightly job.
* Attribution: if `recommendation_id` is given, add-ons from that slate that appear in the order become `purchase` events. Otherwise the slates shown to the same `customer_id` or `session_id` within `attribution_hours` before the order are used, newest first, one credit per item.
* Returns `{"order_id": "...", "duplicate": false, "attributed": 1}`.

`POST /v1/orders/import` (CSV body, header `order_id,item,quantity,price,ts[,customer_id]`): one-off history import for a new store. No stock change, no attribution. Already-seen order ids are skipped.

`POST /v1/events`: `{"request_id": "...", "item": "21733", "event_type": "click" | "add_to_cart"}`.

`GET /v1/report?days=30`: per variant: `requests`, `addons_shown`, `fallback_share`, `expected_profit`, `p50/p95_latency_ms`, `clicks`, `add_to_carts`, `purchases`, `purchased_revenue`, `purchased_profit`, `requests_with_purchase`, `conversion_rate`, `profit_per_request`. For confidence intervals use `scripts/ab_report.py` or the merchant dashboard.

## Catalog and stock

`POST /v1/catalog`: `{"products": [{"item": "21733", "price": 2.95, "unit_cost": 1.34, "stock": 412, "description": "...", "category": "HOLDER", "overstock": false, "active": true}]}`
New items need `price`. For existing items only the fields you send change (send just `{"item", "unit_cost"}` to fix a cost). An item without `unit_cost` is never recommended, because its margin cannot be checked.

`POST /v1/catalog/csv`: the same as CSV, header `item,price[,unit_cost,stock,description,category,overstock,active]`.

`GET /v1/catalog/{item}`: one product as stored.

`POST /v1/inventory`: `{"changes": [{"item": "21733", "stock": 40}, {"item": "22086", "delta": -3}]}`. Give exactly one of `stock` (absolute) or `delta`. Returns `{"updated": 2, "missing": [], "catalog_version": 17}`.

Any catalog, stock or order write bumps the store's `catalog_version`. Every instance sees it within `MARGINGRAPH_VERSION_TTL_S` (default 5 s) and drops cached answers, so an item that sells out stops being offered right away.

## Store settings

`GET /v1/settings` returns the stored settings (plus `effective` after the dashboard overlay when `MARGINGRAPH_DASHBOARD_URL` is set).
`PATCH /v1/settings` merges a partial object and validates it; an invalid value returns `422` and changes nothing.

| Field | Default | Range | Meaning |
| --- | --- | --- | --- |
| `margin_floor` | 0.15 | 0–0.95 | hard minimum gross margin per add-on |
| `floor_mode` | `item` | `item`, `bundle` | floor on each add-on, or on the add-ons together |
| `max_addons` | 2 | 1–5 | slate size |
| `lam` | 0.5 | 0–1 | 0 = most relevant, 1 = most expected profit |
| `overstock_weight` | 1.5 | 1–3 | profit multiplier for overstock items |
| `discounts` | `[0.0]` | each in [0, 0.9) | discount levels the optimizer may offer |
| `discount_elasticity` | 1.5 | 0–10 | ASSUMED uplift of p(accept) per unit of discount |
| `candidates` | 20 | 2–100 | top reranked items passed to the optimizer |
| `solver` | `auto` | `auto`, `milp`, `exact` | `auto` = exact enumeration for up to 2 add-ons (same answer as the MILP), PuLP MILP above |
| `excluded_items` | `[]` | | never recommend these |
| `latency_budget_ms` | 300 | 20–5000 | deadline for the model path before the fallback answers |
| `fallback_days` | 90 | | window for best sellers |
| `attribution_hours` | 24 | | order attribution window |
| `rate_limit_per_minute` | 1200 | 0 = off | per store, across instances when Redis is used |
| `auto_overstock_weeks` | 12 | null = off | nightly job flags items with more than this many weeks of stock |
| `min_train_orders` | 500 | | the nightly job skips smaller stores (they get the fallback) |
| `experiment` | off | | `{"enabled": true, "name": "exp1", "variants": [{"name": "control", "weight": 1, "overrides": {"lam": 0}}, {"name": "treatment", "weight": 1, "overrides": {"lam": 0.5}}]}` |

Variants may override `margin_floor`, `max_addons`, `lam`, `overstock_weight`, `discounts`, `floor_mode`, `candidates`, `solver`, `excluded_items`. Buckets are a SHA-256 hash of store, experiment name and `customer_id` (else `session_id`, else random per call), so a customer stays in one variant. Changing the experiment name reshuffles everyone.

### Merchant dashboard

With `MARGINGRAPH_DASHBOARD_URL` (and `MARGINGRAPH_DASHBOARD_TOKEN`) set, the service reads `GET {dashboard}/api/stores/{id}/settings` (cached 30 s) and maps it: `margin_floor`, `max_addons`, `lam`, `overstock_weight` as is; `allow_discounts` → `discounts [0, 0.1, 0.2]`; `items.*.excluded` → `excluded_items`; `treatment_share` → experiment `control` (λ = 0) vs `treatment` (the dashboard's λ). If the dashboard is down or sends invalid values, the stored settings are used.

The other way round, the dashboard reads this service's events through the `dashboard_events` view (columns `ts, store_id, request_id, variant, event, item, price, unit_cost, overstock, qty, source`; events are `impression`, `click`, `add_to_cart`, `purchase`):

```bash
export MARGINGRAPH_EVENTS_DB=data/margingraph.db
export MARGINGRAPH_EVENTS_SQL="SELECT * FROM svc.dashboard_events"
```

## Models

`GET /v1/models`: trained versions, newest first, with status (`active`, `rejected`, `archived`) and holdout metrics.
`POST /v1/models/{version}/activate`: roll back or forward. Instances switch within about 30 s.

## Admin

| Route | Body | Returns |
| --- | --- | --- |
| `POST /v1/admin/stores` | `{"store_id": "shop1", "name": "...", "settings": {...}}` (`store_id`: lower-case letters, digits, `-`, `_`) | `201 {"store_id", "api_key", "webhook_secret"}` |
| `GET /v1/admin/stores` | | stores with product and order counts and active model |
| `POST /v1/admin/stores/{id}/rotate-key` | | new `api_key` and `webhook_secret`; the old key stops working |
| `POST /v1/admin/stores/{id}/train` | | `202`; runs the batch job inside the API process |

## Operations

| Route | Meaning |
| --- | --- |
| `GET /health` | liveness, no dependencies |
| `GET /ready` | database and cache reachable; lists loaded models; `503` if not ready |
| `GET /metrics` | Prometheus text: `margingraph_http_requests_total{path,status}`, `margingraph_recommendations_total{store,source,variant}`, `margingraph_fallbacks_total{store,reason}`, `margingraph_model_errors_total`, `margingraph_rate_limited_total`, `margingraph_orders_total`, `margingraph_attributed_addons_total`, `margingraph_recommend_latency_ms` histogram, uptime and models loaded |

Every response has `X-Response-Time-ms`.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `MARGINGRAPH_ENV` | `development` | `production` refuses to start without an admin key |
| `MARGINGRAPH_ADMIN_KEY` | `dev-admin-key` in development | admin key |
| `DATABASE_URL` | `sqlite:///data/margingraph.db` | or `postgresql+psycopg://user:pass@host/db` |
| `REDIS_URL` | empty = in-process cache | `redis://` or `rediss://` |
| `MARGINGRAPH_ARTIFACTS` | `artifacts` | model bundles, `<store>/<version>/bundle.pkl` |
| `MARGINGRAPH_CONFIG` | `configs/default.yaml` | model and feature config used by the batch job |
| `MARGINGRAPH_VERSION_TTL_S` | 5 | how long an instance trusts its catalog version |
| `MARGINGRAPH_RESPONSE_CACHE_TTL_S` | 300 | cached answer lifetime |
| `MARGINGRAPH_MAX_LOADED_MODELS` | 4 | stores kept in memory per instance (about 300 MB each for a 4,700-item store) |
| `MARGINGRAPH_PRELOAD` | 1 | load active models at start-up |
| `MARGINGRAPH_LOG_REQUESTS` | 1 | write every recommendation to the log tables |
| `MARGINGRAPH_DASHBOARD_URL`, `MARGINGRAPH_DASHBOARD_TOKEN` | empty | pull settings from the merchant dashboard |
| `MARGINGRAPH_CORS_ORIGINS` | `*` | comma-separated origins for browser calls |

## Minimal integration (any shop platform)

```bash
# 1. operator creates the store
curl -X POST $MG/v1/admin/stores -H "X-Admin-Key: $ADMIN" -H 'content-type: application/json' -d '{"store_id":"shop1"}'
# 2. shop backend loads the catalog (with cost) and order history
curl -X POST $MG/v1/catalog/csv   -H "X-API-Key: $KEY" -H 'content-type: text/csv' --data-binary @products.csv
curl -X POST $MG/v1/orders/import -H "X-API-Key: $KEY" -H 'content-type: text/csv' --data-binary @orders.csv
# 3. operator trains (or waits for the nightly job)
margingraph batch --store shop1
# 4. at checkout
curl -X POST $MG/v1/recommend -H "X-API-Key: $KEY" -H 'content-type: application/json' -d '{"basket":["85123A"],"customer_id":"42"}'
# 5. on every paid order
curl -X POST $MG/v1/orders -H "X-API-Key: $KEY" -H 'content-type: application/json' -d @order.json
```

Shopify and WooCommerce exports can go through `margingraph sync` first (docs/CONNECTORS.md) and then `margingraph import-sync shop1 --folder data/store`.
