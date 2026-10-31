# MarginGraph FAQ

## For store owners

**What is MarginGraph?**
A system that suggests up to 2 add-on products at checkout. It picks items the shopper is likely to buy and, among those, the ones that earn you the most, without ever going below a margin floor you set.

**How is it different from "customers also bought"?**
"Customers also bought" looks only at what sells together. MarginGraph uses that too, and then chooses among the likely items for expected profit, with hard rules: a margin floor, a limit of 2 items, and optional extra push for overstock.

**Will it raise my profit?**
We do not know yet for your store, and we will not promise a number. On a public dataset of real UK gift-shop orders, it raised the profit from the add-on by about 14% compared with showing the 2 most likely items, for a small drop in hits. But that dataset has no unit costs, so we simulated them. A pilot with your real costs is how we would find out, with a fair A/B test.

**Will it hurt sales by pushing expensive items?**
The optimizer can only choose from items the ranking model already rates as likely to be bought, and it weighs profit by that likelihood. You set how far it leans toward profit. At the balanced setting, the shopper's item dropped out of the 2 shown in about 1 order in 100. In a pilot, conversion is tracked as a guard metric, and MarginGraph is called a win only if conversion is not clearly worse.

**Can it break my margin rules?**
The rules are checked in plain code on every suggestion, not by a model. In testing there were 0 margin-floor breaks, against about 4 per 100 orders when simply showing the top 2 likely items.

**Does AI set my prices or discounts?**
No. Nothing in MarginGraph changes prices. AI models are used only to rank products.

**Is it "AI-powered" with ChatGPT-style models?**
We tested open language models (Qwen2.5, 1.5B and 3B) as the ranker. They lost clearly to a simpler model (LightGBM), so we do not use them for ranking. A fine-tuned version lost too. A language model may still help with brand-new products and short explanations. We would rather tell you that than sell you a buzzword.

**What do I need to give you?**
Order history (order ID, date, product, quantity, price), product names, unit costs, and stock if you have it. No customer names or emails. See the [privacy and data note](privacy-and-data.md).

**How much history is enough?**
A year or more of orders works best. A few thousand orders a year and a few hundred products is a good starting point. With less, we start with best sellers that pass your margin floor and switch to the model once there is enough data.

**Which platforms does it work with?**
The core is a small web service that any site can call. Shopify and WooCommerce connectors are being built. A simple script tag is possible for other sites.

**What does it cost?**
The pilot is free. The software is open source. A paid hosted version may follow, and pilot stores would get a founding price.

**Can I switch it off?**
Yes, at any time. The cart then falls back to your best sellers that pass the margin floor.

**Is it in use in any store today?**
No. It has been tested offline on real sales data, not yet in a live store. We are looking for the first pilot stores.

## For developers and researchers

**What is the architecture?**
A candidate shortlist (EASE in three variants, text similarity, a nightly fresh-sales signal, ItemKNN, ALS, repeat purchase, co-purchase, popularity; up to 150 items), a LightGBM reranker with isotonic calibration to get p(buy), and a PuLP mixed-integer program that maximizes Σ (price·(1−d) − cost) · p(buy) · overstock weight, subject to at most 2 items and a 15% post-discount margin floor.

**What data and split?**
UCI Online Retail II (UK online gift retailer, Dec 2009 to Dec 2011): 991,910 clean invoice lines, 39,516 invoices, 4,707 products. Strict time split: train to 30 June 2011, validation Jul to Sep 2011, test 2 Oct to 9 Dec 2011 (4,480 events). One product hidden per invoice (checkout add-on framing).

**Headline results?**
LightGBM Hit@10 38.1% vs EASE 31.1% (+7.0 points, 95% paired bootstrap CI [6.0, 8.0]). MILP at λ=0.5 vs ranker top-2: realized profit +14% (CI +£0.014 to +£0.044 per basket), Hit@2 −1.1 points. All in [`docs/RESULTS.md`](../RESULTS.md).

On four more public datasets (same code, pass/fail rule fixed first): Ta Feng +8.3 [+7.7, +8.8], Dunnhumby +7.8 [+7.2, +8.4], Instacart −3.0 [−3.6, −2.4] (official; +4.1 [+3.7, +4.5] with past purchases first in the candidate pool), Olist a tie on 169 baskets. In a 30-day replay of real checkouts with simulated cost and stock, add-on profit was £1,141 vs £920 for the ranker alone, with 0 vs 164 offers under the floor. See [`docs/RESULTS_PUBLIC.md`](../RESULTS_PUBLIC.md) and the [paper](../../paper/main.pdf).

**What is the ceiling?**
The 150-item shortlist contains the hidden item 65.3% of the time (58.0% at 100 items before the accuracy work), and 7.1% of test items never appear before the test window. Raising shortlist recall is the most direct way to improve.

**How are cost and stock simulated, and does that matter?**
The dataset has no cost or stock. Experiment E11 reruns the comparison under 3 margin distributions × 3 seeds; the profit gain stayed positive in all 9 (every CI above zero). Real costs from a pilot store are the next test.

**Why did the LLM lose?**
Zero-shot yes/no scoring of the top 20 LightGBM items with Qwen2.5-1.5B gave Hit@5 16.8% vs 27.6% for LightGBM on the same 1,000 baskets; 3B was no better. Used as an extra feature in a stacker, its fitted weight was near zero. Product titles in this dataset are short and the co-purchase signal is strong, so behaviour data beats text understanding here. A LoRA fine-tune of the 1.5B model (hard negatives from LightGBM slates) did worse: Hit@5 7.8%, below random order of the slate (11.6%). The LLM track is closed for ranking.

**Is it fast enough?**
The optimizer solves in 2.7 ms on average and matches exact enumeration on 600 of 600 problems. Measured in a container, the research API answers in 22 ms at the median (p95 28 ms) and the multi-store service in 88 ms at p95 end to end; a store's own hosting will differ.

**Does it need a GPU?**
No, for serving or for the main pipeline. Only the optional LLM experiments use a free Kaggle or Colab GPU.

**How do I run it?**
See [`docs/RUNNING.md`](../RUNNING.md). `margingraph run` reproduces every table from the raw dataset with seed 42.

**Can I use the code?**
Once a license is added to the repo (planned: an open-source license such as MIT or Apache-2.0). Until then, please ask.
