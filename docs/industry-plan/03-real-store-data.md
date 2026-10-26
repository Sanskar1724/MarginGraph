# Phase 3: real cost and stock from a pilot store

**Goal:** replace the simulated cost and stock with a real store's numbers, and check the offline result on that store's own history before showing anything to its shoppers. This is the step that can turn "+14% profit (simulated)" into a real number, or show that it does not hold.

**Needs:** a pilot store that said yes (see [07-business-and-outreach.md](07-business-and-outreach.md)), and PR #12 merged for the live part.

**Done when:**

- [ ] The store's orders, products, unit cost and stock are synced, and `summary.json["erp"]` shows the share with real cost.
- [ ] Unit cost is known for products covering at least 90% of the store's revenue (our chosen bar; below that, profit numbers are mostly assumptions).
- [ ] The offline gate passes on the store's own history: LightGBM beats the best baseline and the store's current suggestions (if you can get them), with the CI above zero.
- [ ] Stage 2 results with real cost are in `e8_strategies_store_erp.csv`, with 0 margin-floor breaks.
- [ ] The store is created in the service, trained by the nightly job, and answering `POST /v1/recommend` in a staging check.

## Step 0: practise on a free test store first

Do this before you have a pilot, so the first real sync is not the first sync ever.

- [ ] **Shopify:** create a free Shopify Partners account, then a development store. Add 30 to 50 products with "Cost per item" and stock, and create test orders (Shopify's Bogus Gateway). Then follow the Shopify steps below.
- [ ] Or **WooCommerce:** run it locally with Docker (`wordpress` and `mariadb` images), install WooCommerce and a cost-of-goods plugin, add products and orders.
- [ ] Run the sync and the pipeline. Expect `sync` to warn about too few orders: that is the point, it shows the warnings work.

## Step 1: get the data from the store

Pick the easiest route the store accepts ([CONNECTORS.md](../CONNECTORS.md) has the full details):

| Route | What the store does | Command |
| --- | --- | --- |
| CSV or Excel export | Sends an orders export and a products file with cost and stock | `margingraph sync csv --orders orders.xlsx --products products.csv --mapping mapping.yaml --out data/store/pilot1` |
| Shopify | Creates a custom app with `read_products`, `read_inventory`, `read_orders` (plus `read_all_orders` for history over 60 days) and gives you the token | `margingraph sync shopify --out data/store/pilot1` with `SHOPIFY_SHOP` and `SHOPIFY_ACCESS_TOKEN` in `.env` |
| WooCommerce | Creates a **Read** REST key | `margingraph sync woocommerce --out data/store/pilot1` with `WC_STORE_URL`, `WC_CONSUMER_KEY`, `WC_CONSUMER_SECRET` in `.env` |

```bash
set -a; source .env; set +a      # credentials only from .env, never on the command line history or in git
margingraph sync shopify --out data/store/pilot1
cat data/store/pilot1/pipeline/clean_log.json     # warnings: cost above price, unknown orders, few baskets, cost coverage
```

Before the sync, ask the store to remove names, emails, phones and addresses (see [privacy-and-data.md](../launch/privacy-and-data.md)). Shopify and WooCommerce orders contain customer details; the connector keeps only a customer id. Check that `data/store/pilot1/raw/orders.parquet` has no email column before going further.

## Step 2: check the cost and stock data

- [ ] Cost coverage by revenue (not by product count):
  ```bash
  python - <<'PY'
  import pandas as pd
  lines = pd.read_parquet("data/store/pilot1/pipeline/lines.parquet")   # invoice, item, quantity, revenue, ...
  erp = pd.read_parquet("data/store/pilot1/pipeline/erp.parquet")       # item, unit_cost, stock (NaN = unknown)
  rev = lines.groupby("item")["revenue"].sum()
  has_cost = set(erp.loc[erp["unit_cost"].notna(), "item"])
  has_stock = set(erp.loc[erp["stock"].notna(), "item"])
  print(f"revenue with known cost:  {rev[rev.index.isin(has_cost)].sum() / rev.sum():.1%}")
  print(f"revenue with known stock: {rev[rev.index.isin(has_stock)].sum() / rev.sum():.1%}")
  PY
  ```
  (Checked against the files `sync` writes; the column names are `item`, `unit_cost`, `stock`.)
- [ ] Cost above price: listed in the sync warnings. Ask the store about each one; usually a data entry error or a loss leader.
- [ ] Stock: negative values are clipped to 0. Ask the store whether stock in the system matches the shelf.
- [ ] Ask the store for its **real margin floor**, maximum add-ons, whether discounts are allowed, and which products are overstocked. Put them in the store config (`optimize.margin_floor`, `max_addons`, `discounts`).

## Step 3: offline gate on the store's own history

```bash
margingraph --config data/store/pilot1/config.yaml run --results results_pilot1 --artifacts data/artifacts/pilot1
python scripts/public_datasets.py compare results results_pilot1
python -c "import json; print(json.load(open('results_pilot1/summary.json'))['erp'])"
margingraph-gate --strict results_pilot1        # fails if LightGBM's CI lower bound is below popularity
```

- [ ] LightGBM vs best baseline: CI above zero.
- [ ] If the store already shows "also bought" suggestions, ask for an export of what it showed (or rebuild its rule) and compare Hit@10 against it on the same test baskets. This is the comparison the store cares about.
- [ ] Stage 2 with real cost: compare `ranker_top2` and `milp_lam0.5` in `e8_strategies_store_erp.csv`. Report realized profit and Hit@2 with their CIs, and 0 floor breaks.
- [ ] Keep the store's results private. Do not commit `results_pilot1/` or anything with the store's numbers to a public repo. Write a private report; publish only what the store agrees to.

## Step 4: put the store into the service (PR #12)

```bash
margingraph import-sync pilot1 --folder data/store/pilot1 --create   # creates the store, prints the API key once: save it in a password manager
margingraph batch --store pilot1                                     # trains, runs the quality gate, activates the model
curl -s -X POST $MG/v1/recommend -H "X-API-Key: $KEY" -H 'content-type: application/json' -d '{"basket":["<a real SKU>"]}'
```

- [ ] Real stock updates: point the store's order webhook at `POST /v1/webhooks/pilot1/orders` (signed with the store's `webhook_secret`), or run `margingraph sync` every night.
- [ ] Staging check: 50 real past baskets through the API; every answer has 0 floor breaks, only in-stock items, and sensible products (look at them yourself with the store owner).

## If the store has little history

The service falls back to margin-safe best sellers when the model is not ready, and the quality gate refuses a model that is not better than the simplest baseline. A store with only a few hundred multi-item orders may stay on the fallback. That is safe, but there is nothing to A/B test yet: either wait for more orders or pick a larger store.

## Files involved

| File | Role |
| --- | --- |
| `src/margingraph/connectors/` | CSV, Shopify, WooCommerce sync |
| `docs/CONNECTORS.md` | Setup for each platform, mapping, validation |
| `src/margingraph/data.py` (`store_erp`) | Real cost and stock, with assumptions flagged |
| `src/margingraph/service/` (PR #12) | Multi-store API, `create-store`, `import-sync`, `batch` |
| `docs/launch/privacy-and-data.md` | What data you ask for and promise |

## Prompt for a future Claude session

```text
Phase 3 of docs/industry-plan (03-real-store-data.md). Pilot store "<name>" sent data via <CSV /
Shopify / WooCommerce>. I synced it to data/store/pilot1 on my laptop. Here is clean_log.json and
summary.json["erp"]: <paste>. Do not ask me for the raw data or credentials.
Please: (1) tell me whether cost coverage and data quality pass the bar in the phase file, and what
to ask the store about each warning; (2) give me the exact commands for the offline gate and how to
read e8_strategies_store_erp.csv; (3) draft a private 1-page result summary for the store owner from
the numbers I paste back, with CIs and the simulated/real labels right. Nothing about this store goes
into the public repo.
```
