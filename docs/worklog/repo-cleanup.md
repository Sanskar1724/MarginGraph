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

Full first proposal: kept below under "First proposal". Status at the time: waiting for San's OK. (Superseded by San's decision below.)

## 2026-10-26 11:59 UTC: San's decision

San: keep `main` with the full code, **and** keep a branch per module for modular development, each with a proper README; professional branch names and structure, attractive to recruiters; SVGs in the README; "don't wait for my permission". This replaces the "one branch only" idea in the first proposal.

## 2026-10-26 12:00–12:20 UTC: integrate everything into `main`

Trial merge on a local branch from `origin/main`, in this order, all with merge commits (history kept):

| Order | Branch | PR | Result |
| --- | --- | --- | --- |
| 1 | `claude/project-thread-mkbaip` | #2 core pipeline | clean |
| 2 | `claude/project-thread-j64y7y` | #3 docs | clean |
| 3 | `claude/project-thread-dxygit` | #5 connectors | clean |
| 4 | `claude/project-thread-oyvjte` | #6 dashboard | **conflict in `src/margingraph/cli.py`**: both added a subcommand. Resolved by keeping both `sync` and `dashboard` (docstring lists both). |
| 5 | `claude/project-thread-r1a0d1` | #4 HF Space demo | clean |
| 6 | `claude/project-thread-42h21l` | pitch deck | clean |
| 7 | `claude/project-thread-80g63p` | launch kit | clean |
| 8 | `claude/project-thread-l6b8ga` | research paper | clean |
| 9 | `claude/add-notebooks-and-plan` | #1 early notebooks | conflict in `.gitignore` (add/add). Replaced with one unified `.gitignore`. README kept. Checked: no tokens or keys in the notebooks or their history (`git log -S hf_`). |

Test run after the merge (Python 3.13 venv, `pip install -e ".[dev]" gradio`, `pytest -q`): **59 passed, 1 skipped**.

Pushed to `main` (`7f15b20..01d8ba0`, fast-forward). GitHub marks the PRs merged because their heads are now in `main`.

Later at 12:25 UTC, three new commits on `claude/project-thread-mkbaip` (LLM GPU memory fixes, OOM worklog) were merged too; tests still 59 passed.

## Restructure (commit "Restructure repo …")

| Change | Why |
| --- | --- |
| `MarginGraph.md` → `docs/archive/original-pitch.md` | Outdated Llama-8B + LoRA pitch; README is the front page. Paths inside it updated. |
| `docs/MarginGraph_Detailed_Project_Report.docx` → `docs/archive/` | Binary first report, superseded by `PROJECT_REPORT.md`, kept for history |
| `notebooks/MarginGraph_V1.ipynb`, `V2.ipynb` → `notebooks/exploration/` | Early prototypes on mock data, kept for history |
| New `.gitignore` | Python, caches, venvs, data, `*.xlsx`, `*.db`, secrets, OS/editor files. `artifacts/` changed to `/artifacts/` so `space/artifacts/` stays tracked. |
| `LICENSE` (MIT) | Matches `license: mit` already declared in `space/README.md` |
| `CONTRIBUTING.md` | Branch table, naming rules, workflow, rule that every number comes from a run |
| `.github/pull_request_template.md` | What / why / how checked, worklog reminder |
| README rewrite | Centered header, badges, links bar, `docs/assets/architecture.svg`, `docs/assets/results-hit10.svg`, text diagram folded into `<details>`, updated roadmap ticks (demo, connectors, dashboard built), tree layout, branches section, license |
| Module READMEs | `src/margingraph/`, `connectors/`, `dashboard/`, `notebooks/`, `results/`, `docs/`, `docs/deck/` |
| `pyproject.toml` | readme, license, authors, keywords, project URLs |

SVGs were rendered with headless Chromium and checked by eye before commit. The bar chart numbers are copied from `docs/RESULTS.md` (E3/E5 test table).

Not moved, on purpose: `docs/RUNNING.md`, `CONNECTORS.md`, `DASHBOARD.md` and `docs/WORKLOG.md` are referenced from code, other docs and other threads' instructions, so moving them would break links and cause conflicts.

Kept, flagged: `space/artifacts/ease.npz` (7.4 MB binary) is needed by the Space.

## Module branches

Created from the new `main`, so each one starts from the full, tested project:

`feat/core-pipeline`, `feat/api-service`, `feat/ranker-accuracy`, `feat/llm-reranker`, `feat/store-connectors`, `feat/merchant-dashboard`, `feat/hf-space-demo`, `docs/project-report`, `docs/research-paper`, `docs/pitch-deck`, `docs/launch-kit`, `ci/github-actions`. Table with paths in `CONTRIBUTING.md`.

Old `claude/*` branches are **not deleted yet**: threads (service, accuracy, CI, fine-tune) still push to them. They get merged into `main` and the matching module branch as they land, then deleted once their threads are done.

---

# First proposal (11:55 UTC, superseded)

### 2. Branch names: the recommendation

Renaming a branch that has an open PR and a live thread pushing to it breaks that thread: its next push recreates the old name and the PR stops updating. So I propose **not renaming in-flight branches**. Instead:

1. Merge everything into `main` (order below), then **delete every merged branch**. Result: the repo has exactly one branch, `main`. That is what senior engineers expect: one long-lived branch, short-lived feature branches that disappear after merge.
2. Turn on *Settings → General → Automatically delete head branches* so this stays true.
3. New work from here on uses conventional names: `feat/…`, `fix/…`, `docs/…`, `chore/…`, `ci/…` (e.g. `feat/llm-lora-reranker`, `ci/github-actions`).

## 3. Merge order into `main`

Merge commits (not squash), so the history and work logs stay traceable and the stacked PRs do not conflict.

1. **#2** core pipeline into `main`. GitHub then retargets #3 to #6 to `main` automatically when the #2 branch is deleted.
2. **#3** docs
3. **#5** connectors (touches `cli.py`, `api.py`, `pipeline.py`)
4. **#6** dashboard (also touches `cli.py`; I resolve the conflict if any)
5. **#4** Space demo
6. Later PRs (service, accuracy, CI, paper, deck, launch kit) target `main` directly.
7. **Cleanup PR** (`chore/repo-structure`) last: moves, removals, `.gitignore`, README tree.
8. **#1**: close it. Its unique files are carried into the cleanup PR (see 5), so nothing is lost, and the README deletion is dropped.

## 4. Target tree

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

## 5. Removals and moves

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

## 6. What I need from San

1. OK to merge #2 to #6 into `main` in this order (I do it, resolving conflicts).
2. OK to close #1 and delete the `claude/*` branches after merge.
3. OK to add an MIT LICENSE.
4. Turn on "Automatically delete head branches" in repo settings (only San can).

## 2026-10-26 12:10 UTC: authorship (San: "all pushes should be mine only")

- Found on `main`: 40 commits authored and committed as `Claude <noreply@anthropic.com>` (GitHub shows the "claude" account), 4 as `Sanskar Chandawar <152592524+Sanskar1724@users.noreply.github.com>` (committer GitHub, from the web UI).
- Prepared a rewrite with `git filter-repo --mailmap` (Claude → Sanskar Chandawar, same noreply email San already uses) and a message callback that removes `Co-Authored-By: Claude…` and `Claude-Session:` lines and renames the `Merge remote-tracking branch 'origin/claude/project-thread-…' into trial` messages to `Merge <module branch> (#PR) into main`.
- Check: rewritten tree `7f9d0ae` is identical to the current `main` tree, and 0 trailer lines are left. Every commit hash changes.
- The force-push was blocked by the session's safety check pending San's explicit confirmation. Asked San on a decision card.
- From now on, this thread commits as Sanskar Chandawar with no trailers. The coordinator was asked to tell the other threads to do the same.

## 2026-10-26 12:15 UTC: module branches trimmed to their own module (San: "only main should have full code")

Script (`build.py` in the thread scratchpad): for each module branch, starting from `main` at `d7dfa77`, `git rm` every file outside the module's paths, keep `LICENSE` and `.gitignore`, write a module README (centered title, shields.io badges, links back to `main`, "what this module does", file table, run steps; core and report branches embed `docs/assets/architecture.svg`, ranker-accuracy embeds `results-hit10.svg` from `main` via raw.githubusercontent.com). One commit per branch authored by San, pushed as a fast-forward.

| Branch | Files kept |
| --- | --- |
| `feat/core-pipeline` | 48: package minus connectors/dashboard, configs, results, pipeline tests, run_all notebook, RESULTS/RUNNING, core worklog |
| `feat/api-service` | 5: `api.py`, RUNNING.md |
| `feat/ranker-accuracy` | 14: models, features, rerank, stats, E3–E7 results |
| `feat/llm-reranker` | 7: `llm.py`, two Kaggle notebooks, fine-tune tests |
| `feat/store-connectors` | 15: `connectors/`, tests, CONNECTORS.md, worklog |
| `feat/merchant-dashboard` | 15: `dashboard/`, tests, DASHBOARD.md, item descriptions, worklog |
| `feat/hf-space-demo` | 14: `space/`, tests, worklog |
| `docs/project-report` | 22: report, roadmap, results, worklogs, archive, assets |
| `docs/research-paper` | 21: `paper/`, worklog |
| `docs/pitch-deck` | 7: `docs/deck/`, worklog |
| `docs/launch-kit` | 15: `docs/launch/`, Pages workflow, worklog |
| `ci/github-actions` | 6: `.github/`, CONTRIBUTING.md |

Checks: `feat/core-pipeline` alone passes its tests (6 passed; first try failed because `api.py` and `llm.py` were left out, both added back). `feat/hf-space-demo` alone: 32 passed. `feat/merchant-dashboard` (with core on the path): 11 passed. `feat/store-connectors` needs `configs/` from core, so its CLI tests run on `main` only (stated in its README).

`main` README now has a branch table linking each module branch, and CONTRIBUTING says new work branches from `main` and module branches are refreshed after merge.

Note for the fine-tune thread: `notebooks/llm_*.ipynb` still `git clone -b claude/project-thread-mkbaip`; switch to `main` before that branch is deleted.

## 2026-10-26 12:30 UTC: PRs #10 and #11 merged, branches refreshed

- PR #10 (work log, `claude/project-thread-j64y7y`) and PR #11 (CI, `claude/project-thread-hadeju`, all 7 checks green) merged into `main`. Conflict in `docs/WORKLOG.md` (both edited the thread table): kept #10's table and branch map, took #11's row 9 and marked it merged. Local run: 61 passed, 1 skipped; `ruff check .` clean.
- Module branches refreshed with a merge commit (parents: old branch tip + `main`) whose tree is the trimmed module, so pushes stay fast-forward. `ci/github-actions` now holds the workflows, pre-commit, gitleaks, Dockerfile, scripts, quality gate and load-test results; `feat/api-service` gained the Dockerfile, load tester and load-test results. `feat/core-pipeline` needed `gate.py` (imported by the pipeline test): added; 6 passed on that branch alone.
- PR #12 (service) not merged yet: add/add conflicts with #11 in `.dockerignore`, `.github/workflows/ci.yml`, `Dockerfile`, plus `pyproject.toml` and `docs/WORKLOG.md`. Asked the service thread (via the coordinator) to merge `main` and reconcile.

## Branch deletion (San: "repo has 23 branches please remove unwanted")

Fully contained in `main` (checked with `git merge-base --is-ancestor`): `claude/add-notebooks-and-plan`, `claude/project-thread-{42h21l,80g63p,dxygit,hadeju,j64y7y,l6b8ga,oyvjte,r1a0d1}`.
`git push --delete` was refused by this session's network proxy (HTTP 403), and the GitHub tools have no branch-delete call, so these must be deleted in the GitHub UI (Branches page).
Kept for now: `claude/project-thread-mkbaip` (the Kaggle fine-tune notebooks clone it), `claude/project-thread-psfiei` (PR #12 open), `claude/project-thread-t654yh` (this thread).

## 2026-10-26 12:42 UTC: PR #12 (service) merged

- `claude/project-thread-psfiei` (CI green, `main` already merged in by the service thread) merged into `main`. Local run: 80 passed, 1 skipped; `ruff check .` clean.
- README roadmap: production service ticked, linked to `docs/SERVICE.md`.
- `feat/api-service` is now the service module: `src/margingraph/service/`, `api.py`, tests, SERVICE/API docs, Docker Compose files, Dockerfile, `.env.example`, replay / A/B / load-test scripts and their measured results (39 files). All module branches refreshed from `main`.
- `claude/project-thread-psfiei` is now fully in `main` and can be deleted.

## 2026-10-26 12:58 UTC: logo (San: "add a best svg ... it should be like logo")

- `docs/assets/logo-light.svg` and `logo-dark.svg`: app-icon mark (rounded square, blue to green) with graph nodes on a rising line above a dashed margin-floor line, plus the "MarginGraph" wordmark and tagline. Generated by a small Python script; rendered in headless Chromium on white and on GitHub's dark background to check.
- README header now uses `<picture>` so GitHub serves the dark version in dark mode. The architecture diagram stays further down.
- A first draft (a full pipeline banner) was dropped before commit after San said it should be a logo.

## 2026-10-26 13:00 UTC: PR #13 (industry plan) merged

- `docs/industry-roadmap` merged into `main` (no conflicts; 86 passed, 1 skipped; ruff clean). Added to the README branch table, CONTRIBUTING and the WORKLOG branch map.
- `docs/industry-roadmap` trimmed like the other module branches: `docs/industry-plan/`, the A/B sample-size and public-dataset scripts with their tests, the work log, and its own README. That makes 13 module branches.
