# Results: run of 2026-10-26 (CPU, `margingraph run`, seed 42)

Data: UCI Online Retail II, 1,067,371 raw rows → 991,910 clean invoice lines, 39,516 invoices, 4,707 products.
Split: train to 2011-06-30, val Jul–Sep 2011 (3,822 events), test 2011-10-02 to 2011-12-09 (4,480 events).
Task: checkout add-on, one product hidden per invoice. Test candidates come from models refit on train+val (val ends before test starts); 7.1% of test targets never appear before the test window, so no model can exceed 92.9% Hit@K.
The reranker is trained on val events scored by train-only models.
All CIs are 95% bootstrap over test events. Source files are in `results/`.

## E1 signal audit (gate: passed)

| | Hit@10 on val |
| --- | --- |
| Chance (10 / 4,384 items) | 0.23% |
| Co-purchase fit on shuffled baskets | 4.4% |
| Co-purchase fit on real baskets | 16.1% |

Top-lift pairs are real complements (woodland paper cups + plates, pink + blue egg cosy).

## E3 baselines and E5 reranker (test)

| Model | Hit@5 | Hit@10 | NDCG@10 |
| --- | --- | --- | --- |
| Popularity | 1.9% | 3.1% | 0.016 |
| Repeat purchase | 9.3% | 13.9% | 0.079 |
| Co-purchase | 9.2% | 13.1% | 0.079 |
| ALS | 12.9% | 17.3% | 0.106 |
| ItemKNN | 17.4% | 22.7% | 0.144 |
| EASE (best baseline, λ=250) | 23.2% | 31.1% | 0.188 |
| **LightGBM rerank** | **26.1%** | **35.6%** | **0.217** |

LightGBM − EASE, paired: Hit@10 +4.5 pts [3.6, 5.5], NDCG@10 +0.029 [0.023, 0.035].
E4 candidate pool Recall@100 = 58.0% [56.7, 59.5] (was 43.5% at pool 50 without EASE and refit). This caps every reranker, including the LLM.
E7 isotonic calibration: test Brier 0.00560 vs 0.00568 for a constant base-rate guess, so probabilities are calibrated but only weakly sharp (see `e7_reliability_test.csv`).

## E8 Stage 2 (simulated cost and stock)

Profit is £ gross profit per basket. *Realized* counts only the product the customer really bought.

| Strategy | Hit@2 | Realized profit | Expected profit | 15% floor breaks per basket |
| --- | --- | --- | --- | --- |
| Popularity top-2 | 1.2% | 0.013 | 0.017 | 0.002 |
| Co-purchase top-2 | 6.3% | 0.070 | 0.049 | 0.010 |
| Ranker top-2 | 16.7% | 0.184 | 0.167 | 0.038 |
| MILP λ=0.5 | 15.6% | 0.215 | 0.201 | 0 |
| MILP λ=1.0 | 13.0% | 0.224 | 0.213 | 0 |
| MILP λ=1, overstock w=2.0 | 12.5% | 0.216 | 0.207 | 0 |

MILP λ=0.5 − ranker top-2, paired: realized profit +0.031 [0.017, 0.044] (+17%), Hit@2 −1.1 pts [−1.8, −0.5].
MILP λ=1 − ranker top-2, paired: realized profit +0.040 [0.023, 0.058] (+22%), Hit@2 −3.7 pts [−4.7, −2.8].
E9: PuLP (HiGHS) and exact enumeration agree on 600/600 problems; mean solve time 3.4 ms.
E11: across 3 margin distributions × 3 ERP seeds the realized-profit gain of MILP λ=1 stays positive (+0.015 to +0.062, every CI above zero).
E10 (sequential stock, replay): overstock weight 2.0 clears 114 overstock units vs 74 at w=1.0, for −3.7% profit.
