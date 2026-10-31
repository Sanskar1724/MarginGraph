# Results on public retail datasets (industry plan, phase 1)

*Measured 2026-10-31 in a 4-CPU / 15 GB cloud container. Procedure: [`notebooks/multi_dataset_validation.ipynb`](../notebooks/multi_dataset_validation.ipynb). Full log: [`docs/worklog/multi-dataset.md`](worklog/multi-dataset.md). Raw summaries: [`results/public/`](../results/public/).*

Same pipeline as Online Retail II, unchanged: 150-candidate pool, LightGBM LambdaRank reranker, best baseline picked on validation and scored on test, paired bootstrap 95% CI. 5,000 most-ordered products per dataset.

**Gate (fixed before running):** LightGBM Hit@10 above the best baseline with the CI above zero on most datasets with at least 1,000 test baskets. **Result: passed, 2 of 3 public datasets (3 of 4 counting UCI).**

| Dataset | Test baskets | Pool recall | Best baseline (val) | Baseline Hit@10 | LightGBM Hit@10 | Diff [95% CI] | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UCI Online Retail II (reference) | 4,480 | 65.3% | ease | 31.1% | 38.1% | +7.0 [+6.0, +8.0] | LightGBM wins |
| Ta Feng (Taiwan grocery) | 14,346 | 40.4% | itemknn | 14.3% | 22.6% | +8.3 [+7.7, +8.8] | LightGBM wins |
| Dunnhumby (US supermarket) | 20,000 | 46.9% | repeat | 19.6% | 27.4% | +7.8 [+7.2, +8.4] | LightGBM wins |
| Instacart (US grocery delivery, 20k customers) | 20,000 | 51.7% | repeat | 37.5% | 34.5% | -3.0 [-3.6, -2.4] | baseline wins |
| Olist (Brazil marketplace) | 169 | 36.1% | ease_decay | 17.2% | 20.7% | +3.6 [-1.2, +8.9] | tie (too few baskets for the gate) |

## Caveats per dataset

- **Ta Feng:** no basket id, so one customer on one day is one basket. Files from a GitHub mirror of the Kaggle upload, SHA-256 checked.
- **Dunnhumby:** real dates are hidden; `DAY 1` mapped to 2018-01-01. Price = sales value / quantity after discounts. Weak co-purchase signal (1.7x over shuffled baskets).
- **Instacart:** no prices (Stage 2 not reported) and no real dates (rebuilt from `days_since_prior_order`). 20,000 customers sampled. 62% of lines are re-buys.
- **Olist:** 98% of orders have one product, so only 169 test events: the "sparse basket" case.

## Why Instacart lost

The pool is filled in `retrieval.per_source` order and cut at 150; `ease` and `ease_decay` fill it before the customer's own past items (`repeat`). Pool recall is 51.7%, but `repeat` alone reaches 59.5% at 100. The reranker cannot rank items that never enter the pool.

**Fix: the customer's past items first.** Same data and settings, only `repeat: 60` moved to the front of `per_source` (chosen from the diagnosis; validation pool recall went 51.5% → 68.0% before test was looked at):

| Instacart run | Pool recall (test) | LightGBM Hit@10 | vs `repeat` 37.5% | Verdict |
| --- | --- | --- | --- | --- |
| Default pool (official gate result) | 51.7% | 34.5% | -3.0 [-3.6, -2.4] | baseline wins |
| Repeat-first pool | **70.1%** | **41.6%** | **+4.1 [+3.7, +4.5]** | LightGBM wins |

Dunnhumby showed the same pattern (pool 46.9% vs `repeat` alone 45.0% at 100), so it got the same rerun:

| Dunnhumby run | Pool recall (test) | LightGBM Hit@10 | vs `repeat` 19.6% | Verdict |
| --- | --- | --- | --- | --- |
| Default pool (official gate result) | 46.9% | 27.4% | +7.8 [+7.2, +8.4] | LightGBM wins |
| Repeat-first pool | **56.7%** | **29.4%** | **+9.8 [+9.3, +10.3]** | LightGBM wins by more |

Validation pool recall rose too (46.1% → 55.3%). Simulated Stage 2 with this pool: MILP λ=0.5 +16% profit per basket (+0.015 [+0.012, +0.019]) for -0.9 pts hit rate.

So the Instacart loss came from the candidate pool, not the ranker. For stores with heavy re-buying, `repeat` should be filled first. The gate above still counts the default run, because the bar was fixed before running.

## Stage 2 (profit is not real)

| Dataset | Cost source | MILP λ=0.5 vs ranker top-2: realized profit | Hit rate change |
| --- | --- | --- | --- |
| Ta Feng | simulated | +17% (+0.45 [+0.31, +0.61] per basket) | -1.0 pt |
| Ta Feng | `ASSET` read as cost (**unverified**) | +25% (+0.15 [+0.07, +0.24]) | -5.0 pts (hit rate halves: only 76% of products clear the 15% floor) |
| Dunnhumby | simulated | +13% (+0.012 [+0.009, +0.015]) | -1.1 pts |

With thin real grocery margins a fixed 15% floor is too strict; the bundle-level floor did best on Ta Feng with `ASSET` cost (+38% profit, hit 5.8%).
