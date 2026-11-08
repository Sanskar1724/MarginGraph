# Dataset with real cost and price (2026-11-08)

Asked by San: "search dataset that is perfect, like that has cost and price also i can see result."

Goal: MarginGraph's biggest gap is that unit cost and stock are simulated on Online Retail II. Find a free public dataset with per-item cost **and** selling price (ideally baskets, customer ids and stock), run the full pipeline on it in the cloud container, and compare MarginGraph's profit with the ranker-only baseline.

Notebook: [`notebooks/real_cost_adventureworks.ipynb`](../../notebooks/real_cost_adventureworks.ipynb) (committed cleared). Executed copy with every output: [`results/public/adventureworks_real_cost/real_cost_adventureworks_executed.md`](../../results/public/adventureworks_real_cost/real_cost_adventureworks_executed.md).

## 1. Search and shortlist

Searched Kaggle, UCI, Zenodo, Microsoft sample databases, open-government data and academic retail panels. Ranked by fit (baskets + customers + price + cost + stock) and by whether the container can download it (GitHub works; Kaggle, UCI, Zenodo and most other sites return 403 through the proxy).

| Rank | Dataset | Real shop? | Baskets + customers | Price | Cost | Stock | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **AdventureWorks** (Microsoft sample, bikes and gear, MIT licence) | No, sample company | 27,659 online orders, 18,484 customers, 130 products | Per line | `StandardCost` + dated `ProductCostHistory` | `ProductInventory` per location | **Run** (plain CSVs in the GitHub release) |
| 2 | Wide World Importers (Microsoft sample wholesaler) | No | ~70k invoices, 663 business customers, 227 items | Yes | `LineProfit`, `LastCostPrice` | `StockItemHoldings` | Next. Downloaded the `.bacpac` (61 MB) but its tables are SQL Server native BCP, which needs SQL Server to export |
| 3 | Ta Feng (Taiwan grocery) | Yes | Customer-day baskets | Yes | Maybe (`ASSET`, undocumented) | No | Already run in PR #17 |
| 4 | Dominick's Finer Foods (Kilts Center) | Yes | No, store-week totals | Yes | Gross margin per product-week | No | Not a basket dataset; site blocked |
| 5 | Superstore / Global Superstore (Tableau sample) | No | ~2 lines per order | Yes | `Profit` per line | No | Kaggle only; weaker than #1 |
| 6 | Iowa Liquor Sales (state open data) | Yes | Store orders | Yes | `State Bottle Cost` | No | Fixed ~50% legal markup, so margins barely vary; site blocked |
| 7 | Contoso (Microsoft sample) | No | Online sales | Yes | Yes | Yes | SQL Server backup only, very large |

Finding: no free dataset of a **real** shop has baskets **and** a documented per-item cost. AdventureWorks is the best one that can actually run: cost and stock are the company's own books, but the company is a sample. Real cost still needs a pilot store.

## 2. Code changes

* `scripts/public_datasets.py`: new `adventureworks` converter (`--channel online|reseller|all`, default online). Price = what the shopper paid after the line discount. Cost = the `ProductCostHistory` cost in force on each order date (fallback `StandardCost`), quantity-weighted per product. Stock = inventory summed over locations; products without an inventory row are left unknown, not zero. `convert_stats.json` now records `has_stock`.
* `src/margingraph/sim.py`: new `--erp` option. By default it now uses `<results>/erp_store.csv` when the store has its own cost and stock, else `erp_simulated.csv` as before (UCI results unchanged: `results/` has no `erp_store.csv`).
* `tests/test_public_datasets.py`: the converter test covers `adventureworks`, plus a test for cost-at-order-date, stock summing and the online filter. Full suite: 91 passed, 2 skipped.

## 3. Runs (Claude Code cloud container, 4 CPUs, 15 GB RAM)

| When (UTC) | Run | Time | Peak RAM | Result |
| --- | --- | --- | --- | --- |
| 11-08 06:25 | Download `AdventureWorks-oltp-install-script.zip` from Microsoft's GitHub release | seconds | | SHA-256 `58962e94…c5bd42`, 17.5 MB |
| 11-08 06:26 | `convert adventureworks --top-items 0` | 2 s | | 60,398 lines, 27,659 orders (17,991 with 2+ products), 18,484 customers, 130 products, 2022-05-30 to 2025-06-29. Cost and stock for 100% of products |
| 11-08 06:27 | `margingraph run` (first try, wrapped in `/usr/bin/time`) | | | Failed: `/usr/bin/time` not installed. Reran with a Python wrapper |
| 11-08 06:28 | `margingraph run`, store ERP | 143 s | 1.05 GB | Below |
| 11-08 06:31 | `python -m margingraph.sim --days 30 --seeds 5` | 21 s | | Below |
| 11-08 06:33 | Notebook executed end to end (`nbconvert --execute`) | ~3 min | | First try stopped at the chart: matplotlib was not installed in the container; installed and reran from scratch. Same numbers as the manual run |

## 4. Results

Split: train to 2025-02-12, validation to 2025-04-14, test 2025-04-15 to 2025-06-29 (3,357 test events).

**Margins (store's own cost):** bikes 35 to 48% (median price $1,120), accessories 63% (median $25), clothing 23 to 63%. No product is under 15%, so the fixed 15% floor removes nothing, and the item floor and the bundle floor give identical results. A store-specific floor is not needed for this shop.

**Stage 1:** LightGBM Hit@10 80.8% vs EASE 75.4%, +5.4 pts [+4.4, +6.4]: **LightGBM wins**. Hit rates are high because there are only 130 products and the 150-item pool covers all of them (pool recall 100%).

**Stage 2, per test checkout, store's own cost and stock** (`e8_strategies_store_erp.csv`, `e8_paired_vs_ranker_top2.csv`):

| Strategy | Hit rate | Realized add-on profit | vs ranker [95% CI] |
| --- | --- | --- | --- |
| Ranker top-2 (baseline) | 43.6% | $11.69 | |
| MILP λ = 0.25 | 42.7% | $15.20 | +$3.52 [+0.32, +6.66], +30% |
| MILP λ = 0.5 | 41.3% | $18.55 | +$6.86 [+3.28, +10.39], +59%, hit −2.2 pts |
| MILP λ = 0.75 | 39.2% | $21.69 | +$10.00 [+5.95, +13.95], +86%, hit −4.4 pts |
| MILP λ = 1.0 | 18.1% | $24.10 | +$12.41 [+7.94, +16.69], +106%, hit −25.4 pts |

Floor violations: 0 for every MILP strategy. Overstock weights (1.25 to 2.0) change almost nothing: the inventory is a single snapshot taken after the sales period and it is large next to online demand, so 95% of products count as overstock.

**Why the profit rises:** bikes are 11% of the ranker's offers, 24% at λ = 0.5 and 65% at λ = 1.0. A bike is less likely to be taken than a helmet, but one accepted bike earns hundreds of dollars.

**30-day store simulation** (λ = 1, `retail_sim/summary.csv`): replay of real test checkouts: MarginGraph $80,898 of add-on profit vs $39,240 for the ranker (+106%), accept rate 9.1% vs 21.8%, 0 floor breaks. Stochastic (5 seeds): $133,226 ± 17,522 vs $49,504 ± 7,711.

## 5. In simple words

We could not find a free dataset from a real shop that has shopping baskets *and* the shop's own cost. The closest is Microsoft's AdventureWorks sample bike shop: a pretend company, but with real-looking books (each product's cost, price and stock), so for the first time MarginGraph ran without any simulated cost. The ranker still beats the best simple method, and MarginGraph still earns more profit than the ranker alone: about +59% at the balanced setting (λ = 0.5) for a small drop in how often the shopper takes the add-on. The gain is bigger than on simulated cost because this shop mixes $25 accessories with $1,000+ bikes. Treat it as a strong sanity check, not proof for a real store.

## 6. Next

* Wide World Importers needs a SQL Server export (free SQL Server Express or Docker image) to turn its `.bacpac` into CSVs; it would add a B2B wholesaler with real line profit and stock.
* The real test is still a pilot store's own cost data (San's to-do).
