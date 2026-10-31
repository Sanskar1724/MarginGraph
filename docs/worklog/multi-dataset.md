# Work log: multi-dataset validation (industry plan, phase 1)

*Thread "Validate on more real datasets", started 2026-10-31 09:11 UTC by San. Plan: [`docs/industry-plan/01-multi-dataset-validation.md`](../industry-plan/01-multi-dataset-validation.md). Branches: work on `claude/project-thread-xv99mf` (full tree, PR into `main`); trimmed module branch `feat/multi-dataset`.*

## Goal and gate

Does the Stage 1 ranker (150-candidate pool + LightGBM LambdaRank) beat the best simple method on stores other than the UCI gift wholesaler? Gate, fixed in the plan before running: LightGBM Hit@10 above the best baseline (picked on validation, scored on test) with the paired-bootstrap 95% CI above zero, on most datasets with at least 1,000 test baskets. Stage 2 profit on these datasets uses the **simulated** cost and stock (or, for one Ta Feng run, the undocumented `ASSET` column read as cost) and is labelled that way everywhere.

## Where it ran

Claude Code cloud container: 4 CPUs, 15 GB RAM, Python 3.13, repo installed with `pip install -e .`. Nothing ran on San's laptop. The container cannot reach Kaggle, UCI, Hugging Face, Zenodo or Google Drive (proxy 403), but can reach GitHub.

## Data sources

| Dataset | Where the files came from | Check |
| --- | --- | --- |
| Olist | Olist's own GitHub repo `olist/work-at-olist-data/datasets/` (5 CSVs) | Row counts equal the Kaggle dataset: 99,441 orders, 112,650 item rows, 32,951 products |
| Ta Feng | `RecoHut-Datasets/tafeng`, branch `v1`, `ta-feng-grocery-dataset.zip` (its README cites the Kaggle dataset `chiranjivdas09/ta-feng-grocery-dataset`) | 817,741 rows, same file name and columns as Kaggle; SHA-256 `1d575e5d…7a7b67` pinned in the notebook |
| Dunnhumby | Needs San's Kaggle download (asked 09:16) | The RecoHut/TIFU-KNN copies are re-indexed with no dates or prices, so they were **not** used |
| Instacart | Needs San's Kaggle download (asked 09:16) | Same as above |

## Runs

| When (UTC) | Dataset | Options | Test baskets | Time | Peak RAM | Result |
| --- | --- | --- | --- | --- | --- | --- |
| 10-31 09:13 | Olist | `--top-items 5000`, simulated ERP | 169 | 104 s | 2.0 GB | LightGBM 20.7% vs `ease_decay` 17.2% Hit@10, diff +3.6 pts, 95% CI [-1.2, +8.9]: **tie**. Below the 1,000-basket bar, so it does not count toward the gate |
| 10-31 09:17 | Ta Feng | `--top-items 5000`, simulated ERP | 14,346 | 1,414 s (23.6 min; E10 inventory sim alone 8 min) | 5.2 GB | LightGBM 22.6% vs `itemknn` 14.3% Hit@10, diff +8.3 pts, 95% CI [+7.7, +8.8]: **LightGBM wins**. Hit@5 +5.9 [+5.4, +6.4], NDCG@10 +4.8 [+4.5, +5.1] |

### Olist details (from `results/public/olist/`)

* Converted: 62,626 lines, 61,294 orders, only 1,240 with 2+ products (2%), 60,000 customers, 5,000 products, 2016-09-04 to 2018-08-29.
* Split: 193 validation events, 169 test events. Only 65.7% of test targets were seen in train (95.9% in train or val).
* E1 audit: median basket 1 item, repeat-customer rate 2%. Co-purchase still has real signal: Hit@10 20.7% on real validation baskets vs 0.5% on shuffled ones.
* Pool recall (test) 36.1%: the hidden product is in the 150 candidates only about a third of the time, which caps any reranker.
* LightGBM was trained on 193 validation events, too few to learn much. This is the "sparse basket" case the plan predicted.
| 10-31 09:41 | Ta Feng, `ASSET` as cost | `--top-items 5000 --asset-as-cost`, no `simulate-erp` | 14,346 | 1,430 s | 5.0 GB | Stage 1 identical to the run above (same data, same seed). Stage 2 below |
| 10-31 09:52 | Dunnhumby | `--top-items 5000`, simulated ERP | 20,000 (capped) | 2,491 s (in parallel with other runs) | 6.9 GB | LightGBM 27.4% vs `repeat` 19.6% Hit@10, diff +7.8 pts, 95% CI [+7.2, +8.4]: **LightGBM wins** |
| 10-31 10:05 | Instacart | `--top-items 5000 --max-customers 20000`, simulated ERP | 20,000 (capped) | 2,402 s (in parallel) | 7.0 GB | LightGBM 34.5% vs `repeat` 37.5% Hit@10, diff -3.0 pts, 95% CI [-3.6, -2.4]: **baseline wins** |
| 10-31 10:45 | Instacart, repeat-first pool | same data; `retrieval.per_source` puts `repeat: 60` first (diagnosis below) | 20,000 | running | | |

### Ta Feng details (from `results/public/tafeng/`)

* Converted: 656,360 lines, 114,483 customer-day baskets (93,724 with 2+ products), 31,700 customers, 5,000 products, 2000-11-01 to 2001-02-28 (119 days).
* Split: 13,675 validation events, 14,346 test events; 98.2% of test targets seen in train.
* E1 audit: median basket 4 items, 63% of customers have 2+ baskets. Co-purchase signal is real but weaker than on UCI: Hit@10 12.0% on real validation baskets vs 1.9% shuffled (6.3x lift).
* Pool recall (test) 40.4%.
* Top LightGBM features by gain: `s_itemknn_max`, `r_itemknn_max`, `s_repeat` (the customer bought it before), `r_fresh_co`, `r_itemknn`, `r_ease`.
* Stage 2, **simulated cost and stock**: ranker top-2 realized profit 2.67 per basket; MILP λ=0.5 3.12 (+0.45, 95% CI [+0.31, +0.61], about +17%) for -1.0 pt hit rate (9.2% vs 10.1%).
* Stage 2 with **`ASSET / AMOUNT` read as unit cost (unverified meaning; stock still simulated)**: median product margin is 20.5% (simulated ERP: 39.4%), and only 75.8% of products clear the 15% margin floor (simulated: 96.6%); 2.5% have cost above price. Ranker top-2 realized profit 0.61 per basket; MILP λ=0.5 0.76 (+0.15, 95% CI [+0.07, +0.24], about +25%) but its hit rate halves (5.2% vs 10.1%, -5.0 pts) because the floor removes many of the products shoppers actually add. With thin grocery margins the MILP trade-off is much steeper than on simulated cost. File: `results/public/tafeng_asset_cost/e8_strategies_store_erp.csv`.
* Peak RAM 5.2 GB: on an 8 GB laptop this is tight; use a Kaggle CPU notebook or `--top-items 3000`.

### Dunnhumby details (from `results/public/dunnhumby/`)

* Files copied from San's own Kaggle download (`dunnhumby.zip`, 130 MB); `transaction_data.csv` has 2,595,732 rows, as on Kaggle. `causal_data.csv` (696 MB) is not used and was deleted after unzipping.
* Converted: 1,654,347 lines, 243,257 baskets (174,949 with 2+ products), 2,487 households, 5,000 products; `DAY 1` mapped to 2018-01-01, so dates run 2018-01-01 to 2019-12-12.
* E1 audit: median basket 3 items, median 69 baskets per household, 55% of lines are repeat purchases. Co-purchase signal is weak: Hit@10 12.5% real vs 7.2% shuffled (1.7x lift).
* Pool recall (test) 46.9%, barely above `repeat` alone at 100 (45.0%).
* Top features: `r_repeat`, `s_repeat`, `r_ease`, `r_ease_decay`, `s_ease`, `r_itemknn_max`.
* Stage 2, simulated cost: MILP λ=0.5 realized profit 0.101 vs ranker top-2 0.089 per basket (+0.012, 95% CI [+0.009, +0.015], about +13%) for -1.1 pts hit rate. (Prices are a few dollars, so per-basket profit is small.)

### Instacart details (from `results/public/instacart/`)

* Files copied from San's own Kaggle download (`instacart.zip`, 207 MB); `orders.csv` has 3,421,083 rows, as on Kaggle.
* Converted with 20,000 sampled customers (seed 42): 2,721,735 lines, 322,215 orders, 19,981 customers, 5,000 products. Dates are rebuilt from `days_since_prior_order` with every user's last order on 2017-06-30, so the test set is everyone's latest orders. **No prices** (all 1.0), so Stage 2 numbers are meaningless here and are not reported.
* E1 audit: median basket 7 items, median 10 orders per customer, 62% of lines are repeat purchases. Co-purchase lift only 1.3x over shuffled baskets.
* Top features: `s_repeat`, `r_repeat`, `r_ease_decay`, `customer_known`.

### Why LightGBM lost on Instacart (plan's checklist, in order)

1. **Pool recall:** the pool contains the hidden item 51.7% of the time, but `repeat` alone reaches 59.5% at 100 and 55.9% at 50. The pool is filled in `per_source` order and cut at 150: `ease` (90) and `ease_decay` (60) alone fill it, so the customer's own past items (`repeat`, 9th in the order) are mostly cut. LightGBM cannot rank an item that is not in the pool, while the `repeat` baseline ranks over the whole catalog. This is the cause.
2. Signal audit: weak basket co-purchase signal (1.3x), so the store is mostly about re-buying, which makes point 1 decisive.
3. Validation events: 20,000, plenty.
4. Hyperparameters: not touched.

Fix tried (chosen from the diagnosis, not from test numbers): put `repeat: 60` first in `per_source`. The original run stays the official gate result; the fix is reported next to it. The same pattern shows on Dunnhumby (pool 46.9% vs repeat@100 45.0%), so the fix is run there too.

## Code changes

* `scripts/public_datasets.py compare`: pool recall was read from `e4_retrieval.csv` at `recall@100`, a row that no longer exists since the pool grew to 150 (PR #14), so the column showed `?`. It now reads `e4_test_pool_recall` from `summary.json`, the pool's own test recall at whatever size the config sets.
* `notebooks/multi_dataset_validation.ipynb`: the full procedure (download, convert, sync, simulate-erp, run, compare, per-dataset tables). Committed without outputs (the pre-commit hook refuses outputs); an executed copy is committed next to the results.

## Branch layout

San asked (09:23) for `feat/multi-dataset` to hold only this module's files and its own README, like the other module branches. Full-tree work moved to `claude/project-thread-xv99mf`, which is the PR into `main`. `feat/multi-dataset` is refreshed with a commit whose tree is only: `README.md` (module README), `LICENSE`, `.gitignore`, the notebook, `scripts/public_datasets.py`, `tests/test_public_datasets.py`, `results/public/`, `docs/RESULTS_PUBLIC.md`, `docs/industry-plan/01-multi-dataset-validation.md` and this log. Added the branch to the README branch table, CONTRIBUTING and the WORKLOG branch map.
