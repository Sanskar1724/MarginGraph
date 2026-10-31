# MarginGraph paper

An arXiv-style research paper on MarginGraph (15 pages): UCI Online Retail II, four more public datasets (Ta Feng, Dunnhumby, Instacart, Olist), a 30-day store simulation, and the LLM negative result. Every number comes from `results/` (including `results/public/` from PR #17 and `results/retail_sim/` from PR #18) or from the logged Kaggle LLM runs in `docs/RESULTS.md`.

| File | What it is |
| --- | --- |
| `main.tex` | LaTeX source (reference version) |
| `main.pdf` | Built PDF |
| `references.bib` | Bibliography; every entry checked against the publisher, arXiv or the authors' page |
| `PAPER.md` | Markdown copy generated from `main.tex` |
| `figures/make_figures.py` | Rebuilds `figures/*.pdf` and `*.png` (figs 1-7) from `results/` and `figures/data/` |
| `figures/data/` | Small extracts of the multi-dataset (PR #17) and store-simulation (PR #18) results used by figs 6 and 7 |

## Rebuild

```bash
python paper/figures/make_figures.py          # needs matplotlib, pandas
cd paper && latexmk -pdf main.tex             # needs a TeX Live with natbib, subcaption, booktabs
pandoc main.tex --citeproc --bibliography=references.bib -t gfm -o PAPER.md   # then the clean-up in docs/worklog/paper.md
```

On Overleaf: upload `main.tex`, `references.bib` and `figures/`, then compile with pdfLaTeX.

## Before submitting to arXiv

- Fill in the two red placeholders in `\author{}` (college and e-mail); they print in red until replaced.
- arXiv's cs.IR category needs an endorsement for first-time submitters.
