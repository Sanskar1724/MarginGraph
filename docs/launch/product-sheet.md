# MarginGraph

## Checkout suggestions that sell, and protect your margin

---

### The problem

Most "customers also bought" boxes push cheap, popular items. They sell, but they earn you very little. Some suggested items sit below a healthy margin once a discount is applied. And slow stock sits in the warehouse, because nothing pushes it.

### What MarginGraph does

When a shopper reaches the cart, MarginGraph suggests **up to 2 add-on products**. It picks them in two steps:

1. **What will this shopper want?** A model trained on your own past orders finds products that are often bought together with what is in the cart.
2. **Which of those make you money?** An optimizer picks the 2 that give the most expected profit, while obeying rules **you** set.

| Your rule | How it is kept |
| --- | --- |
| Never suggest an item below a 15% margin (or your own number) | Checked in plain code on every suggestion. In testing it was broken 0 times |
| Show at most 2 add-ons | Same |
| Push overstock a little harder | You choose a weight from 1.0 (off) to 2.0 |
| Balance profit against "most likely to sell" | One dial. You choose how far to lean toward profit |

No AI model ever sets a price or overrides your rules.

### What we have measured so far

We tested MarginGraph on two years of real sales from a UK online gift shop (a public research dataset, 39,516 orders, 4,707 products). We trained on older months and tested on 4,480 real orders from autumn 2011.

| | Result |
| --- | --- |
| Finds the item the shopper really bought, in its top 10 | **35.6%** of orders, against 3.1% for a "top sellers" list and 31.1% for the best standard method |
| Extra profit per order from the add-on, at the balanced setting | **+17%** compared with just showing the 2 most likely items\* |
| Cost in relevance for that profit | About 1 order in 100 where the shopper's item drops out of the 2 shown |
| Times the margin floor was broken | **0** |

\* **Important:** the public dataset has real prices but no unit costs or stock levels, so we simulated them. The relevance numbers are real. The profit numbers are a strong sign, not a promise. That is exactly what a pilot with your real costs would measure.

### What it needs from you

- Your order history (order ID, date, product, quantity, price). A CSV export is fine. A year or more of orders works best.
- Unit cost per product, and stock levels if you have them.
- A place to show 2 suggestions in your cart.

It runs on a single ordinary server. No GPU, no expensive cloud bill.

### Where the project is today

MarginGraph is an **open-source research prototype**. It has been tested offline on real sales data. It has not yet run in a live store. We are looking for **2 or 3 pilot stores** to test it against your current suggestions with a fair A/B test, free of charge.

**Good fit:** an online shop with a few thousand orders a year, a few hundred products, and access to unit costs. Gifts, home decor, stationery, beauty and specialty food are all a good match.

---

**Contact:** San · YOUR_EMAIL · Code: github.com/Sanskar1724/MarginGraph · Demo: DEMO_URL
