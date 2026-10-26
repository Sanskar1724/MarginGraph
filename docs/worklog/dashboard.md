# Worklog: merchant dashboard (thread "Build merchant dashboard")

Branch `claude/project-thread-oyvjte`, based on `claude/project-thread-mkbaip` (PR #2). All times are UTC on 2026-10-26.

## 1. Ask (11:43)

San asked for a product a real retail store could use, built only on free tools that run on an 8 GB laptop.
The coordinator split the work, and this thread got the **merchant dashboard**. A store owner should be able to:
* set the margin floor, overstock weights and excluded products;
* see profit uplift, margin, overstock cleared, recommendation clicks and buys, and A/B results with CIs.

A parallel thread ("Build production recommendation service") is adding the API, per-store settings and request logging.
So the dashboard needed a thin adapter, and it had to work on sample data alone.
At 11:44 San also asked for a full record of the work, which is this file.

## 2. Decisions

| Decision | Why |
| --- | --- |
| FastAPI and server-rendered HTML, not Streamlit | FastAPI is already a dependency, so nothing new to install. Streamlit pulls in ~100 MB of extras and reruns the whole script on every click. Plain HTML forms also work on phones. |
| Inline SVG charts drawn in Python | No CDN, no JS bundle, and the page works offline. Hover tooltips use SVG `<title>`. |
| One SQLite file | Free, zero setup, and the recommendation service can read the same file. |
| Welch normal CIs instead of bootstrap | This is what commercial A/B tools report. It is fast on a laptop, and exact enough at 1,000+ requests per arm. |
| Request-level unit of analysis | A shown slate is what gets randomized, so the CI is computed on the randomized unit. |
| Sample events are tagged `source='sample'` and the page shows a banner | San wants claims to come from real experiments. Simulated numbers must never look measured. |
| Sample per-item buy rates come from E8 (16.7% vs 15.6% Hit@2) | This anchors the demo to a real offline result. The treatment converts less, so the profit gain is not built into the simulation. |
| Settings history table | Any record of who changed what makes A/B results explainable later ("the floor went to 20% on day 12"). |
| Real product descriptions extracted once into `results/item_descriptions.csv` (156 KB) | The full xlsx is 43 MB and takes 70 s to read; the dashboard should start instantly. |

## 3. What was built

| File | What it does |
| --- | --- |
| `src/margingraph/dashboard/db.py` | Schema (`settings`, `item_rules`, `settings_history`, `catalog`, `events`), validated settings save, item rules, event insert, catalog import |
| `src/margingraph/dashboard/adapter.py` | The only place events are read. Uses `MARGINGRAPH_EVENTS_DB` / `MARGINGRAPH_EVENTS_SQL` to map another log. Fills missing price, cost or overstock from the catalog. |
| `src/margingraph/dashboard/kpis.py` | Per-request table, totals, Welch A/B with relative-uplift CI, SRM test, MDE, daily series, top items, policy preview |
| `src/margingraph/dashboard/charts.py` | SVG line chart (profit per request by day) and forest plot (A/B uplift with CIs) |
| `src/margingraph/dashboard/app.py` | HTML pages and JSON API; optional token auth |
| `src/margingraph/dashboard/sample.py` | Demo store: real catalog, simulated A/B events |
| `src/margingraph/cli.py` | `margingraph dashboard [--sample] [--catalog CSV --store ID] [--db] [--port]` |
| `tests/test_dashboard.py` | 11 tests |
| `docs/DASHBOARD.md` | User guide and integration contract |

## 4. Commands run and results

```bash
pip install -e ".[dev]"                     # FastAPI 0.162, PuLP 4.2
python desc.py                              # extract descriptions from online_retail_II.xlsx: 4563 items, 100% matched, 70 s
python -m pytest -q tests/test_dashboard.py # 11 passed in 1.6 s
python -m pytest -q                         # whole repo: 17 passed, 1 skipped, 10 s
margingraph dashboard --sample              # seeded 4,563 catalog items, 27,773 events over 28 days
```

* **Performance** (sample store, about 11,000 requests): the server's RSS is 190 MB. `/store/demo` takes 0.33 s, `/store/demo/settings` 0.02 s and `/api/stores/demo/kpis?days=all` 0.25 s. Seeding takes 3.4 s.
* **Screenshots** were taken with Playwright at 1200 px light, 1200 px dark, the settings page, and a 390 px phone. None of them scroll horizontally. Wide tables and charts scroll inside their card on phones.
* **Demo A/B readout (SIMULATED, not evidence).** Profit per request was £0.266 for control and £0.316 for treatment, +18.8% (95% CI +0.1% to +37.5%, p = 0.034). Conversion was 17.05% vs 15.76% (−7.5%, CI crosses zero). Margin was 40.5% vs 43.0%. The SRM p-value was 0.38, so the split looks fine. These numbers only show that the plumbing works.

## 5. Problems hit and fixes

| Problem | Fix |
| --- | --- |
| A string edit to the top-items table left an unterminated f-string, so the test import failed with a SyntaxError | Rejoined the string and re-ran the tests (11 passed) |
| Negative money printed as `£-0.024` | `fmt` now prints `-£0.024` |
| The forest plot colored significant results with the treatment series color, which mixed up identity and status | Significant positive results are now green and significant negative ones red. Others are gray, and the ✓ label carries the meaning without color. |
| Events logged without an `overstock` flag were stored as 0, so the catalog lookup never ran | The column is now nullable. NULL means "look it up in the catalog". |
| `pkill -f` in a test script matched its own shell and killed it | Started the server on a new port instead |
| The production service thread had not pushed `docs/API.md` when this was built | The adapter env vars let the dashboard read that service's log once its schema is known, with no code change. `GET /api/stores/{id}/settings` is the contract offered to it. |

## 6. Still open

* Wire the production service to the dashboard: read settings from `/api/stores/{id}/settings` and log impressions, clicks and purchases. If it uses its own log table, set the two adapter env vars.
* A real pilot store's catalog with real unit costs. Until then, every profit number is simulated.
* CSRF protection, if the dashboard is ever exposed without the token.
