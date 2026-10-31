# Social posts

*Replace `SITE_URL` and `BLOG_URL` before posting. Attach a screenshot of the demo (a basket with its 2 add-ons) or the profit vs hits chart. Keep the "simulated cost" wording in every post that mentions profit.*

---

## LinkedIn: launch post

> Most "customers also bought" boxes push whatever sells most. That is often a store's cheapest, lowest-margin stock.
>
> For the last few months I have been building MarginGraph, an open-source system that picks checkout add-ons for two things at once: what the shopper is likely to buy, and what actually earns the store money.
>
> How it works:
> 1️⃣ A LightGBM ranker, trained on past orders, finds the products a shopper is likely to want.
> 2️⃣ A small integer program (PuLP) picks the 2 that give the most expected profit, under rules the store sets: a 15% margin floor, at most 2 items, an optional push for overstock.
> No AI model sets prices or can break those rules.
>
> What I measured on 4,480 real orders from a UK online gift shop (public UCI dataset):
> ✅ The item the shopper really bought was in the top 10 for 38.1% of orders, vs 31.1% for the best standard method (+7.0 points, 95% CI 6.0 to 8.0)
> ✅ Choosing for profit raised profit per order from the add-on by about 14%, for ~1 point fewer hits
> ✅ Same code on 4 more public stores: wins in Taiwan and US grocery (+8.3, +7.8 pts), one loss (−3.0) fixed by putting past purchases first (+4.1)
> ✅ 0 margin-floor breaks
>
> The honest part: the dataset has no unit costs, so the profit numbers use simulated costs. The gain held across 9 different cost assumptions, but only a real store can confirm it.
>
> And the part I learned the most from: I tested open LLMs (Qwen2.5 1.5B and 3B) as the ranker. They lost clearly to LightGBM. As an extra feature they added nothing, and a LoRA fine-tune ranked below random. I published those results too.
>
> Everything was built with free tools on an 8 GB laptop and a free Kaggle GPU.
>
> 🔗 Code and full results: github.com/Sanskar1724/MarginGraph
> 📝 Write-up: BLOG_URL
>
> I am looking for 2 or 3 small online shops for a free pilot with a proper A/B test. If you run one, or know someone who does, I would love to talk.
>
> #MachineLearning #Ecommerce #RecommenderSystems #Optimization #OpenSource #Retail

## LinkedIn: short follow-up (a week later)

> A lesson from building MarginGraph: the biggest gain did not come from a better model.
>
> Widening the candidate shortlist from 50 to 100 items, and adding EASE to it, raised the chance that the right product was even in the shortlist from 43.5% to 58.0%, and four more sources at 150 items took it to 65.3%. A better reranker cannot recover an item that was never shortlisted.
>
> If your recommender is stuck, measure shortlist recall first.
>
> Details: github.com/Sanskar1724/MarginGraph

## LinkedIn: message to a store owner (short)

> Hi [Name], I am a student building an open-source tool that chooses checkout add-ons for profit as well as relevance, with a margin floor you set. On real gift-shop data it beat the standard methods, but the costs were simulated, so I am looking for a real store for a free 8-week pilot with a fair A/B test. Would you be open to a 20-minute call? One-page overview: SITE_URL

---

## X (Twitter): single post

> Built an open-source recommender that picks checkout add-ons for relevance AND profit.
>
> LightGBM ranks → a 3 ms integer program picks 2 under a 15% margin floor.
>
> On 4,480 real orders: Hit@10 38.1% vs 31.1% (EASE). ~+14% add-on profit (simulated costs). 0 floor breaks.
>
> The LLM lost. 🧵👇 github.com/Sanskar1724/MarginGraph

## X: thread

1/ Most "customers also bought" widgets optimize for clicks. Stores care about profit. I built MarginGraph to do both, and to publish every number with a confidence interval. 🧵

2/ Setup: real invoices from a UK online gift shop (UCI Online Retail II). 39,516 orders, 4,707 products. Train on older months, test on 4,480 baskets from Oct to Dec 2011, hide one item per basket, try to suggest it.

3/ Stage 1: a shortlist from EASE, ItemKNN, ALS, co-purchase, text similarity and fresh sales, then a LightGBM ranker. Hit@10: 38.1%. Best single model (EASE): 31.1%. Best sellers: 3.1%. Paired gain +7.0 pts, CI [6.0, 8.0].

4/ Stage 2: a PuLP integer program picks 2 add-ons to maximize p(buy) × profit, with a hard 15% margin floor. Profit is always multiplied by p(buy), so it can't push an irrelevant pricey item.

5/ Result: ~+14% profit per order from the add-on vs just showing the top 2, for −1.1 pts Hit@2. 0 margin-floor breaks (the plain top 2 broke it 3.7 times per 100 orders).

6/ Caveat, in bold: the dataset has no unit costs. Costs and stock are simulated. The gain held in all 9 cost scenarios I tried, but a real store is the real test.

7/ The LLM part: Qwen2.5 1.5B zero-shot as reranker: Hit@5 16.8% vs LightGBM 27.6%. 3B: 16.6%. As a stacker feature: weight ≈ 0. LoRA fine-tune: 7.8%, below random. NO-GO ×4. Short titles + strong co-purchase signal = behaviour beats text here.

8/ Lessons: audit the signal vs a shuffled null first. Shortlist recall (now 65%) caps everything. Put business rules in code, not in a model. Set the gate before the run.

9/ All free tools, an 8 GB laptop, a free Kaggle T4. Code, results, and the failed experiments: github.com/Sanskar1724/MarginGraph. Write-up: BLOG_URL

10/ Looking for 2–3 small online shops for a free pilot with an A/B test. DMs open.

---

## Hashtags and where to share

- LinkedIn: #MachineLearning #Ecommerce #RecommenderSystems #OperationsResearch #OpenSource
- X: #MachineLearning #RecSys #buildinpublic
- Communities: r/MachineLearning (use the [P] tag, link the blog, lead with the NO-GO result), r/datascience, r/ecommerce (lead with the store-owner angle, no hard sell), the Kaggle discussion board for UCI Online Retail II.
