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

### Ta Feng details (from `results/public/tafeng/`)

* Converted: 656,360 lines, 114,483 customer-day baskets (93,724 with 2+ products), 31,700 customers, 5,000 products, 2000-11-01 to 2001-02-28 (119 days).
* Split: 13,675 validation events, 14,346 test events; 98.2% of test targets seen in train.
* E1 audit: median basket 4 items, 63% of customers have 2+ baskets. Co-purchase signal is real but weaker than on UCI: Hit@10 12.0% on real validation baskets vs 1.9% shuffled (6.3x lift).
* Pool recall (test) 40.4%.
* Top LightGBM features by gain: `s_itemknn_max`, `r_itemknn_max`, `s_repeat` (the customer bought it before), `r_fresh_co`, `r_itemknn`, `r_ease`.
* Stage 2, **simulated cost and stock**: ranker top-2 realized profit 2.67 per basket; MILP λ=0.5 3.12 (+0.45, 95% CI [+0.31, +0.61], about +17%) for -1.0 pt hit rate (9.2% vs 10.1%).
* Peak RAM 5.2 GB: on an 8 GB laptop this is tight; use a Kaggle CPU notebook or `--top-items 3000`.

## Code changes

* `scripts/public_datasets.py compare`: pool recall was read from `e4_retrieval.csv` at `recall@100`, a row that no longer exists since the pool grew to 150 (PR #14), so the column showed `?`. It now reads `e4_test_pool_recall` from `summary.json`, the pool's own test recall at whatever size the config sets.
* `notebooks/multi_dataset_validation.ipynb`: the full procedure (download, convert, sync, simulate-erp, run, compare, per-dataset tables). Committed without outputs (the pre-commit hook refuses outputs); an executed copy is committed next to the results.

## Branch layout

San asked (09:23) for `feat/multi-dataset` to hold only this module's files and its own README, like the other module branches. Full-tree work moved to `claude/project-thread-xv99mf`, which is the PR into `main`. `feat/multi-dataset` is refreshed with a commit whose tree is only: `README.md` (module README), `LICENSE`, `.gitignore`, the notebook, `scripts/public_datasets.py`, `tests/test_public_datasets.py`, `results/public/`, `docs/RESULTS_PUBLIC.md`, `docs/industry-plan/01-multi-dataset-validation.md` and this log. Added the branch to the README branch table, CONTRIBUTING and the WORKLOG branch map.
