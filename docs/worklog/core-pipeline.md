# Worklog: core pipeline (thread "Build MarginGraph end to end")

Branch `claude/project-thread-mkbaip`, PR #2. All times are UTC on 2026-10-26.
Every number below was measured in a run. Detailed result tables are in `docs/RESULTS.md`, and the raw files are in `results/`.

## 1. Goal and approach (09:00)

San asked to build MarginGraph to about 80–90% working today. The order comes from `docs/experiment_plan.md` (PR #1):
1. data audit
2. temporal split
3. baselines
4. candidate retrieval
5. LightGBM reranker
6. LLM go/no-go
7. PuLP margin optimizer
8. inventory simulation
9. bootstrap statistics
10. API

The task is framed as **checkout add-ons**: for each invoice, one product is hidden and the model must recommend it back from the rest of the basket. This was the coordinator's default, and San has not overridden it.

## 2. Environment constraints found

| Issue | Effect | Resolution |
| --- | --- | --- |
| The container's proxy blocks archive.ics.uci.edu, Kaggle and Hugging Face (403) | The dataset could not be downloaded | San uploaded `online_retail_II.xlsx` to the project files (09:13) |
| PuLP 4.2 has no bundled CBC solver and changed its variable API | `LpVariable(cat=...)` raised a TypeError; `PULP_CBC_CMD` did not exist | Installed `highspy`. The code now picks CBC if present, otherwise HiGHS, and creates variables with `prob.add_variable` on PuLP 4 (`optimize.py`) |
| implicit warns about multi-threaded OpenBLAS | ALS was slow | The CLI sets `OPENBLAS_NUM_THREADS=1` |

## 3. Code built (commit 37d7a82, 09:10)

| Module | What it does |
| --- | --- |
| `data.py` | Reads both xlsx sheets (or a csv). Drops cancellations and adjustments (invoices starting C/A), non-positive quantity or price, non-product stock codes (regex `^\d{5}[A-Za-z]{0,2}$`) and exact duplicates. Writes one row per (invoice, item) to Parquet. Also builds the catalog (description, median price, last-word category) and the **simulated** ERP (cost from margin ~ Beta(4,6), stock = weekly demand × 6 weeks, 15% of items overstocked 3–6×). |
| `split.py` | Global temporal split (train before 2011-07-01, val Jul–Sep, test from Oct), leave-one-out events, and a leakage assertion |
| `audit.py` | E1: popularity skew, repeat rate, basket stats, co-purchase Hit@k on real vs shuffled baskets, top-lift pairs |
| `models.py` | Popularity, recent popularity, repeat purchase, co-purchase, ItemKNN (cosine), EASE, and ALS (implicit, with exact fold-in for a new basket) |
| `features.py` | One pass over the data that produces full-catalog baseline ranks (E3), the merged candidate pool (E4) and reranker features |
| `rerank.py` | LightGBM LambdaRank on val events (time-ordered 70/15/15 for fit / early stop / calibration), isotonic calibration, reliability table |
| `optimize.py` | MILP (PuLP) and exact enumeration over ≤ 2 add-ons; 15% floor per item or per bundle; overstock weight; discount tiers; trade-off λ |
| `stage2.py` | Strategy evaluation (realized vs expected profit) and sequential inventory simulation |
| `pipeline.py`, `cli.py` | `margingraph prepare / run / serve` |
| `api.py` | FastAPI `POST /recommend` |
| `llm.py` | Qwen prompts, yes/no scoring, comparison vs LightGBM, go/no-go verdict; later also the stacker and LoRA fine-tune |
| `tests/` | Tiny synthetic fixture (code checks only), MILP vs enumeration, API test |

## 4. Runs on real data

### Data cleaning (09:15)

1,067,371 raw rows became 991,910 clean lines (39,516 invoices, 4,707 products, 5,852 customers). The raw row count matches UCI's published 1,067,371.

**Bug found:** `lines_without_customer` was 0. Under pandas 3, `astype("Int64").astype(str)` turns missing values into NaN, not `"<NA>"`. Added `.fillna("")`; the corrected value is 225,831 lines.

### Run 1 (09:17–09:22; pool of 50 without EASE)

- **E1 passed.** Co-purchase Hit@10 on val is 16.1% on real baskets, 4.4% on shuffled baskets and 0.23% by chance.
- **Best baseline:** EASE, test Hit@10 26.2%.
- **LightGBM:** Hit@10 28.5%, +2.4 pts over EASE [1.5, 3.4].
- **Pool problem:** pool Recall@50 was 36.1%, lower than EASE alone (41.1% Hit@50 on the full catalog). EASE had been left out of the pool sources by mistake.

### Run 2 (09:23–09:27; EASE added to the pool)

| Result | Value |
| --- | --- |
| Pool Recall@50 (test) | 43.5% |
| LightGBM Hit@10 | 30.5% |
| MILP λ=1 vs ranker top-2 | +21% realized profit, −2.5 pts Hit@2 |
| Solver check | 600/600 agreement |

Committed as 35860f9. San approved the push at 09:37, and PR #2 was opened.

### Recall experiment (09:40)

EASE λ ∈ {100, 250, 500, 1000} on val: Recall@50 was 53.4 / 53.2 / 52.5 / 50.9%, so λ=250 was picked.

Refitting on train+val before scoring test raised EASE test Recall@100 from 47.2% to 55.7%. It also cut the share of test targets never seen before the test window from 16.7% to 7.1%.

### Run 3 (09:41–09:46; pool 100, EASE λ=250, train+val refit for test)

- **Pool:** Recall@100 is 58.0% [56.7, 59.5].
- **Reranker:** EASE Hit@10 31.1%; LightGBM 35.6%, +4.5 pts [3.6, 5.5].
- **Optimizer:** MILP at λ=0.5 gives +17% realized profit for −1.1 pts Hit@2. At λ=1 it gives +22% profit for −3.7 pts. Zero floor violations; the plain ranker breaks the floor in 3.8% of baskets.
- **Solver check:** PuLP/HiGHS matches enumeration on 600/600 problems, mean 3.4 ms.
- **E11:** the profit gain stays positive across all margin distributions and seeds.
- **API demo:** a basket with woodland paper cups returns the matching plates; 18 ms per call once warm.

Committed as 55cfb87.

Runs 4–5 (10:40, 11:17) only added exports (`val_slates.parquet`, `train_slates.parquet`). All metric files were unchanged, apart from solver timing.

## 5. LLM experiments (San ran them on Kaggle, with a T4 GPU)

| # | Time | Setup | Result | Verdict |
| --- | --- | --- | --- | --- |
| 1 | 10:17 | Qwen2.5-1.5B zero-shot, yes/no score on the top-20 LightGBM slate, 1,000 test baskets | LLM Hit@5 16.8% vs LightGBM 27.6%; blend 23.2%; blend Hit@10 34.8% vs 36.1% (CI crosses 0) | NO-GO |
| 2 | 10:39 | Qwen2.5-3B zero-shot, same baskets | LLM Hit@5 16.6%; blend 22.3%; blend Hit@10 −2.2 pts [−4.0, −0.4] | NO-GO |
| 3 | 11:19 | Option 1: logistic-regression stacker (LightGBM + 3B LLM features), fit on 1,147 held-out val baskets | Hit@5 27.5% vs 27.6% (−0.1 [−0.6, +0.3]); LLM weights ≈ 0 (0.015 / 0.055 vs LightGBM 0.736) | NO-GO |
| 4 | in progress | Option 2: LoRA fine-tune of 1.5B on 10,772 train-period pairs (1 hidden item : 3 LightGBM hard negatives), 2 epochs | pending | |

**Conclusion so far:** zero-shot Qwen adds no signal beyond LightGBM. If the fine-tune (#4) is also NO-GO, the plan is option 3: LightGBM stays the ranker, and the LLM is used only for new products with no purchase history (7% of test targets) and for "why this add-on" explanations.

## 6. Kaggle and notebook bugs, and their fixes

| Time | Symptom San saw | Cause | Fix |
| --- | --- | --- | --- |
| 09:56 | "It is using CPU, not GPU" | Step 3 (LightGBM, baselines) is CPU-only by design; the GPU is used only in step 4 | Explained; added a GPU assert and printed the device name before LLM scoring (081921d) |
| 10:03 | `ModuleNotFoundError: margingraph` | `pip install -e` inside a running kernel is not visible until a restart | Notebook adds `src/` to `sys.path`; the pipeline runs via `PYTHONPATH=src python -m margingraph.cli` (05555fc) |
| 10:46 | `git pull` refused: local changes to `results/*.json` | The first run rewrote tracked result files | Run `git checkout -- results` before pulling |
| 10:48 | `fatal: only one reference expected` | The pasted command merged with the old line | Gave a full replacement cell with one command per line |
| 11:38 | `ImportError: incompatible torchao 0.10` inside peft | Kaggle's preinstalled torchao is older than recent peft accepts; we never use torchao | `_skip_torchao_check()` tells peft that torchao is absent (0f22437); verified against a simulated failure |
| 11:42 | CUDA OOM at the lm_head | The model computed logits for the full 151k vocabulary at every position, for batch 16 | `logits_to_keep=1`, gradient checkpointing, batch size 8 (4c69f43) |
| 11:43 | CUDA OOM again (14 GB used) | Models from the earlier failed attempts were still on the GPU | Asked for Restart & Run All |
| 12:00 | CUDA OOM in `load_model` (same kernel, 14 GB used) | The restart had not happened, so the old models still filled GPU 0 | `load_model` now picks the GPU with the most free memory (the second T4 is empty), and stops with a clear "stop the session and start again" message if under 6 GB is free |

## 7. How to reproduce

```bash
pip install -e ".[dev]"
cp online_retail_II.xlsx data/raw/
margingraph run          # about 5 min on 4 CPU cores; writes results/ and artifacts/
pytest -q                # 7 tests
```

GPU notebooks:
- `notebooks/llm_rerank_gpu.ipynb`: zero-shot go/no-go and the option 1 stacker
- `notebooks/llm_finetune_gpu.ipynb`: option 2 fine-tune

## 8. Assumptions to keep in mind

- Unit cost, stock and discount response are simulated, because Online Retail II has none of them. Every Stage 2 profit number depends on them; E11 varies the margin distribution.
- "Realized" profit counts an add-on as accepted only if it is the product the customer really bought. This is conservative, because real shoppers also accept items they did not buy in the logged invoice.
- LightGBM is trained on val events that were scored by train-only models. Test events are scored by models refit on train+val.
