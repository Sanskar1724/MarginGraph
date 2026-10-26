<div align="center">

# MarginGraph · Ranker accuracy

**Candidate retrieval, baseline ladder and the LightGBM reranker, with the measured results to beat.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![Hit@10](https://img.shields.io/badge/Hit%4010-35.6%25-blue) ![recall@100](https://img.shields.io/badge/recall%40100-58.0%25-blue) ![CI](https://img.shields.io/badge/CI-paired%20bootstrap%2095%25-lightgrey)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Ranker accuracy** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

<p align="center"><img src="https://raw.githubusercontent.com/Sanskar1724/MarginGraph/main/docs/assets/results-hit10.svg" alt="Ranker accuracy diagram" width="100%"></p>

## What this module does

Stage 1 of MarginGraph. Six baselines feed a pool of up to 100 candidates (recall 58.0%); a LightGBM LambdaRank model reranks them (Hit@10 35.6% vs 31.1% for EASE, +4.5 pts, 95% CI [3.6, 5.5]). Accuracy work happens here: better candidates, features and calibration.

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/models.py` | Baselines: popularity, repeat, co-purchase, ALS, ItemKNN, EASE |
| `src/margingraph/features.py` | Candidate pools and reranker features |
| `src/margingraph/rerank.py` | LightGBM reranker, isotonic calibration |
| `src/margingraph/stats.py` | Ranking metrics, bootstrap CIs |
| `results/e3_*, e4_*, e5_*, e7_*` | Current numbers to beat |

## Run it

Experiments run through the full pipeline on `main`:

```bash
pip install -e ".[dev]" && margingraph prepare && margingraph run
```

## License

[MIT](LICENSE)
