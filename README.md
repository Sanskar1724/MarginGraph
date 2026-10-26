<div align="center">

# MarginGraph · Research paper

**An arXiv-style paper on margin-aware add-on recommendation, built from the results in this repo.**

![license](https://img.shields.io/badge/license-MIT-green) ![paper](https://img.shields.io/badge/paper-PDF-b31b1b) ![LaTeX](https://img.shields.io/badge/LaTeX-source-008080?logo=latex&logoColor=white) ![citations](https://img.shields.io/badge/citations-verified-brightgreen)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Research paper** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

LaTeX source, built PDF, figures regenerated from `results/`, and a bibliography where every entry was checked against the publisher or arXiv.

## What's in this branch

| Path | What it is |
| --- | --- |
| `paper/main.pdf` | The paper |
| `paper/main.tex` | LaTeX source |
| `paper/references.bib` | Bibliography |
| `paper/PAPER.md` | Markdown copy |
| `paper/figures/` | Figures and the script that makes them |
| `docs/worklog/paper.md` | Work log |

## Run it

```bash
python paper/figures/make_figures.py
cd paper && latexmk -pdf main.tex
```

## License

[MIT](LICENSE)
