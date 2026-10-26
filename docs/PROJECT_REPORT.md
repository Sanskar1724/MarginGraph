# MarginGraph: project report

*Last updated 2026-10-26. Every number in this report comes from an experiment in this repo. The source tables are in [`RESULTS.md`](RESULTS.md) and the raw files in [`../results/`](../results/). Nothing here is a target or a projection.*

---

## 1. The short version

MarginGraph suggests up to 2 add-on products at checkout. It picks items the shopper is likely to buy **and** that make the store money, and it never suggests an item below a 15% margin.

We tested it on real sales from a UK online gift store (UCI Online Retail II, Dec 2009 to Dec 2011). We trained on older months and tested on Oct to Dec 2011: 4,480 real baskets, with one item hidden from each basket.

| What we measured | Result |
| --- | --- |
| Hidden item in the ranker's top 10 | **35.6%**, against 31.1% for the best simple method (EASE). Gain +4.5 points, 95% CI [3.6, 5.5] |
| Profit per basket from the optimizer (λ=0.5) vs showing the ranker's top 2 | **+17%**, CI [+0.017, +0.044] £ per basket, for 1.1 points fewer hits |
| Margin-floor breaks | **0** with the optimizer, against 0.038 per basket for the ranker's top 2 |
| Optimizer correctness | Same answer as brute force on 600 of 600 problems, about 3 ms each |
| LLM (Qwen2.5 1.5B and 3B) as the ranker | **NO-GO** in every test so far. LightGBM stays the ranker |

**The honest limit:** the dataset has real baskets and real prices, but no unit cost and no stock levels. We simulated those. So the relevance numbers are real, but the profit numbers hold only under our cost and stock assumptions. Section 7 shows how we tested how much that matters.

---

## 2. The problem stores face

| Problem | What it costs the store |
| --- | --- |
| **Low-profit suggestions.** "Customers also bought" pushes cheap, popular items. | They sell, but they earn little. |
| **Margin leaks.** Suggested items can sit below the store's healthy margin, especially after discounts. | Sales that lose money or barely break even. |
| **Overstock.** Slow items sit in the warehouse. | Cash tied up, then a heavy markdown later. |
| **Generic suggestions.** Every shopper sees the same best sellers. | Low relevance, so few people click. |

Most recommenders optimize for clicks only. A relevant item can still be a bad suggestion if its margin is thin or it pulls down stock that is already low.

## 3. The idea

Split the job in two, and let each part do what it is good at.

1. **A ranker decides what is relevant.** It learns from real baskets which products go together.
2. **An optimizer decides what to show.** It takes the ranker's best guesses and picks the 2 that give the most expected profit, while obeying hard business rules.

The rules are enforced by plain code, not by a model. No model ever sets a price or overrides the margin floor.

```text
Basket (+ customer history if known)
        │
        ▼
Stage 1a  Candidate shortlist   EASE, ItemKNN, ALS, repeat purchase, co-purchase, popularity
        │  up to 100 products
        ▼
Stage 1b  LightGBM ranker       sorts the shortlist, gives a calibrated chance of purchase
        │  top 20
        ▼
Stage 2   PuLP optimizer        max expected profit, 15% margin floor, max 2 add-ons
        │
        ▼
Up to 2 margin-safe add-ons
```

## 4. The approach, step by step

### 4.1 Data
- **Source:** UCI Online Retail II, both sheets. 1,067,371 raw rows.
- **Cleaning** (`data.py`): drop cancellations and adjustments (19,500), zero or negative quantity or price (6,202), non-product codes such as postage and fees (4,792), and exact duplicates (33,663).
- **After cleaning:** 991,910 invoice lines, 39,516 invoices, 4,707 products, 5,852 known customers.

### 4.2 Is there a real signal? (E1)
Before building anything, we checked that baskets contain real "bought together" patterns. A simple co-purchase model got the hidden item in its top 10 **16.1%** of the time on real baskets, against **4.4%** on shuffled baskets and **0.23%** by chance. That is about 3.7 times the shuffled result, so the patterns are real. The top pairs make sense too, such as woodland paper cups with matching plates.

### 4.3 A fair test split (E2)
We split by date, never at random, so the model never sees the future.
- Train: up to 30 June 2011
- Validation: July to September 2011 (3,822 baskets)
- Test: 2 October to 9 December 2011 (4,480 baskets)

For each basket with 2 to 50 products, one product is hidden at random. The model sees the rest and must guess the hidden one. 7.1% of test items never appeared before the test window, so no model can score above 92.9%.

### 4.4 Simple methods to beat (E3)
We built a ladder of standard methods, from simplest to strongest: popularity, repeat purchase, co-purchase, ALS, ItemKNN and EASE.

### 4.5 The shortlist (E4)
We merge the top items from several methods into one pool of up to 100 products. The hidden item is in the pool **58.0%** of the time [56.7, 59.5]. This is the ceiling for any ranker, LLM included. It rose from 43.5% after we added EASE to the pool and refit the models on train plus validation data.

### 4.6 The ranker (E5, E7)
LightGBM (LambdaRank) learns to sort the pool using about 20 features: each method's score and rank, how recently the customer bought the item, the item's price against the basket, and so on. The most useful feature is EASE's rank. We then calibrate its scores into a purchase probability with isotonic regression.

### 4.7 The optimizer (E8, E9)
For each basket, PuLP solves a small integer program over the ranker's top 20:

```text
maximize   Σ x_i,d · p_i,d · [ (1 − λ)·P̄  +  λ·w_i·(P_i·(1 − d) − C_i) ]

subject to Σ x_i,d ≤ 2                              at most 2 add-ons
           Σ_d x_i,d ≤ 1                            one discount per item
           P_i·(1 − d) − C_i ≥ 15% · P_i·(1 − d)    margin floor on every chosen item
           x_i,d = 0 if item i is out of stock
           x_i,d ∈ {0, 1}
```

`P` = price, `C` = unit cost (simulated), `d` = discount, `p` = calibrated purchase chance (raised by an assumed discount response), `P̄` = average unit profit across the catalog, which puts the relevance term in £, `w` = overstock weight (1.0 to 2.0) for overstocked items, `x` = show or not. `λ` slides between pure relevance (0) and overstock-weighted expected profit (1). The exact code is in `optimize.py`.

### 4.8 Stock over time (E10) and assumption checks (E11)
- **E10** replays the test period in order, so stock goes down as items are "sold", and checks how fast overstock clears.
- **E11** reruns the profit test with 3 different margin distributions and 3 random seeds for the simulated cost data.

### 4.9 Testing an LLM as the ranker (E5 LLM, on Kaggle)
The original idea was an LLM that reads product names and judges relevance. We tested that on a free Kaggle T4 GPU, on the same top-20 shortlists and the same 1,000 test baskets as LightGBM, paired so the comparison is fair.

## 5. Results

### 5.1 Relevance (test, 4,480 baskets)

| Model | Hit@5 | Hit@10 | NDCG@10 |
| --- | --- | --- | --- |
| Popularity | 1.9% | 3.1% | 0.016 |
| Repeat purchase | 9.3% | 13.9% | 0.079 |
| Co-purchase | 9.2% | 13.1% | 0.079 |
| ALS | 12.9% | 17.3% | 0.106 |
| ItemKNN | 17.4% | 22.7% | 0.144 |
| EASE (best simple method) | 23.2% | 31.1% | 0.188 |
| **LightGBM ranker** | **26.1%** | **35.6%** | **0.217** |

LightGBM beats EASE by +4.5 Hit@10 points [3.6, 5.5] and +0.029 NDCG@10 [0.023, 0.035]. The calibrated probabilities are calibrated but not very sharp: Brier score 0.00560 against 0.00568 for a constant guess.

### 5.2 Profit (simulated cost and stock)

Profit is £ gross profit per basket. *Realized* profit counts a suggestion as sold only if it is the item the customer really bought. *Expected* profit uses the calibrated probability.

| Strategy | Hit@2 | Realized profit | Expected profit | 15% floor breaks per basket |
| --- | --- | --- | --- | --- |
| Popularity top 2 | 1.2% | 0.013 | 0.017 | 0.002 |
| Co-purchase top 2 | 6.3% | 0.070 | 0.049 | 0.010 |
| Ranker top 2 | 16.7% | 0.184 | 0.167 | 0.038 |
| **Optimizer λ=0.5** | 15.6% | **0.215** | 0.201 | **0** |
| Optimizer λ=1.0 | 13.0% | 0.224 | 0.213 | 0 |
| Optimizer λ=1, overstock w=2.0 | 12.5% | 0.216 | 0.207 | 0 |

- λ=0.5 against the ranker's top 2: realized profit **+17%** (+0.031 £ [0.017, 0.044]) for **−1.1** Hit@2 points [−1.8, −0.5].
- λ=1.0 against the ranker's top 2: realized profit **+22%** (+0.040 £ [0.023, 0.058]) for **−3.7** points [−4.7, −2.8].
- **The trade:** slightly fewer hits, clearly more profit, and no margin-floor breaks.

### 5.3 Does the profit gain survive other cost assumptions? (E11)

Across 3 margin distributions (mean margin 20%, 40% and 60%) and 3 seeds, the realized-profit gain of the λ=1 optimizer over the ranker's top 2 stayed positive in all 9 runs, from +0.015 to +0.062 £ per basket, with every 95% CI above zero. The gain is largest when margins vary widely, which is when choosing carefully matters most.

### 5.4 Overstock (E10, replay of the test period)

| Strategy | Profit (£) | Overstock units cleared |
| --- | --- | --- |
| Ranker top 2 | 825.7 | 99 |
| Optimizer λ=1, w=1.0 | 1,005.2 | 74 |
| Optimizer λ=1, w=1.5 | 996.5 | 99 |
| Optimizer λ=1, w=2.0 | 968.5 | 114 |

Raising the overstock weight to 2.0 clears 114 overstock units instead of 74, for 3.7% less profit. The store chooses that trade with one setting.

### 5.5 Optimizer reliability (E9)
PuLP (with the HiGHS solver) and brute-force enumeration agreed on all 600 test problems, with a mean solve time of about 3 ms.

### 5.6 LLM as the ranker: NO-GO so far

All runs: 1,000 test baskets, LightGBM's top-20 shortlist, paired against LightGBM.

| Test | Hit@5 | vs LightGBM 27.6% | Verdict |
| --- | --- | --- | --- |
| Qwen2.5-1.5B, zero-shot | 16.8% | −10.8 [−13.7, −7.9] | NO-GO |
| Qwen2.5-1.5B blended with LightGBM | 23.2% | −4.4 [−6.5, −2.4] | NO-GO |
| Qwen2.5-3B, zero-shot | 16.6% | −11.0 [−13.7, −8.4] | NO-GO |
| Qwen2.5-3B blended with LightGBM | 22.3% | −5.3 [−7.2, −3.4] | NO-GO |
| Qwen2.5-3B score as an extra feature (stacker) | 27.5% | −0.1 [−0.6, +0.3] | NO-GO, LLM weight near zero |

**What this tells us:** a general-purpose LLM reading product names does not know this store's buying patterns as well as a model trained on its baskets. A bigger model did not help. **Next:** a LoRA fine-tune on this store's baskets (E6, `notebooks/llm_finetune_gpu.ipynb`, built, not yet run). If that also fails, the LLM's place is cold-start items (new products with no sales yet) and plain-language explanations, not ranking.

## 6. Work done

| Part | Where | Status |
| --- | --- | --- |
| Data cleaning and audit (E1) | `data.py`, `audit.py` | Done |
| Date-based split (E2) | `split.py` | Done |
| Six baselines (E3) | `models.py`, `features.py` | Done |
| Candidate pool (E4) | `features.py` | Done, 58.0% recall |
| LightGBM ranker and calibration (E5, E7) | `rerank.py` | Done |
| PuLP optimizer and strategy comparison (E8, E9) | `optimize.py`, `stage2.py` | Done |
| Stock simulation and cost sensitivity (E10, E11) | `stage2.py`, `pipeline.py` | Done |
| Paired bootstrap confidence intervals | `stats.py` | Done |
| One-command pipeline `margingraph run` | `cli.py`, `pipeline.py` | Done |
| FastAPI demo `POST /recommend` | `api.py` | Done (demo level) |
| LLM rerank notebook (Kaggle) | `notebooks/llm_rerank_gpu.ipynb` | Run, NO-GO |
| LLM fine-tune notebook (E6) | `notebooks/llm_finetune_gpu.ipynb` | Built, not run yet |
| Tests on a small synthetic fixture | `tests/` | Done |
| Production API, demo app, store connectors | separate pull requests | **In progress** |

The earlier V1 and V2 notebooks are kept as history only. Their numbers came from mock or random data and are not results.

## 7. Honest limits

1. **Cost and stock are simulated.** Unit cost is drawn from a Beta(4, 6) distribution (mean margin 40%) and stock is set from past demand. E11 shows the gain holds across several assumptions, but only real store data can confirm the profit numbers.
2. **The discount response is an assumption.** The effect of a discount on purchase chance (elasticity 1.5) is made up. The main results above use no discounts.
3. **Offline replay is not a live test.** We check whether we would have suggested the item the customer really bought. A real shopper might also buy a suggested item they would not have found alone. Only an A/B test measures that.
4. **The shortlist caps everything.** The right item reaches the pool 58.0% of the time, so no ranker can score above that.
5. **One store, one period.** A UK gift wholesaler with many trade buyers. Other stores will differ.
6. **API latency is not benchmarked yet.** The optimizer step is about 3 ms (E9). End-to-end latency under load is part of the production work.

## 8. Glossary

| Term | Meaning |
| --- | --- |
| **Add-on** | An extra product suggested at checkout. |
| **Baseline** | A simple method to beat, such as "show the best sellers". |
| **Hit@K** | How often the hidden item is in the top K suggestions. |
| **NDCG@10** | Like Hit@10, but gives more credit when the item is ranked higher. |
| **Recall@100** | How often the hidden item makes the 100-item shortlist. |
| **Co-purchase** | Items often bought in the same basket. |
| **ALS** | A method that learns hidden "taste" factors for customers and products. |
| **ItemKNN** | Suggests items similar to those in the basket, based on who bought them. |
| **EASE** | A strong simple method built from "bought together" patterns across all items. |
| **LightGBM** | A fast model that learns to rank from many small decision trees. |
| **LambdaRank** | A way to train a model to get the order right, not just the scores. |
| **Calibration** | Adjusting scores so that "10%" really means about 1 in 10 buy. |
| **Brier score** | Error of predicted probabilities. Lower is better. |
| **MILP** | Mixed-integer linear programming: math that picks the best yes/no choices while obeying rules. |
| **PuLP / HiGHS** | PuLP is a free Python tool for writing MILPs. HiGHS is the free solver that answers them. |
| **λ (lambda)** | Our slider between relevance (0) and profit (1). |
| **Margin** | The share of the selling price that is profit. |
| **Margin floor** | The lowest margin allowed for any suggestion, here 15%. |
| **Overstock weight** | A multiplier (1.0 to 2.0) that favors items with too much stock. |
| **95% CI** | The range the true value probably sits in. If it does not include zero, the difference is very unlikely to be luck. |
| **Paired bootstrap** | Comparing two methods on the same baskets, resampled many times, to get a CI. |
| **Zero-shot** | Using an LLM without training it on our data. |
| **LoRA fine-tune** | A cheap way to train a small part of an LLM on our data. |
| **NO-GO** | The test failed our gate, so we do not use that option. |
| **A/B test** | Half the shoppers see the old system, half the new one, then we compare. |
