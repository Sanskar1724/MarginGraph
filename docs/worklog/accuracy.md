# Worklog: Stage 1 accuracy (thread "Improve recommendation accuracy")

Branch `claude/project-thread-pxguuk`. All times are UTC on 2026-10-26. Every number below comes from a run in this container (4 CPU cores, no GPU). Raw rows are in `results/accuracy/experiments.csv`. The script that produced them is `scripts/accuracy_experiments.py`.

## 1. Goal and rules (11:43)

San asked for a better, usable product on free tools that fits a laptop with 8 GB of RAM. The coordinator scoped this thread to Stage 1 accuracy: raise candidate recall (58.0%) and LightGBM Hit@10 (35.6%) without touching the LLM work.

The rules for this thread were:
- Use the same data, temporal split and leave-one-out events as `margingraph run`. Test is Oct to Dec 2011, with 4,480 events.
- **Selection is done on val, never on test.** A change is kept only if it wins on the held-out 30% of val events (1,147 events, the last ones in time, never used to fit trees). Test results are reported for every variant, winners and losers alike.
- Every test comparison is paired against the same 4,480 events, with 2,000 bootstrap resamples and 95% CIs.

## 2. Setup and baseline reproduction (11:46–11:51)

- `pip install -e ".[dev]"` and `gensim` (for item2vec only). Then `margingraph prepare` turned the uploaded xlsx into 991,910 lines, 39,516 invoices and 4,707 products, the same as the earlier run.
- **A0 baseline** (the config before this thread): pool recall 58.0%, LightGBM Hit@10 35.6% on test. This matches `RESULTS.md` exactly, so the harness is faithful.
- **Fact found:** 7.1% of test targets were never sold before October. Of those, **96.2% were sold earlier in the test window, before the event's day**, mostly new Christmas stock. A nightly-refreshed source can therefore reach items that the frozen models cannot.

## 3. New candidate sources (code in `models.py`, switched on in `retrieval.extra`)

| Source | What it scores |
| --- | --- |
| `ease_decay` | EASE fit on recency-weighted baskets (weight 0.5^(age/120 days)) |
| `cust_ease` | EASE scores of the customer's past items ("customers like you also buy") |
| `text` | TF-IDF cosine of product descriptions (word 1-2 grams + char 3-4 grams), max over the basket. Finds colour and size variants and items with few sales |
| `item2vec` | gensim skip-gram over shuffled baskets (≤ 50 items, window 20, 64 dims, 5 epochs) |
| `fresh` → `trend`, `fresh_co` | Sales since the models were fit, as a nightly job would see them: only invoices from days **before** the event's day. `trend` counts invoices in the last 14 days; `fresh_co` is co-purchase with the basket over that stream |

To let `fresh` recommend new products, the item index can now cover the whole catalog (`index_scope: catalog`). Products with no sales before the event get zero from every source, so they cannot leak in.

## 4. Experiments, in the order they were run

Δ is paired against A0 unless noted. Val Δ is on the held-out val events.

### B. One source at a time, pool kept at 100 (11:51–12:13)

| Variant | Test pool recall | Val Δ Hit@10 | Test Hit@10 | Test Δ Hit@10 [95% CI] | Kept? |
| --- | --- | --- | --- | --- | --- |
| + ease_decay | 57.8% | +0.35 | 35.8% | +0.16 [−0.47, +0.78] | no (alone) |
| + cust_ease | 56.9% | +1.22 | 35.6% | +0.02 [−0.60, +0.65] | no (alone) |
| + text | 57.2% | +0.52 | 35.2% | −0.42 [−1.07, +0.27] | no (alone) |
| + item2vec | 56.0% | 0.00 | 35.4% | −0.22 [−0.89, +0.40] | no |
| + fresh | 58.6% | +0.61 | 36.0% | +0.45 [−0.33, +1.27] | no (alone) |

Every source alone was within noise. The reason was the pool size: the pool is filled source by source and cut at 100, so a new source pushes out EASE and ItemKNN candidates. Pool recall barely moved, and fell for most sources.

**Bug found and fixed:** the first item2vec run used a window equal to the largest basket (several hundred items) and ran for over 12 minutes without finishing. I capped baskets at 50 items and the window at 20, and it then trains in about 30 seconds.

### Marginal-recall check (12:15)

I measured how often each source's top K holds a target that the old 100-item pool missed (`results/accuracy/source_marginal_recall.csv`). These are test figures, used as a diagnosis only; nothing was selected on them.

| Source | New targets in its top 20 | New targets in its top 50 |
| --- | --- | --- |
| text | 3.8% | 6.4% |
| fresh_co | 3.1% | 5.6% |
| trend | 2.7% | 4.9% |
| item2vec | 1.3% | 2.8% |
| cust_ease | 0.8% | 2.0% |
| ease_decay | 0.2% | 1.5% |

So the sources do find items the old pool misses. They needed room in the pool.

### C. Combined sources and pool size (12:17–12:26)

Sources ease_decay + cust_ease + text + fresh, inserted right after EASE, with per-source quotas scaled with the pool.

| Pool | Test pool recall | Val Hit@10 | Test Hit@10 | Test Δ Hit@10 [95% CI] |
| --- | --- | --- | --- | --- |
| 100 | 60.3% | 40.2% | 37.4% | +1.76 [+0.83, +2.70] |
| **150** | **65.3%** | **40.6%** | **37.3%** | **+1.70 [+0.80, +2.61]** |
| 200 | 69.0% | 40.5% | 37.7% | +2.08 [+1.14, +3.04] |

**Picked pool 150.** It had the best val Hit@10, and 200 did not beat it on val while costing a third more rows. Test hints that 200 may be slightly better. I did not switch, because that would be choosing on test.

### C-ablation: drop one source at a time, pool 150 (12:26–12:41)

| Variant | Val Hit@10 | Val Δ vs full combo | Test Hit@10 |
| --- | --- | --- | --- |
| All four (reference) | 40.6% | — | 37.3% |
| without ease_decay | 39.5% | −1.1 | 37.5% |
| without cust_ease | 38.5% | −2.1 | 36.0% |
| without text | 39.2% | −1.4 | 36.7% |
| without fresh | 39.3% | −1.3 | 35.8% |
| plus item2vec | 39.5% | −1.1 | 37.1% |

Each of the four sources helps on val, so all four are kept. Adding item2vec makes val worse, so it is **dropped** (it stays in the code, off by default). On test, removing ease_decay looks neutral (+0.2). It is kept by the val rule, which is the honest choice.

### D. Ranker (12:41–12:46)

The reference is the C pool-150 setup. Δ is against that reference.

| Variant | Val Δ Hit@10 | Test Hit@10 | Test Δ Hit@10 [95% CI] | Kept? |
| --- | --- | --- | --- | --- |
| **3 hidden-item events per val invoice** (fit data ×2.9) | +0.52 | 38.1% | +0.78 [+0.11, +1.52] | **yes** |
| num_leaves 63, lr 0.03, min_child 50 | −1.05 | 37.0% | −0.31 [−0.92, +0.27] | no |
| num_leaves 15, lr 0.05, min_child 100 | +0.09 | 37.8% | +0.47 [−0.11, +1.07] | no (tie on val) |
| lr 0.03, feature 0.7, bagging 0.8 | −1.22 | 37.0% | −0.31 [−0.94, +0.31] | no |
| lambdarank truncation 20 | −0.87 | 37.5% | +0.22 [−0.33, +0.80] | no |

The extra events re-hide a different product from the same val invoice, and only for invoices before the holdout cut. Early stopping, calibration and every metric use the original events only. The default LightGBM settings stay.

### F. Final configuration vs the old one (12:56)

| Metric (test, 4,480 baskets) | Before | After | Paired Δ [95% CI] |
| --- | --- | --- | --- |
| Pool recall | 58.0% (pool 100) | **65.3%** (pool 150) | +7.3 pts [+6.2, +8.3] |
| LightGBM Hit@5 | 26.1% | **28.8%** | |
| LightGBM Hit@10 | 35.6% | **38.1%** | **+2.5 pts [+1.6, +3.4]** |
| LightGBM NDCG@10 | 0.217 | **0.237** | +0.020 [+0.015, +0.025] |
| Val Hit@10 (held-out) | 37.2% | 41.2% | +3.9 pts [+2.1, +5.8] |

## 5. Wired into the product (12:46–12:58)

- `configs/default.yaml`: pool 150, the four sources, `index_scope: catalog`, `train_events_per_invoice: 3`. Item2vec is documented there as tried and off.
- `features.py`: the extra sources, a nightly stream (`set_stream`), and per-event times passed to `generate`. The API calls `generate` without a time, which means "now", so it uses every sale in the stream before today.
- `split.py` / `rerank.py`: `add_extra_hides` creates the extra events, and `split_events` keeps them out of early stopping and calibration.
- `pipeline.py`: streams per split, E3/E4 on original events only. The LLM fine-tune slates (train-period events) run with the stream off, because val sales would be in their future.
- `tests/test_accuracy_sources.py`: fresh uses only sales from earlier days, text finds colour variants, customer EASE, decay weights. The full suite passes: 63 passed, 1 skipped.

## 6. Full `margingraph run` with the new config (12:47–12:58)

- **Runtime 10.2 min and peak RAM 3.9 GB** on 4 CPU cores. That fits an 8 GB laptop.
- E5: LightGBM Hit@10 38.1% vs EASE 31.1% (+7.0 pts [6.0, 8.0]). Hit@5 28.8%, NDCG@10 0.237. This matches experiment F.
- E7 calibration: test Brier 0.00417. A constant base-rate guess scores 0.00435 (base rate 0.437%), so the probabilities are sharper than before (0.00560 vs 0.00568).
- E8 (simulated cost and stock): ranker top-2 Hit@2 17.8% (was 16.7%), realized profit 0.205 (was 0.184). MILP λ=0.5 gives +0.028 [0.014, 0.044] profit (+14%) for −1.1 pts Hit@2. MILP λ=1 gives +0.049 [0.031, 0.069] (+24%) for −2.9 pts. The margin floor broke 0 times.
- E9: 600/600 MILP vs enumeration agree, 2.7 ms mean.
- E11: the MILP λ=1 profit gain stays positive in all 9 cost scenarios (+0.024 to +0.071, every CI above 0).

## 7. What did not work, and open ideas

- item2vec: no gain, alone or combined.
- Bigger or smaller trees, bagging, LambdaRank truncation: no val gain.
- Not tried yet: pool 200 chosen on a fresh val window, a seasonal "same weeks last year" source, and the price-band and country features.
