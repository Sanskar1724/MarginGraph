# Phase 7: business and pilot outreach

**Goal:** sign one pilot store that can give real cost data and enough traffic for a conclusive A/B test, then use its result to win the second and third. Start this on day one: it is the slowest phase, and Phases 3 and 4 wait for it.

**Done when:**

- [ ] One pilot store has signed the pilot agreement and the data processing agreement.
- [ ] Its traffic is enough for the A/B test (Phase 4 sizing), or both sides agreed to a longer test.
- [ ] An outreach tracker exists and is up to date, with your own measured reply rate.

## What you can honestly say today

Use the wording from the launch kit ([product-sheet.md](../launch/product-sheet.md), [pilot-proposal.md](../launch/pilot-proposal.md)), which already follows these rules:

- "On two years of real sales from a UK online gift shop, it found the item shoppers actually bought in its top 10 for **38.1%** of orders, against **31.1%** for the best standard method."
- "With **simulated** costs, choosing for profit raised add-on profit by about **14%** for a small drop in hits." Always say simulated.
- After Phase 1: add the multi-dataset sentence exactly as measured.
- Never quote a profit gain for a real store until its A/B test is finished.

## Who to pitch (ideal pilot profile)

| Must have | Why |
| --- | --- |
| Unit cost per product, in a system or a spreadsheet | No cost, no profit proof (Phase 3) |
| Enough checkouts: ideally **300+ per day**, at least about 100 | Below that, the A/B test takes months (Phase 4 table) |
| A few hundred to a few thousand products, many orders with 2+ items | The ranker needs baskets; very large catalogs need the sparse-model work first |
| Shopify or WooCommerce, or a developer who can call an API from the cart | Integration effort |
| An owner who will reply and decide | Pilots die waiting for approvals |

Good fits: gifts, home decor, stationery, beauty, specialty food, pet supplies, hobby and craft shops. Avoid for a first pilot: marketplaces (Olist-like sparse baskets), single-product brands, very large retailers.

The traffic bar is the hard part for a student: small shops with cost data often have too little traffic. Two ways out: a mid-size shop that wants a free test, or a **group of small shops on one platform** (each with its own test, analysed together as a meta-analysis, decided in advance).

## Where to find them (free)

- [ ] Shops you can see are on Shopify or WooCommerce in your city or country (Indian D2C brands on Shopify, local gift and stationery shops online).
- [ ] Shopify and WooCommerce community forums and subreddits (follow each community's rules on self-promotion; ask for feedback first, not sales).
- [ ] Your university: incubator, entrepreneurship cell, alumni who run online shops, professors with retail contacts.
- [ ] LinkedIn: e-commerce managers at mid-size brands, with a short personal note ([social-posts.md](../launch/social-posts.md) has a template).
- [ ] Shopify agencies and freelancers: one agency can introduce several stores.
- [ ] After the demo is live: Show HN / Product Hunt ([product-hunt-and-show-hn.md](../launch/product-hunt-and-show-hn.md)), only once the demo URL works.

## Outreach process

- [ ] Make a tracker (a free spreadsheet): store, URL, platform, est. traffic, has cost data?, contact, date sent, reply, next step, status (`lead → contacted → call → agreed → data received → live → done`).
- [ ] 10 personalized messages a week. Use [pilot-proposal.md](../launch/pilot-proposal.md) section 2, with one real detail about each shop.
- [ ] Follow up once after 5 to 7 days. Then stop.
- [ ] Measure your own reply and acceptance rates in the tracker; do not plan with made-up rates.
- [ ] On a call: ask about their current "also bought" box, their margins, overstock, monthly orders, and who can change the cart. Show the demo. Offer the free 8-week pilot.

## Pilot terms (to put in writing)

- [ ] Free, about 8 weeks (longer if the sample size needs it), no obligation after.
- [ ] What they give: order export, unit costs, stock, a place in the cart for 2 suggestions, a developer's few hours.
- [ ] What you give: setup, a fair A/B test with a pre-registered plan, a written result whether it wins or loses, the ability to switch it off at any time.
- [ ] Data: the [privacy note](../launch/privacy-and-data.md) and a signed DPA (Phase 5). Deletion within 30 days after the pilot.
- [ ] Case study: only with written permission; name only if they agree.
- [ ] A simple one-page pilot agreement. A free template from your university's legal clinic or incubator is better than writing one alone.

## Business model (hypotheses to test, from [ROADMAP.md](../ROADMAP.md))

| Plan | Who | Idea |
| --- | --- | --- |
| Free | Small shops | A request cap per month, best-seller fallback, basic dashboard |
| Pro | Growing shops | Full optimizer, overstock push, A/B reports, flat monthly fee |
| Performance | Larger shops | A share of the measured extra profit from the A/B test |

None of these prices or plans is tested. After the first pilot, ask the owner what they would pay and how; write the answers down as data.

## Competition (what a store compares you with)

Shopify's own product recommendations and many "frequently bought together" and upsell apps already exist, some free. Most optimize clicks or conversion. MarginGraph's difference: a **hard margin floor the store controls**, an **explicit profit objective**, open source, and a fair A/B test as the proof. Before each call, check what the store already uses and how it chooses products, so you compare against the right thing.

## Recruiter and research angle

- [ ] Keep the repo's README, results and paper honest and current; that is the strongest signal.
- [ ] Post the paper on arXiv (endorsement needed, Phase 0) once E6 and Phase 1 are recorded.
- [ ] A short write-up after the pilot (blog post in the launch kit) with the real result, win or lose.

## Files involved

| File | Role |
| --- | --- |
| `docs/launch/` | Pilot letter, product sheet, privacy note, FAQ, social posts, landing page |
| `docs/deck/MarginGraph_pitch_deck.pptx` | Pitch deck |
| `docs/ROADMAP.md` | Business model and risks |
| New, private: outreach tracker, pilot agreement, DPA | Not in the public repo |

## Prompt for a future Claude session

```text
Phase 7 of docs/industry-plan (07-business-and-outreach.md). Here are 10 shops I found (name, URL,
what they sell, platform, anything about traffic): <list>. For each, (1) say how well it fits the
pilot profile in the phase file and why, and (2) draft a personalized first message from
docs/launch/pilot-proposal.md section 2 using one real detail from their site that I gave you.
Keep every claim to the measured numbers in the phase file, and say "simulated" for profit.
Do not invent anything about the shops beyond what I wrote.
```

After a call:

```text
I had a call with <store>. Notes: <paste>. Using docs/industry-plan/07 and 04, tell me whether its
traffic is enough for a conclusive A/B test (run scripts/ab_sample_size.py with the numbers I give),
and draft the follow-up email with the pilot terms and next steps.
```
