# Work log: repo cleanup thread

Thread goal (San, 2026-10-26): professional branch names, a clean folder layout, remove anything unnecessary.

## 2026-10-26 11:55 UTC: audit

Commands: `git fetch --all`, `git branch -a`, `git ls-tree -r` per branch, `git diff --stat` of each PR branch vs `claude/project-thread-mkbaip`, GitHub PR list.

Findings:
- 8 branches: `main`, `claude/add-notebooks-and-plan` (PR #1), `claude/project-thread-{mkbaip,j64y7y,r1a0d1,dxygit,oyvjte}` (PRs #2 to #6), and this thread's branch.
- `main` holds only the old README and `MarginGraph.md`.
- PR #1 is based on an older `main` and would delete `README.md`. Its unique files: `notebooks/MarginGraph_V1.ipynb` (932 KB), `MarginGraph_V2.ipynb`, `docs/MarginGraph_Detailed_Project_Report.docx`, `docs/experiment_plan.md`.
- PRs #3, #4, #5 show `docs/worklog/core-pipeline.md` as deleted only because they branched before it was added; a merge does not delete it.
- `MarginGraph.md` still describes Llama-3.1-8B + LoRA as the design; experiments ruled that out.

Decision: do not rename branches that have open PRs and live threads (a rename makes the thread's next push recreate the old name and detach the PR). Instead merge into `main` and delete merged branches; new branches use `feat/`, `fix/`, `docs/`, `chore/`, `ci/`.

Full proposal: see the plan below. Status: waiting for San's OK. Nothing renamed, merged or deleted yet.

### 2. Branch names: the recommendation

Renaming a branch that has an open PR and a live thread pushing to it breaks that thread: its next push recreates the old name and the PR stops updating. So I propose **not renaming in-flight branches**. Instead:

1. Merge everything into `main` (order below), then **delete every merged branch**. Result: the repo has exactly one branch, `main`. That is what senior engineers expect: one long-lived branch, short-lived feature branches that disappear after merge.
2. Turn on *Settings → General → Automatically delete head branches* so this stays true.
3. New work from here on uses conventional names: `feat/…`, `fix/…`, `docs/…`, `chore/…`, `ci/…` (e.g. `feat/llm-lora-reranker`, `ci/github-actions`).

### 3. Merge order into `main`

Merge commits (not squash), so the history and work logs stay traceable and the stacked PRs do not conflict.

1. **#2** core pipeline into `main`. GitHub then retargets #3 to #6 to `main` automatically when the #2 branch is deleted.
2. **#3** docs
3. **#5** connectors (touches `cli.py`, `api.py`, `pipeline.py`)
4. **#6** dashboard (also touches `cli.py`; I resolve the conflict if any)
5. **#4** Space demo
6. Later PRs (service, accuracy, CI, paper, deck, launch kit) target `main` directly.
7. **Cleanup PR** (`chore/repo-structure`) last: moves, removals, `.gitignore`, README tree.
8. **#1**: close it. Its unique files are carried into the cleanup PR (see 5), so nothing is lost, and the README deletion is dropped.

### 4. Target tree

```text
MarginGraph/
├── README.md               # one front page: what, results, quickstart, layout
├── LICENSE                 # MIT (needs San's OK)
├── pyproject.toml
├── .gitignore
├── configs/                # default.yaml
├── src/margingraph/        # package: data, rerank, stage2, api, connectors/, dashboard/
├── tests/
├── notebooks/
│   ├── run_all.ipynb, llm_rerank_gpu.ipynb, llm_finetune_gpu.ipynb
│   └── exploration/        # MarginGraph_V1.ipynb, MarginGraph_V2.ipynb (from PR #1)
├── results/                # measured experiment outputs (CSV/JSON)
├── space/                  # Hugging Face Space demo
├── docs/
│   ├── PROJECT_REPORT.md, ROADMAP.md, RESULTS.md, experiment_plan.md
│   ├── guides/             # RUNNING.md, CONNECTORS.md, DASHBOARD.md
│   ├── worklog/            # WORKLOG.md index + one log per thread
│   └── archive/            # original_pitch.md, MarginGraph_Detailed_Project_Report.docx
├── paper/                  # when the paper thread lands
└── .github/workflows/      # when the CI thread lands
```

### 5. Removals and moves

Nothing with unique work is deleted. Everything stays in git history either way.

| File | Action | Why |
| --- | --- | --- |
| `MarginGraph.md` (root) | Move to `docs/archive/original_pitch.md` | Outdated (Llama-8B + LoRA claim), duplicates the README |
| `docs/MarginGraph_Detailed_Project_Report.docx` (PR #1) | Move to `docs/archive/` | Binary, superseded by `PROJECT_REPORT.md`, kept for the record |
| `notebooks/MarginGraph_V1.ipynb`, `V2.ipynb` (PR #1) | Move to `notebooks/exploration/` | Early exploration, kept |
| `docs/experiment_plan.md` (PR #1) | Keep in `docs/` | Still useful |
| `docs/WORKLOG.md` | Move to `docs/worklog/README.md` | One place for logs |
| `docs/RUNNING.md`, `CONNECTORS.md`, `DASHBOARD.md` | Move to `docs/guides/` and fix links | Fewer files at the top of `docs/` |
| 6 `claude/*` branches | Delete after merge | Merged work lives in `main` |

`.gitignore` additions: `.venv/`, `venv/`, `.DS_Store`, `.ipynb_checkpoints/`, `.ruff_cache/`, `.mypy_cache/`, `*.db`, `*.sqlite`, `.coverage`, `htmlcov/`, `dist/`, `build/`, `*.log`, `*.xlsx` (the dataset).

Kept as is, flagged: `space/artifacts/ease.npz` (7.4 MB binary). The Space needs it, and it fits under GitHub's limits. It could be rebuilt at deploy time later.

### 6. What I need from San

1. OK to merge #2 to #6 into `main` in this order (I do it, resolving conflicts).
2. OK to close #1 and delete the `claude/*` branches after merge.
3. OK to add an MIT LICENSE.
4. Turn on "Automatically delete head branches" in repo settings (only San can).
