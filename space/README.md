---
title: MarginGraph
emoji: 🛒
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 6.30.0
python_version: "3.13"
app_file: app.py
pinned: false
license: mit
short_description: Checkout add-ons that sell and keep your margin
---

# MarginGraph demo

Profit-aware checkout add-on recommendations. Stage 1 (EASE co-purchase model)
finds what customers are likely to add; Stage 2 picks at most 2 add-ons that
maximize expected profit under hard rules (margin floor, in stock, overstock push).

* **Demo store:** 2,000 real products from UCI Online Retail II. Costs and stock are simulated.
* **Your store:** upload `products.csv` (item, description, price, unit_cost, stock, overstock)
  and optionally `orders.csv` (order_id, item) to train on your own data in about 2 seconds.
* **Batch:** upload open baskets, download recommendations as CSV.
* **Backtest:** measured numbers on held-out Oct to Dec 2011 invoices.

Runs on the free CPU tier (about 250 to 350 MB RAM). Source:
https://github.com/Sanskar1724/MarginGraph (folder `space/`).

Rebuild the artifacts: `python space/build_artifacts.py --xlsx online_retail_II.xlsx`
