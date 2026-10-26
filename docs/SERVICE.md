# MarginGraph production service

*Built 2026-10-26. Every number on this page was measured in this repo's container on the real UCI Online Retail II data; the raw outputs are in [`results/service/`](../results/service/). Unit cost and stock are **simulated** for that dataset, so profit numbers depend on the simulation.*

## The idea

A checkout "you may also like" box usually shows the most popular or most co-bought items. They sell, but often at thin margins, and they ignore what is piling up in the warehouse. MarginGraph picks the two add-ons with the best **expected profit** for this basket, never below the store's margin floor, with extra weight on overstock. The research pipeline (`margingraph run`, [RESULTS.md](RESULTS.md)) showed the method works offline. This service runs it for real stores.

## What a store gets

* `POST /v1/recommend` at checkout: up to N add-ons with price, margin, p(accept), expected profit and a short reason ("Often bought with ..."). Contract: [API.md](API.md).
* Hard rules on every answer, from any code path: active, in stock, known cost, not already in the basket, margin at or above the floor.
* Live stock: an order webhook or inventory update changes the next answer, on every instance, within 5 seconds.
* A/B testing built in: sticky control and treatment buckets, request logging, purchase attribution, a report endpoint and a view for the merchant dashboard.
* A nightly batch job that retrains each store and refuses to publish a model that is worse than the simplest baseline.
* It keeps working when things break: no model, unknown items, slow model or an exception all fall back to margin-safe best sellers.

## Architecture

```
            shop checkout                         shop platform / connector
                 |                                         |
         POST /v1/recommend                     POST /v1/orders, /v1/inventory,
                 |                                /v1/catalog, signed webhook
   +-------------v-------------------------------------v-----------+
   |  FastAPI (stateless, 1..N copies, uvicorn workers)            |
   |   auth (hashed keys) -> rate limit -> A/B bucket -> cache     |
   |   model path (in a thread, deadline latency_budget_ms):       |
   |     candidates (EASE, ItemKNN, co-purchase, ALS, repeat, pop) |
   |     -> LightGBM LambdaRank -> isotonic p(accept)              |
   |     -> drop unsellable -> optimizer under the margin floor    |
   |   fallback path: best sellers that clear the floor            |
   +------+----------------+--------------------+------------------+
          |                |                    |
   SQLite / Postgres   Redis / memory     artifacts/<store>/<version>/bundle.pkl
   stores, products,   versions, answers,        ^
   orders, logs,       rate limits               |
   model registry                       nightly batch job (margingraph batch / scheduler)
```

Design choices and why:

| Choice | Why |
| --- | --- |
| Same `CandidateGenerator` and `Reranker` as the research pipeline | Online and offline features come from one code path, so measured accuracy carries over |
| Cost, stock and overstock read from the live catalog, not the model bundle | A stock change must not wait for the next training run |
| Catalog snapshot per instance, refreshed by reading only rows changed since the last refresh | Reloading 4,700 products on every order cost about 50 ms per request; the incremental refresh removed it |
| Exact enumeration for 2 add-ons, PuLP MILP for more | Enumeration gives the same objective as PuLP (checked in E9 and in tests) and is much faster; PuLP stays for bigger bundles |
| SQLite by default, Postgres by URL | Zero setup on an 8 GB laptop; the same SQL runs on free hosted Postgres |
| Redis optional | One instance needs nothing extra; several instances share answers and rate limits through Redis |
| Model registry with a quality gate and rollback | A bad nightly run (broken data, fewer orders) cannot reach shoppers; `POST /v1/models/{v}/activate` rolls back |
| Pickled bundles only from the service's own artifacts directory | Pickle is unsafe for untrusted files; bundles are never uploaded through the API |

## Results

### Batch job on the full dataset (all countries, 952,575 order lines, 4,707 products)

The last 14 days (to 2011-12-09, 39,335 lines) were held back to replay as live traffic. The rest was imported and trained.

| Run | Import | Train | Peak RAM | Bundle | Holdout events | LightGBM Hit@10 | Best baseline Hit@10 | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SQLite, 30-day holdout | 21.6 s | 73.0 s | 1.65 GB | 259 MB | 328 | 36.6% | EASE 30.5% | passed |
| Postgres, 60-day holdout | 41.5 s | 84.4 s | 1.68 GB | 259 MB | 565 | 34.0% | EASE 29.0% | passed |

The research pipeline measured 35.6% vs 31.1% (EASE) in its first run (38.1% after the accuracy work) on 20,000 test events, so the nightly job's small holdout gives the same picture. The 60-day holdout is now the default because it trains on more events. Holdout sets this small have wide error bars (a few points), which is why the gate only asks LightGBM to match or beat the best single source.

### Live replay through the API (real orders, one product hidden per order)

`scripts/replay.py` sends each of the first 1,031 held-back orders (2 to 50 products) to `/v1/recommend` with one product hidden, then posts the full real order with the `recommendation_id`. An add-on "converts" only when it is the product the customer really bought. Stock was decreased by every order.

| Setup | Requests | Model / fallback | Server p50 | p95 | p99 | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| SQLite, in-memory cache, 1 worker | 1,031 | 1,027 / 4 | 61–70 ms | 88–100 ms | 101–121 ms | 0 |
| Postgres + Redis, 2 workers | 1,031 | 1,027 / 4 | 64 ms | 89 ms | 105 ms | 0 |
| Docker image, SQLite, cold call after preload | 1 | model | 124 ms | | | 0 |

The model path alone takes about 37 ms per real basket in-process (profiled over 178 baskets); the rest is HTTP, logging and the order writes running in the same process. An identical repeat call is served from cache in about 0.1 ms. The 4 fallbacks were baskets with no product the model knew. The API container uses about 420 MB of RAM with one store loaded.

### A/B replays (control = λ 0, most relevant; treatment = margin-aware)

From `scripts/ab_report.py`, bootstrap 95% CIs, about 500 requests per arm:

| Treatment | Conversion control → treatment | Difference (95% CI) | Profit per request difference (95% CI) |
| --- | --- | --- | --- |
| λ = 1.0 (SQLite run) | 16.8% → 12.0% | −4.8 pts [−9.0, −0.5] | +4.35 [−0.92, +13.23] |
| λ = 1.0 (Postgres + Redis run, other model) | 15.7% → 10.5% | −5.2 pts [−9.2, −1.1] | +0.31 [−1.59, +2.15] |
| λ = 0.5 (SQLite run) | 15.7% → 12.9% | −2.8 pts [−7.1, +1.4] | +3.17 [−1.71, +11.81] |

What this says, honestly:

* The margin-aware policy **does cost conversion**. At λ = 1 the drop is about 5 points and clearly real; at λ = 0.5 it is smaller and not significant at this sample size.
* **Profit gains are not proven by these replays.** The point estimates are positive, but every profit CI includes zero. Online Retail II is wholesale, so a few orders with huge quantities dominate profit; per unit sold the difference is near zero or negative (for example −0.05 [−0.12, +0.02] at λ = 0.5).
* So the default is now λ = 0.5 (it was 1.0 in the first draft), matching the offline result (+14% realized profit for −1.1 pts Hit@2 after the accuracy work; +17% in the first run) and the dashboard's default. A store should run its own A/B test for a few thousand checkouts before trusting any profit number. The report and the dashboard are built for exactly that.

### Tests

`pytest -q`: 78 passed, 1 skipped (the skip is an optional LLM test) on SQLite. `tests/test_service.py` (19 tests) also passes against a real Postgres 16 (`MARGINGRAPH_TEST_DATABASE_URL`). Covered: the full store lifecycle over HTTP, margin floor as a hard rule, stock changes taking effect at once, fallback for unknown baskets and model-less stores, store isolation, partial catalog updates, order attribution and idempotency, webhook signatures, auth and rate limits, sticky and balanced A/B buckets, settings validation, the quality gate keeping the old model, rollback, metrics, the dashboard view and settings mapping, Redis via fakeredis, and connector folders with missing costs.

## Run it

```bash
pip install -e ".[service]"            # add ,dev for tests
margingraph prepare                    # Online Retail II at data/raw/online_retail_II.xlsx
margingraph bootstrap-demo --store demo    # import + train (~2 min, < 2 GB RAM); prints the API key once
margingraph api                        # http://localhost:8000/docs
python scripts/replay.py --key mg_... --csv data/replay_demo.csv   # optional live replay
```

Real store: `margingraph create-store shop1`, then load products and orders (API, `import-catalog` / `import-orders`, or `margingraph sync ...` followed by `margingraph import-sync shop1`), then `margingraph batch --store shop1`.

Docker: `cp .env.example .env`, edit the admin key, then `docker compose up -d` (API + nightly scheduler, SQLite). Add Postgres and Redis with `docker compose -f docker-compose.yml -f docker-compose.full.yml up -d`; with those shared, more API copies can run behind any load balancer.

## Free hosting

| Piece | Free option | Notes |
| --- | --- | --- |
| API | Hugging Face Spaces (Docker SDK, 16 GB RAM) or Render free web service (512 MB) | The image reads `PORT`. Render's 512 MB fits a small store; the 4,700-item demo needs about 420 MB to serve and 1.7 GB to train, so train elsewhere |
| Database | Neon or Supabase Postgres | set `DATABASE_URL=postgresql+psycopg://...` (both need `?sslmode=require`) |
| Cache | Upstash Redis | `REDIS_URL=rediss://...` |
| Nightly training | the `scheduler` container, a laptop cron (`margingraph batch`), or a free GitHub Actions cron with the database URL as a secret | the bundle must land where the API reads `MARGINGRAPH_ARTIFACTS`; on hosts without a persistent disk, train on the same machine as the API |
| CI | GitHub Actions (`.github/workflows/ci.yml`) | tests on SQLite and Postgres, builds the image and smoke-tests it |
| Metrics | Grafana Cloud free tier scraping `/metrics` | |

## Limits and next steps

* **Cost and stock in the demo are simulated.** Real stores must send `unit_cost`; items without it are never recommended.
* **Cold start:** a product never sold has no co-purchase signal, so only the fallback can show it. The LLM experiments ([RESULTS.md](RESULTS.md)) did not beat LightGBM at ranking; using an LLM for new items and for the "reason" text is the open idea.
* **Bundles are 259 MB for 4,700 items** (dense item-item matrices). A store with 50,000 products needs sparse top-k neighbour lists instead; that change is local to `models.py`.
* **The in-process training endpoint** (`/v1/admin/stores/{id}/train`) shares memory with live traffic; use the scheduler or `margingraph batch` for anything bigger than a small store.
* **Attribution is last-touch** within 24 hours and only counts add-ons that were shown. It cannot tell whether the shopper would have bought the item anyway; only the A/B comparison answers that.
* **One SQLite file** is fine for one machine. Several API copies need Postgres (and Redis for shared rate limits).
* The pickled bundle format ties a model to the library versions that trained it. Retrain after upgrading LightGBM or scikit-learn.
