# Phase 1: validate on several stores' data

**Goal:** show whether the Stage 1 ranker (candidate pool + LightGBM) beats simple methods on stores that are not a UK gift wholesaler: groceries, a supermarket, a marketplace. Report every outcome, including ties and losses.

**What this phase can and cannot prove.** None of these public datasets has real unit cost or stock (Ta Feng's `ASSET` column might be cost, but it is undocumented). So this phase validates **relevance** (Hit@K, NDCG, pool recall). Stage 2 profit on these datasets still uses the simulated cost and stock, exactly like UCI, and stays labelled simulated. Real profit proof is Phase 3 and 4.

**Done when:**

- [ ] Each of the 4 datasets below has been converted, synced and run, and its results folder is committed under `results/public/<name>/`.
- [ ] `docs/RESULTS_PUBLIC.md` has one table (from `scripts/public_datasets.py compare`) with every dataset, the test size, pool recall, the best baseline, LightGBM, and the paired difference with its 95% CI.
- [ ] Each dataset's caveats are written next to its row (sampling, synthetic dates, missing prices).
- [ ] README and paper say what the multi-dataset result is, in one honest sentence (for example "LightGBM beat the best baseline on 3 of 5 datasets; tied on Olist, where most orders have one product").

**Gate for calling it "generalizes":** LightGBM's Hit@10 is higher than the best baseline with the 95% CI above zero on most datasets with enough test baskets (at least 1,000). This is our chosen bar, decided before running, so it cannot be moved after seeing the results.

## The datasets

Sizes below are from the dataset pages and are approximate. After converting, `convert_stats.json` gives the real numbers for your sample: use those.

| Dataset | What it is | Prices | Dates | Basket id | Size (approx.) | Kaggle slug (check it) | What it tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Instacart Market Basket** (2017) | US grocery delivery | **no** | relative only (days since prior order) | yes | 3.4M orders, 32M lines, 206k users, 50k products | competition `instacart-market-basket-analysis` (accept the rules on the competition page), or dataset `psparks/instacart-market-basket-analysis` | Large grocery baskets, heavy repeat buying |
| **Dunnhumby The Complete Journey** | US supermarket, 2,500 households, 2 years | yes (sales value, discounts) | day number + time | yes | 2.6M lines, 276k baskets, 92k products | `frtgnn/dunnhumby-the-complete-journey` | Supermarket with discounts and many products |
| **Olist Brazilian E-Commerce** | Brazilian marketplace, 2016 to 2018 | yes (+ freight) | real timestamps | yes | 99k orders, 113k item rows, 33k products | `olistbr/brazilian-ecommerce` | **Sparse baskets**: most orders have one product, so few events. Tests the "too little history" case |
| **Ta Feng Grocery** | Taiwan grocery, Nov 2000 to Feb 2001 | yes | real dates | no (customer + day = one basket) | 817k lines, 32k customers, 24k products | `chiranjivdas09/ta-feng-grocery-dataset` | Short time span, Asian grocery, possible cost column |

If a slug does not work, search the dataset's name on kaggle.com/datasets and use the one with the expected files (listed under each converter in [`scripts/public_datasets.py`](../../scripts/public_datasets.py)).

Optional later (no converter yet; adding one is a small function in the same script):

| Dataset | Why | Problem |
| --- | --- | --- |
| H&M Personalized Fashion (Kaggle competition) | Fashion, prices, product text | 31M transactions, no basket id; needs customer+day baskets and heavy sampling |
| RetailRocket e-commerce (`retailrocket/ecommerce-dataset`) | Views and add-to-carts, not only purchases | No prices; transactions are sparse |

## Where to run it

| Where | RAM | When to use |
| --- | --- | --- |
| **Kaggle notebook, CPU** (free) | about 30 GB | **Recommended.** Add the dataset as notebook input (no download), and your laptop stays free |
| Your laptop (8 GB) | 8 GB | Fine for Olist, Ta Feng and Dunnhumby with `--top-items 5000`; for Instacart use `--max-customers 20000` |

For scale: the full UCI run (4,707 products, about 1M lines) takes about 5 minutes on 4 CPU cores ([core-pipeline.md](../worklog/core-pipeline.md)), and the service's training on the same data peaked at 1.65 GB RAM (PR #12's SERVICE.md). Keep each dataset near that size with `--top-items 5000` and you stay in the same range. EASE builds a dense item-by-item matrix, so memory grows with the square of the number of products: 5,000 items is about 200 MB per copy, 10,000 is about 800 MB.

## Steps (same for every dataset)

```text
download → convert → sync csv → simulate-erp → run → compare → commit results → write up
```

### 1. Get the data

**Kaggle notebook (recommended):** New Notebook → Add Input → search the dataset → Add. It appears under `/kaggle/input/<slug-name>/`. For Instacart's competition data, open the competition page and accept the rules first.

**Laptop:** install the Kaggle CLI and an API token (kaggle.com → Settings → API → Create New Token, save to `~/.kaggle/kaggle.json`, `chmod 600`). Never commit that file.

```bash
pip install kaggle
mkdir -p data/public/{dunnhumby,olist,tafeng,instacart}
kaggle datasets download -d frtgnn/dunnhumby-the-complete-journey -p data/public/dunnhumby --unzip
kaggle datasets download -d olistbr/brazilian-ecommerce            -p data/public/olist     --unzip
kaggle datasets download -d chiranjivdas09/ta-feng-grocery-dataset -p data/public/tafeng    --unzip
kaggle competitions download -c instacart-market-basket-analysis   -p data/public/instacart
cd data/public/instacart && for f in *.zip; do unzip -o "$f"; done && cd -
```

`data/` is in `.gitignore`. Never commit raw datasets.

### 2. Convert, sync, run (one dataset)

Example for Dunnhumby on the laptop. Swap the name and paths for the others.

```bash
pip install -e .
N=dunnhumby
python scripts/public_datasets.py convert $N --src data/public/$N --out data/public/$N/mg --top-items 5000
margingraph sync csv --orders data/public/$N/mg/orders.csv --products data/public/$N/mg/products.csv --out data/store/$N
python scripts/public_datasets.py simulate-erp data/store/$N/config.yaml
margingraph --config data/store/$N/config.yaml run --results results/public/$N --artifacts data/artifacts/$N
python scripts/public_datasets.py compare results results/public/$N
```

Per-dataset options:

| Dataset | Convert options | Notes |
| --- | --- | --- |
| Instacart | `--max-customers 20000 --top-items 5000` | No prices: every price is 1.0, so Stage 2 numbers are meaningless here; report Stage 1 only. Dates are rebuilt from `days_since_prior_order` with every user's last order on 2017-06-30, so the test set is everyone's latest orders. Say this in the write-up |
| Dunnhumby | `--top-items 5000` | `DAY 1` is mapped to 2018-01-01 (the real dates are hidden). Price = sales value / quantity (after discounts) |
| Olist | `--top-items 5000` | Expect few test events because most orders have one product. `sync` warns if fewer than 200 orders have 2+ products. A tie or a loss here is a real finding: write it up as the "sparse basket" case |
| Ta Feng | `--top-items 5000`; optional `--asset-as-cost` | One basket = one customer on one day. With `--asset-as-cost`, skip `simulate-erp` for a second run to see Stage 2 with `ASSET` as cost, labelled "ASSET read as cost, unverified" |

On Kaggle, the same commands in notebook cells:

```python
!git clone -q https://github.com/Sanskar1724/MarginGraph.git && cd MarginGraph && pip install -q -e .
%cd MarginGraph
!python scripts/public_datasets.py convert dunnhumby --src /kaggle/input/dunnhumby-the-complete-journey --out /kaggle/working/dh --top-items 5000
!margingraph sync csv --orders /kaggle/working/dh/orders.csv --products /kaggle/working/dh/products.csv --out /kaggle/working/store_dh
!python scripts/public_datasets.py simulate-erp /kaggle/working/store_dh/config.yaml
!margingraph --config /kaggle/working/store_dh/config.yaml run --results /kaggle/working/results_dh --artifacts /kaggle/working/art_dh
!python scripts/public_datasets.py compare results /kaggle/working/results_dh
!cp /kaggle/working/dh/convert_stats.json /kaggle/working/results_dh/ && cd /kaggle/working && zip -qr results_dh.zip results_dh
```

Download `results_dh.zip` from the notebook's Output panel and unzip it into `results/public/dunnhumby/` on your laptop.

### 3. What to commit

Commit only the small summary files, not models or large per-item tables:

```bash
cd results/public/dunnhumby
git add summary.json clean_log.json convert_stats.json e1_audit.json e2_split.json e3_baselines.csv \
        e4_retrieval.csv e5_rerank.csv e5_paired.csv e5_importance.csv e7_calibration.json \
        e8_strategies_simulated_erp.csv e8_paired_vs_ranker_top2.csv e9_solver_check.json
```

Do not commit model bundles (`data/artifacts/`), `erp_simulated.csv`, `e1_top_pairs.csv` or anything under `data/`.

### 4. Write up

Create `docs/RESULTS_PUBLIC.md`:

```bash
python scripts/public_datasets.py compare results results/public/instacart results/public/dunnhumby \
       results/public/olist results/public/tafeng
```

Paste the table, then for each dataset add: the converter options, the caveats from the table above, the E1 audit result (co-purchase on real vs shuffled baskets: if the real signal is weak, say so), and which features LightGBM used most (`e5_importance.csv`).

## Checklist

- [ ] Kaggle account and API token set up (token not in git)
- [ ] Dunnhumby: converted, synced, run, results committed (date, folder)
- [ ] Ta Feng: converted, synced, run, results committed
- [ ] Ta Feng second run with `--asset-as-cost` (Stage 2 only, labelled unverified)
- [ ] Olist: converted, synced, run, results committed (or the sync warning recorded if too few baskets)
- [ ] Instacart: converted with sampling, synced, run, results committed
- [ ] `docs/RESULTS_PUBLIC.md` written with the compare table and caveats
- [ ] README results section: one sentence and a link
- [ ] Paper: a "generalization" paragraph with the table
- [ ] `docs/worklog/multi-dataset.md` with every command, runtime, RAM and problem; row in `docs/WORKLOG.md`

## If LightGBM does not win somewhere

That is a result, not a failure. Check, in this order, and write down what you find:

1. **Pool recall** (`e4_retrieval.csv`): if the hidden item is rarely in the 100 candidates, no reranker can help. Fix the pool, not the ranker.
2. **Signal audit** (`e1_audit.json`): if co-purchase on real baskets is barely above shuffled baskets, the dataset has little basket signal (likely for Olist).
3. **Too few validation events** to train LightGBM well: the reranker is trained on validation events, so a small store gives it little to learn from. Try `split` dates that give more validation data.
4. **Hyperparameters** in `configs/default.yaml` (`rerank`, `baselines.ease_lambda`) were tuned on UCI. Retune on validation only, never on test.

## Files involved

| File | Role |
| --- | --- |
| `scripts/public_datasets.py` | `convert`, `simulate-erp`, `compare` |
| `src/margingraph/connectors/csv_source.py`, `sync.py` | `margingraph sync csv`, writes `config.yaml` with 70% / 85% time cuts |
| `src/margingraph/pipeline.py` | `margingraph run`, E1 to E11 |
| `configs/default.yaml` | Model settings, simulated ERP |
| `results/public/<name>/` | Committed summaries (new) |
| `docs/RESULTS_PUBLIC.md` | Write-up (new) |

## Prompt for a future Claude session

```text
Phase 1 of docs/industry-plan (01-multi-dataset-validation.md). I ran <dataset> on Kaggle and
unzipped the results into results/public/<name>/ (or: here is the notebook output: <paste>).
Please: (1) check the files are complete and the run used --top-items <n> and simulate-erp;
(2) run scripts/public_datasets.py compare across every folder in results/public plus results/;
(3) create or update docs/RESULTS_PUBLIC.md with the table and this dataset's caveats from the
phase file, using only numbers from the files; (4) if LightGBM did not win, go through the
"If LightGBM does not win" list and report what the files show; (5) update the README sentence,
the worklog and the checklist. One PR against main.
```

To add a new dataset converter:

```text
Add a converter for <dataset> to scripts/public_datasets.py, following the existing four:
output the same orders.csv/products.csv columns, document what is real and what is assumed
in its docstring, and add a fake-file test to tests/test_public_datasets.py. I have the files
at <path>; their columns are: <paste head of each file>.
```
