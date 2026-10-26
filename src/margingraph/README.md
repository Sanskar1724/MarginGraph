# `margingraph` package

The Python package behind the `margingraph` command. Experiments E1–E11 map to modules as below.

| Module | Role | Experiment |
| --- | --- | --- |
| `data.py` | Load and clean UCI Online Retail II (one row per invoice × product) | |
| `audit.py` | Is there learnable basket signal? Co-purchase lift vs shuffled baskets | E1 |
| `split.py` | Global temporal split, leave-one-out basket events | E2 |
| `models.py` | Baselines: popularity, repeat, co-purchase, ALS, ItemKNN, EASE | E3 |
| `features.py` | Candidate pools and reranker features | E3/E4 |
| `rerank.py` | LightGBM LambdaRank reranker and isotonic calibration | E5, E7 |
| `llm.py` | Qwen yes/no reranker and LoRA fine-tune helpers | E5/E6 |
| `optimize.py` | Stage 2 MILP: at most K add-ons under margin, stock and discount rules | E8, E9 |
| `stage2.py` | Strategy comparison and sequential inventory simulation | E8–E11 |
| `stats.py` | Ranking metrics and paired bootstrap CIs | all |
| `pipeline.py` | Runs E1–E11 end to end and writes `results/` | all |
| `api.py` | FastAPI: POST a basket, get up to 2 margin-safe add-ons | |
| `cli.py` | `margingraph {prepare,run,serve,sync,dashboard}` | |
| [`connectors/`](connectors/) | Store data sync: CSV/Excel, Shopify, WooCommerce | |
| [`dashboard/`](dashboard/) | Merchant dashboard over SQLite | |
