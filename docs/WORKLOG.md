# MarginGraph work log

*A record of every piece of work on this project: who asked, what was done, where it lives, and what came out. Last updated 2026-10-26 11:56 UTC.*

Each work thread keeps its own detailed log in [`docs/worklog/`](worklog/). This page is the index. Results quoted anywhere in the log come from [`RESULTS.md`](RESULTS.md); nothing is a target number.

## Threads and pull requests

| # | Thread (goal) | Started | Pull request | Branch | Status | Detailed log |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Rate MarginGraph and plan experiments | 2026-10-25 | [#1](https://github.com/Sanskar1724/MarginGraph/pull/1) Add notebooks, project report, and experiment plan | `claude/add-notebooks-and-plan` | Merged into `main` 2026-10-26 | [history](worklog/history-2026-10-26.md#1-review-and-experiment-plan-2026-10-25) |
| 2 | Build MarginGraph end to end | 2026-10-26 09:00 | [#2](https://github.com/Sanskar1724/MarginGraph/pull/2) Pipeline: audit, baselines, LightGBM, MILP, simulation, API | `claude/project-thread-mkbaip` | Merged into `main` 2026-10-26; E6 fine-tune running on Kaggle | [history](worklog/history-2026-10-26.md#2-end-to-end-build-2026-10-26) |
| 3 | Write project report and roadmap | 2026-10-26 11:38 | [#3](https://github.com/Sanskar1724/MarginGraph/pull/3) Project report, roadmap, work log | `claude/project-thread-j64y7y` (into #2) | Merged into `main` 2026-10-26 | [history](worklog/history-2026-10-26.md#4-project-report-roadmap-and-work-log-2026-10-26) |
| 4 | Build production recommendation service | 2026-10-26 11:37 | in progress | | In progress | added when its PR lands |
| 5 | Deploy free live demo | 2026-10-26 11:37 | [#4](https://github.com/Sanskar1724/MarginGraph/pull/4) Free Hugging Face Space demo for retail stores | `claude/project-thread-r1a0d1` (into #2) | Merged into `main` 2026-10-26 | [demo.md](worklog/demo.md) |
| 6 | Connect real store data sources | 2026-10-26 11:38 | [#5](https://github.com/Sanskar1724/MarginGraph/pull/5) Store data connectors: CSV/Excel, Shopify, WooCommerce + `margingraph sync` | `claude/project-thread-dxygit` (into #2) | Merged into `main` 2026-10-26 | [connectors.md](worklog/connectors.md) |
| 7 | Improve recommendation accuracy | 2026-10-26 11:43 | in progress | | In progress | added when its PR lands |
| 8 | Build merchant dashboard | 2026-10-26 11:43 | [#6](https://github.com/Sanskar1724/MarginGraph/pull/6) Merchant dashboard: policy settings, KPIs and A/B results with CIs | `claude/project-thread-oyvjte` (into #2) | Merged into `main` 2026-10-26 | [dashboard.md](worklog/dashboard.md) |
| 9 | Add CI and release checks | 2026-10-26 11:43 | in progress | | In progress | added when its PR lands |
| 10 | Clean up GitHub repo structure | 2026-10-26 11:53 | pushed to `main` (no PR; San said go ahead) | `claude/project-thread-t654yh` | Done; old `claude/*` branches retire as their threads finish | [repo-cleanup.md](worklog/repo-cleanup.md) |

## Experiment runs

| When (UTC) | Run | Where | Result | Recorded in |
| --- | --- | --- | --- | --- |
| 2026-10-26 09:27 | E1–E11, first full CPU run (pool 50) | Claude container | LightGBM Hit@10 30.5% vs EASE 26.2%; MILP +21% profit, −2.5 Hit@2; pool recall 43.5% | superseded by next run |
| 2026-10-26 09:46 | E1–E11 rerun (EASE in pool, pool 100, train+val refit) | Claude container | LightGBM Hit@10 35.6% vs EASE 31.1%; MILP λ=0.5 +17% profit, −1.1 Hit@2; pool recall 58.0% | `RESULTS.md` (current) |
| 2026-10-26 10:17 | LLM rerank, Qwen2.5-1.5B zero-shot | Kaggle T4 (San) | Hit@5 16.8% vs LightGBM 27.6%: **NO-GO** | `RESULTS.md` |
| 2026-10-26 10:39 | LLM rerank, Qwen2.5-3B zero-shot | Kaggle T4 (San) | Hit@5 16.6% vs 27.6%: **NO-GO** | `RESULTS.md` |
| 2026-10-26 11:19 | Option 1: LLM score as stacker feature (3B) | Kaggle T4 (San) | Hit@5 27.5% vs 27.6%, LLM weight near 0: **NO-GO** | `RESULTS.md` |
| 2026-10-26 11:43 → | Option 2 / E6: LoRA fine-tune of Qwen2.5-1.5B | Kaggle T4 (San) | Running, after two fixes (see history) | to be recorded |

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
| 2026-10-26 | Docs: README linked a missing `docs/experiment_plan.md` and said "no results yet" | README rewritten with current results and links | PR #3 |

## How to add to this log

Each thread writes `docs/worklog/<topic>.md` in its own PR and adds or updates its row above: goal, PR link, status, and every result with the file it is recorded in.
