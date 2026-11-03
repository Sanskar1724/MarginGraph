# MarginGraph paper

An arXiv-style research paper on MarginGraph (19 pages): UCI Online Retail II, four more public datasets (Ta Feng, Dunnhumby, Instacart, Olist), a 30-day store simulation, a comparison of six rerankers (LightGBM, XGBoost x2, CatBoost, HistGB, logistic regression), the gaps against industrial recommenders with a free-resource plan, and the LLM negative result. Every number comes from `results/` (including `results/public/` from PR #17 and `results/retail_sim/` from PR #18) `results/reranker_comparison/` (reranker comparison, Sec. 6.2), or from the logged Kaggle LLM runs in `docs/RESULTS.md`.

| File | What it is |
| --- | --- |
| `main.tex` | LaTeX source (reference version) |
| `main.pdf` | Built PDF |
| `references.bib` | Bibliography; every entry checked against the publisher, arXiv or the authors' page |
| `PAPER.md` | Markdown copy generated from `main.tex` |
| `figures/make_figures.py` | Rebuilds `figures/*.pdf` and `*.png` (fig0-fig10) from `results/` and `figures/figdata/` |
| `figures/figdata/` | Small extracts of the multi-dataset (PR #17) and store-simulation (PR #18) results used by figs 6 and 7 |

## Rebuild

```bash
python paper/figures/make_figures.py          # needs matplotlib, pandas
cd paper && latexmk -pdf main.tex             # needs a TeX Live with natbib, subcaption, booktabs
pandoc main.tex --citeproc --bibliography=references.bib -t gfm -o PAPER.md   # then the clean-up in docs/worklog/paper.md
```

On Overleaf: upload `main.tex`, `references.bib` and `figures/`, then compile with pdfLaTeX.

## Before submitting to arXiv

- Author line: Sanskar Chandawar, MIT Academy of Engineering (MITAOE), Alandi, Pune; 202401040137@mitaoe.ac.in.
- arXiv's cs.IR category needs an endorsement for first-time submitters.
