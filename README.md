<div align="center">

# MarginGraph · Research paper

**A 17-page research paper on margin-aware checkout add-on recommendation: five public retail datasets, a 30-day store simulation, and a negative result for small LLM rerankers.**

![license](https://img.shields.io/badge/license-MIT-green) ![paper](https://img.shields.io/badge/paper-PDF-b31b1b) ![LaTeX](https://img.shields.io/badge/LaTeX-source-008080?logo=latex&logoColor=white) ![citations](https://img.shields.io/badge/citations-29-brightgreen)

[Read the PDF](paper/main.pdf) · [Markdown copy](paper/PAPER.md) · [Full project (`main`)](https://github.com/Sanskar1724/MarginGraph)

</div>

> This branch holds only the **Research paper** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## Key results in the paper

| Result | Number |
| --- | --- |
| Ranker vs best baseline, UCI Online Retail II (4,480 baskets) | Hit@10 +7.0 pts [6.0, 8.0] |
| Ta Feng / Dunnhumby, unchanged pipeline | +8.3 [7.7, 8.8] / +7.8 [7.2, 8.4] |
| Instacart, official / with past purchases first in the pool | −3.0 [−3.6, −2.4] / +4.1 [3.7, 4.5] |
| Olist (169 baskets) | tie, +3.6 [−1.2, 8.9] |
| Profit per basket, optimizer vs ranker top-2 (simulated cost) | +14% UCI, +17% Ta Feng, +13% Dunnhumby |
| 30-day store simulation (simulated cost) | £1,141 vs £920, 0 vs 164 margin-floor breaks |
| Qwen2.5 1.5B/3B rerankers (zero-shot, blend, stacker, LoRA) | none beat LightGBM |

## What's in this branch

| Path | What it is |
| --- | --- |
| `paper/main.pdf` | The paper |
| `paper/main.tex` | LaTeX source |
| `paper/references.bib` | Bibliography |
| `paper/PAPER.md` | Markdown copy |
| `paper/figures/` | 10 figures (system diagram and 9 result charts), the script that makes them, and `figdata/` extracts |
| `docs/worklog/paper.md`, `docs/worklog/paper-deck-update.md` | Work logs |

## Build it

```bash
python paper/figures/make_figures.py      # figs 1-5 need results/ from main
cd paper && latexmk -pdf main.tex
```

## License

[MIT](LICENSE)
