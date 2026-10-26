# MarginGraph pilot proposal

*A template. Replace everything in `[brackets]` before sending. Section 2 is the letter; section 3 onward is the attachment.*

---

## 1. How to use this

1. Look at the store first: what it sells, roughly how many products, whether it already shows "you may also like" suggestions.
2. Personalize the letter's first paragraph with one real detail about their shop.
3. Attach the [product sheet](product-sheet.md) and the [privacy and data note](privacy-and-data.md).
4. Send it to the owner or the person who runs the online shop, not a general inbox, if you can find them.

---

## 2. Offer letter

**Subject:** A free pilot to make your checkout suggestions more profitable

Dear [Name],

I came across [Store name] while looking at [one real detail, e.g. "independent stationery shops in Pune", "your range of handmade candles"]. I am a student building MarginGraph, an open-source system that suggests add-on products at checkout, chosen both for what the shopper is likely to want and for the profit they bring you.

Most "customers also bought" boxes push whatever sells most, which is often your cheapest, lowest-margin stock. MarginGraph picks up to 2 add-ons that the shopper is likely to buy, then chooses among them for expected profit, and it never suggests anything below a margin floor that you set.

So far I have tested it on two years of real sales from a UK online gift shop. It found the item shoppers actually bought in its top 10 suggestions for 38.1% of orders, against 31.1% for the best standard method. With simulated costs, choosing for profit raised the profit from the add-on by about 14%, for a small drop in hits. I want to be clear that those costs were simulated, because the public data has none. That is why I am looking for a real store to test it with.

**What I am offering:**

- A free pilot of about [8] weeks, with no fee now and no obligation afterwards.
- I do the setup and analysis. Your time is about 2 hours in total.
- A fair test: half your visitors see your current suggestions, half see MarginGraph's, and you get a written report with the result, whether it wins or loses.

**What I would ask of you:** an export of past orders, your unit costs, a place in your cart to show 2 suggestions, and, if it goes well, permission to describe the result as a case study (your name only if you agree).

Could we have a 20-minute call in the next two weeks? I have attached a one-page overview and a note on how your data would be handled.

Kind regards,
[Your full name]
[University / course, if you want to mention it]
[Email] · [Phone]
github.com/Sanskar1724/MarginGraph · https://huggingface.co/spaces/EquilStable/MarginGraph

---

## 3. Pilot plan

### Goal

Find out, with the store's real costs and real shoppers, whether MarginGraph earns more gross profit per visitor than the store's current suggestions, without hurting conversion.

### Timeline (about 8 weeks)

| Week | What happens | Store's time |
| --- | --- | --- |
| 0 | Kick-off call. Agree the margin floor, the profit dial and any products to exclude | 30 min |
| 1 | Store sends order history, product list, unit costs, stock | 30 min |
| 1–2 | We train on the store's history and run the **offline check**: does MarginGraph beat the store's current suggestions and a best-seller list on past orders? If not, we stop here and tell you | none |
| 2 | Connect to the cart (Shopify, WooCommerce or a simple script tag) and test on a staging page | 30 min |
| 3–6 | **A/B test** live, at least 2 full weeks and until the planned sample size is reached | none |
| 7 | Written report and a results call | 30 min |

### A/B test design

| | |
| --- | --- |
| Split | 50/50 by visitor, fixed per visitor |
| Control | The store's current suggestions (or best sellers if none) |
| Treatment | MarginGraph's 2 add-ons |
| Main metric | Gross profit per visitor |
| Guard metrics | Conversion rate, average order value, margin-floor breaks (must be 0), errors |
| Sample size | Fixed before the test starts, from the store's traffic |
| Analysis | 95% confidence interval on the difference, as in the offline work |
| Decision rule | MarginGraph is called a win only if profit per visitor is higher with the interval above zero and conversion is not clearly worse |

### Safety

- If the service is slow or fails, the cart falls back to the store's best sellers that pass the margin floor. The shop page never breaks.
- The store can switch MarginGraph off at any time, immediately.
- Every suggestion is re-checked against the margin floor and the 2-item limit in code before it is shown.

### What the store gets

- The written report, including the raw numbers.
- Free use of the setup for [3 months] after the pilot, whatever the result.
- If a paid version exists later, a founding-store price.

### What we get

- Permission to use the anonymized result in research and promotion. The store's name is used only with written consent.

### Honest risks

- The offline result used simulated costs. With your real costs the profit gain may be smaller, larger, or zero. The pilot is how we find out.
- Stores with very few orders give the model little to learn from. We will tell you in week 2 if that is the case.
- Hosting during the pilot runs on free tiers. We keep the fallback on so a slow server cannot hurt your shop.

---

## 4. Simple pilot agreement (non-binding outline)

*Not legal advice. If the store wants a signed agreement, have it reviewed.*

1. **Parties:** [Store legal name] ("the Store") and [Your name] ("the Developer").
2. **Term:** [start date] to [end date], about 8 weeks. Either side can end it at any time with written notice (email is fine).
3. **Fee:** none.
4. **Data:** handled as in the attached privacy and data note. The Developer uses the data only for this pilot, keeps no customer names, emails or addresses, and deletes everything within 30 days of the end, with written confirmation.
5. **Control:** the Store keeps full control of its site and can switch the suggestions off at any time.
6. **Results:** the Store receives the full report. The Developer may publish anonymized results. The Store's name appears only with its written consent.
7. **No warranty:** the software is provided as is. The Developer is not liable for lost sales.

Signed: ____________________ (Store)   ____________________ (Developer)   Date: __________
