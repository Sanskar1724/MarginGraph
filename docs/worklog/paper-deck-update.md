# Worklog: paper and deck update with the new results (2026-10-31)

*Thread: "Update research paper and pitch deck", started 2026-10-31 15:41 UTC.*

## Ask
San: "now edit research paper and ppt you made for it, and other required things and add these details in it, make it proper and professional, research look like research, ppt should be ppt only."

New results to add: the multi-dataset validation (PR #17) and the 30-day retail simulation (PR #18).

## What was done

| Step | Result |
| --- | --- |
| Read `docs/RESULTS_PUBLIC.md`, `results/public/*/` (PR #17 branch) and `results/retail_sim/` (PR #18 branch) | Every new number taken from those files; Dunnhumby Stage 2 per-basket values read from `e8_strategies_simulated_erp.csv` |
| Paper (`paper/main.tex`) | Now 15 pages. New: datasets table (Tab. 1), "Experimental protocol" section with the pre-registered success rule, store simulation (Sec. 6.4, Tab. 4, Fig. 3), external validity (Sec. 6.5, Tab. 5, Fig. 4), Instacart pool-order analysis (Sec. 6.6), Stage 2 beyond UCI and the Ta Feng `ASSET` cost run (Sec. 6.7, Tab. 6), a Discussion section, expanded Limitations, 7 new references (4 datasets, TIFU-KNN, NBR reality check, Kohavi A/B guide) |
| Figures | `make_figures.py` gained `fig6_multidataset` (forest plot of Hit@10 gains with CIs) and `fig7_retail_sim` (cumulative profit by day). Their inputs are small extracts in `paper/figures/figdata/` with the source file named in the first line |
| Author line | "Sanskar Chandawar" with two red placeholders: college and e-mail |
| `paper/PAPER.md` | Regenerated with pandoc, cleaned with a script (figures as PNG images, numbered tables/figures from `main.aux`, footnote rows moved under tables) |
| Deck (`docs/deck/build.js`) | Rewritten as a 14-slide visual deck: one message per slide, native charts on 7 slides, big-number callouts, speaker notes. New slides: results at a glance, five datasets, Instacart fix, profit on 3 stores, store simulation, thin-margin floor. Old business-model and roadmap slides folded into the closing ask |
| README, landing page, launch kit | New "Beyond one store" section in README; new "Tested beyond one store" section on the landing page (`docs/launch/site/index.html`, checked at 1280 px and 390 px, no horizontal scroll); one or two lines added to the launch README, product sheet, FAQ, press release, Show HN, social posts, pilot proposal and blog post |

## Honesty rules kept
- Instacart's −3.0 is reported as the official result everywhere the fix (+4.1) is mentioned.
- Every profit number says the cost and stock are simulated; Ta Feng's `ASSET` is called undocumented and unverified.
- The simulation is described as reproducing the earlier E10 stock replay totals (£1,141 vs £920), with the daily ledger, weekly restock and stochastic seeds added.

## Commands
```bash
pip install matplotlib pandas
apt-get install -y --no-install-recommends texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended latexmk
python paper/figures/make_figures.py
cd paper && latexmk -pdf -interaction=nonstopmode main.tex && latexmk -c      # 15 pages, no overfull boxes, no undefined refs
npm install pptxgenjs react react-dom react-icons sharp
NODE_PATH=./node_modules SKILL=<pptx skill dir> node docs/deck/build.js MarginGraph_pitch_deck.pptx
python <pptx skill>/scripts/office/validate.py MarginGraph_pitch_deck.pptx   # All validations PASSED
```

## Issues and fixes
- `apt-get install` failed at first (stale package lists); fixed with `apt-get update`.
- pandoc failed on the `\todo` macro after a sed rewrite broke its definition; the definition line is now dropped before conversion.
- Two overfull tables (Tab. 5, Tab. 6): narrower column padding and a new column layout for Tab. 6.
- `apply_theme.js` could not find pptxgenjs; fixed with `NODE_PATH`.
- Landing page stat cards wrapped long values ("Floor per store"); replaced with a number (+38%).

## Depends on
PRs #17 and #18 hold the result files the paper cites (`results/public/`, `results/retail_sim/`, `docs/RESULTS_PUBLIC.md`). Merge them first; this PR does not touch their files.

## Still to do (San)
- Fill in college and e-mail in `paper/main.tex` (red placeholders), rebuild the PDF.
- arXiv cs.IR needs an endorsement for a first submission.

## Module branches
Clean versions of `docs/research-paper` and `docs/pitch-deck` were built with only their own files and only their own history (two commits each: the 26 Oct first version, then this update; no `main` commits). The existing remote branches carry mixed history and this environment cannot force-push, so San deletes the two old branches on GitHub first, then the clean ones are pushed under the same names. Rebuild script and module READMEs: `/mnt/project-files/margingraph/paper-deck/`.

Note: `paper/figures/data/` would be ignored by the repo's `data/` rule in `.gitignore`, so the figure inputs live in `paper/figures/figdata/`.
