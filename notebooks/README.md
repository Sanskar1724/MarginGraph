# Notebooks

| Notebook | Runs on | What it does |
| --- | --- | --- |
| `run_all.ipynb` | Colab / Kaggle CPU | Full E1–E11 pipeline, same as `margingraph prepare && margingraph run` |
| `llm_rerank_gpu.ipynb` | Kaggle T4 | Zero-shot Qwen2.5 reranker go/no-go (result: NO-GO) |
| `llm_finetune_gpu.ipynb` | Kaggle T4 | E6: LoRA fine-tune of Qwen2.5-1.5B as a yes/no reranker |
| `reranker_comparison.ipynb` | CPU (cloud container) | LightGBM vs XGBoost, CatBoost, HistGB and logistic regression on the same pools and features, 1,000 UCI test baskets (paper Sec. 6.2). Committed cleared; the executed run is `results/reranker_comparison/reranker_comparison_executed.md` |
| `exploration/MarginGraph_V1.ipynb`, `V2.ipynb` | | Early prototypes, kept for history. Their numbers came from mock or random data and are **not** results. |

Secrets go in Colab / Kaggle *Secrets*, never in a notebook.
