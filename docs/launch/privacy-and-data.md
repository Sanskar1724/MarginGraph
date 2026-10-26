# MarginGraph: privacy and data handling for merchants

*Plain-language note for store owners. Version 2026-10-26. This describes how a pilot is run; it is not legal advice. If your store is in the EU or UK (GDPR), India (DPDP Act 2023) or California (CCPA), your own privacy notice still applies to your customers, and we act on your instructions.*

---

## In one paragraph

MarginGraph learns which products are bought together. For that it needs your **orders and products**, not your customers' identities. We ask you to remove names, emails, phone numbers and addresses before you send anything. We use your data only to run your pilot, we keep it on access-controlled storage, we never sell or share it, and we delete it within 30 days after the pilot ends.

## What we need

| Data | Why | Required? |
| --- | --- | --- |
| Order ID, order date, product ID, quantity, unit price | To learn which products are bought together | Yes |
| Product name, category | To show readable suggestions and for new products with no sales | Yes |
| Unit cost per product | To compute margin and enforce your margin floor | Yes, for the profit features |
| Stock level per product | For overstock priority and to avoid suggesting items you cannot ship | Optional |
| A customer ID (any random code, the same for repeat customers) | Lets the model use a returning customer's past orders | Optional. If you send one, make it a random code, not an email |
| Country or region of the order | Optional signal | Optional |

## What we do not want

- Customer names, emails, phone numbers, postal addresses.
- Payment details of any kind.
- Passwords or admin logins to your store. For a live connection we use a limited, read-only API key that you create and can revoke.

If any of this arrives by mistake, we delete it on receipt and tell you.

## During the live A/B test

To show suggestions, the cart sends MarginGraph the **product IDs in the cart**, plus a random visitor code so a visitor always stays in the same test group. We log what was shown, what was clicked and what was bought, with timestamps, to measure the result. No names, emails or IP addresses are stored in these logs.

## Where the data is kept and who can see it

- Stored on access-controlled storage (encrypted at rest where the host supports it) and sent only over HTTPS.
- Access is limited to the developer running your pilot.
- Your data is used only for your store. It is never used to train models for other stores, and never sold, rented or shared.
- Free hosting providers may run in another country. We will tell you which provider and region before the pilot starts, and you can ask for a different region.

## How long we keep it

- **During the pilot:** as long as needed to run it.
- **After the pilot:** deleted within **30 days**, including backups and the trained model, with written confirmation.
- **What we may keep:** only the aggregate result numbers in the report (for example "profit per visitor +X%, CI [a, b]"), with no row-level data. Your store's name stays private unless you agree in writing.

## Your controls

- Switch the suggestions off at any time; the cart falls back to your own best sellers.
- Ask for a copy of everything we hold, or for early deletion, at any time.
- Revoke the API key at any time.

## How suggestions are made (transparency)

Suggestions come from a ranking model trained on your past orders and an optimizer that applies your business rules. No customer is profiled by name, age, gender or any sensitive trait. No AI model sets prices. Your margin floor is enforced by plain code on every suggestion.

## If something goes wrong

If we learn of any unauthorized access to your data, we will tell you within 72 hours, say what was affected, and what we are doing about it.

## Contact

San · YOUR_EMAIL
