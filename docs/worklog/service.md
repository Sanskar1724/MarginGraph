# Worklog: production recommendation service (thread "Build production recommendation service")

Branch `claude/project-thread-psfiei`, started from `claude/project-thread-mkbaip` (PR #2), then merged with `main` after PRs #1–#9 landed. All times UTC on 2026-10-26. Every number below comes from a command run in this thread; raw outputs are in `results/service/`.

## 1. Ask (11:37)

San: make the product fully functional and usable by a real retail store, on free resources only, on an 8 GB RAM laptop, tested, pushed to GitHub, with the plan, work, results, idea and approach written down. The coordinator scoped this thread to the serving layer: stateless FastAPI, multi-store settings, nightly batch artifacts, optional Redis with an in-memory fallback, SQLite by default and Postgres optional, stock webhook, margin-safe popularity fallback, health and metrics, A/B request logging, API keys, Docker, tests, and `docs/API.md` for the other threads.

Later instructions in the thread:
* 11:44 San: keep a record of everything → this file.
* 11:54 coordinator: align with the merchant dashboard contract (docs/DASHBOARD.md) → settings pull and the `dashboard_events` view.
* 12:08 coordinator: PRs #1–#9 are merged; merge `main` and open the PR against `main`.
* 12:08 San: all commits under San's name only → the branch is committed as `Sanskar1724` with no co-author trailer.

## 2. Decisions

| Decision | Why |
| --- | --- |
| New package `margingraph.service`, research `api.py` left untouched | The research demo stays reproducible; production code gets its own tests |
| Reuse `CandidateGenerator`, `Reranker`, `solve_enum` / `solve_milp` | One feature code path offline and online |
| SQLAlchemy Core, SQLite default, Postgres by `DATABASE_URL` | No server to install on a laptop; same code on free hosted Postgres |
| Redis optional behind one small cache interface; memory fallback; Redis errors never fail a request | Free tier friendly; a cache outage degrades speed, not answers |
| Live cost/stock from the DB, not from the bundle | Stock changes must apply at once |
| Items without `unit_cost` are never recommended | The margin floor cannot be checked without cost |
| Quality gate: LightGBM Hit@10 ≥ best single source on the newest holdout, else `rejected` | A bad retrain must not reach shoppers |
| Model path runs in a thread with a deadline; any failure → margin-safe best sellers | The checkout page must never break |
| Hashed API keys, admin key required in production, HMAC-signed order webhook | Basic security a store expects |
| Sticky SHA-256 A/B buckets; impressions, clicks, purchases logged | Measuring profit needs an A/B test, not a claim |
| Default λ changed from 1.0 to 0.5 after the replays | λ = 1 cut conversion by about 5 points (significant) and its profit gain was not significant |

## 3. What was built

| File | What it does |
| --- | --- |
| `src/margingraph/service/settings.py` | Environment settings |
| `src/margingraph/service/db.py` | Tables (stores, products, orders, order_lines, recommendations, rec_events, models), upserts, stock changes, history import, attribution lookups, report, model registry, `dashboard_events` view |
| `src/margingraph/service/cache.py` | `MemoryCache` (TTL + LRU) and `RedisCache` |
| `src/margingraph/service/schemas.py` | API models and `StoreSettings` with validation and A/B variants |
| `src/margingraph/service/engine.py` | Model registry (LRU), live catalog snapshot with incremental refresh, policy, variant hashing, model path, fallback path |
| `src/margingraph/service/train.py` | Nightly job: holdout, train, calibrate, evaluate, gate, publish, overstock refresh, pruning |
| `src/margingraph/service/app.py` | FastAPI app: auth, rate limit, recommend, catalog, inventory, orders, webhook, events, report, settings, models, admin, health, ready, metrics, dashboard settings overlay |
| `src/margingraph/service/metrics.py` | Prometheus text format without extra dependencies |
| `src/margingraph/service/cli.py` | `api`, `init-db`, `create-store`, `import-catalog`, `import-orders`, `import-sync`, `bootstrap-demo`, `batch`, `scheduler` |
| `scripts/replay.py`, `scripts/ab_report.py` | Real-order replay through the HTTP API; A/B summary with bootstrap CIs |
| `tests/test_service.py` | 19 tests |
| `Dockerfile`, `docker-compose.yml`, `docker-compose.full.yml`, `.env.example`, `.dockerignore`, `.github/workflows/ci.yml` | Container, lite and full stacks, CI on SQLite + Postgres with an image smoke test |
| `docs/API.md`, `docs/SERVICE.md` | API contract; idea, design, results, free hosting, limits |

## 4. Commands run and what came out

```bash
pip install -e ".[dev]" sqlalchemy redis "psycopg[binary]" fakeredis
ln -s /mnt/project-files/online_retail_II.xlsx data/raw/online_retail_II.xlsx
margingraph prepare                        # 1m30s; 1,067,371 raw rows -> 991,910 clean lines, 39,516 invoices, 4,707 items
margingraph bootstrap-demo --store demo    # 1m41s total: import 952,575 lines in 21.6 s, train 73 s, peak RSS 1,654 MB, bundle 259 MB
                                           # holdout (30 days, 328 events): LightGBM Hit@10 36.6% vs EASE 30.5% -> active
margingraph api --port 8000
python scripts/replay.py --key $KEY --csv data/replay_demo.csv --max-orders 1500
```

Replays (1,031 real orders from 2011-11-25 to 2011-12-09, one product hidden each, the real order posted after):

| # | Setup | Result |
| --- | --- | --- |
| 1 | SQLite, λ 0 vs 1, before the snapshot fix | p50 112 ms, p95 193 ms; all purchases missing from the report (bug 3) |
| 2 | SQLite, λ 0 vs 1, after fixes | p50 70 ms, p95 100 ms, p99 121 ms; 1,027 model / 4 fallback; hit 16.8% vs 12.0% |
| 3 | Postgres 16 + Redis 7, 2 workers, 60-day-holdout model, λ 0 vs 1 | p50 64 ms, p95 89 ms, p99 105 ms; hit 15.7% vs 10.5%; 0 errors |
| 4 | SQLite, λ 0 vs 0.5 | p50 61 ms, p95 88 ms; hit 16.1% vs 13.1% |

A/B CIs (`scripts/ab_report.py`): conversion difference −4.8 pts [−9.0, −0.5] (λ 1), −5.2 [−9.2, −1.1] (λ 1, Postgres run), −2.8 [−7.1, +1.4] (λ 0.5). Profit per request differences +4.35 [−0.92, +13.23], +0.31 [−1.59, +2.15], +3.17 [−1.71, +11.81]: none significant. Full tables in `docs/SERVICE.md`.

Other checks:

```bash
pytest -q                                       # 78 passed, 1 skipped
MARGINGRAPH_TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5433/mgtest pytest -q tests/test_service.py   # 19 passed on Postgres 16
docker build -t margingraph:test .              # 1.22 GB image (local variant, see bug 6)
docker run ... margingraph:test                 # /ready ok, model preloaded, first call 124 ms, cached 0.11 ms, 421 MB RAM, healthcheck healthy
```

The dashboard adapter was pointed at the service DB (`MARGINGRAPH_EVENTS_DB=data/margingraph.db`, `MARGINGRAPH_EVENTS_SQL="SELECT * FROM svc.dashboard_events"`) and loaded 2,209 events (2,062 impressions, 147 purchases) from replay 4.

## 5. Problems hit and fixes

| # | Problem | Cause | Fix |
| --- | --- | --- | --- |
| 1 | First request after start fell back with `timeout` (693 ms) | The 259 MB bundle loads on first use | Preload active models at start-up in a background thread; `/ready` lists loaded models |
| 2 | Replay latency p50 112 ms vs 20–37 ms for the model alone | Every order bumps the catalog version and the snapshot reloaded all 4,707 products | Snapshot refresh reads only rows with `updated_at` since the last refresh (2 s overlap); p50 dropped to about 65 ms |
| 3 | Report showed 0 purchases although about 150 add-ons were bought | Report filtered events by the order's own timestamp (2011) | Events are matched to recommendations in the window; purchase events get `max(order ts, shown ts)` |
| 4 | Replay died with 429 | The store rate limit (1,200/min) worked as designed | Replays set `rate_limit_per_minute: 0` |
| 5 | Model path paid two LightGBM passes | `proba()` rescores | Calibrate the existing score; 43 → 37 ms per basket |
| 6 | `docker build` failed here | This container's network blocks Debian mirrors (403) and plain HTTP | Verified with a local-only Dockerfile variant (proxy CA, host `libgomp`, no apt). The committed Dockerfile keeps `apt-get install libgomp1`, which works on GitHub Actions and laptops; CI builds and smoke-tests it |
| 7 | Container could not find the model | Registry stored paths relative to the trainer's working directory | Paths are stored relative to `MARGINGRAPH_ARTIFACTS` |
| 8 | Fallback was empty for a new store | No order history means no best sellers | Every sellable item competes, best sellers first, then by unit profit |
| 9 | Quality-gate test failed on the synthetic fixture | Co-purchase alone is perfect on planted pairs, so LightGBM could only tie | Gate is "≥ best single source"; separate test rigs a bad retrain and checks the old model keeps serving |
| 10 | 259 MB `artifacts_pg/` bundle got into a local commit | `.gitignore` only listed `artifacts/` | Removed before any push; `.gitignore` now has `artifacts*/` |
| 11 | Merge with `main` conflicted in `cli.py` and `.gitignore` | `main` added `sync` and `dashboard` commands | Kept both sets of commands |
| 12 | First CI run on PR #12: `test_quality_gate_keeps_the_serving_model` failed with a unique-key error | On GitHub's faster runners two trainings finished in the same second, so both got the same model version | Versions now end in a random 4-hex suffix (`20261026-122832-fce6`) |
| 13 | PR #12 conflicted with the CI PR #11 (Dockerfile, ci.yml, .dockerignore, pyproject.toml, WORKLOG.md) | Both threads added a Dockerfile and a CI workflow | One Dockerfile: the production API is the default command, and the research demo API runs from the same image with `uvicorn margingraph.api:app`. One ci.yml: #11's jobs (lint, secret scan, pre-commit, tests on 3.10/3.12, quality gate, Docker load test), plus a Postgres service for the service tests and a production API smoke test in the Docker job. `dev` extras merged |
| 14 | ruff (from #11) flagged FastAPI `Depends` defaults (B008), two `zip()` calls (B905) and an unused variable | New lint rules from main | `extend-immutable-calls` for FastAPI markers, `strict=True` on the zips, variable removed |
| 15 | pre-commit `check-yaml` rejected `!reset` in `docker-compose.full.yml` | The custom compose tag is not plain YAML | The full stack no longer has a bundled load balancer. With Postgres and Redis shared, more API copies can run behind any load balancer |
| 16 | Service tests failed on a reused Postgres database | `drop_all` cannot drop tables the `dashboard_events` view depends on | Test setup drops the view first |

## 6. Not done / open

* Real cost and stock: the demo uses the simulated ERP. A pilot store has to send real `unit_cost`.
* A profit claim needs a few thousand real checkouts per arm; the replays here are about 500 per arm and inconclusive on profit.
* Bundles use dense item-item matrices (259 MB at 4,700 items); a 50,000-item store needs sparse neighbour lists.
* The full Docker compose stack (Postgres + Redis + Caddy) was not run as containers here; the same Postgres and Redis setup was tested with native servers.
