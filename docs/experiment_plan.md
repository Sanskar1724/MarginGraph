# MarginGraph review and experiment plan

Oct 25, 2026 · San

The architecture is worth keeping, but none of the reported numbers count as evidence yet: V1 ran on generated mock sessions, and V2 on random candidates and random carts. The next step is a clean Stage 1 on real data, with strong non-LLM baselines.

## Scorecard

The idea scores well; the evidence behind it scores very low. Ratings are out of 10.

| Part | Rating | Why |
| --- | --- | --- |
| Core idea (LLM for relevance, solver for money) | 7 | Clean split of jobs, a real business problem, easy to explain. Loses points because relevance and profit are never linked in the objective. |
| Stage 1 design (LLM writes product IDs) | 3 | Asking an LLM to generate opaque IDs like "1067" gives it nothing to reason about. Retrieve first, then rerank with titles: that is the right shape, and the 2.0 plan already says so. |
| Stage 2 design (PuLP) | 4 | With a per-item margin filter and at most 2 items, the MILP reduces to "sort by score, take the top 2". It is correct, but it does no real optimization yet. |
| V1 notebook evidence | 2 | Ran on generated mock sessions; the LLM trained for 30 steps; the economic tests used popularity items, not LLM output. |
| V2 notebook evidence | 1 | Stage 1 candidates are random SKUs, carts are random, and cost/stock/conversion are random. The 1549% figure is an artifact. |
| Detailed project report | 6 | Honest self-critique of backfill, leakage and inventory. Misses the biggest issue: it calls the data real OTTO, but V1 overwrote it with mock data. |
| Repo and reproducibility | 2 | Before this commit the repo held only a README: no code, splits, configs or result files. |

## What the past results really show

None of the reported results yet tells us whether the LLM or the optimizer helps.

| Claim | What actually happened | What it supports |
| --- | --- | --- |
| V1: OTTO behavioral data, 50,000 sessions | V1 cell 34 writes `/content/data/train.jsonl` from `np.random`: 100 item IDs (1000–1099) with random event types. | Nothing about real behavior. |
| V1: popularity Hit@5 8.8%, LLM 8.1% | With 100 items and about 1.8 random targets, chance Hit@5 is 1 − 0.95^1.8 ≈ 8.8%. Both numbers are pure chance. | The pipeline runs end to end. |
| V1: fine-tuned Llama 3.1 8B | 30 steps × 16 = 480 of 39,907 examples (about 1% of an epoch), on random targets. Several later cells decode a stale `outputs` variable without calling `generate`. | The fine-tuning code runs on a T4. |
| V1: +84.7% profit from the optimizer | The candidates were popularity items for every session. "llm_only" picks by conversion alone, and the reported profit has no conversion factor. | The solver picks higher-margin items when told to. |
| V1: 95% CI $169–$173 | Nearly every session had the same 3 candidates, so the inputs barely vary. It covers one strategy, not a paired difference. | Nothing. |
| V1: overstock clearance +89% | Counts how often overstocked SKUs were picked; stock is never decremented. | Selection rate under a 1.3× weight. |
| V1: 0 violations in 1,000 stress tests | The solver enforces the per-item 15% floor and the ≤ 2 items limit. | **Real; keep it.** |
| V2: +1549% vs popularity | Stage 1 is random SKUs; carts are random (the OTTO download failed on `--unzip`); popularity was counted on the eval carts themselves; Strategy D always adds the same 10 overstocked SKUs. | Nothing. |
| 2.0: LLM Hit@5 0% vs popularity 0.8% (500 customers) | 0 hits vs 4 hits out of 500, too few to separate the two. | Stage 1 is not working yet; the data may also lack signal (see E1). |

## Design critique

**Keep**

- The ranker owns relevance; the solver owns money and hard rules.
- The 15% floor, ≤ 2 add-ons, discount tiers and the constraint stress test.
- The retrieve → rerank shape, and the rule that claims must come from experiments.

**Change**

1. **Tie conversion to relevance.** Use p(accept) = a calibrated Stage 1 score (isotonic regression on validation data), so the optimizer can't push irrelevant high-margin items.
2. **Let the LLM read, not recall.** Give it 20–50 retrieved candidates with titles, labelled A, B, C…, and have it rank the labels.
3. **Compare against a strong non-LLM reranker,** for example LightGBM on co-purchase, recency, category and price features.
4. **Make the solver earn its place:** a bundle-level margin floor, discount as a decision variable, a minimum relevance per bundle, or shared stock.
5. **Use real prices where possible.**
6. **One codebase, not notebooks:** `src/`, a config file, fixed seeds, and result tables saved with the commit that produced them.

## Experiment plan

**Phase A — Stage 1 (do first)**

| # | Experiment | Gate to continue |
| --- | --- | --- |
| E1 | Data signal audit: popularity skew, repeat-purchase rate, co-purchase lift vs a shuffled null; chance Hit@5 = 5 ÷ catalog size. | Lift clearly above the null; otherwise switch dataset. |
| E2 | Strict temporal split with one global cutoff; popularity counted on train only. | No targets before the cutoff. |
| E3 | Baseline ladder: popularity, recent popularity, repeat purchase, co-purchase, ItemKNN/EASE, ALS/BPR. | Best baseline beats chance with separated CIs. |
| E4 | Candidate recall at K = 20 and 50. | Recall@50 high enough to leave room for reranking. |
| E5 | Rerankers on the same pool: LightGBM, zero-shot LLM, combined. | LLM within reach of LightGBM. |
| E6 | Fine-tune the reranker (≥ 1 epoch, hard negatives, early stopping; 1.5–3B vs 8B). | **Go/no-go:** beats the best non-LLM reranker, with a paired CI above zero. |

**Phase B — Stage 2 (only after the E6 gate)**

| # | Experiment | Output |
| --- | --- | --- |
| E7 | Calibrate p(accept). | Calibration plot, Brier score |
| E8 | Strategy comparison at 0/10/20% discount, overstock weight w ∈ {1.0, 1.25, 1.5, 2.0}. | Profit, Hit@2, margin, violations, paired bootstrap |
| E9 | Richer MILP. | Same as E8, plus solve time |
| E10 | Sequential inventory simulation, 20 seeds. | Units cleared, sessions to clear |
| E11 | ERP sensitivity analysis. | Robustness of conclusions |

The headline result should be a profit vs relevance trade-off curve, not a single percentage.

## Free stack

- **Primary dataset:** [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii): real baskets, real prices, short descriptions. Scale-up option: H&M Personalized Fashion (Kaggle). OTTO is a poor fit for the LLM because its item IDs are anonymous.
- **Compute:** laptop or Colab CPU for E1–E4 and Stage 2; Kaggle Notebooks or a free Colab T4 for E5–E6.
- **Storage:** Parquet + DuckDB; no database server.
- **Libraries:** `implicit`, LightGBM, Unsloth QLoRA (Qwen2.5-1.5B/3B for iterating, Llama 3.1 8B for the final run), PuLP + CBC.
- **Tracking and hosting:** results CSVs in GitHub, LoRA adapter on the Hugging Face Hub, Gradio or FastAPI on a free HF Space.
- **Secrets:** Colab/Kaggle secrets only.

## Path to production

The problem is real, but the system only becomes credible after it shows an online lift on a retailer's real data. Until then, the target is a pilot-ready system.

1. Run the LLM in a nightly batch and store the ranked lists.
2. Online path: lookup → stock filter → PuLP → 2 add-ons, in under 100 ms, with a margin-safe "bought together" fallback.
3. Real cost, price and stock from the ERP/Shopify feed; purchase probability learned from the retailer's own logs.
4. Trust: a 2–4 week A/B test on profit per session, hard constraints enforced in code, an audit log, no personal data sent to the LLM, and merchant controls.
5. Free pilot: FastAPI on an HF Space, plus a Shopify development store loaded with Online Retail II data.
