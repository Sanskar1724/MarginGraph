# Phase 0: close the open items

**Goal:** finish every loose end the earlier work threads left, so the repo, demo and paper are in a state you can show to stores and recruiters.

**Done when:** the demo and landing page are live with their URLs filled in, PR #12 is merged (or closed with a reason), only `main` and the module branches remain, E6 is recorded everywhere, and the paper has your full name.

Each item says where it came from, so you can check the original note.

## A. Things only you can do (accounts and settings)

- [ ] **Deploy the Hugging Face Space demo.** Follow [`space/DEPLOY.md`](../../space/DEPLOY.md) (about 10 minutes, free CPU basic). Option A is all in the browser. *Source: demo worklog, "this container cannot reach huggingface.co".*
  - Done when: `https://huggingface.co/spaces/<your-username>/margingraph` loads and returns 2 add-ons for a sample basket.
- [ ] **Turn on GitHub Pages for the landing page.** Repo → Settings → Pages → Source: **GitHub Actions**. Then Actions → "Landing page" → Run workflow. The workflow is [`.github/workflows/pages.yml`](../../.github/workflows/pages.yml). *Source: launch worklog item 3.*
  - Done when: `https://sanskar1724.github.io/MarginGraph/` loads.
- [ ] **Fill the placeholders in the launch kit.** After the two steps above:
  ```bash
  grep -rn "DEMO_URL\|SITE_URL\|BLOG_URL\|YOUR_EMAIL\|\[Your full name\]" docs/launch
  ```
  Replace each one, commit on a `docs/launch-urls` branch, PR to `main`.
- [ ] **Delete the finished `claude/*` branches** in the GitHub UI (Code → Branches → trash icon). The cleanup thread could not delete them (the session's proxy refused `git push --delete`). Already fully in `main`: `claude/add-notebooks-and-plan`, `claude/project-thread-42h21l`, `-80g63p`, `-dxygit`, `-hadeju`, `-j64y7y`, `-l6b8ga`, `-oyvjte`, `-r1a0d1`. *Source: [repo-cleanup.md](../worklog/repo-cleanup.md), section "Branch deletion".*
  - Keep for now: `claude/project-thread-mkbaip` (the Kaggle fine-tune notebooks clone it; see item C2), `claude/project-thread-psfiei` (PR #12 is open), `claude/project-thread-t654yh` (cleanup thread). Delete each once its reason is gone.
  - `claude/project-thread-79n8vk` was created for this plan's thread but this plan used `docs/industry-roadmap`; it can be deleted.
  - Check before deleting any branch: `git fetch origin && git merge-base --is-ancestor origin/<branch> origin/main && echo safe`.
- [ ] Optional: Settings → General → **Automatically delete head branches**, so merged PR branches go away on their own.
- [ ] **Confirm the old Hugging Face token and Kaggle key were rotated.** The early V2 notebook had them hard-coded (fixed in PR #1; you were told to rotate them). CI's secret scan found no live token in history, but rotation is the only real fix. *Source: [WORKLOG.md](../WORKLOG.md) bug table.*
- [ ] **Paper author.** Put your full name and affiliation in [`paper/main.tex`](../../paper/main.tex) (`\author{...}`, line 20) and in `paper/PAPER.md`, then rebuild the PDF (Overleaf free works: upload `paper/`, compile, download `main.pdf`). *Source: [paper.md](../worklog/paper.md) "Still to do".*
- [ ] **arXiv.** A first cs.IR submission needs an endorsement. Ask a professor or a researcher who has published in cs.IR. Only submit after E6 is recorded (C1).
- [ ] **Commit-history rewrite** (all old commits shown as you). The cleanup thread prepared it, but a force-push needs your explicit OK and a session that allows it. It is planned for after the in-flight threads land. *Source: [repo-cleanup.md](../worklog/repo-cleanup.md) 12:10 entry.*

## B. Pull requests and in-flight work

- [ ] **Review and merge PR [#12](https://github.com/Sanskar1724/MarginGraph/pull/12)** (production service: multi-store API, A/B buckets and reporting, nightly training with a quality gate and rollback, Docker, Postgres and Redis). Phases 3, 4, 5 and 6 build on it. Check its CI is green first.
  - After merging: tick "Production API with fallback, logging and auth" in the README roadmap, and update the API row in [ROADMAP.md](../ROADMAP.md).
- [ ] **Ranker-accuracy thread** (`feat/ranker-accuracy`): check its status in the project. If it produced a result, it needs a PR and a row in WORKLOG.
- [ ] **Merge this plan's PR** (`docs/industry-roadmap`).

## C. Record results that are still pending

- [x] **C1. E6 LoRA fine-tune result**: NO-GO (Hit@5 7.8% vs 27.6%), recorded in PR #15 and on `main`. When it finishes, record it in all of these, with the same numbers:
  - `docs/RESULTS.md` (E5 LLM section), `docs/worklog/core-pipeline.md` (table row 4), `docs/WORKLOG.md` (experiment runs)
  - `paper/PAPER.md` and `paper/main.tex` (LLM section)
  - Launch kit: `docs/launch/product-sheet.md`, `blog-post.md`, `faq.md`, `site/index.html`, `social-posts.md` (search for "fine-tune" and "NO-GO")
  - README results table (LLM row) and roadmap checkbox
  - Then follow [02-llm-options.md](02-llm-options.md).
- [x] **C2.** Point the Kaggle notebooks at `main` instead of `claude/project-thread-mkbaip` (search the notebooks for `mkbaip`), then delete that branch.
- [ ] **C3.** [ROADMAP.md](../ROADMAP.md) Phase 1 still has "Benchmark end-to-end API latency" unticked. It was measured (p50 22 ms, p95 28 ms; [ci.md](../worklog/ci.md)). Tick it and link the result.

## D. Known limits to fix later (logged by earlier threads)

These are not blockers for a pilot, but each is a real gap.

- [ ] The HF Space demo uses EASE, not the stronger LightGBM ranker (Hit@10 31.1% vs 38.1% on UCI). *Source: demo worklog.*
- [ ] The demo's "balance" slider barely changes results between 0.5 and 1.0 (the relevance term is tiny next to profit in pounds). A normalized objective would fix it. *Source: demo worklog.*
- [ ] Dashboard: CSRF protection if it is ever exposed without its token; wire the service's logs to it (PR #12 adds a settings overlay; check after merge). *Source: dashboard worklog.*
- [ ] Shopify: a GraphQL adapter, since Shopify is moving apps from REST to GraphQL. *Source: connectors worklog.*
- [ ] Large catalogs: model bundles are 259 MB for 4,707 items (dense item-item matrices). A 50,000-product store needs sparse top-k neighbour lists in `models.py`. *Source: SERVICE.md on PR #12.* See [05-production-hardening.md](05-production-hardening.md).

## Prompt for a future Claude session

```text
Phase 0 of docs/industry-plan (00-open-items.md). I have done these items myself: <list>.
Please: (1) check PR #12's CI and summarize what still blocks merging it; (2) list which branches
are fully merged into main with git merge-base --is-ancestor, and tell me which to delete in the UI;
(3) replace DEMO_URL=<url> and SITE_URL=<url> everywhere in docs/launch and README;
(4) point the Kaggle notebooks at main instead of claude/project-thread-mkbaip;
(5) tick the finished boxes in 00-open-items.md with today's date. One PR against main.
```

For the E6 result:

```text
The E6 LoRA fine-tune finished on Kaggle. Here is the notebook's final output: <paste>.
Record it, with the same numbers and CIs, in every place listed in
docs/industry-plan/00-open-items.md item C1, with a GO or NO-GO verdict using the gate in
docs/industry-plan/02-llm-options.md. Do not round differently in different files. One PR against main.
```
