# Phase 2: the LLM, after E6

**Goal:** decide, with measured results, where a language model earns a place in MarginGraph. It has not earned one as a ranker so far. A product is still industry-ready without an LLM; this phase is about not over-claiming and about finding the one job where it helps.

**Rule that does not change:** the LLM never sets prices, never overrides the margin floor, and never runs on the live checkout path (latency budget and free hosting rule it out). It can rank offline, write text, and help with new products.

## What has been measured (Kaggle T4, 1,000 UCI test baskets, top-20 LightGBM slate)

| Run | Hit@5 | vs LightGBM 27.6% | Verdict |
| --- | --- | --- | --- |
| Qwen2.5-1.5B zero-shot | 16.8% | −10.8 [−13.7, −7.9] | NO-GO |
| Qwen2.5-3B zero-shot | 16.6% | −11.0 [−13.7, −8.4] | NO-GO |
| Stacker: LightGBM + 3B score, logistic regression | 27.5% | −0.1 [−0.6, +0.3]; LLM weights near 0 | NO-GO |
| E6: LoRA fine-tune of 1.5B (10,772 train-period pairs, 1 positive : 3 LightGBM hard negatives, 2 epochs) | running | | pending |

Source: [RESULTS.md](../RESULTS.md), [core-pipeline.md](../worklog/core-pipeline.md).

## Step 1: finish and record E6

- [ ] Let the Kaggle run finish (`notebooks/llm_finetune_gpu.ipynb`). If the session timed out, rerun it; the bug fixes for out-of-memory and `torchao` are already in (see WORKLOG bug table).
- [ ] Download the LoRA adapter from the notebook's Output panel and keep it (it is small). Do not commit it to git; if you want to share it, push it to a free Hugging Face model repo.
- [ ] **Gate (set before the run):** the fine-tuned model, alone or blended, must beat LightGBM's Hit@5 on the same 1,000 paired baskets with the 95% CI above zero.
- [ ] Record the result in every file listed in [00-open-items.md](00-open-items.md) item C1.

Then go to Step 2A if GO, or Step 2B if NO-GO.

## Step 2A: if E6 is GO

A GO on one dataset is not enough to change the product.

- [ ] Rerun the same fine-tune and paired test on a second dataset from Phase 1 (Dunnhumby has the richest product text after UCI). Gate the same way.
- [ ] Measure the cost to serve it. It cannot run per checkout on free CPU hosting, so the only realistic designs are offline:
  - **Nightly pair scores:** score (item, item) pairs for each item's top 50 candidates once a night on Kaggle, save them, and give LightGBM an `llm_pair_score` feature. Pair scores ignore the rest of the basket; measure whether that keeps the gain.
  - **Distillation:** train LightGBM on the LLM's scores as an extra label. Same gate.
- [ ] Only ship if the offline design still beats LightGBM alone with the CI above zero.

## Step 2B: if E6 is NO-GO (option 3, already planned)

LightGBM stays the ranker. The LLM, or a much smaller text model, gets the jobs below. Each one is a separate experiment with its own gate, decided before running.

### B1. Cold-start candidates (new products)

7.1% of UCI test targets never appear before the test window ([RESULTS.md](../RESULTS.md)), so no purchase-based model can recommend them. Product text can.

- [ ] Embed product titles with a small free sentence model on CPU (`sentence-transformers/all-MiniLM-L6-v2`, about 90 MB, runs on the laptop).
- [ ] Add a `text` source to the candidate pool (`features.py`, `retrieval.per_source`): for each basket item, its nearest neighbours by text.
- [ ] **Gate:** pool Recall@100 goes up with the CI above zero, and Hit@10 is not lower (CI includes or is above zero). Report recall on the new-product subset separately.
- This also attacks the pool recall ceiling, which limits every ranker. **Done in PR #14:** a TF-IDF text source is now in the pool, and with three other new sources and a 150-item pool it raised recall from 58.0% to 65.3%.

### B2. "Why this add-on" text

PR #12's service already returns a short template reason ("Often bought with ..."). An LLM could write a nicer one, offline.

- [ ] Generate one sentence per (item, top neighbour) pair nightly on Kaggle with Qwen2.5-1.5B, store it, serve it from the cache. Never generate at checkout.
- [ ] Check 100 random sentences by hand: no invented facts (price, material, discount). Any invented fact → template only.
- [ ] Measure in the A/B test only if the store agrees to a third arm; otherwise keep the template.

### B3. Catalog cleanup for new stores

Real stores have messy titles and missing categories. An LLM can fill a missing `category` from the title, offline, once per new product. Gate: agreement with the store's own category on products that have one.

## What not to spend time on

- Bigger zero-shot models: 3B was no better than 1.5B, and the stacker gave the LLM a weight near zero. Without new information (text, cold start), size alone is unlikely to help.
- Paid LLM APIs: against the free-tools rule, and they would put customer data with a third party (see the privacy note).

## Done when

- [ ] E6 recorded with GO or NO-GO.
- [ ] Either 2A shipped behind its gate, or B1 run and recorded (GO or NO-GO), and the README says plainly what the LLM does in the product.

## Files involved

| File | Role |
| --- | --- |
| `notebooks/llm_finetune_gpu.ipynb`, `notebooks/llm_rerank_gpu.ipynb` | Kaggle runs |
| `src/margingraph/llm.py` | Prompts, scoring, LoRA training |
| `src/margingraph/features.py`, `configs/default.yaml` (`retrieval.per_source`) | Where a text candidate source would go |
| `tests/test_llm_finetune.py` | Existing LLM tests |

## Prompt for a future Claude session

```text
Phase 2 of docs/industry-plan (02-llm-options.md). E6 finished: <paste the notebook's final tables
and GO/NO-GO lines>. Record it per 00-open-items.md item C1. Then, since it was <GO/NO-GO>,
implement step <2A / B1>: for B1, add a "text" candidate source using
sentence-transformers/all-MiniLM-L6-v2 on CPU (must fit an 8 GB laptop), behind a config flag that
is off by default, with a test on the synthetic fixture. Give me the exact commands to run the
gate on UCI on my laptop or Kaggle CPU; do not report any number you did not measure.
One PR against main.
```
