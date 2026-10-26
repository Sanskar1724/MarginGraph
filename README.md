<div align="center">

# MarginGraph · Core pipeline

**Data audit, temporal split, baselines, LightGBM rerank, calibration and the margin MILP: experiments E1–E11 on real retail data.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![ranker](https://img.shields.io/badge/ranker-LightGBM-9cf) ![optimizer](https://img.shields.io/badge/optimizer-PuLP%20%2F%20HiGHS-orange) ![Hit@10](https://img.shields.io/badge/Hit%4010-35.6%25%20vs%2031.1%25%20EASE-blue) ![profit](https://img.shields.io/badge/profit-%2B17%25%20at%20--1.1%20pts%20Hit%402-brightgreen)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Core pipeline** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

<p align="center"><img src="https://raw.githubusercontent.com/Sanskar1724/MarginGraph/main/docs/assets/architecture.svg" alt="Core pipeline diagram" width="100%"></p>

## What this module does

Loads UCI Online Retail II (991,910 clean invoice lines), checks there is real basket signal, splits by time, and runs a baseline ladder (popularity, repeat, co-purchase, ALS, ItemKNN, EASE). A LightGBM LambdaRank reranker scores up to 100 candidates; isotonic calibration turns scores into purchase probabilities; a MILP picks at most 2 add-ons that maximize expected profit under a 15% margin floor, stock and discount rules. Every number is written to `results/`.

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/` | Package: data, audit, split, models, features, rerank, llm, optimize, stage2, stats, gate, pipeline, api, cli |
| `configs/default.yaml` | Split dates, pool sizes, margin floor, simulated ERP |
| `results/` | Raw outputs of E1–E11 |
| `tests/` | Pipeline and optimizer tests on a synthetic fixture |
| `notebooks/run_all.ipynb` | Same run in Colab / Kaggle |
| `docs/RESULTS.md` | Results tables |
| `docs/RUNNING.md` | Running guide |
| `docs/worklog/core-pipeline.md` | Decisions, runs, bugs and fixes |

## Run it

```bash
pip install -e ".[dev]"
margingraph prepare && margingraph run   # ~10 min on a laptop CPU
pytest tests/test_pipeline.py -q
```

## License

[MIT](LICENSE)
