# Work log: research paper (2026-10-26)

Thread: *Write MarginGraph research paper*. Branch `claude/project-thread-l6b8ga`, based on PR #2 (`claude/project-thread-mkbaip`). Index: [`../WORKLOG.md`](../WORKLOG.md) (in PR #3).

## What was asked

San asked for "all technical writing" so the project can be shown and promoted: slides, reports, research paper and so on. This thread covers the research paper: arXiv style, LaTeX with a PDF, a Markdown copy, figures from the real results, verified citations, measured numbers only (including the LLM NO-GO results), and honest limits.

## What was done

| Time (UTC) | Step | Result |
| --- | --- | --- |
| 11:51 | Read `docs/RESULTS.md`, `results/*.csv|json`, `configs/default.yaml`, `src/margingraph/{features,rerank,optimize,stage2,data,llm}.py`, `docs/worklog/core-pipeline.md` and the project history | All numbers and method details taken from these files |
| 11:53 | Installed matplotlib and TeX Live (`texlive-latex-base/recommended/extra`, `fonts-recommended`, `latexmk`) in the container | Build tools available |
| 11:54 | Searched and checked 22 citations (list below) | 22 entries in `paper/references.bib` |
| 11:56 | Wrote `paper/figures/make_figures.py`; built 5 figures from `results/` | Checked each PNG by eye; fixed label overlap (fig 1), cut-off labels (fig 3), annotation side (fig 2) |
| 11:57 | Wrote `paper/main.tex`; built with `latexmk -pdf` | 9-page PDF, no undefined references, no overfull boxes after two fixes |
| 11:59 | Generated `paper/PAPER.md` with pandoc + citeproc, then cleaned it (figures as Markdown images, title and abstract added, LaTeX leftovers removed) | Markdown copy |

## Commands

```bash
pip install matplotlib
apt-get install -y --no-install-recommends texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended latexmk
python paper/figures/make_figures.py
cd paper && latexmk -pdf -interaction=nonstopmode main.tex && latexmk -c
pandoc main.tex --citeproc --bibliography=references.bib -t gfm -o PAPER.md   # then a short Python clean-up
```

## Failures and fixes

- `lmodern.sty` not found (the minimal TeX install lacks it). Switched to `mathptmx` (Times).
- Two overfull boxes: the Stage 2 table (set `\small`) and long `\texttt` paths in the Reproducibility section (`\sloppy`).
- Fig 3 y labels were cut at the first comma ("Beta(2"). Fixed the label code.
- pandoc turned subfigures into nested `<figure>` HTML with `<embed>` of the PDF. Replaced with Markdown images pointing at the PNGs.

## Decisions

- **Numbers.** Every number is read from `results/` or from the logged Kaggle runs in `docs/RESULTS.md`. Nothing is a target. The E9 solve time is given as "about 3 ms": `results/e9_solver_check.json` now says 3.04 ms, `docs/RESULTS.md` says 3.4 ms from an earlier run.
- **Not used:** the "18 ms" API latency (never benchmarked; listed as a limitation instead).
- **Fine-tune (E6):** described as running, with the promise to report it whatever the outcome. The LLM figure and table only show finished runs.
- **Overstock nuance reported honestly:** MILP with weight 1.0 sells fewer overstock units (74) than the ranker top-2 (99); only the weight 2.0 setting (114) sells more.
- **Author line:** "Sanskar" only, since the full name and affiliation are not known. San should fill these in before submitting.
- **AI-use statement** added, since arXiv and most venues ask for one.

## Citations checked (source used)

| Key | Checked at |
| --- | --- |
| chen2019onlineretail | UCI dataset 502 page (creator Daqing Chen, DOI 10.24432/C5CG6D) |
| chen2012rfm | LSBU Open Research record |
| steck2019ease | arXiv 1905.03375; Webis anthology (WWW 2019, pp. 3251–3257, DOI) |
| hu2008implicit | ICDM 2008, several course and paper listings |
| sarwar2001itemcf | WWW 2001 (Webis anthology, UMN experts) |
| ke2017lightgbm | NeurIPS 2017 proceedings |
| burges2010lambdamart | Microsoft Research, MSR-TR-2010-82 |
| zadrozny2002calibration | KDD 2002, author PDF at UCSD |
| jannach2017price | arXiv 1707.08029 |
| louca2019profit | CEUR-WS Vol-2440 PDF (authors and RMSE @ RecSys 2019) |
| pei2019value | arXiv 1902.00851 (authors) |
| abdollahpouri2020multistakeholder | arXiv 1905.01986 (authors, DOI 10.1007/s11257-019-09256-1); UMUAI title from the Colorado record |
| agarwal2011clickshaping | KDD 2011, DOI 10.1145/2020408.2020435 |
| hou2024zeroshot | arXiv 2305.08845 |
| bao2023tallrec | arXiv 2305.00447 |
| qwen2025qwen25 | arXiv 2412.15115 |
| hu2022lora | arXiv 2106.09685; ICLR 2022 (mlanthology) |
| dacrema2019progress | arXiv 1907.06902 (RecSys 2019) |
| krichene2020sampled | Google Research page (KDD 2020, DOI 10.1145/3394486.3403226) |
| mitchell2011pulp | Optimization Online, 2011 |
| huangfu2018highs | J. Hall's page (MPC 10(1):119–142, DOI) |
| efron1993bootstrap | library catalogue records (Chapman & Hall, 1993) |

Page numbers were removed where they could not be confirmed from the source page.

## Files added

- `paper/main.tex`, `paper/main.pdf`, `paper/references.bib`, `paper/PAPER.md`, `paper/README.md`, `paper/.gitignore`
- `paper/figures/make_figures.py` and `fig1`–`fig5` as PDF and PNG
- `docs/worklog/paper.md` (this file)

## Still to do

- Add the E6 LoRA fine-tune result when San's Kaggle run finishes.
- San to fill in full name and affiliation; arXiv cs.IR needs an endorsement for a first submission.
