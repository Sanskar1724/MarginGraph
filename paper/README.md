# MarginGraph paper

An arXiv-style write-up of the MarginGraph experiments. Every number comes from `results/` or from the logged Kaggle LLM runs in `docs/RESULTS.md`.

| File | What it is |
| --- | --- |
| `main.tex` | LaTeX source (reference version) |
| `main.pdf` | Built PDF |
| `references.bib` | Bibliography; every entry checked against the publisher, arXiv or the authors' page |
| `PAPER.md` | Markdown copy generated from `main.tex` |
| `figures/make_figures.py` | Rebuilds `figures/*.pdf` and `*.png` from `results/` |

## Rebuild

```bash
python paper/figures/make_figures.py          # needs matplotlib, pandas
cd paper && latexmk -pdf main.tex             # needs a TeX Live with natbib, subcaption, booktabs
pandoc main.tex --citeproc --bibliography=references.bib -t gfm -o PAPER.md   # then the clean-up in docs/worklog/paper.md
```

On Overleaf: upload `main.tex`, `references.bib` and `figures/`, then compile with pdfLaTeX.

## Before submitting to arXiv

- Put your full name and affiliation in `\author{}`.
- arXiv's cs.IR category needs an endorsement for first-time submitters.
