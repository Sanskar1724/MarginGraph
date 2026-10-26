# MarginGraph: roadmap to a real product

*Last updated 2026-10-26. This is a plan, not a result. Measured results are in [`PROJECT_REPORT.md`](PROJECT_REPORT.md) and [`RESULTS.md`](RESULTS.md). Any number below marked "target" is a goal to test, not a claim.*

The rule for the whole roadmap: **a claim moves from "target" to "result" only after an experiment or a live test measures it.**

---

## Where we are now

| Area | State |
| --- | --- |
| Relevance (LightGBM ranker) | Proven offline on real baskets: Hit@10 38.1% vs 31.1% for EASE (was 35.6% before the accuracy work) |
| Profit optimizer (PuLP) | Proven offline, **with simulated cost and stock**: +14% profit at λ=0.5 |
| Margin floor | 0 breaks in every test |
| LLM ranker | NO-GO zero-shot (1.5B, 3B) and as a stacker feature. LoRA fine-tune (E6) is next |
| API | Demo-level FastAPI (`margingraph serve`) |
| Production API, demo app, store connectors | **In progress** in separate pull requests |

## Phase 1: finish the research (now, free)

- [ ] **E6 LoRA fine-tune** on free Kaggle T4 (`notebooks/llm_finetune_gpu.ipynb`). Gate: must beat LightGBM Hit@5 on the same 1,000 paired baskets, with the CI above zero.
- [ ] If E6 is NO-GO, use the LLM only for **cold-start items** (new products with no sales) and **plain-language explanations** ("goes with your woodland party cups"), never for ranking or prices.
- [x] Raise shortlist recall above 58.0%: now 65.3% with a 150-item pool and text, fresh-sales, customer-EASE and time-decayed EASE sources ([accuracy worklog](worklog/accuracy.md)).
- [ ] Pick the pool size (150 vs 200) on a fresh validation window; 200 reached 69.0% recall but did not win on val.
- [ ] Benchmark end-to-end API latency (p50, p95) on a free CPU host and record it in `RESULTS.md`.

## Phase 2: production service (in progress, free tier)

Built to run on a student budget. No GPU is needed to serve: LightGBM and PuLP run on one CPU.

```text
          nightly batch (GitHub Actions cron, free)
   ┌──────────────────────────────────────────────┐
   │ pull orders → retrain EASE + LightGBM        │
   │ → write model bundle + candidate lists       │
   └───────────────┬──────────────────────────────┘
                   ▼
   Store webhook ─► FastAPI (Docker, stateless) ─► Redis cache (candidates, stock)
   (order, stock)     │  POST /recommend            Postgres (catalog, cost, stock, logs)
                      ▼
          up to 2 margin-safe add-ons, with a fallback
```

| Piece | Free option | Why |
| --- | --- | --- |
| API host | Hugging Face Spaces (Docker) or Render free tier | Free CPU, public HTTPS URL |
| Database | Supabase or Neon (free Postgres) | Catalog, cost, stock, request and purchase logs |
| Cache | Upstash Redis (free tier) | Candidate lists and stock, so the live path stays fast |
| Nightly retrain | GitHub Actions scheduled workflow | Free minutes on public repos |
| Model storage | Hugging Face Hub or GitHub Releases | Versioned model bundles |
| Monitoring | Grafana Cloud free tier, or a simple `/metrics` page | Latency, errors, floor breaks |
| Demo | Gradio on Hugging Face Spaces | A shareable page for a store owner to try |
| LLM steps (if used) | Kaggle or Colab free GPU, offline only | Never on the live path |

**Must-haves before a pilot:**
- [ ] **Fallback:** if the model or solver fails or is slow, return the best sellers that pass the margin floor, so the shop page never breaks.
- [ ] **Hard rule check on every response:** re-check the 15% floor and the 2-item limit in code before returning.
- [ ] **Per-store settings:** margin floor, max add-ons, λ, overstock weights.
- [ ] **Logging:** what was shown, what was clicked, what was bought, with timestamps.
- [ ] **Auth:** an API key per store; no secrets in code or notebooks.
- [ ] **Tests and CI:** run `pytest` on every pull request.

## Phase 3: connect a real store

- [ ] **Shopify** (free development store) or **WooCommerce** (free plugin) connector: sync products, prices and orders; show add-ons in the cart.
- [ ] Import **real unit cost and stock** from the store's own data. This is the step that turns the profit result from simulated to real.
- [ ] Rerun `margingraph run` on the store's history and check the offline gate again: the ranker must beat the store's current "also bought" and best sellers.

## Phase 4: pilot and A/B test

**Pilot store profile:** a small online shop with at least a few thousand orders a year, a few hundred products, and access to unit cost. Good fits: gift, home decor, stationery, beauty, specialty food. Offer it free for the pilot in return for the data and a case study.

**A/B test design:**

| | |
| --- | --- |
| Split | 50/50 by visitor, fixed for each visitor |
| Control | The store's current suggestions (or best sellers) |
| Treatment | MarginGraph add-ons |
| Main metric | Gross profit per visitor |
| Guard metrics | Conversion rate, average order value, margin-floor breaks (must be 0), API errors and latency |
| Length | At least 2 full weeks, and until the planned sample size is reached. Decide the sample size before starting |
| Analysis | Paired bootstrap or a t-test on profit per visitor, with a 95% CI, as in the offline work |

**Decision rule:** ship to the whole store only if profit per visitor is higher with the CI above zero, and conversion is not clearly worse.

## Phase 5: grow it into a service

**Multi-store:** one shared service, with a separate model, settings and data for each store.

**Business model (to test with pilot stores, not proven):**

| Plan | Who | Idea |
| --- | --- | --- |
| Free | Small shops | Up to a fixed number of requests a month, best-seller fallback, basic dashboard |
| Pro | Growing shops | Full optimizer, overstock push, A/B test reports, a flat monthly fee |
| Performance | Larger shops | A share of the measured extra profit from the A/B test, so the store pays only for proven gains |

**Selling point:** "Suggestions that sell **and** keep your margin, with a hard floor you control." The proof is each store's own A/B test, not our offline numbers.

## Risks and how we handle them

| Risk | Plan |
| --- | --- |
| Real cost data changes the profit result | E11 already varies the assumptions. The pilot measures it for real before any profit claim is made |
| A store has too little history | Start with best sellers that pass the floor and co-purchase. Switch to the ranker once there is enough data |
| New products have no sales | Cold-start by product text (the LLM's most likely role) |
| Free tiers sleep or have limits | Keep the fallback. Move to a paid tier only when a paying store needs it |
| Overstock push annoys shoppers | Cap the overstock weight at 2.0 and watch conversion as a guard metric |

## Milestones

| Milestone | Done when |
| --- | --- |
| M1 Research complete | E6 run and recorded, latency benchmarked |
| M2 Service live | Production API, fallback, logging and demo deployed on free hosting |
| M3 First store connected | Real cost and stock imported, offline gate passed on its data |
| M4 Pilot result | A/B test finished and written up, win or lose |
| M5 Second and third store | Multi-store settings in use, first paid plan tested |
