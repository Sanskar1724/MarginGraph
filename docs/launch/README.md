# MarginGraph launch and promotion kit

*Prepared 2026-10-26. Every number in this kit comes from [`../RESULTS.md`](../RESULTS.md) (run of 2026-10-26). If a result changes, update [the fact sheet](#approved-facts-and-numbers) first, then every file that quotes it.*

This folder holds everything needed to show MarginGraph to store owners, the press, and developer communities.

| File | Audience | Use it for |
| --- | --- | --- |
| [`product-sheet.md`](product-sheet.md) | Store owners | One-page overview in plain business language. Print it or send it as a PDF |
| [`pilot-proposal.md`](pilot-proposal.md) | A specific store | Pilot proposal plus a ready-to-edit offer letter |
| [`privacy-and-data.md`](privacy-and-data.md) | Store owners, their lawyers | What data we need, how it is handled, how it is deleted |
| [`faq.md`](faq.md) | Everyone | Common questions, business and technical |
| [`press-release.md`](press-release.md) | Press, university news, blogs | Announcement of the open-source release |
| [`blog-post.md`](blog-post.md) | Developers (Medium, dev.to, Hashnode) | Long technical write-up, including the LLM that lost |
| [`social-posts.md`](social-posts.md) | LinkedIn, X | Ready-to-post copy and a short thread |
| [`product-hunt-and-show-hn.md`](product-hunt-and-show-hn.md) | Product Hunt, Hacker News | Listing copy, first comment, and how to answer common replies |
| [`site/index.html`](site/index.html) | Everyone | Static landing page for GitHub Pages ([how to publish](#publish-the-landing-page)) |

---

## Approved facts and numbers

Use only these. Copy the wording of the caveat with every profit number.

**What the data is.** UCI Online Retail II: real invoices from a UK online gift retailer, Dec 2009 to Dec 2011. 1,067,371 raw rows, cleaned to 991,910 invoice lines, 39,516 invoices, 4,707 products. Trained on data up to 30 June 2011, tested on 4,480 real baskets from 2 Oct to 9 Dec 2011, one product hidden per basket.

| Claim | Number | Caveat to carry with it |
| --- | --- | --- |
| Ranker finds the hidden item in its top 10 | **35.6%** of test baskets | Offline backtest on one public dataset |
| Best simple method (EASE) on the same test | 31.1% | |
| Ranker gain over EASE | **+4.5 points**, 95% CI [3.6, 5.5] | Paired bootstrap over test baskets |
| "Top sellers" list on the same test | 3.1% | |
| Profit per basket, optimizer (λ=0.5) vs showing the ranker's top 2 | **+17%** (+£0.031 per basket, CI [0.017, 0.044]) | **Cost and stock are simulated.** The dataset has no unit cost |
| What that costs in relevance | −1.1 points Hit@2, CI [−1.8, −0.5] | |
| Stronger profit setting (λ=1.0) | +22% profit for −3.7 points Hit@2 | Simulated cost and stock |
| Margin-floor (15%) breaks | **0** with the optimizer vs 0.038 per basket for the plain top 2 | Under simulated cost |
| Robustness | Profit gain stayed positive in all 9 cost scenarios tested (3 margin shapes × 3 seeds) | Still simulated, but a range of assumptions |
| Optimizer correctness and speed | Matches brute force on 600 of 600 problems, 3.4 ms mean solve time | Solver time only. **End-to-end API latency is not measured yet** |
| Shortlist coverage | Hidden item is in the 100-item shortlist 58.0% of the time | This caps every ranker |
| LLM as ranker (Qwen2.5 1.5B and 3B, zero-shot, and as an extra feature) | **NO-GO.** Hit@5 16.8% (1.5B) vs 27.6% for LightGBM on the same 1,000 baskets | A LoRA fine-tune is still being tested |

**Status words to use:** "open-source research prototype", "tested offline on real sales data", "looking for pilot stores".

**Never say:** "AI that boosts profit by 17%" (without the simulated-cost caveat), "proven in stores", "LLM-powered ranking", "real-time" or any latency figure, "production-ready", "used by retailers", or any revenue, conversion, or customer count. None of these are measured.

**Why this matters:** the honesty is the selling point. Most recommender pitches quote targets. This one quotes confidence intervals and admits what lost.

---

## Before you post anything: checklist

- [ ] **Add a license.** The repo has no `LICENSE` file, so nobody else can legally use or fork the code. MIT or Apache-2.0 are the usual choices for a project like this. Every "open-source" line in this kit assumes one is added.
- [ ] **Merge the base work** (PR #2) so the repo's `README.md` shows the results instead of "no claims yet".
- [ ] **Deploy the demo** (Hugging Face Space, see `space/DEPLOY.md` in PR #4) and replace `DEMO_URL` in every file of this kit. Search for it: `grep -rn DEMO_URL docs/launch`.
- [ ] **Publish the landing page** (below) and replace `SITE_URL`.
- [ ] Replace `YOUR_EMAIL` with the contact address you want public. Consider a separate address for the project.
- [ ] Re-read the [fact sheet](#approved-facts-and-numbers) against `docs/RESULTS.md`. If the LoRA fine-tune (E6) finishes, update the LLM row in every file.
- [ ] Take 2 screenshots of the demo (a basket with its 2 add-ons, and the profit vs hits chart) for Product Hunt, LinkedIn and the blog.

## Suggested launch order

1. Landing page and demo live.
2. Blog post on dev.to (canonical) and Medium (import with the canonical link set to dev.to).
3. LinkedIn post linking the blog. X thread the same day.
4. Show HN on a weekday morning, US Eastern time. Stay online for 3 hours to answer comments.
5. Product Hunt a week later, once HN feedback is in the README.
6. Send the product sheet and pilot proposal to 10 to 20 small online shops (gift, home decor, stationery, specialty food).
7. Press release to your university news office and local tech press, and post it on the landing page.

## Publish the landing page

The page is a single static file with no build step: [`site/index.html`](site/index.html). The workflow `.github/workflows/pages.yml` publishes it.

1. Merge this PR into the repo's default branch.
2. On GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Run the workflow from the **Actions** tab (or push any change under `docs/launch/site/`).
4. The page appears at `https://sanskar1724.github.io/MarginGraph/`. That is your `SITE_URL`.

To preview it locally: `python -m http.server -d docs/launch/site 8000`, then open `http://localhost:8000`.
