# Work log: CI and release checks

Thread goal (San, 2026-10-26 11:37 UTC): make MarginGraph a product a retail store can rely on, using only free tools that fit an 8 GB laptop. This thread's part: automatic checks on every push, a secret scan, a measured load and latency test for the `/recommend` API, a model-quality gate, and contributor docs.

Branch: `claude/project-thread-hadeju`, merged with `main` (PRs #1 to #9) before the PR. PR: see the row for thread 9 in [`../WORKLOG.md`](../WORKLOG.md).

## What was added, and why

| File | What it does | Why |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Six jobs on every push to any branch and every PR: `lint`, `test` (Python 3.10 and 3.12), `secret scan`, `pre-commit`, `model quality gate`, `docker` | Free GitHub Actions minutes; catches broken code, leaked keys and model regressions before merge. No secrets or dataset needed. |
| `pyproject.toml` | Ruff config (`E, F, W, I, B`, line length 120), pytest `slow` marker, `margingraph-gate` command, `ruff` and `pre-commit` in `[dev]` | One lint standard for all threads |
| `src/margingraph/gate.py`, `tests/test_gate.py` | Fails when LightGBM Hit@10 on test is below the popularity baseline. `--strict` compares the ranker's 95% CI lower bound | A release must never ship a ranker worse than "show the best sellers" |
| `scripts/loadtest.py` | Standard-library load tester: N requests at concurrency C, client and server p50/p95/p99, throughput, error rate, `--max-p95-ms` budget | No extra install (locust would add gevent and a web UI the laptop does not need) |
| `scripts/fixture_bundle.py` | Builds a model bundle from the synthetic test fixture in seconds | Lets CI run the API, load test and gate without the 45 MB dataset |
| `Dockerfile`, `.dockerignore` | `python:3.11-slim` + `libgomp1`, non-root user, health check; model bundle is mounted, not baked in | Same image runs on a laptop, a free VM or a store's server |
| `.pre-commit-config.yaml`, `.gitleaks.toml`, `scripts/check_notebooks.py` | gitleaks (plus a Kaggle-key rule), private-key detection, files over 2 MB, YAML/TOML checks, merge markers, ruff, and a check that notebooks carry no cell outputs | A Hugging Face token and Kaggle key were hardcoded in an earlier notebook (fixed in PR #1). This stops it happening again |
| `src/margingraph/api.py`, `cli.py` | Load the model at startup (`MARGINGRAPH_PRELOAD=1` default); `/health` reports `model_loaded`; `margingraph serve --workers N` | Found by the load test, see below |
| `CONTRIBUTING.md` | "Checks" section: commands, what fails each CI job, how to mark slow tests, load test usage | |
| `README.md` | Static "59 passed" badge replaced by the live CI badge | |
| `results/loadtest/*.json` | Raw load-test reports on the real model | Every number below comes from these files |

Lint fixes needed to make the merged repo pass (17 findings, no behaviour change): import order in `space/` and two tests, `raise ... from e` in `dashboard/app.py` and `space/app.py`, an unused variable in `space/core.py` and in `tests/test_connectors.py`, `zip(..., strict=True)` where both sides must have equal length (`features.py`, `llm.py`, `dashboard/sample.py`, a test), loop-variable binding in a test lambda.

## Timeline and commands (UTC)

**11:45 Baseline.** Branched from `claude/project-thread-mkbaip`. Python 3.13 venv, `pip install -e ".[dev]"`, `pytest -q`: 6 passed, 1 skipped (LLM fine-tune test skips without torch), 13 s. `ruff check .` with default rules: 28 findings, mostly import order.

**11:47 Full real run for the load test.** `margingraph run --results /tmp/.../results --artifacts /tmp/.../artifacts` on `online_retail_II.xlsx`: finished in 7.5 minutes (11:47:05 to 11:54:37) on a 4-core container. `summary.json` is identical to the committed `results/summary.json` (checked the LightGBM vs EASE Hit@10 row), so the run is reproducible. Bundle size 257 MB.

**11:49 Secret scan of history.** Pattern search over `git log --all -p` on every branch for Hugging Face, GitHub, AWS, OpenAI, Google and Slack tokens and 32-hex Kaggle keys: **0 matches**. The only `KAGGLE_KEY` hit is the setup doc telling users to use Colab Secrets. (gitleaks itself runs in CI; see failures.)

**11:50 Docker.** Image builds and runs: 1.14 GB. `/health` and `/recommend` answer correctly with the fixture bundle mounted. Fixture-model load test through the container: 300/300 OK, p50 66.9 ms, p95 88.3 ms at 4 concurrent users.

**12:08 Merged `main`** (PRs #1 to #9: connectors, dashboard, Space demo, paper, docs). One merge, no conflicts. Ruff on the merged repo: 17 findings, fixed. `pytest -q`: **61 passed, 1 skipped, 22 s**.

**12:10 Real-model load test**, after the startup fix. Server: `margingraph serve --artifacts <full bundle> --workers W`. Client: `python scripts/loadtest.py --artifacts <bundle> -n 1000 -c C`, baskets of 1 to 4 random catalog items, 20 warm-up requests. Same 4-core container for client and server.

## Measured latency (real model, Online Retail II, 1,000 requests each)

| Workers | Concurrent users | OK | Throughput | Client p50 | Client p95 | Client p99 | Server p50 | Server p95 | RAM (all workers) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1000/1000 | 43.3 req/s | 22.4 ms | 28.1 ms | 33.2 ms | 19.0 ms | 24.4 ms | 478 MB |
| 1 | 4 | 1000/1000 | 36.6 req/s | 109.0 ms | 131.9 ms | 142.7 ms | 99.2 ms | 119.2 ms | |
| 1 | 8 | 1000/1000 | 34.4 req/s | 230.0 ms | 277.5 ms | 297.2 ms | 209.3 ms | 251.2 ms | |
| 2 | 1 | 1000/1000 | 45.3 req/s | 20.7 ms | 27.3 ms | 32.2 ms | 17.5 ms | 23.4 ms | 993 MB |
| 2 | 4 | 1000/1000 | 92.0 req/s | 41.8 ms | 71.3 ms | 85.3 ms | 36.4 ms | 64.0 ms | |
| 2 | 8 | 1000/1000 | 77.0 req/s | 99.5 ms | 183.6 ms | 219.0 ms | 87.8 ms | 166.4 ms | |

The 2-worker rows are from a clean rerun; a first 2-worker run gave the same numbers within 5 ms. "Server" is the `latency_ms` the API reports (candidates + LightGBM + MILP, no HTTP). Error rate was 0 in every run.

**Headline:** one user at a time, the full pipeline answers in **p50 22 ms, p95 28 ms**. With 2 workers it serves about **90 requests/s at p95 71 ms** using about 1 GB RAM, which fits an 8 GB laptop.

What this means for a store: checkout traffic of a small or mid-size shop (a few requests per second) is far below 40 req/s, so one worker is enough. More workers scale throughput until the CPU cores are used up; each worker holds its own 0.5 GB copy of the model.

## Failures and findings

| Found | What happened | What was done |
| --- | --- | --- |
| Load test | **First request took 32 s**: the 257 MB model bundle was loaded lazily on the first `/recommend` call (cold disk cache). A store's first customer after a restart would time out. | Model now loads at startup (FastAPI lifespan); the server only accepts traffic once it is ready (3.6 s on a warm cache) and `/health` reports `model_loaded`. First request after the fix: 65 ms. |
| Load test | With 1 worker, throughput **drops** as users are added (43 → 34 req/s) and latency grows linearly: the endpoint is CPU-bound Python, so threads queue on the GIL. | Added `margingraph serve --workers N`. 2 workers doubled throughput at 4 users (36.6 → 92.0 req/s). |
| Local check | The container has no access to the gitleaks release download (blocked by this environment's policy). | gitleaks runs in CI (official Docker image, free) and in pre-commit; history was checked here with a pattern scan instead (0 matches). |
| Local check | `docker build` could not reach the Debian package mirror from this container, so `apt-get install libgomp1` failed. `python:3.11-slim` does not ship `libgomp1`, which LightGBM needs. | Verified the rest of the image locally with a test-only Dockerfile that copies the host's `libgomp.so.1`; the real Dockerfile installs it with apt, which works on GitHub's runners. The `docker` CI job is the proof for the apt step. |
| Pre-commit design | `nbstripout` would rewrite all three working notebooks (metadata changes even with no outputs) and fail CI, and would churn files other branches edit. | Replaced with a check-only hook (`scripts/check_notebooks.py`) that fails if a notebook has cell outputs. The two archived notebooks in `notebooks/exploration/` keep their outputs as the record (scanned: no secrets). |
| Pre-commit design | `space/artifacts/ease.npz` (7.3 MB) is over the 2 MB large-file limit. | Excluded `space/artifacts/` (the demo model the HF Space needs). |
| Lint | Default ruff rules flagged 220 issues, mostly long lines in research code. | Chose `E, F, W, I, B` and ignored line length and one-line semicolons, so the check catches bugs (unused names, unbound loop variables, unsorted imports, lost exception context) without a mass reformat that would conflict with every open branch. |

## Model-quality gate results

| Run | LightGBM Hit@10 | 95% CI low | Popularity Hit@10 | Gate |
| --- | --- | --- | --- | --- |
| Committed real run (`results/`, test Oct to Dec 2011, 4,480 baskets) | 35.6% | 34.2% | 3.1% | PASS (strict) |
| Synthetic fixture (code test only, not a reported number) | 48.3% | 41.3% | 11.7% | PASS |

## Not verified here

- The GitHub Actions run itself: it runs on the first push; its result is on the PR's Checks tab.
- The `apt-get` step of the Dockerfile (see failures).
- Python 3.10 and 3.12 locally (only 3.13 here); CI tests both.

## How to reproduce

```bash
pip install -e ".[dev]"
ruff check . && pytest -q
margingraph-gate results --strict
margingraph run                                   # needs data/raw/online_retail_II.xlsx, ~8 min
margingraph serve --artifacts artifacts --workers 2 &
python scripts/loadtest.py --artifacts artifacts -n 1000 -c 4 --out loadtest.json
docker build -t margingraph . && docker run -p 8000:8000 -v "$PWD/artifacts:/app/artifacts:ro" margingraph
```
