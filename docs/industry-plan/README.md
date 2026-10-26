# MarginGraph: plan to an industry-ready product

*Written 2026-10-26. Owner: San. This is a plan, not a result: every number here is either a measured result (with the file it comes from) or clearly marked as a target or an assumption. Update the checkboxes yourself as you go.*

## Why this plan exists

MarginGraph works offline on one public dataset (UCI Online Retail II: one UK gift shop, mostly wholesale buyers, 2009 to 2011, no real cost or stock). That proves the method can work. It does not prove it works for other stores, and it cannot prove the profit gain, because the cost and stock were simulated. An industry-level product needs three kinds of proof:

1. **It generalizes:** the ranker beats simple methods on several different stores' data, not just one. ([Phase 1](01-multi-dataset-validation.md))
2. **The profit gain is real:** measured with a real store's unit cost and stock. ([Phase 3](03-real-store-data.md))
3. **It works on live shoppers:** a fair A/B test on that store. ([Phase 4](04-ab-test.md))

Everything else in this folder (LLM, hardening, hosting, open items, business) supports those three.

## Where the project stands (measured, 2026-10-26)

| Area | Result | Source |
| --- | --- | --- |
| Ranker (UCI, 4,480 test baskets) | LightGBM Hit@10 **38.1%** vs EASE 31.1%, +7.0 pts [6.0, 8.0] (35.6% before the accuracy work, PR #14) | `results/e5_*.csv`, [RESULTS.md](../RESULTS.md) |
| Candidate pool | Recall@150 **65.3%** [63.9, 66.7] (was 58.0% at 100); caps every ranker | `results/e4_retrieval.csv` |
| Optimizer, simulated cost and stock | MILP λ=0.5: **+14%** realized profit per basket, −1.1 pts Hit@2; 0 margin-floor breaks (+17% against the weaker first ranker) | `results/e8_*.csv` |
| LLM ranker | Qwen2.5 1.5B and 3B zero-shot, and as a stacker feature: **NO-GO**. LoRA fine-tune (E6) of 1.5B: Hit@5 7.8% vs 27.6%, also **NO-GO**; LLM track closed | [RESULTS.md](../RESULTS.md) |
| Research API latency | p50 22 ms, p95 28 ms (1 user); about 90 req/s with 2 workers | [worklog/ci.md](../worklog/ci.md) |
| Production service | PR [#12](https://github.com/Sanskar1724/MarginGraph/pull/12), **open**: multi-store API, A/B buckets, nightly training with a quality gate, fallback. Replay p95 89 to 100 ms | `docs/SERVICE.md` on that branch |
| A/B replay on UCI (about 500 requests per arm) | λ=1: conversion −4.8 pts [−9.0, −0.5]; profit per request CI includes zero | `results/service/` on PR #12 |
| Connectors | CSV/Excel, Shopify, WooCommerce; tested on UCI via CSV, **no live store yet** | [CONNECTORS.md](../CONNECTORS.md) |

The A/B replay row matters: the margin-aware policy costs some conversion, and about 500 requests per arm was too few to show a profit gain. Phase 4 sizes the real test for that.

## The phases

| # | Phase | Needs a real shop? | Can start | Main done-criterion | File |
| --- | --- | --- | --- | --- | --- |
| 0 | Close open items | no | now | HF Space live, Pages live, PR #12 merged, branches cleaned, paper author filled | [00-open-items.md](00-open-items.md) |
| 1 | Multi-dataset validation | no | now | LightGBM vs best baseline measured on 4 more datasets, every result recorded, win or lose | [01-multi-dataset-validation.md](01-multi-dataset-validation.md) |
| 2 | LLM: finish E6, then the remaining options | no | now (Kaggle) | E6 GO or NO-GO recorded; one LLM use that passes its own gate, or a written decision to drop it | [02-llm-options.md](02-llm-options.md) |
| 3 | Real cost and stock from a pilot store | **yes** | after a store says yes | Store synced, cost known for most revenue, offline gate passed on its data | [03-real-store-data.md](03-real-store-data.md) |
| 4 | Live A/B test | **yes** | after Phase 3 | Pre-registered test run to its planned size, written up | [04-ab-test.md](04-ab-test.md) |
| 5 | Production hardening | no | now, in parallel | Security, monitoring, multi-tenant and data-protection checklists done | [05-production-hardening.md](05-production-hardening.md) |
| 6 | Free deployment | no | after PR #12 | API, database, nightly training and dashboard running on free tiers | [06-free-deployment.md](06-free-deployment.md) |
| 7 | Business and pilot outreach | no | **now** (it takes weeks to find a store) | One signed pilot store | [07-business-and-outreach.md](07-business-and-outreach.md) |

Start Phase 7 outreach on day one. Finding a pilot store is the slowest step, and Phases 3 and 4 wait for it.

## Suggested order (about 12 to 16 weeks, part-time)

This is a suggested schedule, not a promise. Weeks are counted from when you start.

| Weeks | Do |
| --- | --- |
| 1 | Phase 0 open items. Record E6. Send the first 10 outreach messages (Phase 7) |
| 2 to 4 | Phase 1 on Kaggle CPU, one dataset at a time. Phase 5 security and monitoring items. Keep outreach going |
| 4 to 5 | Phase 6: put the service online. Phase 2 follow-up (text-based candidates, cold start) |
| 5 to 7 | Phase 3 with the first pilot store (when one says yes) |
| 7 to 8 | One-week A/A test, then start the A/B test |
| 8 to 14 | A/B test runs to its planned size (Phase 4). Do not stop early |
| 14 to 16 | Write up the result, update the paper and launch kit, ask for the second store |

## How to use and update these files

- Each phase file has: **goal**, **tasks** as checkboxes, **done when**, **commands**, **files involved**, and a **prompt** to paste into a future Claude session.
- Tick a box (`- [x]`) when it is done, and add the date and where the result is saved, for example `- [x] Dunnhumby run (2026-11-10, results/public/dunnhumby/)`.
- A number moves into README, RESULTS, the paper or the launch kit only after it is measured. Targets stay marked as targets.
- Every work session writes `docs/worklog/<topic>.md` and adds a row to [docs/WORKLOG.md](../WORKLOG.md) (the project's record-keeping rule).

## Rules for every phase

- **Free tools only.** Kaggle and Colab free GPUs and CPUs, GitHub Actions, free hosting tiers. Free tiers change: check the provider's pricing page before relying on a limit quoted here.
- **8 GB laptop.** Heavy jobs (big datasets, GPUs) run on Kaggle. Keep `--top-items` at 5,000 or below on the laptop.
- **Git.** Branch from `main` with `feat/`, `fix/`, `docs/`, `ci/` or `chore/`, open a PR against `main` (see [CONTRIBUTING.md](../../CONTRIBUTING.md)). Commits are authored as `Sanskar Chandawar <152592524+Sanskar1724@users.noreply.github.com>`, with no co-author trailer.
- **No secrets in git.** Keys go in `.env` (ignored) or Kaggle/Colab/GitHub Secrets.
- **Honest numbers.** Report losses and ties as clearly as wins. Simulated cost and stock are always labelled.

## New helper scripts added with this plan

| Script | What it does | Tested |
| --- | --- | --- |
| [`scripts/public_datasets.py`](../../scripts/public_datasets.py) | `convert` Instacart, Dunnhumby, Olist or Ta Feng into the connector's `orders.csv` and `products.csv`; `simulate-erp` makes a synced config use the same simulated cost and stock as UCI; `compare` prints a LightGBM vs best-baseline table across results folders | `tests/test_public_datasets.py` on small fake files shaped like each dataset; the full chain `convert → sync csv → simulate-erp → run → compare` ran on a fake Dunnhumby file. **Not yet run on the real downloads** |
| [`scripts/ab_sample_size.py`](../../scripts/ab_sample_size.py) | Sample size and test length for the A/B test, from conversion or profit-per-visitor | `tests/test_ab_sample_size.py` against the textbook formula |

## A starting prompt for any future Claude session

Paste this first, then the phase prompt from the phase file:

```text
Repo: https://github.com/Sanskar1724/MarginGraph (main holds the full code).
Read docs/industry-plan/README.md and the phase file I name below before doing anything.
Rules: free tools only; my laptop has 8 GB RAM, so heavy jobs go to Kaggle; branch from main
(feat/, fix/, docs/, ci/, chore/) and open a PR against main; commit as
"Sanskar Chandawar <152592524+Sanskar1724@users.noreply.github.com>" with no Co-Authored-By trailer;
no secrets in git; only real measured numbers, targets marked as targets; write
docs/worklog/<topic>.md and add a row to docs/WORKLOG.md; tick the checkboxes in the phase
file with the date and where the result is saved.
```
