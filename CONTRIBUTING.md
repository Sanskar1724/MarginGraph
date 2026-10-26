# Contributing

## Branches

`main` always holds the full, working project. Each module has its own long-lived branch for development; changes reach `main` through a pull request.

| Branch | Module | Main paths |
| --- | --- | --- |
| `main` | Everything, integrated and tested | all |
| `feat/core-pipeline` | Data, baselines, LightGBM rerank, MILP, simulation | `src/margingraph/`, `configs/`, `results/`, `tests/` |
| `feat/api-service` | Production recommendation API | `src/margingraph/api.py`, service code |
| `feat/ranker-accuracy` | Ranker accuracy experiments | `src/margingraph/rerank.py`, `features.py` |
| `feat/llm-reranker` | LLM reranker and LoRA fine-tune (Kaggle) | `src/margingraph/llm.py`, `notebooks/llm_*.ipynb` |
| `feat/store-connectors` | CSV/Excel, Shopify, WooCommerce sync | `src/margingraph/connectors/` |
| `feat/merchant-dashboard` | Merchant dashboard | `src/margingraph/dashboard/` |
| `feat/hf-space-demo` | Free Hugging Face Space demo | `space/` |
| `docs/project-report` | Report, roadmap, results, work log | `docs/` |
| `docs/research-paper` | arXiv-style paper | `paper/` |
| `docs/pitch-deck` | Pitch deck | `docs/deck/` |
| `docs/launch-kit` | Launch and promotion kit, landing page | `docs/launch/` |
| `ci/github-actions` | CI and release checks | `.github/workflows/` |

New short-lived work uses the same prefixes: `feat/…`, `fix/…`, `docs/…`, `ci/…`, `chore/…`, lowercase with hyphens.

## Workflow

1. Branch from the module branch (or `main`), make the change, add tests.
2. Run `pytest -q`.
3. Record what you did, why, the commands and the results in `docs/worklog/<topic>.md`.
4. Open a PR into the module branch or `main`. Use merge commits so the history stays traceable.

## Checks (run before you push)

CI runs on every push to every branch and on every PR (`.github/workflows/ci.yml`, free GitHub Actions minutes). Run the same checks locally; all of them fit on an 8 GB laptop:

```bash
pip install -e ".[dev]"
pre-commit install            # once: scans each commit for secrets, keys, large files
ruff check .                  # lint (config in pyproject.toml)
pytest -q                     # ~25 s; uses the synthetic fixture, no dataset needed
margingraph-gate results --strict   # ranker must beat popularity on Hit@10
```

| CI job | What fails it |
| --- | --- |
| `lint` | any `ruff check` error |
| `test` (Python 3.10 and 3.12) | any failing test under `tests/` (new test files are picked up automatically) |
| `secret scan` | gitleaks finds a token anywhere in git history |
| `pre-commit` | a hook fails on any file (secrets, private keys, files over 2 MB, notebook outputs) |
| `model quality gate` | LightGBM Hit@10 below popularity, on the committed real run (95% CI lower bound) or on a fresh fixture run |
| `docker` | the image does not build, the container does not answer `/health` and `/recommend`, or the load test has errors or p95 over 2 s |

Tests that need the full dataset or a GPU must be marked `@pytest.mark.slow` (or skip themselves when a package is missing, like `tests/test_llm_finetune.py`). Never commit tokens: use Kaggle/Colab secrets or environment variables. If a secret is ever committed, revoke it first, then remove it from history.

Load test against a running API:

```bash
margingraph serve --artifacts artifacts --workers 2 &
python scripts/loadtest.py --artifacts artifacts -n 1000 -c 4 --out loadtest.json
```

## Rules for numbers

Every number in this repo comes from a run that is in `results/` or logged in `docs/RESULTS.md`. Simulated inputs (cost, stock) are always labelled as simulated.
