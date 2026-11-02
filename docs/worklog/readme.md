# README refresh with new research findings (2026-11-02)

**Asked by:** San, 2026-11-02 04:13 UTC: "update MarginGraph README according to new research findings".
**Branch:** `claude/project-thread-1hsrhp` → PR into `main`.

## What changed in `README.md`

- Status line: tested on five real datasets plus a 30-day store simulation.
- New **Key findings** section (five points): the ranker generalizes, the optimizer earns more with 0 floor breaks, the shortlist matters (Instacart), a fixed 15% item floor is too strict for low-margin grocers, the LLM does not rank.
- **Results on four more public datasets**: Hit@10 table for UCI, Ta Feng, Dunnhumby, Instacart, Olist, including the "past purchases first" reruns, and a Stage 2 profit table (simulated cost; Ta Feng `ASSET` cost marked unverified).
- **30-day store simulation**: replay and 5-seed results for the four policies, accept rate and floor breaks.
- **LLM decision**: zero-shot, stacker and LoRA results; LightGBM ranks; LLM only for cold-start and explanations (not yet measured).
- Fixed outdated text: the design rule "The LLM ranks products" and "LLM tested, NO-GO so far".
- Data table lists the four public datasets instead of the never-used H&M option; roadmap ticks multi-dataset validation and the store simulation, and adds two open items (past-purchases-first as default, per-store floor); repo layout lists `results/public/` and `results/retail_sim/`; branch table adds `feat/multi-dataset`; nav adds "Other datasets".

## Where the numbers come from

No new experiments were run. Every number is copied from:

| Section | Source |
| --- | --- |
| UCI results, LLM decision | `docs/RESULTS.md` (main) |
| Public datasets, Stage 2 on other stores | `docs/RESULTS_PUBLIC.md` (PR #17) |
| Store simulation | `docs/worklog/retail-sim.md`, `results/retail_sim/summary.csv` (PR #18) |

## Merge order

PRs #17, #18 and #19 were still open when this was written. The new README links `docs/RESULTS_PUBLIC.md`, `notebooks/multi_dataset_validation.ipynb`, `src/margingraph/sim.py`, `docs/worklog/retail-sim.md` and `results/retail_sim/`, which arrive with #17 and #18, so merge this after them. #17 and #19 also edit `README.md`; this README already contains their content, so on a conflict keep this version. All of them add a row to `docs/WORKLOG.md`: keep every row.
