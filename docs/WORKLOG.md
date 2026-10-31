# MarginGraph work log

*A record of every piece of work on this project: who asked, what was done, where it lives, and what came out. Last updated 2026-10-26 12:15 UTC.*

Each work thread keeps its own detailed log in [`docs/worklog/`](worklog/). This page is the index. Results quoted anywhere in the log come from [`RESULTS.md`](RESULTS.md); nothing is a target number.

## Threads and pull requests

| # | Thread (goal) | Started | Pull request | Branch | Status | Detailed log |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Rate MarginGraph and plan experiments | 2026-10-25 | [#1](https://github.com/Sanskar1724/MarginGraph/pull/1) Notebooks, project report, experiment plan | `claude/add-notebooks-and-plan` | Merged into `main` 2026-10-26 | [history](worklog/history-2026-10-26.md#1-review-and-experiment-plan-2026-10-25) |
| 2 | Build MarginGraph end to end | 2026-10-26 09:00 | [#2](https://github.com/Sanskar1724/MarginGraph/pull/2) Pipeline: audit, baselines, LightGBM, MILP, simulation, API | `claude/project-thread-mkbaip` → `feat/core-pipeline`, `feat/llm-reranker` | Merged into `main` 2026-10-26; E6 fine-tune NO-GO, LLM track closed (option 3) | [core-pipeline.md](worklog/core-pipeline.md), [history](worklog/history-2026-10-26.md#2-end-to-end-build-2026-10-26) |
| 3 | Write project report and roadmap | 2026-10-26 11:38 | [#3](https://github.com/Sanskar1724/MarginGraph/pull/3) Project report, roadmap, work log | `claude/project-thread-j64y7y` → `docs/project-report` | Merged into `main` 2026-10-26 | [history](worklog/history-2026-10-26.md#4-project-report-roadmap-and-work-log-2026-10-26) |
| 4 | Build production recommendation service | 2026-10-26 11:37 | [#12](https://github.com/Sanskar1724/MarginGraph/pull/12) Production service: multi-store API, nightly training, A/B logging, Docker | `claude/project-thread-psfiei` → `feat/api-service` | In review; replay of 1,031 real orders p50 about 65 ms | [service.md](worklog/service.md) |
| 5 | Deploy free live demo | 2026-10-26 11:37 | [#4](https://github.com/Sanskar1724/MarginGraph/pull/4) Free Hugging Face Space demo | `claude/project-thread-r1a0d1` → `feat/hf-space-demo` | Merged into `main` 2026-10-26 | [demo.md](worklog/demo.md) |
| 6 | Connect real store data sources | 2026-10-26 11:38 | [#5](https://github.com/Sanskar1724/MarginGraph/pull/5) Connectors: CSV/Excel, Shopify, WooCommerce + `margingraph sync` | `claude/project-thread-dxygit` → `feat/store-connectors` | Merged into `main` 2026-10-26 | [connectors.md](worklog/connectors.md) |
| 7 | Improve recommendation accuracy | 2026-10-26 11:43 | PR into `main` (see the thread) | `claude/project-thread-pxguuk` → `feat/ranker-accuracy` | Merged (PR #14); Hit@10 35.6% → 38.1%, pool recall 58.0% → 65.3% | [accuracy.md](worklog/accuracy.md) |
| 8 | Build merchant dashboard | 2026-10-26 11:43 | [#6](https://github.com/Sanskar1724/MarginGraph/pull/6) Dashboard: policy settings, KPIs, A/B results with CIs | `claude/project-thread-oyvjte` → `feat/merchant-dashboard` | Merged into `main` 2026-10-26 | [dashboard.md](worklog/dashboard.md) |
| 9 | Add CI and release checks | 2026-10-26 11:43 | [#11](https://github.com/Sanskar1724/MarginGraph/pull/11) CI: lint, tests, secret scan, quality gate, Docker, load test | `claude/project-thread-hadeju` → `ci/github-actions` | Merged into `main` 2026-10-26; API p50 22 ms / p95 28 ms measured | [ci.md](worklog/ci.md) |
| 10 | Clean up GitHub repo structure | 2026-10-26 11:53 | pushed to `main` (no PR; San said go ahead) | `claude/project-thread-t654yh` | Done; old `claude/*` branches retire as their threads finish | [repo-cleanup.md](worklog/repo-cleanup.md) |
| 11 | Write MarginGraph research paper | 2026-10-26 11:50 | [#9](https://github.com/Sanskar1724/MarginGraph/pull/9) arXiv-style paper (LaTeX, PDF, Markdown, figures) | `claude/project-thread-l6b8ga` → `docs/research-paper` | Merged into `main` 2026-10-26 | [paper.md](worklog/paper.md) |
| 12 | Create MarginGraph pitch deck | 2026-10-26 11:50 | [#7](https://github.com/Sanskar1724/MarginGraph/pull/7) 15-slide pitch deck | `claude/project-thread-42h21l` → `docs/pitch-deck` | Merged into `main` 2026-10-26 | [deck.md](worklog/deck.md) |
| 13 | Prepare launch and promotion kit | 2026-10-26 11:50 | [#8](https://github.com/Sanskar1724/MarginGraph/pull/8) Launch kit for stores, press and developers | `claude/project-thread-80g63p` → `docs/launch-kit` | Merged into `main` 2026-10-26 | [launch.md](worklog/launch.md) |
| 14 | Plan path to industry-ready product | 2026-10-26 12:38 | this PR | `docs/industry-roadmap` | Open | [industry-plan.md](worklog/industry-plan.md) |
| 19 | Update research paper and pitch deck | 2026-10-31 15:41 | PR into `main` (see the thread) | `claude/project-thread-kxf8sc` → `docs/research-paper`, `docs/pitch-deck` | Paper 15 pp with 5 datasets + store simulation; deck 14 slides | [paper-deck-update.md](worklog/paper-deck-update.md) |

PRs #1 to #9 were merged into `main` by the repo cleanup on 2026-10-26 (pushed directly, so GitHub shows them as closed). The cleanup itself is logged in [repo-cleanup.md](worklog/repo-cleanup.md): merge order, the two conflicts and how they were resolved, the test run (59 passed, 1 skipped), the restructure, and the new branches.

## Branch map

`main` holds the full, tested project. Each module branch holds only that module's files and its own README; new work branches from `main` and reaches it through a pull request. New short-lived branches use `feat/`, `fix/`, `docs/`, `ci/` or `chore/`. Details in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

| Branch | Module | Main paths | Came from |
| --- | --- | --- | --- |
| `main` | Everything, integrated and tested | all | all PRs below |
| `feat/core-pipeline` | Data, baselines, LightGBM rerank, MILP, simulation | `src/margingraph/`, `configs/`, `results/`, `tests/` | #2 `claude/project-thread-mkbaip` |
| `feat/api-service` | Production recommendation API | `src/margingraph/api.py`, service code | thread 4 (in progress) |
| `feat/ranker-accuracy` | Ranker accuracy experiments | `src/margingraph/rerank.py`, `features.py` | thread 7 (in progress) |
| `feat/llm-reranker` | LLM reranker and LoRA fine-tune (Kaggle) | `src/margingraph/llm.py`, `notebooks/llm_*.ipynb` | #2 `claude/project-thread-mkbaip` |
| `feat/store-connectors` | CSV/Excel, Shopify, WooCommerce sync | `src/margingraph/connectors/` | #5 `claude/project-thread-dxygit` |
| `feat/merchant-dashboard` | Merchant dashboard | `src/margingraph/dashboard/` | #6 `claude/project-thread-oyvjte` |
| `feat/hf-space-demo` | Free Hugging Face Space demo | `space/` | #4 `claude/project-thread-r1a0d1` |
| `docs/project-report` | Report, roadmap, results, work log | `docs/` | #3 `claude/project-thread-j64y7y` |
| `docs/research-paper` | arXiv-style paper | `paper/` | #9 `claude/project-thread-l6b8ga` |
| `docs/pitch-deck` | Pitch deck | `docs/deck/` | #7 `claude/project-thread-42h21l` |
| `docs/launch-kit` | Launch and promotion kit, landing page | `docs/launch/` | #8 `claude/project-thread-80g63p` |
| `docs/industry-roadmap` | Industry plan, A/B sizing, public dataset converters | `docs/industry-plan/` | #13 `docs/industry-roadmap` |
| `ci/github-actions` | CI and release checks | `.github/workflows/` | #11 `claude/project-thread-hadeju` |

Old `claude/*` branches are deleted once their work is in `main` (see [repo-cleanup.md](worklog/repo-cleanup.md)).

## Experiment runs

| When (UTC) | Run | Where | Result | Recorded in |
| --- | --- | --- | --- | --- |
| 2026-10-26 09:27 | E1–E11, first full CPU run (pool 50) | Claude container | LightGBM Hit@10 30.5% vs EASE 26.2%; MILP +21% profit, −2.5 Hit@2; pool recall 43.5% | superseded by next run |
| 2026-10-26 09:46 | E1–E11 rerun (EASE in pool, pool 100, train+val refit) | Claude container | LightGBM Hit@10 35.6% vs EASE 31.1%; MILP λ=0.5 +17% profit, −1.1 Hit@2; pool recall 58.0% | superseded at 12:58 |
| 2026-10-26 11:51–12:56 | Accuracy experiments A–F: 19 variants (5 new sources, pool 100/150/200, ablations, 3× training events, 4 LightGBM settings) | Claude container | Kept: 4 sources, pool 150, 3 events per invoice. Lost: item2vec and all 4 LightGBM settings | [accuracy.md](worklog/accuracy.md), `results/accuracy/` |
| 2026-10-26 12:47 | E1–E11 rerun with the accuracy config | Claude container (10 min, 3.9 GB peak RAM) | LightGBM Hit@10 38.1% vs EASE 31.1% (+2.5 pts [1.6, 3.4] vs the 35.6% run); pool recall 65.3%; MILP λ=0.5 +14% profit, −1.1 Hit@2 | `RESULTS.md` (current) |
| 2026-10-26 10:17 | LLM rerank, Qwen2.5-1.5B zero-shot | Kaggle T4 (San) | Hit@5 16.8% vs LightGBM 27.6%: **NO-GO** | `RESULTS.md` |
| 2026-10-26 10:39 | LLM rerank, Qwen2.5-3B zero-shot | Kaggle T4 (San) | Hit@5 16.6% vs 27.6%: **NO-GO** | `RESULTS.md` |
| 2026-10-26 11:19 | Option 1: LLM score as stacker feature (3B) | Kaggle T4 (San) | Hit@5 27.5% vs 27.6%, LLM weight near 0: **NO-GO** | `RESULTS.md` |
| 2026-10-26 11:43 → | Option 2 / E6: LoRA fine-tune of Qwen2.5-1.5B | Kaggle T4 (San), 3.6 GB peak | Hit@5 7.8% (random order 11.6%), blend 16.2% vs LightGBM 27.6%: **NO-GO**. LLM track closed: LightGBM ranks, LLM only for cold-start and explanations | `RESULTS.md`, [core-pipeline.md](worklog/core-pipeline.md) |

## Bugs found and fixed

| When | Bug | Fix | Commit |
| --- | --- | --- | --- |
| 2026-10-25 | V1 notebook's "OTTO" data was overwritten by a mock generator; V2 used random candidates, carts and ERP, so its 1549% claim was an artifact | Notebooks kept as history only, results marked invalid, rebuilt on real data | PR #1, PR #2 |
| 2026-10-25 | V2 notebook hardcoded a Hugging Face token and Kaggle key | Read from Colab Secrets instead; San told to rotate the keys | `c8002dd` (PR #1) |
| 2026-10-26 | Missing customer IDs were encoded wrongly | Fixed encoding of lines without a customer | `35860f9` |
| 2026-10-26 | Candidate pool recall only 43.5% | EASE added to pool, pool 100, models refit on train+val for test: 58.0% | `55cfb87` |
| 2026-10-26 | Notebook could not find the data on Kaggle | Search `/kaggle/input` for xlsx or csv | `577ea00` |
| 2026-10-26 | Notebook could run Qwen silently on CPU | Fail fast without a GPU, pin model to one GPU | `081921d` |
| 2026-10-26 | `ModuleNotFoundError: margingraph` on Kaggle after install | Import from the cloned `src/` without a kernel restart | `05555fc` |
| 2026-10-26 | `git pull` refused on Kaggle because the run rewrote tracked result files | Discard local `results/` before pulling | instructions to San |
| 2026-10-26 | Fine-tune: newest `peft` refused Kaggle's old `torchao` 0.10 | Skip peft's torchao version check | `0f22437` |
| 2026-10-26 | Fine-tune: CUDA out of memory on a T4 (logits for full 151k vocab at every position) | Keep only last-token logits, gradient checkpointing, batch 8 | `4c69f43` |
| 2026-10-26 | API: first request after restart took 32 s (lazy 257 MB model load) | Load the model at startup; `/health` reports `model_loaded` | PR #11 |
| 2026-10-26 | API: one worker loses throughput as users are added (GIL-bound) | `margingraph serve --workers N`; 2 workers: 37 → 92 req/s at 4 users | PR #11 |
| 2026-10-26 | Docs: README linked a missing `docs/experiment_plan.md` and said "no results yet" | README rewritten with current results and links | PR #3 |
| 2026-10-26 | item2vec training did not finish in 12 min (window = largest basket, hundreds of items) | Baskets capped at 50 items, window 20: about 30 s | accuracy PR |

## How to add to this log

Each thread writes `docs/worklog/<topic>.md` in a PR against `main` (merge `main` into the branch first) and adds or updates its row above: goal, PR link, status, and every result with the file it is recorded in.
