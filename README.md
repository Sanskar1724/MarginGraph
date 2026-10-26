<div align="center">

# MarginGraph · Merchant dashboard

**Store owners set margin floor and overstock rules, and see profit uplift and A/B results with 95% CIs.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![web](https://img.shields.io/badge/web-FastAPI%20%2B%20HTML-009688?logo=fastapi&logoColor=white) ![storage](https://img.shields.io/badge/storage-SQLite-003B57?logo=sqlite&logoColor=white) ![RAM](https://img.shields.io/badge/RAM-~190%20MB-lightgrey)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Merchant dashboard** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

Per-store policy settings (margin floor, overstock weights, excluded products) and KPIs: profit uplift, margin, overstock cleared, clicks, buys, and A/B results with bootstrap CIs. Server-rendered SVG charts, no JS chart library. Sample data is simulated and labelled.

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/dashboard/` | app, db, kpis, charts, adapter, sample |
| `tests/test_dashboard.py` | KPI, storage and route tests |
| `docs/DASHBOARD.md` | Guide and integration contract |
| `results/item_descriptions.csv` | Product titles for the demo store |
| `docs/worklog/dashboard.md` | Work log |

## Run it

```bash
margingraph dashboard --sample   # http://127.0.0.1:8501
```

Needs the core package from `main`.

## License

[MIT](LICENSE)
