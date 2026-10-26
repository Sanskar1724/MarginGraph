# Work log: plan to an industry-ready product

Thread: *Plan path to industry-ready product*. Branch `docs/industry-roadmap` (from `main` at `a395bc9`), PR against `main`.

## 2026-10-26 12:35 to 12:39 UTC: the ask

- San asked whether one dataset is enough for an industry-level product. The coordinator answered no: Online Retail II is one UK gift wholesaler (2009 to 2011) with no real cost or stock; the product needs validation on several stores' data, real cost and stock from a pilot store, and a live A/B test.
- San: make a new branch with the whole plan of action, so San can carry it out alone after the credits run out, and update it themselves.

## What was done

| Time (UTC) | Step | Result |
| --- | --- | --- |
| 12:40 | Read `main` (README, RESULTS, ROADMAP, WORKLOG, every `docs/worklog/*.md`, CONNECTORS, RUNNING, configs, CLI) and open PR #12 (production service: SERVICE.md, API.md, service worklog) | Open items and every number in the plan taken from these files |
| 12:44 | Wrote `scripts/public_datasets.py`: `convert` (Instacart, Dunnhumby, Olist, Ta Feng → the connector's `orders.csv` / `products.csv`), `simulate-erp`, `compare` | |
| 12:45 | Tested on small fake files shaped like each dataset's real files: `convert` → `margingraph sync csv` → `simulate-erp`, all four OK | |
| 12:46 | Full chain on the fake Dunnhumby file: `margingraph run` (E1 to E11) in 20 s, then `compare` | Chain works. The fake data's numbers mean nothing and are not recorded as results |
| 12:46 | `compare` on the committed UCI `results/` reproduces RESULTS.md: LightGBM 35.6% vs EASE 31.1%, +4.5 [+3.6, +5.5], pool recall 58.0% | Script reads the files correctly |
| 12:47 | Wrote `scripts/ab_sample_size.py` (conversion and profit-per-visitor sample sizes) and its test against the textbook formula (5% → 6%: 8,155 per arm) | |
| 12:48 to 12:55 | Wrote `docs/industry-plan/` (README + phases 0 to 7, each with tasks, done-criteria, commands, files and a prompt for a future session); links from README, docs/README, ROADMAP | |

## Decisions

| Decision | Why |
| --- | --- |
| Public datasets validate Stage 1 only; their Stage 2 uses the same simulated ERP as UCI (`simulate-erp`) | None has real unit cost; the connector's default (cost = 60% of price for every item) would make the margin floor and profit objective meaningless |
| `--top-items 5000` by default | EASE fits a dense item x item matrix; 5,000 items is about 200 MB per copy and stays near the UCI run's footprint on an 8 GB laptop |
| Instacart: synthetic dates, each user's last order on 2017-06-30; price 1.0 | Instacart has neither real dates nor prices; written as a caveat in the plan |
| Ta Feng `ASSET` as cost only behind `--asset-as-cost`, labelled unverified | The dataset does not document the column |
| Kaggle CPU notebooks recommended for Phase 1 | Free, more RAM than the laptop, datasets attach without downloading |
| A/B test sized for profit per checkout, not conversion | PR #12's UCI replay: with about 500 requests per arm every profit CI included zero |
| Sample-size table in the plan is labelled as formula output | It is a calculation from assumed base rates, not a result |

## Not done here (needs San or a later session)

- The converters have not been run on the real downloads (this container has no Kaggle access). Kaggle slugs in the plan are marked "check it".
- Everything in `docs/industry-plan/00-open-items.md` that needs San's accounts (HF Space, Pages, branch deletion, paper author).

## Tests

`pytest -q`: 67 passed, 1 skipped (the optional LLM test). `ruff check .`: clean. New: `tests/test_public_datasets.py` (4), `tests/test_ab_sample_size.py` (2).
