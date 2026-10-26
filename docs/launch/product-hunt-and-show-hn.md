# Product Hunt and Show HN

*Replace `DEMO_URL`, `SITE_URL` and `BLOG_URL` first. Both sites need something people can try: launch only after the demo is live.*

---

## Show HN

**Rules that matter:** the post must link to something people can try or run (the repo or the demo). No marketing language, no upvote requests. Post on a weekday around 8 to 10 am US Eastern and stay for 3 hours to answer.

**Title (max 80 chars):**

> Show HN: MarginGraph – checkout recommendations that optimize for profit, not clicks

Alternative:

> Show HN: A profit-aware recommender, tested on real baskets (the LLM lost)

**URL:** `https://github.com/Sanskar1724/MarginGraph`

**First comment (post it right after submitting):**

> Hi HN, I'm a student and this is my project. MarginGraph suggests up to 2 checkout add-ons. A LightGBM ranker finds what the shopper is likely to buy; a small integer program (PuLP/HiGHS, ~3 ms) then picks the 2 with the highest p(buy) × profit, under a hard 15% margin floor enforced in code.
>
> I tested it on UCI Online Retail II (real UK gift-shop invoices): strict time split, 4,480 test baskets, one item hidden per basket.
>
> - Hit@10: 38.1% vs 31.1% for EASE, the best baseline (+7.0 pts, paired bootstrap CI [6.0, 8.0])
> - Optimizer vs plain top-2: about +14% realized profit per basket, −1.1 pts Hit@2, 0 margin-floor breaks
> - The dataset has no unit cost or stock, so those are simulated. The gain stayed positive across 9 cost scenarios, but I'd treat it as a sign, not a result, until a real store tests it
>
> The original plan put an LLM at the centre. Qwen2.5 1.5B and 3B zero-shot lost to LightGBM by ~11 pts Hit@5 on the same slates, and as a stacker feature they got ~0 weight. My guess: short product titles and a strong co-purchase signal. A LoRA fine-tune of the 1.5B did worse (Hit@5 7.8%, below random order), so the LLM is out of the ranking.
>
> Biggest practical lesson: shortlist recall (58% at 100 items, now 65% at 150) mattered more than the reranker.
>
> Everything reruns from the raw data with one command. I'd love feedback on the evaluation setup, and on whether p(buy) × margin is the right objective vs something like a constrained bandit. Write-up: BLOG_URL

**Likely replies, and honest answers:**

| They say | Answer |
| --- | --- |
| "14% on simulated costs means nothing" | Agreed that it isn't proof. It shows the optimizer does what it should under a range of assumptions (E11: 9 scenarios, all CIs above zero). The relevance numbers use no simulation. A real store's costs are the next step. |
| "Leave-one-out on a basket isn't a real add-on task" | Fair. It is the closest offline proxy with this data. The pilot plan is an A/B test on profit per visitor. |
| "Why not just sort by margin × popularity?" | That ignores the basket. Popularity top-2 has Hit@2 1.2% vs 15.6% for the optimizer at λ=0.5. |
| "Your LLM prompt was bad" | Possible. It was yes/no scoring of the top 20 slate; prompts and code are in `notebooks/` and `src/margingraph/llm.py`. A LoRA fine-tune is the stronger test; it scored Hit@5 7.8% vs 27.6%, below random order. |
| "Why a MILP for picking 2 items?" | You could enumerate, and the repo does for bulk sweeps (they agree on 600/600). The MILP generalizes to bundle floors and discount choice without rewriting. |
| "What's the latency?" | Solver is 2.7 ms mean. In a container the research API is p50 22 ms / p95 28 ms, and the multi-store service p95 88 ms end to end. Your hosting will differ. |

---

## Product Hunt

**Name:** MarginGraph

**Tagline (max 60 chars):**

> Checkout suggestions that sell and protect your margin

**Topics:** E-Commerce, Open Source, Artificial Intelligence, Developer Tools

**Description (max 260 chars):**

> MarginGraph picks up to 2 checkout add-ons a shopper is likely to buy, then chooses the most profitable ones under a margin floor you set. Open source, runs on one CPU. Tested on 4,480 real orders; profit gains so far use simulated costs.

**Gallery (in this order):**

1. Demo screenshot: a basket and the 2 add-ons, with margin shown
2. The "how it works" diagram (shortlist → ranker → optimizer)
3. Chart: profit vs Hit@2 for top-2, λ=0.5, λ=1.0
4. Table of results with the simulated-cost note
5. A screenshot of the margin-floor and profit-dial settings

**Maker's first comment:**

> Hi Product Hunt 👋 I'm San, a student, and MarginGraph is my project.
>
> The problem: "customers also bought" boxes push whatever sells most, which is often a shop's cheapest, lowest-margin stock.
>
> MarginGraph does it in two steps. A ranking model learns from past orders what goes together. Then an optimizer picks the 2 suggestions with the best expected profit, and never goes below the margin floor you set. No AI touches your prices.
>
> On real orders from a UK gift shop, it found the item shoppers actually bought in its top 10 suggestions 38.1% of the time (vs 31.1% for the best standard method), and choosing for profit raised add-on profit by about 14%. Honest caveat: that dataset has no costs, so costs were simulated. That's why I'm looking for 2–3 shops for a free pilot with a real A/B test.
>
> It's open source and runs on a single ordinary server. Try the demo: DEMO_URL. I'd love your feedback, especially from anyone who runs a store. 🙏

**Launch day tips:** launch at 12:01 am Pacific; reply to every comment; share the PH link on LinkedIn and X that morning; do not ask for upvotes directly (PH penalizes it), ask for feedback instead.
