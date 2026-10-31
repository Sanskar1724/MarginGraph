# Press release

*Template. Replace `[brackets]` and `SITE_URL` before sending. Keep the "simulated cost" sentence: removing it would make the release inaccurate.*

---

**FOR IMMEDIATE RELEASE**

## Student-built open-source tool picks checkout suggestions for profit as well as relevance, and publishes the experiments where AI lost

**[City], [Date]:** MarginGraph, an open-source research project by [San's full name], a student at [University], was released today on GitHub. It suggests up to two add-on products at an online store's checkout, chosen both for what the shopper is likely to buy and for the profit they bring the store, and never below a margin floor the store sets.

Most product-suggestion boxes optimize for clicks or sales alone and tend to push the cheapest, best-selling items. MarginGraph splits the job in two. A ranking model, trained on the store's past orders, finds the items a shopper is likely to want. A mathematical optimizer then chooses which two to show, maximizing expected profit under rules enforced by plain code: a minimum margin, at most two items, and an optional push for overstocked products. No AI model sets prices or can override the rules.

In an offline test on two years of real orders from a UK online gift retailer (the public UCI Online Retail II dataset, 39,516 orders and 4,707 products), MarginGraph's ranker found the item shoppers actually bought among its top ten suggestions in 38.1% of 4,480 test orders, compared with 31.1% for the best standard method and 3.1% for a best-seller list. Choosing for profit raised the profit per order from the add-on by about 14% compared with showing the two most likely items, for a drop of about one percentage point in hits, and broke the margin floor zero times.

The dataset contains real prices but no unit costs or stock levels, so those were simulated. The project reports the profit result with that caveat, along with tests showing that the gain held across nine different cost assumptions.

The project also publishes its negative results. Open language models (Qwen2.5 with 1.5 and 3 billion parameters) were tested as the ranker and performed clearly worse than a conventional gradient-boosted model, so they are not used for ranking.

"Retail AI pitches are full of target numbers. I wanted every number in this project to come from an experiment anyone can rerun, including the ones where the fashionable approach lost," said [San's full name]. "The next step is the real test: a pilot with a store's own costs and an A/B test against what they use today."

MarginGraph runs on a single ordinary server without a GPU and was built entirely with free tools. The developer is looking for two or three small online stores to take part in a free pilot.

### About MarginGraph

MarginGraph is an open-source research prototype for margin-aware product recommendations. Code, data pipeline and full results: github.com/Sanskar1724/MarginGraph. Project page: SITE_URL. Demo: https://huggingface.co/spaces/EquilStable/MarginGraph.

### Key facts

- Tested offline on real public sales data; not yet deployed in a live store.
- Top-10 hit rate 38.1% vs 31.1% for the best standard method (+7.0 points, 95% confidence interval 6.0 to 8.0).
- About +14% profit per order from the add-on under simulated costs; 0 margin-floor breaks.
- On four more public datasets: wins in Taiwan grocery (+8.3 points) and a US supermarket (+7.8); a loss on a US grocery app (−3.0) that turned into +4.1 once shoppers' past purchases were put first; a tie on a small Brazilian marketplace sample.
- In a 30-day replay of real checkouts with simulated costs: £1,141 vs £920 add-on profit, and 0 offers below the margin floor vs 164.
- Language models tested as rankers did not beat the conventional model.

### Media contact

[San's full name] · YOUR_EMAIL · [phone, optional]

###
