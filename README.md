<div align="center">

# MarginGraph · Multi-dataset validation

**Does the LightGBM ranker that won on one UK gift wholesaler still win on other stores? Tested on a Brazilian marketplace, a Taiwanese grocer, a US supermarket and US grocery delivery.**

![license](https://img.shields.io/badge/license-MIT-green) ![datasets](https://img.shields.io/badge/datasets-Olist%20%C2%B7%20Ta%20Feng%20%C2%B7%20Dunnhumby%20%C2%B7%20Instacart-blue) ![stats](https://img.shields.io/badge/stats-paired%20bootstrap%2095%25%20CI-purple) ![profit](https://img.shields.io/badge/Stage%202%20profit-simulated%20cost-yellow)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [UCI results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **multi-dataset validation** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

It runs the unchanged MarginGraph pipeline on public retail datasets and compares the **LightGBM LambdaRank** reranker with the best simple method (popularity, co-purchase, item-kNN, EASE, ALS and others, picked on validation and scored on test). Metrics: Hit@5, Hit@10, NDCG@10 and candidate-pool recall, with paired bootstrap 95% confidence intervals.

The bar was fixed before running: LightGBM "generalizes" if its Hit@10 beats the best baseline with the CI above zero on most datasets with at least 1,000 test baskets. Ties and losses are reported as they are.

None of these datasets has real unit cost or stock, so this module validates **relevance**. Stage 2 profit numbers here use simulated cost and stock and are labelled simulated.

## Results so far

Full write-up: [`docs/RESULTS_PUBLIC.md`](docs/RESULTS_PUBLIC.md). Gate (fixed before running) passed: LightGBM wins on 2 of 3 public datasets with 1,000+ test baskets.

| Dataset | Test baskets | Pool recall | Best baseline Hit@10 | LightGBM Hit@10 | Diff [95% CI] | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Ta Feng (Taiwan grocery, customer-day baskets) | 14,346 | 40.4% | 14.3% (`itemknn`) | 22.6% | +8.3 [+7.7, +8.8] | **LightGBM wins** |
| Dunnhumby (US supermarket, 2 years) | 20,000 | 46.9% | 19.6% (`repeat`) | 27.4% | +7.8 [+7.2, +8.4] | **LightGBM wins** |
| Instacart (US grocery delivery, 20k customers) | 20,000 | 51.7% | 37.5% (`repeat`) | 34.5% | -3.0 [-3.6, -2.4] | baseline wins (default pool drops repeat items) |
| Instacart, repeat-first pool | 20,000 | 70.1% | 37.5% (`repeat`) | 41.6% | +4.1 [+3.7, +4.5] | **LightGBM wins** once past purchases enter the pool |
| Olist (marketplace, 98% single-item orders) | 169 | 36.1% | 17.2% (`ease_decay`) | 20.7% | +3.6 [-1.2, +8.9] | tie, too few baskets for the gate |
| *UCI Online Retail II (reference, `main`)* | 4,480 | 65.3% | 31.1% (`ease`) | 38.1% | +7.0 [+6.0, +8.0] | LightGBM wins |

## What's in this branch

| Path | What it is |
| --- | --- |
| `notebooks/multi_dataset_validation.ipynb` | The whole procedure: download, convert, sync, simulate-erp, run, compare |
| `scripts/public_datasets.py` | Converters for Instacart, Dunnhumby, Olist, Ta Feng; `simulate-erp`; `compare` |
| `tests/test_public_datasets.py` | Tests for the converters |
| `results/public/<dataset>/` | Committed summaries of each run (E1 to E11), `convert_stats.json`, `run_stats.json` |
| `docs/RESULTS_PUBLIC.md` | Write-up with the comparison table and caveats |
| `docs/industry-plan/01-multi-dataset-validation.md` | The plan and the gate |
| `docs/worklog/multi-dataset.md` | Work log: every run, time, RAM, problem |

## Run it

Needs the full project from `main`:

```bash
git clone https://github.com/Sanskar1724/MarginGraph.git && cd MarginGraph && pip install -e .
jupyter notebook notebooks/multi_dataset_validation.ipynb
```

Olist and Ta Feng download automatically. Dunnhumby and Instacart come from Kaggle (add them as inputs in a Kaggle notebook, or unzip into `data/public/<name>/`). One dataset takes about 2 to 15 minutes on 4 CPUs and fits in 8 GB of RAM with `--top-items 5000`.

## License

[MIT](LICENSE)
