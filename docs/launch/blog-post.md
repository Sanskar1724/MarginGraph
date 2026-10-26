---
title: "I built a profit-aware recommender for checkout add-ons. The LLM lost."
tags: machinelearning, recommender-systems, python, optimization
canonical_url: (set to the dev.to URL when cross-posting to Medium)
---

# I built a profit-aware recommender for checkout add-ons. The LLM lost.

*Subtitle: A LightGBM ranker plus a 3-millisecond integer program, tested on 4,480 real baskets, with confidence intervals and the experiments that failed.*

Most "customers also bought" widgets answer one question: what will this shopper click? A store owner cares about a second one: will it make me money? A relevant item can still be a bad suggestion if its margin is thin after a discount, or if it drains stock that is already low.

MarginGraph is my attempt to answer both questions without letting a model make financial decisions. This post walks through the design, the numbers, and the parts that did not work. Every number comes from a script in the repo that you can rerun: [github.com/Sanskar1724/MarginGraph](https://github.com/Sanskar1724/MarginGraph).

## The task

I used [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii): invoices from a UK online gift retailer, December 2009 to December 2011. After cleaning: 991,910 invoice lines, 39,516 invoices, 4,707 products.

The framing is a checkout add-on. Take a real basket, hide one product, and ask the system to suggest it from the rest. The split is strictly by time:

| Split | Dates | Events |
| --- | --- | --- |
| Train | up to 30 Jun 2011 | |
| Validation | Jul to Sep 2011 | 3,822 |
| Test | 2 Oct to 9 Dec 2011 | 4,480 |

One honest detail up front: 7.1% of the hidden test items never appear before the test window, so no model can exceed 92.9%.

## Step 0: is there a signal at all?

Before building anything, I checked that co-purchase structure is real. A simple co-purchase model fit on real baskets reaches 16.1% Hit@10 on validation. The same model fit on baskets with items shuffled between invoices reaches 4.4%, and chance is 0.23%. The top-lift pairs are the kind of thing you would expect: woodland paper cups with woodland plates, pink egg cosy with blue egg cosy. Signal exists, so on to the build.

## Architecture

```text
Basket
  │
  ▼
Shortlist      EASE (plain, time-decayed, per customer), text similarity, fresh sales,
               ItemKNN, ALS, repeat purchase, co-purchase, popularity  →  up to 150 items
  │
  ▼
Ranker         LightGBM (lambdarank), isotonic calibration  →  p(buy) for the top 20
  │
  ▼
Optimizer      PuLP integer program  →  up to 2 add-ons
```

The optimizer solves:

```text
maximize   Σ_i  x_i · p_i · ( (1 − λ) · P̄  +  λ · w_i · profit_i )
subject to Σ_i x_i ≤ 2
           profit_i ≥ 0.15 · revenue_i       for every chosen i   (margin floor)
           x_i = 0 if item i is out of stock
           x_i ∈ {0, 1}
```

`profit_i` is price after discount minus unit cost, `p_i` the calibrated purchase probability, `w_i` an overstock weight between 1.0 and 2.0, and `P̄` a constant scale so that λ = 0 means "pure relevance" and λ = 1 means "overstock-weighted expected profit". The key design rule: **profit is always multiplied by the probability of purchase.** The optimizer cannot rescue an irrelevant high-margin item, because its expected profit is near zero.

## Stage 1: relevance

| Model | Hit@5 | Hit@10 | NDCG@10 |
| --- | --- | --- | --- |
| Popularity | 1.9% | 3.1% | 0.016 |
| Repeat purchase | 9.3% | 13.9% | 0.079 |
| Co-purchase | 9.2% | 13.1% | 0.079 |
| ALS | 12.9% | 17.3% | 0.106 |
| ItemKNN | 17.4% | 22.7% | 0.144 |
| EASE (λ=250) | 23.2% | 31.1% | 0.188 |
| LightGBM rerank, first run | 26.1% | 35.6% | 0.217 |
| **LightGBM rerank, current** | **28.8%** | **38.1%** | **0.237** |

LightGBM minus EASE, paired over the same test baskets: Hit@10 +7.0 points, 95% bootstrap CI [6.0, 8.0] (first run: +4.5 [3.6, 5.5]).

Two things mattered more than model choice:

1. **The shortlist.** Adding EASE to the candidate pool and widening it from 50 to 100 raised shortlist recall from 43.5% to 58.0%. Later, four more sources (time-decayed EASE, per-customer EASE, text similarity of product names, and a nightly fresh-sales signal) and a 150-item pool took it to 65.3%. Recall caps every reranker, including an LLM, so this was the biggest single lever.
2. **Training the reranker honestly.** The reranker learns from validation events scored by models trained only on the training period, then the candidate models are refit on train plus validation before test. Skipping this leaks future data and inflates everything.

Calibration was modest but real: isotonic regression gives a test Brier score of 0.00417 against 0.00435 for a constant base rate (0.00560 vs 0.00568 in the first run). Good enough to multiply into profit, not something to brag about.

## Stage 2: profit

The dataset has real prices but **no unit cost and no stock**. I simulated them, labelled them as simulated everywhere, and tested how much the conclusion depends on them. "Realized profit" counts only the item the customer actually bought.

| Strategy | Hit@2 | Realized profit per basket (£) | Margin-floor breaks per basket |
| --- | --- | --- | --- |
| Popularity top 2 | 1.1% | 0.013 | 0 |
| Ranker top 2 | 17.8% | 0.205 | 0.037 |
| MILP λ=0.5 | 16.7% | 0.234 | 0 |
| MILP λ=1.0 | 14.9% | 0.255 | 0 |

At λ=0.5, profit is up 14% (CI +£0.014 to +£0.044 per basket) for −1.1 points Hit@2 (CI [−1.7, −0.6]). At λ=1.0 it is +24% for −2.9 points. (Against the weaker first ranker these were +17% and +22%: a better ranker raises the baseline the optimizer has to beat.) That is the trade-off a store owner would actually choose on, so the product exposes λ as a single dial.

Does the result survive different cost assumptions? I reran it with 3 margin distributions × 3 random seeds. The gain at λ=1 stayed positive in all nine, from +£0.024 to +£0.071 per basket, every CI above zero. That is reassuring, but it is still simulation. Only real costs settle it.

The solver itself is not the bottleneck. PuLP with HiGHS matched brute-force enumeration on 600 of 600 problems, with a mean solve time of 2.7 ms. (I have not benchmarked end-to-end API latency yet, so I will not quote one.)

I also ran a sequential stock replay. Setting the overstock weight to 2.0 cleared 116 overstock units versus 78 at 1.0, for 3.7% less profit. Useful as a knob, with a visible price.

## The LLM experiment

The original plan had a language model at the centre: read the product titles, understand the basket, rerank. I tested it properly, with a go/no-go gate set before the run: beat LightGBM on the same slates, paired, with the CI above zero.

Setup: Qwen2.5-Instruct, zero-shot yes/no scoring of LightGBM's top 20, on 1,000 random test baskets, on a free Kaggle T4.

| | Hit@1 | Hit@5 | Hit@10 |
| --- | --- | --- | --- |
| Qwen2.5-1.5B | 5.1% | 16.8% | 29.5% |
| Blend (rank average) | 7.3% | 23.2% | 34.8% |
| LightGBM | 11.1% | 27.6% | 36.1% |

The 1.5B model lost by 10.8 points at Hit@5. The 3B model was no better (16.6%). Then I tried the LLM score as an extra feature in a stacker with LightGBM: the fitted weights were 0.015 and 0.055 for the LLM features against 0.736 for LightGBM, and Hit@5 moved by −0.1 points. **NO-GO, three times.**

My reading: these product titles are short ("PINK REGENCY TEACUP AND SAUCER"), and the co-purchase signal is strong. Behaviour data already knows that the pink teacup goes with the green one. Text understanding adds little on top. A LoRA fine-tune on LightGBM slates with hard negatives is running now; it faces the same gate. If it loses too, the LLM's job shrinks to what it might be good at: cold-start products with no sales, and one-line explanations.

## What I would tell someone building this

- **Audit the signal against a shuffled null before you model.** It takes ten minutes and tells you whether there is anything to learn.
- **Spend effort on the shortlist.** A better reranker on a 43% recall pool loses to a plain one on a 58% pool, and going from 58% to 65% recall was worth more than any LightGBM tuning I tried.
- **Multiply profit by probability.** It is the one line that keeps a profit optimizer honest.
- **Put business rules in code, not in a model.** The margin floor was broken 0 times by the optimizer and 0.037 times per basket by the plain top 2.
- **Set the gate before the run, and publish the NO-GO.**

## What is next

Real costs. The next step is a pilot with a small online store: import its real unit costs and stock, rerun the offline check on its history, then a 50/50 A/B test on gross profit per visitor with conversion as a guard metric. If you run a shop and want to try it, or you want to poke at the code, the repo is [github.com/Sanskar1724/MarginGraph](https://github.com/Sanskar1724/MarginGraph) and the demo is at DEMO_URL.

Everything here was built with free tools on an 8 GB laptop and a free Kaggle GPU.
