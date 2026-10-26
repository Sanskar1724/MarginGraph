# Results: run of 2026-10-26 13:00 UTC (CPU, `margingraph run`, seed 42)

> **Updated by the accuracy thread** ([worklog](worklog/accuracy.md)): the pool now has four more sources and holds 150 items, and the ranker trains on 3 events per val invoice. LightGBM Hit@10 rose from 35.6% to **38.1%** (paired +2.5 pts [1.6, 3.4]), and pool recall from 58.0% to **65.3%**. The full run took 10 minutes with a peak of 3.9 GB of RAM. The LLM section below was measured on the earlier 35.6% slates.

Data: UCI Online Retail II, 1,067,371 raw rows → 991,910 clean invoice lines, 39,516 invoices, 4,707 products.
Split: train to 2011-06-30, val Jul–Sep 2011 (3,822 events), test 2011-10-02 to 2011-12-09 (4,480 events).
Task: checkout add-on, one product hidden per invoice. Test candidates come from models refit on train+val (val ends before test starts); 7.1% of test targets never appear before the test window, so no model can exceed 92.9% Hit@K.
The reranker is trained on val events scored by train-only models (3 hidden-item events per val invoice; early stopping and calibration use only the original events).
The fresh-sales source sees only invoices from days before each event, like a nightly batch job.
All CIs are 95% bootstrap over test events. Source files are in `results/`.

## E1 signal audit (gate: passed)

| | Hit@10 on val |
| --- | --- |
| Chance (10 / 4,384 items) | 0.23% |
| Co-purchase fit on shuffled baskets | 4.4% |
| Co-purchase fit on real baskets | 16.1% |

Top-lift pairs are real complements (woodland paper cups + plates, pink + blue egg cosy).

## E3 baselines and E5 reranker (test)

Single-source Hit@10 (test, from `e3_baselines.csv`):

| Model | Hit@10 |
| --- | --- |
| Popularity | 3.1% |
| Recent popularity, last 90 days (`recent_pop`) | 3.0% |
| Trending, last 14 days, nightly (`trend`) | 5.4% |
| Customer EASE (`cust_ease`) | 9.5% |
| Co-purchase | 13.0% |
| Repeat purchase | 13.4% |
| Fresh co-purchase, nightly (`fresh_co`) | 16.8% |
| ALS | 17.3% |
| Text similarity, TF-IDF (`text`) | 20.5% |
| ItemKNN | 22.7% |
| Time-decayed EASE (`ease_decay`) | 30.1% |
| EASE (best baseline on val, λ=250) | 31.1% |

| Model | Hit@5 | Hit@10 | NDCG@10 |
| --- | --- | --- | --- |
| EASE | 23.2% | 31.1% | 0.188 |
| LightGBM rerank, previous run (pool 100) | 26.1% | 35.6% | 0.217 |
| **LightGBM rerank, this run (pool 150)** | **28.8%** | **38.1%** | **0.237** |

LightGBM − EASE, paired: Hit@10 +7.0 pts [6.0, 8.0], NDCG@10 +0.049 [0.043, 0.055].
New − previous LightGBM, paired on the same 4,480 events: Hit@10 +2.5 pts [1.6, 3.4], NDCG@10 +0.020 [0.015, 0.025] (`results/accuracy/experiments.csv`, row `F_final_vs_baseline`).
E4 candidate pool Recall@150 = 65.3% [63.9, 66.7] (was 58.0% at pool 100, 43.5% at pool 50). This caps every reranker, including the LLM.
E7 isotonic calibration: test Brier 0.00417 vs 0.00435 for a constant base-rate guess (was 0.00560 vs 0.00568), so the probabilities are sharper than before (see `e7_reliability_test.csv`).

## E8 Stage 2 (simulated cost and stock)

Profit is £ gross profit per basket. *Realized* counts only the product the customer really bought.

| Strategy | Hit@2 | Realized profit | Expected profit | 15% floor breaks per basket |
| --- | --- | --- | --- | --- |
| Popularity top-2 | 1.1% | 0.013 | 0.014 | 0 |
| Co-purchase top-2 | 6.1% | 0.072 | 0.057 | 0.004 |
| Ranker top-2 | 17.8% | 0.205 | 0.185 | 0.037 |
| MILP λ=0.5 | 16.7% | 0.234 | 0.212 | 0 |
| MILP λ=1.0 | 14.9% | 0.255 | 0.223 | 0 |
| MILP λ=1, overstock w=2.0 | 14.6% | 0.245 | 0.219 | 0 |

MILP λ=0.5 − ranker top-2, paired: realized profit +0.028 [0.014, 0.044] (+14%), Hit@2 −1.1 pts [−1.7, −0.6].
MILP λ=1 − ranker top-2, paired: realized profit +0.049 [0.031, 0.069] (+24%), Hit@2 −2.9 pts [−3.7, −2.0].
The better ranker raised ranker top-2 itself from Hit@2 16.7% and profit 0.184 (previous run) to 17.8% and 0.205.
E9: PuLP (HiGHS) and exact enumeration agree on 600/600 problems; mean solve time 2.7 ms.
E11: across 3 margin distributions × 3 ERP seeds the realized-profit gain of MILP λ=1 stays positive (+0.024 to +0.071, every CI above zero).
E10 (sequential stock, replay): overstock weight 2.0 clears 116 overstock units vs 78 at w=1.0, for −3.7% profit.

## E5 LLM rerank (Kaggle T4, run by San on 2026-10-26)

Qwen2.5-1.5B-Instruct, zero-shot yes/no scoring of the top-20 LightGBM slate, 1,000 random test baskets. Paired against LightGBM on the same slates.

| Metric | LLM | Blend (rank average) | LightGBM | LLM − LGBM [95% CI] | Blend − LGBM [95% CI] |
| --- | --- | --- | --- | --- | --- |
| Hit@1 | 5.1% | 7.3% | 11.1% | −6.0 [−8.2, −3.8] | −3.8 [−5.6, −2.0] |
| Hit@5 | 16.8% | 23.2% | 27.6% | −10.8 [−13.7, −7.9] | −4.4 [−6.5, −2.4] |
| Hit@10 | 29.5% | 34.8% | 36.1% | −6.6 [−9.3, −3.8] | −1.3 [−3.0, +0.4] |

**Gate: NO-GO** for 1.5B zero-shot. LightGBM stays the reranker. Next: Qwen2.5-3B zero-shot, then E6 (fine-tune on LightGBM slates with hard negatives, or use the LLM score as a LightGBM feature).

Qwen2.5-3B-Instruct, same setup and baskets: LLM Hit@5 16.6% vs LightGBM 27.6% (−11.0 [−13.7, −8.4]); blend Hit@5 22.3% (−5.3 [−7.2, −3.4]); blend Hit@10 33.9% vs 36.1% (−2.2 [−4.0, −0.4]). **NO-GO**; 3B is no better than 1.5B zero-shot.

Option 1, LLM as an extra signal (Qwen2.5-3B scores; logistic regression on LightGBM + LLM features fit on 1,147 held-out val baskets, tested on the same 1,000 test baskets): Hit@5 27.5% vs LightGBM 27.6% (−0.1 [−0.6, +0.3]); Hit@10 −0.1 [−0.6, +0.4]. The fitted LLM weights are near zero (llm 0.015, llm_z 0.055 vs lgbm 0.736). **NO-GO**: zero-shot Qwen adds no signal beyond LightGBM. Next: E6 LoRA fine-tune (`notebooks/llm_finetune_gpu.ipynb`).

Option 2 / E6, LoRA fine-tune (Qwen2.5-1.5B, r=16, 10,772 training-period pairs: each hidden item with 3 LightGBM hard negatives from the same slate; 2 epochs, batch 8, class-weighted Yes/No loss; Kaggle T4, 3.6 GB peak GPU). The weighted loss fell from 1.80 to about 0.70 by step 300 and then stayed at ln 2 ≈ 0.693, i.e. the model stopped separating the classes. Same 1,000 test baskets and slates:

| System | Hit@1 | Hit@5 | Hit@10 |
| --- | --- | --- | --- |
| LightGBM | 11.1% | 27.6% | 36.1% |
| Fine-tuned 1.5B alone | 1.4% | 7.8% | 17.4% |
| Rank blend (LightGBM + fine-tuned) | 4.0% | 16.2% | 30.4% |
| Random order of the slate | 2.3% | 11.6% | 23.2% |

Paired differences vs LightGBM, points [95% CI]: fine-tuned alone Hit@1 −9.7 [−11.7, −7.7], Hit@5 −19.8 [−22.8, −16.7], Hit@10 −18.7 [−21.7, −15.5]; blend Hit@1 −7.1 [−9.2, −4.9], Hit@5 −11.4 [−13.9, −8.8], Hit@10 −5.7 [−7.7, −3.6]. The random-order row is exact: the target is in the top-20 slate for 46.3% of baskets, so random Hit@k = 0.463 × k/20. **NO-GO**: the fine-tuned model ranks below random order. Our reading (not tested): the negatives are LightGBM's own near-misses, often the same product in another colour or size, so the short product names give the model nothing to tell positive from negative, and it learned to answer 50/50.

**LLM track closed (option 3).** LightGBM stays the ranker. The LLM is kept only for (a) products with no purchase history, which no co-purchase model can rank (7.1% of test targets), and (b) one-line "why this add-on" explanations. Neither use has been measured yet.
