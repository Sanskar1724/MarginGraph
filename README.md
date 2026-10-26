<div align="center">

# MarginGraph · Industry roadmap

**The plan from a tested prototype to a product real stores trust: more datasets, real cost data, a sized A/B test, hardening and free hosting.**

![license](https://img.shields.io/badge/license-MIT-green) ![phases](https://img.shields.io/badge/phases-7-blue) ![A/B](https://img.shields.io/badge/A%2FB-sample--size%20calculator-purple) ![status](https://img.shields.io/badge/status-plan%2C%20not%20results-yellow)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Industry roadmap** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

MarginGraph works offline on one public dataset with simulated cost and stock. This plan sets out the three proofs a store needs (the ranker generalizes across stores, the profit gain holds with real cost, and it wins a fair A/B test on live shoppers) and the supporting work: LLM options, production hardening, free deployment, business and outreach. Every number in it is either measured, with its source file, or clearly marked as a target.

## What's in this branch

| Path | What it is |
| --- | --- |
| `docs/industry-plan/README.md` | Overview, current measured state, phases |
| `docs/industry-plan/00-07-*.md` | Open items, multi-dataset validation, LLM options, real store data, A/B test, hardening, free deployment, business |
| `scripts/public_datasets.py` | Converts public retail datasets into files `margingraph sync csv` reads |
| `scripts/ab_sample_size.py` | How many checkouts per arm an A/B test needs |
| `tests/` | Tests for both scripts |
| `docs/worklog/industry-plan.md` | Work log |

## Run it

Start with [`docs/industry-plan/README.md`](docs/industry-plan/README.md).

```bash
python scripts/ab_sample_size.py --help
```

## License

[MIT](LICENSE)
