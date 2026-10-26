# MarginGraph: Margin-Aware, Constrained Recommendation of Checkout Add-Ons

*A reproducible study on UCI Online Retail II, with a negative result for small LLM rerankers*

Sanskar · [github.com/Sanskar1724/MarginGraph](https://github.com/Sanskar1724/MarginGraph) · Draft of 26 October 2026

> This Markdown copy is generated from `paper/main.tex` with pandoc (see `paper/README.md`). The PDF (`paper/main.pdf`) is the reference version.

## Abstract

Recommenders in retail are usually trained to predict what a shopper
will buy, while the store is paid by what it earns. We study this gap
for a narrow, common decision: which (at most two) add-on products to
suggest at checkout. MarginGraph is a two-stage system. Stage 1
retrieves 150 candidates from eleven sources (classical recommenders,
text similarity and a nightly fresh-sales signal) and reranks them with
a LightGBM LambdaRank model whose scores are calibrated into purchase
probabilities. Stage 2 solves a small mixed-integer program per basket
that trades expected relevance against expected gross profit, under a
hard 15% per-item margin floor, a two-item limit, stock availability,
and an optional overstock weight. On a strict temporal split of UCI
Online Retail II (4,480 test baskets), the reranker reaches Hit@10 of
38.1%, 7.0 points above the best baseline (EASE, 31.1%; paired 95% CI
\[6.0, 8.0\]). With *simulated* unit cost and stock, the optimizer at
$\lambda=0.5$ raises realized gross profit per basket by 14% over the
ranker’s top-2 (paired CI of the gain £0.014–0.044) for a 1.1-point drop
in Hit@2, with zero margin-floor violations; the gain stays positive
over nine cost and stock scenarios. We also report a negative result:
zero-shot Qwen2.5 1.5B and 3B rerankers, their rank blends, and a
stacker that feeds the LLM score to a logistic model all fail to beat
LightGBM on the same slates. All numbers in this paper are read from
files the pipeline writes; none are targets.

## Introduction

A checkout add-on is a small, high-volume decision. The shopper has
already chosen a basket; the store may show one or two more products.
Showing the product the shopper is most likely to add maximises
conversions, but that product may carry a thin margin, may be out of
stock, or may compete with stock the store needs to clear. Price- and
profit-aware recommendation is a long-standing topic (Jannach and
Adomavicius 2017; Abdollahpouri et al. 2020), yet most open recommender
benchmarks report only accuracy, and many published accuracy gains do
not survive strong, well-tuned baselines (Ferrari Dacrema, Cremonesi,
and Jannach 2019).

This paper makes four contributions.

1.  **A leakage-free checkout add-on benchmark** on UCI Online Retail
    II (Chen 2019): one product hidden per invoice, one global temporal
    cutoff per split, and full-catalog ranking (no sampled
    negatives (Krichene and Rendle 2020)).

2.  **A strong Stage 1**: a baseline ladder of eleven candidate sources,
    a 150-item candidate pool, and a calibrated LightGBM reranker, each
    step measured with bootstrap confidence intervals.

3.  **A Stage 2 optimizer** that turns calibrated probabilities into an
    add-on choice under hard business rules, checked against exact
    enumeration on 600 problems, evaluated by replaying real purchases,
    and stress-tested across simulated cost and stock scenarios.

4.  **A documented negative result** for small open LLMs as rerankers on
    this task, including a blend and a stacker, run on the same slates
    as LightGBM.

The dataset has prices but no cost or stock, so every profit number
depends on a simulation that we state in full
(Section 4.3). We treat this as the main limitation
of the study rather than a footnote.

## Related work

**Classical next-item and basket recommenders**

Item-based collaborative filtering (Sarwar et al. 2001),
implicit-feedback matrix factorization (ALS) (Y. Hu, Koren, and Volinsky
2008) and the closed-form linear autoencoder EASE (Steck 2019) remain
strong on sparse purchase data. Ferrari Dacrema, Cremonesi, and Jannach
(2019) showed that simple, tuned neighbourhood methods often match or
beat recent neural models, which is why our ladder includes them and why
the reranker must beat the best of them on paired tests. Krichene and
Rendle (2020) showed that sampled ranking metrics can reorder models; we
therefore rank against the full catalog.

**Learning to rank and calibration**

We rerank with LambdaRank-style gradient boosting (Burges 2010) as
implemented in LightGBM (Ke et al. 2017). Stage 2 needs probabilities,
not scores, so we fit an isotonic map from score to purchase
probability (Zadrozny and Elkan 2002).

**Profit-aware and multi-objective recommendation**

Jannach and Adomavicius (2017) survey price and profit awareness in
recommenders, and Abdollahpouri et al. (2020) frame the store as one of
several stakeholders whose utility a recommender should account for.
Louca et al. (2019) jointly optimise profit and relevance in e-commerce
ranking at Etsy; Pei et al. (2019) maximise expected profit with
reinforcement learning at Taobao; Agarwal et al. (2011) optimise one
objective under constraints on others for content recommendation.
MarginGraph is closest to the constrained view: it keeps relevance in
the objective and puts the store’s rules (margin floor, item limit,
stock) in hard constraints, solved exactly per basket with an
open-source MILP stack (Mitchell, O’Sullivan, and Dunning 2011; Huangfu
and Hall 2018). Unlike the industrial studies above, every component and
result here is public and reproducible on a free dataset and a CPU.

**LLMs as recommenders**

Hou et al. (2024) show that LLMs can rank candidates zero-shot but are
sensitive to order and history length and trail trained recommenders on
several benchmarks. TALLRec (Bao et al. 2023) shows that
parameter-efficient tuning (LoRA (E. J. Hu et al. 2022)) aligns an LLM
with recommendation data far better than prompting. We test the cheapest
version of this idea a student can run for free: Qwen2.5 (Qwen Team
2024) 1.5B and 3B on a single Kaggle T4 GPU.

## Data and task

**Data**

UCI Online Retail II (Chen 2019; Chen, Sain, and Guo 2012) contains the
transactions of a UK online gift and homeware wholesaler from December
2009 to December 2011. From 1,067,371 raw rows we drop cancellations and
adjustments (19,500), non-positive quantity or price (6,202),
non-product codes such as postage and fees (4,792), and exact duplicates
(33,663), leaving 991,910 invoice lines over 39,516 invoices, 4,707
products and 5,852 known customers. The data has a unit price but no
unit cost and no stock level.

**Task**

For each evaluation invoice with 2–50 distinct products we hide one
product at random; the model sees the remaining basket (and the
customer’s earlier history, if known) and must rank the full catalog.
The hidden product is the single relevant item. We report Hit@$K$,
NDCG@10 and MRR.

**Split**

One global cutoff per boundary: train up to 2011-06-30 (709,574 lines),
validation July–September 2011 (3,822 events), test 2011-10-02 to
2011-12-09 (4,480 events), with no invoice in two splits. Test
candidates come from models refit on train+validation, which ends before
the test window starts. 7.1% of test targets never appear before the
test window, so no model can exceed 92.9% Hit@$K$ on test.

**Signal audit (E1)**

Before modelling we checked that baskets carry a learnable signal. On
validation, a co-purchase model fit on real baskets reaches Hit@10 of
16.1%, against 4.4% when the same model is fit on baskets whose items
were shuffled across invoices, and 0.23% for chance. The highest-lift
pairs are recognisable complements (matching paper cups and plates; egg
cosies in two colours).

## Method

### Stage 1: retrieval, reranking and calibration

**Baselines and candidate pool**

Seven classical scorers are fit on the training period: global
popularity, 90-day popularity, the customer’s repeat purchases,
co-purchase counts, ItemKNN (Sarwar et al. 2001), EASE ($\lambda=250$,
chosen on validation) (Steck 2019) and ALS (64 factors) (Y. Hu, Koren,
and Volinsky 2008). Four further sources were added after a
validation-only selection
(Section 5.1): EASE on recency-weighted
baskets (half-life 120 days), EASE applied to the customer’s own past
items, TF-IDF similarity of product descriptions (word 1–2 and character
3–4 grams, maximum over the basket), and a *fresh* signal that, like a
nightly job, sees only invoices from days before the event: 14-day
trending items and co-purchase over that stream. The item index covers
the whole catalog, so products first sold after the fit cutoff can be
recommended once the fresh source sees them sell; a product with no
earlier sales gets zero from every source. The candidate pool unions the
top lists of each source in a fixed order (EASE 90, decayed EASE 60,
customer EASE 30, text 30, trending 22, fresh co-purchase 30, ItemKNN
45, ALS 45, repeat 45, co-purchase 30, the two popularity scorers 15
each), deduplicated and capped at 150 items, with basket items removed.

**Reranker**

A LightGBM LambdaRank model (Ke et al. 2017; Burges 2010) (31 leaves,
learning rate 0.05, up to 500 trees with early stopping) scores each
candidate from 35 features: the score and rank from every source, price,
price relative to the basket, item age and recency, basket size, share
of basket items in the same category, and whether the customer is known.
It is trained on validation events whose candidates were produced by
train-only models, so the reranker never sees test-period data; each
validation invoice contributes three events, each hiding a different
product (early stopping and calibration use only the original one). The
most important features by gain are the decayed-EASE and EASE ranks, the
repeat-purchase score and the text similarity.

**Calibration**

An isotonic regression (Zadrozny and Elkan 2002), fit on a held-out,
later slice of validation events, maps the reranker score to $p_i$, the
probability that candidate $i$ is the product the shopper adds.

### Stage 2: constrained add-on selection

For a basket, take the top $N=20$ reranked candidates. Let
$x_{i,d}\in\{0,1\}$ mean “offer item $i$ at discount $d$”, with price
$r_i$, simulated unit cost $c_i$, revenue $r_{i,d}=r_i(1-d)$ and unit
profit $\pi_{i,d}=r_{i,d}-c_i$. The optimizer solves $$\begin{aligned}
\max_{x}\;& \sum_{i,d} x_{i,d}\; p_{i,d}\,\Big[(1-\lambda)\,\bar{\pi} + \lambda\, w_i\, \pi_{i,d}\Big] \label{eq:obj}\\
\text{s.t.}\;& \textstyle\sum_d x_{i,d} \le 1 \;\;\forall i, \qquad \sum_{i,d} x_{i,d} \le 2, \notag\\
& x_{i,d}=0 \text{ if stock}_i \le 0, \qquad \pi_{i,d} \ge 0.15\, r_{i,d} \text{ whenever } x_{i,d}=1. \notag
\end{aligned}$$ Here $\bar\pi$ is the catalog’s mean unit gross profit,
which puts the relevance term on the same scale as profit, so
$\lambda=0$ ranks by probability alone and $\lambda=1$ maximises
overstock-weighted expected profit. $w_i\in[1,2]$ up-weights items
flagged as overstock. We also test a bundle-level margin floor in place
of the per-item floor. Discounts use an *assumed* response
$p_{i,d}=\min(1,\,p_i(1+1.5d))$ for $d\in\{0,0.1,0.2\}$; this elasticity
is not estimated from data. The program is built in PuLP (Mitchell,
O’Sullivan, and Dunning 2011) and solved with HiGHS (Huangfu and Hall
2018); because at most two items are chosen, exact enumeration of all
singles and pairs gives the same optimum and is used for the bulk
offline sweeps.

### Simulated cost and stock

Unit cost is $c_i=r_i(1-m_i)$ with gross margin
$m_i\sim\text{Beta}(4,6)$ (mean 40%). Base stock is six weeks of the
item’s mean weekly training demand; 15% of items are flagged overstock
and given 3–6$\times$ that stock.
Section 5.3 repeats the main comparison under
margins drawn from Beta(2,8) (mean 20%) and Beta(6,4) (mean 60%), each
with three random seeds.

### Evaluation of Stage 2

*Replay* scoring counts an offer as accepted only if it is the product
the shopper actually added (the hidden item); this is grounded in real
behaviour and conservative. *Realized profit* is the unit gross profit
of an accepted offer, averaged over all test baskets. *Expected profit*
instead sums $p_{i,d}\,\pi_{i,d}$ over the offered items and so depends
on calibration. For stock, a sequential simulation replays test baskets
in time order against shared, decrementing stock. All confidence
intervals are 95% bootstrap intervals over test baskets with 2,000
resamples (Efron and Tibshirani 1993); differences between systems are
paired over the same baskets.

## Results

### Stage 1

<div id="tab:stage1">

| Model                                 |    Hit@5 |   Hit@10 |   Hit@50 |   NDCG@10 |       MRR |
|:--------------------------------------|---------:|---------:|---------:|----------:|----------:|
| Popularity                            |      1.9 |      3.1 |     10.0 |     0.016 |     0.017 |
| Recent popularity (90 days)           |      1.8 |      3.0 |     10.6 |     0.016 |     0.018 |
| Trending, 14 days (fresh)             |      3.1 |      5.4 |     16.5 |     0.029 |     0.029 |
| Customer EASE                         |      6.0 |      9.5 |     22.7 |     0.050 |     0.045 |
| Co-purchase                           |      9.2 |     13.0 |     24.8 |     0.079 |     0.071 |
| Repeat purchase                       |      9.7 |     13.4 |     26.9 |     0.078 |     0.068 |
| Fresh co-purchase                     |     12.4 |     16.8 |     29.8 |     0.104 |     0.094 |
| ALS                                   |     12.7 |     17.3 |     31.8 |     0.105 |     0.094 |
| Text similarity (TF-IDF)              |     14.3 |     20.5 |     39.4 |     0.113 |     0.096 |
| ItemKNN                               |     17.4 |     22.7 |     36.6 |     0.144 |     0.128 |
| Decayed EASE                          |     22.9 |     30.1 |     48.7 |     0.185 |     0.160 |
| *EASE*                                |   *23.2* |   *31.1* |   *48.9* |   *0.188* |   *0.161* |
| LightGBM rerank, first run (pool 100) |     26.1 |     35.6 |     54.6 |     0.217 |     0.184 |
| **LightGBM rerank**                   | **28.8** | **38.1** | **58.4** | **0.237** | **0.204** |

Full-catalog ranking on 4,480 test baskets. Best baseline in italics.
LightGBM minus EASE, paired: Hit@10 +7.0 pts \[6.0, 8.0\], NDCG@10
+0.049 \[0.043, 0.055\].

</div>

![Baseline ladder and reranker, Hit@10 on test.](figures/fig1_ladder.png)

*Baseline ladder and reranker, Hit@10 on test.*

![Reliability of calibrated p_i on test (log scale; lowest bin omitted).](figures/fig5_reliability.png)

*Reliability of calibrated p_i on test (log scale; lowest bin omitted).*


Table 1 and
Figure 1 show the ladder. EASE is the strongest
single model by a wide margin, consistent with Steck (2019) and Ferrari
Dacrema, Cremonesi, and Jannach (2019). The reranker improves on it on
every metric, and the paired intervals exclude zero.

**Retrieval ceiling**

The 150-item pool contains the hidden product for 65.3% of test baskets
\[63.9, 66.7\]; EASE alone reaches 55.7% at depth 100, decayed EASE
56.3%, text 48.7%, ItemKNN 43.4%. This recall caps every reranker,
including an LLM: 35% of test baskets cannot be answered by any choice
of Stage 1 order. Earlier configurations reached 43.5% (50 items, no
EASE) and 58.0% (100 items, seven sources).

**Calibration**

On test, the calibrated probabilities have a Brier score of 0.00417
against 0.00435 for a constant base-rate guess (first run: 0.00560
against 0.00568). They track observed rates across bins
(Figure 3) and are sharper than in the first run,
but still modest, which limits how much Stage 2 can separate good from
bad offers.

**What raised Stage 1 (validation-only selection)**

The first run used seven sources, a 100-item pool and one event per
validation invoice (Hit@10 35.6%). Each change was kept only if it won
on the last 30% of validation events (1,147 events never used to fit
trees); test results were recorded for all 19 variants, winners and
losers. Added one at a time to the 100-item pool, each new source was
within noise, because it displaced EASE and ItemKNN candidates.
Together, with the pool enlarged to 150 (chosen over 100 and 200 on
validation), they raised pool recall by 7.3 points \[6.2, 8.3\];
training on three events per validation invoice added the rest. Against
the first run on the same test baskets, Hit@10 rose by 2.5 points \[1.6,
3.4\] and NDCG@10 by 0.020 \[0.015, 0.025\]. An item2vec source and four
LightGBM parameter sets lost on validation and were dropped.

### Stage 2

<div id="tab:stage2">

| Strategy                               | Hit@2 (%) | Realized profit | Expected profit | Floor breaks / basket |
|:---------------------------------------|----------:|----------------:|----------------:|----------------------:|
| Popularity top-2                       |       1.1 |           0.013 |           0.014 |                     0 |
| Co-purchase top-2                      |       6.1 |           0.072 |           0.057 |                 0.004 |
| Ranker top-2                           |      17.8 |           0.205 |           0.185 |                 0.037 |
| MILP $\lambda=0$                     |      17.5 |           0.204 |           0.186 |                     0 |
| MILP $\lambda=0.5$                   |      16.7 |           0.234 |           0.212 |                     0 |
| MILP $\lambda=1$                     |      14.9 |           0.255 |           0.223 |                     0 |
| MILP $\lambda=1$, overstock $w=2$  |      14.6 |           0.245 |           0.219 |                     0 |
| MILP $\lambda=1$, bundle floor       |      15.0 |           0.256 |           0.223 |                     0 |
| MILP $\lambda=1$, discounts 0/10/20% |      14.9 |           0.255 |           0.223 |                     0 |

Stage 2 on 4,480 test baskets, **simulated cost and stock**. Profit is
£ gross profit per basket. Baselines run without the floor; the last
column counts how often they would break the 15% per-item floor.

</div>

![Relevance–profit frontier as λ varies.](figures/fig2_frontier.png)

*Relevance–profit frontier as λ varies.*

![Gain of MILP λ = 1 over ranker top-2 under nine cost/stock scenarios.](figures/fig3_sensitivity.png)

*Gain of MILP λ = 1 over ranker top-2 under nine cost/stock scenarios.*


Table 2 and
Figure 4 give the trade-off. Paired against
the ranker’s top-2 on the same baskets, MILP $\lambda=0.5$ raises
realized profit by £0.028 per basket \[0.014, 0.044\], or 14%, while
Hit@2 falls by 1.1 points \[$-1.7$, $-0.6$\]. At $\lambda=1$ the gain
is £0.049 \[0.031, 0.069\] (24%) for $-2.9$ points of Hit@2 \[$-3.7$,
$-2.0$\]. At $\lambda=0$ the optimizer is, as intended, almost
identical to the ranker ($-0.25$ points Hit@2 and $-$£0.001 profit), the
small gap coming from the margin floor removing some candidates. Every
MILP solution satisfies every hard rule, while the unconstrained ranker
top-2 would break the margin floor 0.037 times per basket. The stronger
ranker also lifted the ranker’s own top-2, from Hit@2 16.7% and £0.184
in the first run to 17.8% and £0.205, so the optimizer’s relative gain
is measured against a harder reference (first run: +17%).

Three further observations. (i) A bundle-level floor behaves like the
per-item floor here. (ii) With discounts allowed, the optimizer almost
never discounts (mean discount 0.07%): under the assumed elasticity,
giving away margin rarely pays. (iii) The solver is not a bottleneck:
PuLP with HiGHS and exact enumeration agree on all 600 checked problems
(maximum objective gap 0), with a mean MILP solve time of 2.7 ms per
basket on a CPU.

**Overstock (E10)**

In the sequential replay with shared stock, MILP $\lambda=1$ earns
£1,141 over the test period against £920 for the ranker’s top-2. Raising
the overstock weight from 1.0 to 2.0 increases overstock units sold from
78 to 116, at a 3.7% profit cost (£1,099). The plain profit objective
($w=1$) sells fewer overstock units than the ranker (114); the weight
is what moves stock, and at $w=2$ the optimizer roughly matches the
ranker on overstock while earning 19% more. Over 20 stochastic
acceptance seeds the ordering is the same (ranker £829, MILP
$\lambda=1$ £993, $w=2$ £976 on average).

### Sensitivity to the simulated cost

Figure 6 repeats the MILP $\lambda=1$ versus
ranker comparison for three margin distributions and three random seeds
each. The realized-profit gain stays positive in all nine scenarios
(from £0.024 to £0.071 per basket) with every confidence interval above
zero; the Hit@2 cost ranges from 2.3 to 6.6 points and is largest when
margins are low, where the floor removes more candidates. This shows the
direction of the result is not an artefact of one cost draw; it does not
show its size on a real store’s costs.

### Small LLMs as rerankers: a negative result

<div id="tab:llm">

| System                           | Hit@5 | Hit@10 | Hit@5 $-$ LightGBM          |
|:---------------------------------|------:|-------:|:----------------------------|
| LightGBM                         |  27.6 |   36.1 | —                           |
| Qwen2.5-1.5B zero-shot           |  16.8 |   29.5 | $-10.8$ \[$-13.7$, $-7.9$\] |
| rank blend with LightGBM         |  23.2 |   34.8 | $-4.4$ \[$-6.5$, $-2.4$\]   |
| Qwen2.5-3B zero-shot             |  16.6 |      — | $-11.0$ \[$-13.7$, $-8.4$\] |
| rank blend with LightGBM         |  22.3 |   33.9 | $-5.3$ \[$-7.2$, $-3.4$\]   |
| Stacker (LightGBM + 3B features) |  27.5 |      — | $-0.1$ \[$-0.6$, $+0.3$\]   |

LLM reranking on the top-20 LightGBM slate, 1,000 random test baskets,
same slates for all rows. Differences are paired against LightGBM with
95% bootstrap CIs, in points. Kaggle T4 GPU.

</div>

![Hit@5 of LLM-based rerankers on the same 1,000 test slates.](figures/fig4_llm.png)

*Hit@5 of LLM-based rerankers on the same 1,000 test slates.*


We asked Qwen2.5-Instruct (Qwen Team 2024) a yes/no question for each
(basket, candidate) pair (“Would this customer also add *X* to the same
order?”, with the basket’s product descriptions) and ranked by the
probability of “Yes”. Table 3 and
Figure 7 report the results. Both model sizes are
far behind LightGBM, and the 3B model is no better than the 1.5B model.
Averaging LLM and LightGBM ranks still loses at Hit@5, and at Hit@10 the
1.5B blend is not significantly different ($-1.3$ \[$-3.0$, $+0.4$\])
while the 3B blend loses ($-2.2$ \[$-4.0$, $-0.4$\]). A logistic stacker
fit on 1,147 held-out validation baskets, with LightGBM and 3B scores as
inputs, ties LightGBM ($-0.1$ points at both Hit@5 and Hit@10) and gives
the LLM features near-zero weight (0.015 and 0.055 against 0.736 for
LightGBM, on standardised inputs). In short, zero-shot Qwen adds no
measurable signal beyond the trained reranker on this task.

This agrees with Hou et al. (2024), who find zero-shot LLM rankers trail
trained models, and suggests the gap is larger for wholesale baskets
described only by terse product names. A LoRA fine-tune (E. J. Hu et al.
2022; Bao et al. 2023) of the 1.5B model on 10,772 training-period pairs
(one hidden item to three LightGBM hard negatives, two epochs) is
running at the time of writing; we will report it whatever the outcome.
Until an LLM wins on a paired test, LightGBM remains MarginGraph’s
ranker, and the LLM’s role is limited to explanations and to products
with no purchase history.

## Limitations

- **Simulated economics.** Unit cost, stock and the overstock flag are
  simulated, and the discount response is assumed. All Stage 2 profit
  numbers, including the 14% and 24% gains, are conditional on these
  assumptions. Section 5.3 varies the cost distribution, not
  its structure (for example, costs correlated with popularity).

- **Offline replay.** Replay credits an offer only if the shopper bought
  it without being shown it. It cannot see purchases an offer would have
  caused, so it likely understates any recommender, and it cannot
  measure how shoppers react to being shown higher-margin items. Only an
  online A/B test can.

- **One store, one task.** One UK wholesaler, mostly business buyers,
  2009–2011. Hiding one item per invoice is a proxy for a real checkout
  widget.

- **Retrieval ceiling.** 35% of test targets are outside the candidate
  pool, which bounds every Stage 1 and Stage 2 result.

- **LLM scope.** We tested two small instruction-tuned models zero-shot,
  one prompt and one scoring method, on the slates of the first ranker
  (Hit@10 35.6%). Larger models, other prompts, or fine-tuning may
  behave differently; the fine-tune is pending.

- **Latency.** Solver time is 2.7 ms. The serving latency in the
  repository (p50 22 ms for the research API, p95 88 ms end to end for
  the multi-store service) was measured in a container, not in a store’s
  production setting.

## Conclusion

On a public retail dataset and a CPU, a calibrated gradient-boosted
reranker beats a strong classical ladder for checkout add-ons, and a
tiny per-basket MILP converts its probabilities into choices that
respect hard margin and stock rules while raising (simulated) profit at
a small, tunable cost in hit rate. Small open LLMs, used zero-shot, did
not help. The next steps are to replace simulated costs with a real
store’s data, to run an online test, and to finish the fine-tuned LLM
experiment.

## Reproducibility

Code, configuration and every result file are in the repository.
`margingraph run` rebuilds experiments E1–E11 on a CPU (seed 42) and
writes them to `results/`; `paper/figures/make_figures.py` rebuilds the
figures from those files. The LLM experiments use
`notebooks/llm_rerank_gpu.ipynb` and `notebooks/llm_finetune_gpu.ipynb`
on a free Kaggle T4 GPU; their numbers are recorded in
`docs/RESULTS.md`.

## Use of AI tools

The software, experiments and this manuscript were developed with the
help of an AI coding assistant (Claude Code). All reported numbers come
from the pipeline’s output files or from logged Kaggle runs, and were
checked against them.

## References

<div id="refs" class="references csl-bib-body hanging-indent">

<div id="ref-abdollahpouri2020multistakeholder" class="csl-entry">

Abdollahpouri, Himan, Gediminas Adomavicius, Robin Burke, Ido Guy,
Dietmar Jannach, Toshihiro Kamishima, Jan Krasnodebski, and Luiz
Pizzato. 2020. “Multistakeholder Recommendation: Survey and Research
Directions.” *User Modeling and User-Adapted Interaction* 30: 127–58.
<https://doi.org/10.1007/s11257-019-09256-1>.

</div>

<div id="ref-agarwal2011clickshaping" class="csl-entry">

Agarwal, Deepak, Bee-Chung Chen, Pradheep Elango, and Xuanhui Wang.
2011. “Click Shaping to Optimize Multiple Objectives.” In *Proceedings
of the 17th ACM SIGKDD International Conference on Knowledge Discovery
and Data Mining (KDD)*. <https://doi.org/10.1145/2020408.2020435>.

</div>

<div id="ref-bao2023tallrec" class="csl-entry">

Bao, Keqin, Jizhi Zhang, Yang Zhang, Wenjie Wang, Fuli Feng, and
Xiangnan He. 2023. “TALLRec: An Effective and Efficient Tuning Framework
to Align Large Language Model with Recommendation.” In *Proceedings of
the 17th ACM Conference on Recommender Systems (RecSys)*.

</div>

<div id="ref-burges2010lambdamart" class="csl-entry">

Burges, Christopher J. C. 2010. “From RankNet to LambdaRank to
LambdaMART: An Overview.” MSR-TR-2010-82. Microsoft Research.

</div>

<div id="ref-chen2019onlineretail" class="csl-entry">

Chen, Daqing. 2019. “Online Retail II.” UCI Machine Learning Repository.
<https://doi.org/10.24432/C5CG6D>.

</div>

<div id="ref-chen2012rfm" class="csl-entry">

Chen, Daqing, Sai Laing Sain, and Kun Guo. 2012. “Data Mining for the
Online Retail Industry: A Case Study of RFM Model-Based Customer
Segmentation Using Data Mining.” *Journal of Database Marketing &
Customer Strategy Management* 19 (3): 197–208.

</div>

<div id="ref-efron1993bootstrap" class="csl-entry">

Efron, Bradley, and Robert J. Tibshirani. 1993. *An Introduction to the
Bootstrap*. Chapman & Hall/CRC.

</div>

<div id="ref-dacrema2019progress" class="csl-entry">

Ferrari Dacrema, Maurizio, Paolo Cremonesi, and Dietmar Jannach. 2019.
“Are We Really Making Much Progress? A Worrying Analysis of Recent
Neural Recommendation Approaches.” In *Proceedings of the 13th ACM
Conference on Recommender Systems (RecSys)*.

</div>

<div id="ref-hou2024zeroshot" class="csl-entry">

Hou, Yupeng, Junjie Zhang, Zihan Lin, Hongyu Lu, Ruobing Xie, Julian
McAuley, and Wayne Xin Zhao. 2024. “Large Language Models Are Zero-Shot
Rankers for Recommender Systems.” In *Advances in Information Retrieval:
46th European Conference on Information Retrieval (ECIR)*.

</div>

<div id="ref-hu2022lora" class="csl-entry">

Hu, Edward J., Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi
Li, Shean Wang, Lu Wang, and Weizhu Chen. 2022. “LoRA: Low-Rank
Adaptation of Large Language Models.” In *International Conference on
Learning Representations (ICLR)*.

</div>

<div id="ref-hu2008implicit" class="csl-entry">

Hu, Yifan, Yehuda Koren, and Chris Volinsky. 2008. “Collaborative
Filtering for Implicit Feedback Datasets.” In *IEEE International
Conference on Data Mining (ICDM)*.

</div>

<div id="ref-huangfu2018highs" class="csl-entry">

Huangfu, Qi, and J. A. Julian Hall. 2018. “Parallelizing the Dual
Revised Simplex Method.” *Mathematical Programming Computation* 10 (1):
119–42. <https://doi.org/10.1007/s12532-017-0130-5>.

</div>

<div id="ref-jannach2017price" class="csl-entry">

Jannach, Dietmar, and Gediminas Adomavicius. 2017. “Price and Profit
Awareness in Recommender Systems.” *arXiv Preprint arXiv:1707.08029*.

</div>

<div id="ref-ke2017lightgbm" class="csl-entry">

Ke, Guolin, Qi Meng, Thomas Finley, Taifeng Wang, Wei Chen, Weidong Ma,
Qiwei Ye, and Tie-Yan Liu. 2017. “LightGBM: A Highly Efficient Gradient
Boosting Decision Tree.” In *Advances in Neural Information Processing
Systems 30 (NeurIPS)*.

</div>

<div id="ref-krichene2020sampled" class="csl-entry">

Krichene, Walid, and Steffen Rendle. 2020. “On Sampled Metrics for Item
Recommendation.” In *Proceedings of the 26th ACM SIGKDD International
Conference on Knowledge Discovery and Data Mining (KDD)*.
<https://doi.org/10.1145/3394486.3403226>.

</div>

<div id="ref-louca2019profit" class="csl-entry">

Louca, Raphael, Moumita Bhattacharya, Diane Hu, and Liangjie Hong. 2019.
“Joint Optimization of Profit and Relevance for Recommendation Systems
in e-Commerce.” In *Workshop on Recommendation in Multistakeholder
Environments (RMSE) at ACM RecSys*. Vol. 2440. CEUR Workshop
Proceedings.

</div>

<div id="ref-mitchell2011pulp" class="csl-entry">

Mitchell, Stuart, Michael O’Sullivan, and Iain Dunning. 2011. “PuLP: A
Linear Programming Toolkit for Python.” Optimization Online.

</div>

<div id="ref-pei2019value" class="csl-entry">

Pei, Changhua, Xinru Yang, Qing Cui, Xiao Lin, Fei Sun, Peng Jiang,
Wenwu Ou, and Yongfeng Zhang. 2019. “Value-Aware Recommendation Based on
Reinforced Profit Maximization in e-Commerce Systems.” *arXiv Preprint
arXiv:1902.00851*.

</div>

<div id="ref-qwen2025qwen25" class="csl-entry">

Qwen Team. 2024. “Qwen2.5 Technical Report.” *arXiv Preprint
arXiv:2412.15115*.

</div>

<div id="ref-sarwar2001itemcf" class="csl-entry">

Sarwar, Badrul, George Karypis, Joseph Konstan, and John Riedl. 2001.
“Item-Based Collaborative Filtering Recommendation Algorithms.” In
*Proceedings of the 10th International Conference on World Wide Web
(WWW)*.

</div>

<div id="ref-steck2019ease" class="csl-entry">

Steck, Harald. 2019. “Embarrassingly Shallow Autoencoders for Sparse
Data.” In *The World Wide Web Conference (WWW)*, 3251–57.
<https://doi.org/10.1145/3308558.3313710>.

</div>

<div id="ref-zadrozny2002calibration" class="csl-entry">

Zadrozny, Bianca, and Charles Elkan. 2002. “Transforming Classifier
Scores into Accurate Multiclass Probability Estimates.” In *Proceedings
of the 8th ACM SIGKDD International Conference on Knowledge Discovery
and Data Mining (KDD)*.

</div>

</div>
