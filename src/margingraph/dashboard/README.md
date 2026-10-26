# Merchant dashboard

A store owner sets the margin floor, overstock weights and excluded products, and sees profit uplift, margin, overstock cleared, clicks, buys and A/B results with 95% CIs. FastAPI + plain HTML + SQLite, about 190 MB of RAM.

```bash
margingraph dashboard --sample    # demo store on http://127.0.0.1:8501 (sample data is simulated and labelled)
```

| File | Role |
| --- | --- |
| `app.py` | FastAPI routes and HTML pages |
| `db.py` | SQLite schema, settings and event storage |
| `kpis.py` | KPI and A/B computations with bootstrap CIs |
| `charts.py` | Inline SVG charts |
| `adapter.py` | Thin adapter between the event source and the KPI code |
| `sample.py` | Seeds a simulated demo store |

Guide and integration contract: [`docs/DASHBOARD.md`](../../../docs/DASHBOARD.md). Tests: `tests/test_dashboard.py`.
