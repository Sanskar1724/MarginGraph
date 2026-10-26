# Running MarginGraph

```bash
pip install -e ".[dev]"
# put UCI Online Retail II (dataset 502) at data/raw/online_retail_II.xlsx
margingraph prepare          # clean -> data/processed/*.parquet
margingraph run              # E1-E11 -> results/, model bundle -> artifacts/
margingraph serve            # FastAPI on :8000, POST /recommend
pytest -q                    # code tests on a tiny synthetic fixture
```

To train on a real store's data instead (CSV/Excel export, Shopify or
WooCommerce), see [CONNECTORS.md](CONNECTORS.md):

```bash
margingraph sync shopify --out data/store
margingraph --config data/store/config.yaml run --results results_store --artifacts artifacts_store
```

| Step | Module | Output in `results/` |
| --- | --- | --- |
| Clean data | `data.py` | `clean_log.json` |
| E1 signal audit | `audit.py` | `e1_audit.json`, `e1_top_pairs.csv` |
| E2 temporal split, leave-one-out events | `split.py` | `e2_split.json` |
| E3 baselines (popularity, recent, repeat, co-purchase, ItemKNN, EASE, ALS) | `models.py`, `features.py` | `e3_baselines.csv` |
| E4 candidate pool recall | `features.py` | `e4_retrieval.csv` |
| E5 LightGBM LambdaRank | `rerank.py` | `e5_rerank.csv`, `e5_paired.csv`, `e5_importance.csv` |
| E7 isotonic calibration | `rerank.py` | `e7_calibration.json`, `e7_reliability_test.csv` |
| E8 strategy comparison, trade-off curve | `optimize.py`, `stage2.py` | `e8_strategies_simulated_erp.csv`, `e8_paired_vs_ranker_top2.csv` |
| E9 PuLP vs exact enumeration | `optimize.py` | `e9_solver_check.json` |
| E10 sequential inventory simulation | `stage2.py` | `e10_inventory_*.csv` |
| E11 ERP sensitivity | `pipeline.py` | `e11_erp_sensitivity_milp_vs_ranker.csv` |
| LLM rerank on GPU | `llm.py`, `notebooks/llm_rerank_gpu.ipynb` | run on Kaggle/Colab |

**Task framing.** Checkout add-ons: for each val/test invoice with 2 to 50 products, one product is hidden at random and the rest is the basket. A model scores the hidden product's rank.

**What is real and what is simulated.** Baskets, prices, descriptions and timestamps are real. Unit cost, stock and the discount response are simulated (`erp` and `optimize.discount_elasticity` in the config), so Stage 2 profit numbers hold only under those assumptions; E11 varies them.

**Two profit measures.** *Realized* profit counts an offer as accepted only when it is the product the customer really bought. *Expected* profit uses the calibrated p(accept). Realized is grounded in real behaviour; expected depends on calibration.
