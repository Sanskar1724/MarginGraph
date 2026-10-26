<div align="center">

# MarginGraph · Production recommendation service

**Multi-store FastAPI service: margin-safe add-ons at checkout, live stock, built-in A/B testing, nightly retraining and safe fallbacks.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![API](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white) ![DB](https://img.shields.io/badge/DB-SQLite%20%2F%20Postgres-4169E1?logo=postgresql&logoColor=white) ![cache](https://img.shields.io/badge/cache-Redis-DC382D?logo=redis&logoColor=white) ![deploy](https://img.shields.io/badge/deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white) ![p95](https://img.shields.io/badge/p95-88%20ms%20end%20to%20end-blue)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Production recommendation service** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

`POST /v1/recommend` returns up to N add-ons with price, margin, p(accept), expected profit and a reason. Every answer passes hard rules (active, in stock, known cost, not in the basket, margin at or above the floor). Order webhooks update stock on every instance within 5 s. Sticky A/B buckets log impressions, clicks and purchases. A nightly job retrains each store and refuses to publish a model worse than the simplest baseline. No model, unknown items, a slow model or an exception all fall back to margin-safe best sellers.

Measured on real UCI baskets (cost and stock simulated): p50 61 ms, p95 88 ms end to end on SQLite; Postgres + Redis with 2 workers p50 64 ms, p95 89 ms, 0 errors. The model path alone takes about 37 ms. About 500 replayed checkouts per arm are not enough for a profit claim; that needs a real A/B test.

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/service/` | app, engine, db, cache, schemas, settings, train, metrics, cli |
| `src/margingraph/api.py` | Minimal single-store demo API |
| `tests/test_service.py` | Service tests |
| `docs/SERVICE.md` | Design, measurements, deployment |
| `docs/API.md` | API contract |
| `docker-compose*.yml, Dockerfile, .env.example` | API + nightly scheduler; optional Postgres and Redis |
| `scripts/` | Replay, A/B report, load test |
| `results/service/, results/loadtest/` | Measured replays and load tests |
| `docs/worklog/service.md` | Work log |

## Run it

```bash
cp .env.example .env            # set the admin key
docker compose up -d            # API + nightly scheduler (SQLite)
docker compose -f docker-compose.yml -f docker-compose.full.yml up -d   # + Postgres and Redis
```

Without Docker, install the package from `main` and see [`docs/SERVICE.md`](docs/SERVICE.md).

## License

[MIT](LICENSE)
