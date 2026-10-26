# Results

Raw outputs of `margingraph run` (UCI Online Retail II, seed 42). The tables in [`docs/RESULTS.md`](../docs/RESULTS.md) are built from these files.

| File | Experiment |
| --- | --- |
| `clean_log.json` | Data cleaning counts |
| `e1_audit.json`, `e1_top_pairs.csv` | E1 signal audit |
| `e2_split.json` | E2 temporal split |
| `e3_baselines.csv` | E3 baseline ladder |
| `e4_retrieval.csv` | E4 candidate recall |
| `e5_rerank.csv`, `e5_paired.csv`, `e5_importance.csv` | E5 LightGBM reranker |
| `e7_calibration.json`, `e7_reliability_test.csv` | E7 calibration |
| `e8_strategies_simulated_erp.csv`, `e8_paired_vs_ranker_top2.csv` | E8 Stage 2 strategies |
| `e9_solver_check.json` | E9 solver check |
| `e10_inventory_runs.csv`, `e10_inventory_summary.csv` | E10 inventory simulation |
| `e11_erp_sensitivity_milp_vs_ranker.csv` | E11 sensitivity to ERP assumptions |
| `erp_simulated.csv` | Simulated cost and stock (labelled as simulated) |
| `item_descriptions.csv` | Product titles, used by the dashboard |
| `summary.json` | Headline numbers |
| `loadtest/real_w{workers}_c{concurrency}.json` | `/recommend` load test on the full model (`scripts/loadtest.py`, 1,000 requests each); see [`docs/worklog/ci.md`](../docs/worklog/ci.md) |
