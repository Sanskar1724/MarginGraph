<div align="center">

# MarginGraph · Recommendation API

**FastAPI service: POST a basket, get up to 2 margin-safe add-ons.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![API](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white) ![p50](https://img.shields.io/badge/p50-22%20ms-blue)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Recommendation API** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

Serves the trained pipeline over HTTP. The request is a basket; the response is at most 2 add-ons chosen by the Stage 2 optimizer, each re-checked against the margin floor. The production version (fallbacks, logging, auth) is being built on this branch.

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/api.py` | FastAPI app: `POST /recommend`, `GET /health`; model loaded at startup |
| `Dockerfile` | Container image |
| `scripts/loadtest.py` | Load tester |
| `results/loadtest/` | Measured: 1 worker 43 req/s, p50 22.4 ms, p95 28.1 ms; 2 workers 92 req/s at 4 users |
| `docs/RUNNING.md` | How to train the artifacts the API loads |

## Run it

Needs the core package from `main`:

```bash
git clone https://github.com/Sanskar1724/MarginGraph && cd MarginGraph
pip install -e ".[dev]" && margingraph prepare && margingraph run
margingraph serve --workers 2   # http://127.0.0.1:8000/docs
```

## License

[MIT](LICENSE)
