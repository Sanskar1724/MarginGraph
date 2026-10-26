# Work log: free live demo (Hugging Face Space)

Date: 2026-10-26 · Branch: `claude/project-thread-r1a0d1` (based on `claude/project-thread-mkbaip`, PR #2)
Asked by San: a product a retail store can actually use, built on free resources, light enough for an 8 GB laptop.

## Idea

A shop owner should be able to open one link and see, for any basket, which 2 add-ons to show at checkout,
and how much more profit that earns than the plain "customers also bought" top 2. Then upload their own
products (price, cost, stock) and orders and get the same thing for their store, one basket or thousands.

## Plan and approach

| Choice | Why |
|---|---|
| Gradio app on a free Hugging Face Space (CPU basic) | Free, public URL, no server to run, every button is also an API endpoint. |
| Ship EASE only, not the LightGBM reranker | EASE is one matrix (7 MB) and needs only numpy. The reranker needs the whole feature pipeline (implicit, lightgbm, duckdb) and more RAM. EASE is the strongest single baseline in the repo. |
| 2,000 most-bought products (train+val) | Keeps the model at 7 MB and RAM at ~250 MB. Covers 77% of test lines. |
| Calibrate p(buy) with a 3-weight logistic model on held-out baskets | The optimizer needs probabilities, not scores. Fit on Jul-Sep 2011, never on test. |
| Exact optimizer by enumeration instead of PuLP | For at most 2 add-ons, enumerating all singles and pairs is exact, has no solver dependency and runs in microseconds. Same objective and rules as `margingraph.optimize`. Checked against brute force in tests. |
| Merchant mode trains on uploaded orders in the browser session | A real store has its own catalog; reusing Online Retail II co-purchases would be wrong for them. Training 2,500 products takes ~2 s on CPU. |
| Self-contained `space/` folder | Another thread is building the production API; the demo must not depend on it. |

## What was built

* `space/core.py`: EASE fit, leave-one-out calibration, exact Stage 2 solver, `Model.recommend`, merchant training.
* `space/app.py`: 4 tabs. *Demo store* (basket picker, sliders for margin floor, overstock weight, relevance/profit balance,
  discounts, 1 or 2 add-ons; side-by-side cards plain top-2 vs MarginGraph with "bought with" reason).
  *Your store* (products CSV and orders CSV with column-name aliases such as sku, cost, on_hand, order_id;
  templates to download; single basket; batch CSV in, recommendations CSV out). *Backtest*. *How it works / API*.
* `space/build_artifacts.py`: builds `space/artifacts/` from the xlsx with the repo's own cleaning and ERP simulation.
* `space/DEPLOY.md`: click-by-click Space setup. `space/README.md`: Space config.
* `tests/test_space_demo.py`: 32 tests (solver vs brute force on 30 random cases with discounts and stock,
  merchant training end to end, unknown codes and missing prices).

## Commands run

```bash
pip install gradio scikit-learn pyarrow pyyaml pytest      # gradio 6.30.0, python 3.13
# clean once with margingraph.data (reads both xlsx sheets, ~2 min), cached to parquet
python space/build_artifacts.py --lines lines.parquet --catalog catalog.parquet   # 20 s
python -m pytest -q tests/test_space_demo.py                 # 32 passed
GRADIO_SERVER_PORT=7860 python space/app.py                  # then a Playwright script drove the UI
```

## Results (measured, Oct-Dec 2011 test invoices, 4,000 leave-one-out baskets)

Data after cleaning: 991,910 lines, 39,516 invoices, 4,707 products.

Stage 1, EASE on the 2,000-product catalog: Hit@2 16.6%, Hit@5 26.5%, Hit@10 36.1%.
Not comparable to the repo's 31.1% EASE Hit@10: here the hidden item is always one of the 2,000 products
(baskets are restricted to them), which makes the task easier.

Stage 2 (margin floor 15%, no discounts; **cost and stock simulated**):

| Strategy | Hit@2 | Realized profit / basket | vs top-2 | 95% CI of diff (£/basket) | Below floor / basket | Overstock share |
|---|---|---|---|---|---|---|
| Plain top-2 | 16.6% | £0.192 | | | 0.024 | 14.9% |
| MarginGraph balance 0.5 | 13.4% | £0.235 | +22.1% | [+0.025, +0.062] | 0 | 13.0% |
| MarginGraph balance 1.0 | 13.2% | £0.235 | +22.1% | [+0.024, +0.062] | 0 | 13.0% |
| Balance 1.0, overstock 2x | 12.7% | £0.228 | +18.6% | [+0.018, +0.055] | 0 | 26.3% |

Realized profit counts only the product the customer really bought, so it is grounded in behaviour.
Trade-off: about +22% profit for about -3.3 points of Hit@2. The overstock weight doubles the share of overstock offers
for a smaller profit gain, which is the expected cost of clearing stock.

UI test (Playwright, headless Chromium), all passed with no page errors:
* Demo store loads with a real basket: +83% expected profit, -2.7 pts sale chance, 0 floor violations for that basket.
* Random real basket button changes the basket and result.
* Your store with 3,138 products + 6,000 orders: trained 2,500 products in ~2 s; backtest on its newest 20% of orders:
  Hit@2 14.8%, Hit@10 31.8% (1,007 baskets). Recommend and batch (CSV download) work.
* Products-only upload (no orders): 1,782 of 3,138 codes matched the demo model and were recommendable.
* RAM: 240 MB at start, 345 MB after a merchant trained a 2,500-product model.

## Failures and fixes along the way

1. **Calibration NaN on small catalogs.** The merchant test (20 products) produced `-inf` scores in the candidate list,
   so the logistic fit returned NaN and nothing was recommended. Fixed: drop non-finite candidates, and use L2 = 1.0
   (stable on near-separable data). Artifacts rebuilt after the fix; numbers above are from the rebuilt run.
2. **UI test picked the wrong upload box.** Gradio has hidden file inputs; selecting by position put the orders file into
   the batch box. Fixed with `elem_id`s on the three file components.
3. **Dropdown list covered the Recommend button** in the test. Closed it with Escape first. Test-only issue.
4. `pkill -f "python app.py"` killed the test shell itself. Switched to a pid file. Environment issue only.

## Known limits (honest)

* Costs and stock in the demo store are simulated (Beta(4,6) margins, 15% overstocked). Real stores should upload real numbers.
* Balance 0.5 and 1.0 behave almost the same: the relevance term is `avg p(buy) ≈ 0.022`, tiny next to unit profit in pounds,
  so profit dominates from about 0.1 up. A normalized objective would make the slider more even; left as is to match the repo.
* Discount response (`p × (1 + 1.5 × discount)`) is an assumption, not measured.
* Demo uses EASE, not the stronger LightGBM reranker (Hit@10 35.6% vs 31.1% in the repo).
* Free Spaces sleep after 48 h idle. Uploaded files are kept only in the session.
* This container cannot reach huggingface.co, so the Space itself has not been deployed from here; see `space/DEPLOY.md`.

## Deployment (2026-10-26, 13:20 to 13:47 UTC)

San created the Space at https://huggingface.co/spaces/EquilStable/MarginGraph and uploaded `space/` through the browser
(bundle and guide: `/mnt/project-files/margingraph/space_upload/`). It is live.

1. First start logged `Running on local URL: http://0.0.0.0:7860` and then `Stopping Node.js server...`, then
   **Runtime error: No @spaces.GPU function detected during startup**. Cause: the Space was created on **ZeroGPU**
   hardware, which requires at least one `@spaces.GPU` function.
2. Switching to CPU basic was refused: "Without a PRO subscription, you can't downgrade this Space to cpu-basic."
3. Fix: `app.py` now defines an empty `@spaces.GPU` placeholder inside `try: import spaces ... except ImportError`.
   On ZeroGPU it satisfies the startup check; everywhere else (CPU Space, laptop) the import fails and nothing changes.
   The app itself still runs entirely on CPU. Tested locally before San uploaded it; San confirmed the Space is live at 13:47 UTC.
4. The API example in the How it works tab now points at `EquilStable/MarginGraph`.
