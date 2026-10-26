# Connecting a real store

`margingraph sync` pulls a store's products and orders into a local folder,
and `margingraph run` then trains on that store instead of Online Retail II.
Everything uses free software and the standard library for HTTP; a sync of a
few hundred thousand order lines fits comfortably in 8 GB of RAM.

```bash
pip install -e .
margingraph sync csv --orders my_orders.xlsx --products my_products.csv --mapping my_mapping.yaml --out data/store
margingraph --config data/store/config.yaml run --results results_store --artifacts artifacts_store
margingraph --config data/store/config.yaml serve --artifacts artifacts_store   # POST /recommend
```

## Sources

| Source | Command | Credentials | Incremental |
| --- | --- | --- | --- |
| CSV / TSV / Excel export | `sync csv --orders FILE [--products FILE]` | none | no, the file is re-read each time |
| Shopify Admin REST API | `sync shopify` | `SHOPIFY_SHOP`, `SHOPIFY_ACCESS_TOKEN` | orders by `updated_at_min` |
| WooCommerce REST API (wc/v3) | `sync woocommerce` | `WC_STORE_URL`, `WC_CONSUMER_KEY`, `WC_CONSUMER_SECRET` | orders by `modified_after` |

Credentials are read only from environment variables. Put them in a `.env`
file (already in `.gitignore`) and `set -a; source .env; set +a` before
syncing. Never commit them.

### CSV / Excel

The orders file has one row per order line, which is what most POS and
shop exports look like. Order fields (date, customer, status) may repeat on
every line. A products file is optional; without one, titles and prices come
from the order lines, and any product fields mapped onto the orders file
(`cost`, `stock`, `category`, `price`) are used.

Map your column names to the schema with a YAML file, `--map`, or a preset:

```yaml
# my_mapping.yaml
columns:                 # orders file
  order_id: Order Number
  product_id: SKU
  title: Item Name
  quantity: Qty
  unit_price: Unit Price  # "$1,234.50" style values are fine
  ordered_at: Date
  customer_id: Customer Email
  country: Country
  status: Status
product_columns:         # products file
  product_id: SKU
  price: Retail Price
  cost: Unit Cost
  stock: On Hand
  category: Department
cancelled_values: [cancelled, refunded, voided]   # status values to drop
cancelled_order_prefixes: []                       # e.g. [C] for credit-note ids
product_id_regex: null                             # keep only matching ids
decimal: "."                                       # "," for 1.234,50
dayfirst: false                                    # true for 31/01/2024
```

```bash
margingraph sync csv --orders orders.csv --map order_id="Order Number" --map products.cost="Unit Cost" ...
```

A field you do not map is looked up under its schema name, so a file that
already uses `order_id, product_id, quantity, unit_price, ordered_at` needs
no mapping. Required: `order_id, product_id, quantity, unit_price,
ordered_at`. If one is missing the error lists the file's real columns.

Presets: `online_retail_ii` (the UCI file the experiments use) and
`shopify_orders_export` (Shopify admin's "Export orders" CSV, if you do not
want to set up API access).

### Shopify

1. Shopify admin → Settings → Apps and sales channels → Develop apps → Create an app.
2. Admin API scopes: `read_products`, `read_inventory`, `read_orders`
   (plus `read_all_orders` for orders older than 60 days, which Shopify grants on request).
3. Install the app and copy the Admin API access token (`shpat_...`).

```bash
export SHOPIFY_SHOP=my-store.myshopify.com
export SHOPIFY_ACCESS_TOKEN=shpat_xxx
export SHOPIFY_API_VERSION=2024-10   # optional
margingraph sync shopify --out data/store
```

- Items are **variants** (one per sellable SKU). Title = product title plus the variant title.
- Unit cost = the variant's "Cost per item" (`InventoryItem.cost`), fetched in batches of 100.
- Stock = `inventory_quantity` summed across locations; negative (oversold) is clipped to 0.
- Line price = unit price minus the line's discount allocations.
- Cancelled orders and refunded / voided payments are dropped.
- Pagination follows the `Link: rel="next"` header; 429 responses are retried using `Retry-After`.

### WooCommerce

1. WooCommerce → Settings → Advanced → REST API → Add key, permission **Read**.
2. Copy the consumer key and secret.

```bash
export WC_STORE_URL=https://shop.example.com
export WC_CONSUMER_KEY=ck_xxx
export WC_CONSUMER_SECRET=cs_xxx
export WC_QUERY_AUTH=1            # only if your host strips the Authorization header
export WC_COST_META_KEY=_my_cost  # only if your cost plugin uses another meta key
margingraph sync woocommerce --out data/store
```

- Items are simple products and the **variations** of variable products.
- WooCommerce has no built-in cost. The connector reads it from product meta
  written by common cost-of-goods plugins (`_wc_cog_cost`, `_alg_wc_cog_cost`,
  `_purchase_price`, `_cost_price`, `cost_price`); a variation without its own
  cost inherits the parent's.
- Line price = line `total` / quantity (after coupons, before tax).
- Orders with status cancelled, refunded, failed, pending, trash or checkout-draft are dropped.
- Pagination uses `X-WP-TotalPages`. Incremental sync needs WooCommerce 5.8+ (`modified_after`); on older
  versions run with `--full`.

## Incremental sync

The output folder keeps `sync_state.json` with the newest order `updated_at`
seen. The next `sync shopify` / `sync woocommerce` asks only for orders
updated since then and upserts them by order id, so an order that was later
cancelled or edited is replaced, not duplicated. Products are refetched in
full each time because stock changes do not reliably bump a product's
timestamp. `--full` ignores the watermark. Switching source in the same
folder also forces a full sync. A nightly cron is enough:

```cron
0 3 * * * cd /path/to/margingraph && set -a && . ./.env && margingraph sync shopify --out data/store && margingraph --config data/store/config.yaml run --results results_store --artifacts artifacts_store
```

## The common schema

| Table | Columns |
| --- | --- |
| products | `product_id`, `title`, `category`, `price`, `cost`, `stock`, `updated_at` |
| orders | `order_id`, `ordered_at` (UTC), `customer_id`, `country`, `status` (`ok`/`cancelled`), `updated_at` |
| order_lines | `order_id`, `product_id`, `title`, `quantity`, `unit_price` |

Code: `src/margingraph/connectors/schema.py`. Every adapter produces these
three tables; to add a new platform, write a class with `name` and
`fetch(products_since, orders_since) -> StoreData`, and `sync()` does the rest.

## Output folder

```
data/store/
  raw/{products,orders,order_lines}.parquet   merged store data, common schema
  sync_state.json                             watermark for incremental runs
  pipeline/lines.parquet                      what `run` trains on
  pipeline/catalog.parquet
  pipeline/erp.parquet                        store cost and stock (NaN = unknown)
  pipeline/clean_log.json                     cleaning counts + validation report
  config.yaml                                 configs/default.yaml pointed at the above
```

`config.yaml` sets the train / val / test cut dates at the 70% and 85% time
quantiles of the store's orders, so the newest 15% is the test set. Edit them
if you want other cuts.

## Validation

Errors stop the sync (no order lines, a required column all missing or
unparseable). Warnings are printed and saved in `clean_log.json`:
unparseable rows, returns and zero-price lines, duplicate ids, order lines
for unknown orders, cost above price, fewer than `--min-orders` (default 200)
orders with 2+ products, and the share of products with a known cost.

## Missing cost or stock

The recommender's margin floor and profit objective need unit cost. When the
store has no cost for an item:

- cost = price × `erp.cost_ratio` (default **0.6**, i.e. an assumed 40% margin);
- the item is flagged `cost_source = assumed` in `results/erp_store.csv`, in
  every `/recommend` card, and the share is reported in `summary.json["erp"]`.

When the store does not track stock for an item, stock = weekly demand ×
`erp.weeks_of_cover` (as in the simulation) and it is flagged
`stock_source = simulated`. With real stock, an item is overstock when its
stock covers more than `erp.overstock_weeks` (default 12) weeks of demand.

With store data, Stage 2 results go to `e8_strategies_store_erp.csv`, and
E11 (the sweep over simulated margins) is skipped because the margins are
the store's own.

## Limits

- Shopify's REST Admin API is the long-supported path for custom apps; Shopify is moving new public apps to GraphQL.
  The adapter is one file if it needs porting.
- Very large stores: the first full sync holds all orders in memory once (roughly 1 GB per few million lines).
- The recommender needs history: a few hundred orders with 2+ products at minimum, more is better.
