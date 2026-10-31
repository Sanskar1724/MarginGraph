# MarginGraph: retail store simulation

This branch holds only the retail store simulation module. The full project lives on `main`.

It runs MarginGraph inside a simulated store, one day at a time. Real Online Retail II test checkouts are replayed over 30 days. For each checkout, LightGBM scores p(accept), a policy picks up to 2 add-ons, the shopper accepts or rejects, and stock and profit update. Stock is refilled every 7 days.

| Policy | Add-on profit (replay) | vs ranker | Accept rate | Offers under the 15% floor |
|---|---|---|---|---|
| ranker top-2 | £920 | – | 8.9% | 164 |
| MarginGraph, item floor | £1,141 | +24% | 7.5% | 0 |
| MarginGraph, bundle floor | £1,145 | +24% | 7.5% | 21 (each bundle still meets 15%) |
| MarginGraph, overstock weight 2 | £1,099 | +19% | 7.3% | 0 |

Cost and stock are simulated, because the dataset has none. The results show how the system behaves, not real-store profit.

- Code: `src/margingraph/sim.py`
- Flow diagram, assumptions and run log: `docs/worklog/retail-sim.md`
- Notebook: `notebooks/retail_sim.ipynb`. The executed copy with outputs is `results/retail_sim/retail_sim_executed.md`.

To run it from `main`:

    margingraph prepare && margingraph run
    python -m margingraph.sim --days 30 --seeds 5
