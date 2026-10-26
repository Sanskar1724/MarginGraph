# Results: run of 2026-10-26 (CPU, `margingraph run`, seed 42)

Data: UCI Online Retail II, 1,067,371 raw rows → 991,910 clean invoice lines, 39,516 invoices, 4,707 products.
Split: train to 2011-06-30, val Jul–Sep 2011 (3,822 events), test 2011-10-02 to 2011-12-09 (4,480 events).
Task: checkout add-on, one product hidden per invoice. 16.7% of test targets never appear in train, so no model can exceed 83.3% Hit@K.
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
| Popularity | 1.8% | 3.0% | 0.015 |
| Repeat purchase | 9.6% | 13.8% | 0.078 |
| Co-purchase | 9.0% | 13.0% | 0.076 |
| ALS | 12.0% | 16.7% | 0.102 |
| ItemKNN | 15.6% | 20.5% | 0.131 |
| EASE (best baseline) | 19.4% | 26.2% | 0.160 |
| **LightGBM rerank** | **23.0%** | **30.5%** | **0.185** |

LightGBM − EASE, paired: Hit@10 +4.3 pts [3.4, 5.2], NDCG@10 +0.025 [0.020, 0.030].
E4 candidate pool Recall@50 = 43.5% [42.1, 44.9]. This caps every reranker, including the LLM.
E7 isotonic calibration: test Brier 0.0083 vs base rate 0.0096.

## E8 Stage 2 (simulated cost and stock)

Profit is £ gross profit per basket. *Realized* counts only the product the customer really bought.

| Strategy | Hit@2 | Realized profit | Expected profit | 15% floor breaks |
| --- | --- | --- | --- | --- |
| Popularity top-2 | 1.1% | 0.015 | 0.023 | 2.2% |
| Co-purchase top-2 | 6.1% | 0.067 | 0.055 | 3.3% |
| Ranker top-2 | 14.0% | 0.165 | 0.165 | 5.7% |
| MILP λ=0.5 | 13.2% | 0.191 | 0.200 | 0 |
| MILP λ=1.0 | 11.5% | 0.200 | 0.210 | 0 |
| MILP λ=1, overstock w=2.0 | 11.2% | 0.195 | 0.205 | 0 |

MILP λ=1 − ranker top-2, paired: realized profit +0.035 [0.020, 0.051] (+21%), Hit@2 −2.5 pts [−3.2, −1.7].
E9: PuLP (HiGHS) and exact enumeration agree on 600/600 problems; mean solve time 2.9 ms.
E11: the realized-profit gain stays positive across all three margin distributions (+0.019 to +0.051).
E10 (sequential stock, replay): overstock weight 2.0 clears 115 overstock units vs 86 at w=1.0, for −2.3% profit.
