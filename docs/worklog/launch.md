# Worklog: launch and promotion kit

*Thread "Prepare launch and promotion kit", 2026-10-26. Branch `claude/project-thread-80g63p`, based on `claude/project-thread-mkbaip` (PR #2).*

## What was asked

San asked for all the writing needed to show MarginGraph to retail shops, release it on other sites, and do PR: product material, press, technical write-ups. The coordinator scoped this thread to the launch kit in `docs/launch/`.

## What was done

| File | What it is |
| --- | --- |
| `docs/launch/README.md` | Index, the **approved facts and numbers** sheet, words never to use, a pre-launch checklist, launch order, how to publish the landing page |
| `docs/launch/product-sheet.md` | One page for store owners, plain business language |
| `docs/launch/pilot-proposal.md` | Offer letter, 8-week pilot plan, A/B design, risks, non-binding agreement outline |
| `docs/launch/privacy-and-data.md` | What data is needed and not wanted, storage, 30-day deletion, merchant controls |
| `docs/launch/faq.md` | Store-owner and developer questions |
| `docs/launch/press-release.md` | Release template |
| `docs/launch/blog-post.md` | Long technical post for dev.to / Medium, including the LLM NO-GO results |
| `docs/launch/social-posts.md` | LinkedIn launch post, follow-up, owner DM, X post and 10-post thread |
| `docs/launch/product-hunt-and-show-hn.md` | HN title, first comment, prepared answers; PH tagline, description, gallery, maker comment |
| `docs/launch/site/index.html` | Static landing page, no build step, light and dark mode |
| `.github/workflows/pages.yml` | Deploys `docs/launch/site/` to GitHub Pages on push to `main` or by hand |

Copies are in `/mnt/project-files/margingraph/launch/`.

## Decisions and why

- **Only numbers from `docs/RESULTS.md` (run of 2026-10-26).** Every profit number carries the "cost and stock are simulated" caveat. San wants claims from real experiments only.
- **The NO-GO LLM results are a headline, not hidden.** It is true, it is the most interesting part for HN and developers, and it keeps the copy from reading as an AI-buzzword pitch.
- **No latency figure.** Only the solver time (3.4 ms) is measured; end-to-end API latency is not, so nothing quotes one.
- **"Not yet in a live store" is stated everywhere it matters,** and the call to action is a free pilot with an A/B test, matching the roadmap's Phase 4.
- **Objective in the blog post matches `src/margingraph/optimize.py`** (`p · ((1 − λ)·P̄ + λ·w·profit)`). A first draft used a generic formula; it was corrected against the code.
- **Placeholders, not guesses:** `DEMO_URL`, `SITE_URL`, `BLOG_URL`, `YOUR_EMAIL` and `[brackets]` must be filled by San (22 placeholder spots; `grep -rn "DEMO_URL\|SITE_URL\|BLOG_URL\|YOUR_EMAIL" docs/launch`).

## Checks run

- Landing page rendered with Playwright (Chromium) at 1280 px light and 390 px dark: no horizontal scroll (scrollWidth equals viewport), all sections visible. Grid min width lowered from 240 to 200 px after the first render left single orphan cards.
- Every number in the kit cross-checked against `docs/RESULTS.md`.
- The Pages workflow was not run (needs merge to `main` and Pages enabled in repo settings).

## Open items for San

1. **Add a LICENSE.** The repo has none, so "open source" is not yet true legally. MIT or Apache-2.0.
2. Deploy the demo (PR #4) and fill `DEMO_URL`.
3. Merge to `main`, enable Pages (Settings → Pages → Source: GitHub Actions), fill `SITE_URL`.
4. If the E6 LoRA fine-tune finishes, update the LLM rows in the fact sheet, blog, FAQ, landing page and posts.
5. Not in this kit: a pitch deck (slides) and a research-paper write-up. These need their own pass.
