<div align="center">

# MarginGraph · CI & release checks

**GitHub Actions on every push and PR: lint, tests on Python 3.10 and 3.12, full-history secret scan, model quality gate, Docker build and API load test.**

![license](https://img.shields.io/badge/license-MIT-green) ![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white) ![lint](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=white) ![secrets](https://img.shields.io/badge/secrets-gitleaks-red) ![API p50](https://img.shields.io/badge/API%20p50-22%20ms-blue) ![Docker](https://img.shields.io/badge/Docker-build%20%2B%20smoke%20test-2496ED?logo=docker&logoColor=white)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **CI & release checks** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

Free CI that blocks a release when code breaks, a key leaks, or the ranker falls below "show the best sellers". The quality gate (`margingraph-gate`) checks LightGBM Hit@10 (35.6%, CI low 34.2%) against popularity (3.1%). The Docker job starts the API and load-tests it: 1 worker serves 43 req/s at p50 22.4 ms / p95 28.1 ms with 0 errors; 2 workers with 4 users reach 92 req/s.

## What's in this branch

| Path | What it is |
| --- | --- |
| `.github/workflows/ci.yml` | Lint, tests, secret scan, pre-commit, quality gate, Docker + load test |
| `.github/workflows/pages.yml` | Landing page deploy |
| `.pre-commit-config.yaml, .gitleaks.toml` | Local hooks and secret-scan config |
| `Dockerfile, .dockerignore` | API image |
| `scripts/` | Load tester, notebook-output check, test fixture bundle |
| `src/margingraph/gate.py, tests/test_gate.py` | Model quality gate |
| `results/loadtest/` | Measured load-test reports |
| `CONTRIBUTING.md` | Branches, workflow, checks |
| `docs/worklog/ci.md` | Work log |

## Run it

```bash
pip install pre-commit && pre-commit install   # same checks locally
margingraph-gate                                # quality gate on results/
python scripts/loadtest.py --help
```

On GitHub everything runs automatically on push and pull request.

## License

[MIT](LICENSE)
