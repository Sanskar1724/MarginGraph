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

## Rules for numbers

Every number in this repo comes from a run that is in `results/` or logged in `docs/RESULTS.md`. Simulated inputs (cost, stock) are always labelled as simulated.
