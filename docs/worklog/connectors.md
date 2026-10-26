# Work log: store data connectors (2026-10-26)

Record of what was built, why, the commands run, the test results and what
went wrong along the way. Branch `claude/project-thread-dxygit`, based on
`claude/project-thread-mkbaip` (PR #2).

## Goal

Let a real retail store use MarginGraph on its own data, not only on UCI
Online Retail II: pull products (price, cost, stock, category), orders and
order lines from a file export, Shopify or WooCommerce, then train and serve
with the existing pipeline unchanged. Constraints from San: free tools only,
light enough for a laptop with 8 GB RAM.

## What was built

| File | What it does |
| --- | --- |
| `src/margingraph/connectors/schema.py` | Common schema (products / orders / order_lines), dtype normalisation, validation report, conversion to the pipeline's `lines` / `catalog` / store ERP |
| `src/margingraph/connectors/http.py` | Standard-library HTTPS client: retries 429/5xx using `Retry-After`, `Link` header parsing, secrets redacted from errors, injectable transport for tests |
| `src/margingraph/connectors/csv_source.py` | CSV / TSV / Excel reader with YAML or `--map` column mapping, currency/thousands parsing, cancelled-status and credit-note handling, presets `online_retail_ii` and `shopify_orders_export` |
| `src/margingraph/connectors/shopify.py` | Shopify Admin REST: variants as items, `InventoryItem.cost` as unit cost, `Link` pagination, `updated_at_min` incremental, discount allocations netted out |
| `src/margingraph/connectors/woocommerce.py` | WooCommerce wc/v3: variations as items, cost from COG-plugin meta keys (variation inherits parent), `X-WP-TotalPages` pagination, `modified_after` incremental, header or query-string auth |
| `src/margingraph/connectors/sync.py` | Merges into an output folder, upserts orders by id, keeps the watermark, validates, writes pipeline input and a fitted `config.yaml` |
| `src/margingraph/data.py` `store_erp` | Real cost and stock into Stage 2; missing cost = price × `erp.cost_ratio` (0.6) flagged `assumed`; missing stock simulated and flagged |
| `src/margingraph/pipeline.py` | Uses `data.erp_path` when present, reports cost/stock coverage in `summary.json`, writes `e8_strategies_store_erp.csv`, skips E11 (simulated-margin sweep) for store data |
| `src/margingraph/api.py` | `/recommend` cards carry `cost_source` / `stock_source`; the note states the coverage instead of "simulated" |
| `src/margingraph/cli.py` | `margingraph sync {csv,shopify,woocommerce}` |
| `tests/test_connectors.py` | 10 tests, all HTTP mocked |
| `docs/CONNECTORS.md` | Setup for each source, mapping format, schema, incremental sync, fallbacks |

## Decisions and why

- **Standard-library HTTP, no SDKs.** `shopify_python_api` and `woocommerce`
  packages add dependencies for a handful of GET calls. urllib keeps install
  small and the transport is swappable, so tests mock HTTP without a network
  or extra test libraries.
- **Variants are the item.** A T-shirt in S and M has different stock and
  can have a different cost; the MILP's stock and margin constraints need
  the sellable unit.
- **Orders incremental, products full.** Orders are the large table. Stock
  changes do not reliably bump a Shopify or WooCommerce product's
  `updated_at`, so an incremental product sync would leave stale stock.
- **Upsert by order id, replace that order's lines.** An order edited or
  cancelled after the last sync is replaced, never duplicated.
- **Cost fallback is explicit.** No store cost → `price × 0.6`, flagged per
  item, coverage reported in the sync output, `summary.json` and every API
  card. Stage 2 profit numbers are only as good as this coverage, and the
  output says so.
- **Split dates fitted per store** at the 70% / 85% time quantiles, since the
  default config's 2011 dates mean nothing for another store.
- **E11 skipped for store data.** It varies simulated margins, which a store
  with real costs does not have.

## Commands run

```bash
git checkout -B claude/project-thread-dxygit origin/claude/project-thread-mkbaip
pip install -e ".[dev]"
python -m pytest -q                       # before changes: 6 passed, 1 skipped
python -m pytest -q tests/test_connectors.py
python -m pytest -q                       # after: 16 passed, 1 skipped
# real-data parity check (script below), run twice
python uci_check.py <out_dir>
```

The parity script loads `/mnt/project-files/online_retail_II.xlsx` through
the CSV adapter with `--preset online_retail_ii`, syncs it, then compares the
resulting `lines.parquet` row by row with the original `data.clean` output.

## Test results

Unit and integration tests (`pytest -q`, CPU, ~15 s): **16 passed, 1 skipped**
(the skip is the existing GPU-only LLM test).

Connector tests cover: 429 retry with `Retry-After`; 401 error with the
secret redacted; `Link` parsing; CSV mapping errors that list the file's
columns; `$1,200.00` parsing; credit-note prefixes; a blocking validation
error; Shopify two-page product pagination, inventory-item cost batching,
discount netting, timezone conversion to UTC, full then incremental sync
with a later-cancelled order and a new order, oversold stock clipped to 0;
WooCommerce page-count pagination, variable products, parent-cost
inheritance, refunded orders dropped, Basic auth and query-string auth,
incremental `modified_after`; missing env vars; and an end-to-end CLI
`sync csv` → `run` → `/recommend` on synthetic data with cost for half the
items (checks the assumed costs equal `price × 0.6`, store-ERP output files,
E11 skipped, API flags).

Real data, Online Retail II through the CSV adapter (about 80 s; memory was
not measured):

| | Original `data.clean` | CSV adapter |
| --- | --- | --- |
| clean lines | 991,910 | 991,910 |
| invoices | 39,516 | 39,516 |
| items | 4,707 | 4,707 |
| customers | 5,852 | 5,852 |
| (invoice, item) rows matched | | 991,910 both, 0 only-one-side |
| quantity and revenue equal | | 100% |
| customer equal | | 100% |
| timestamp equal | | 99.67% |

The 0.33% timestamp difference is by design: the adapter stamps every line
with the order's first timestamp, the original with each item's first scan
within the invoice. The split assigns whole invoices by their first
timestamp in both, so train/val/test membership is the same.

The generated config put the cuts at val 2011-05-26 and test 2011-09-26
(original hand-set: 2011-07-01 and 2011-10-01).

Not run here: a live Shopify or WooCommerce store (no store or credentials
in this environment; the container also cannot reach external shops). The
API adapters are tested against mocked responses shaped like the documented
REST payloads. The first real sync is the remaining check.

## Failures and fixes along the way

1. **First parity run: quantity matched on only 96.8% of rows.** The original
   cleaner drops 33,663 exact duplicate rows; the adapter did not. Added a
   `drop_duplicate_rows` mapping option (default off, since a POS can emit
   two identical lines legitimately) and turned it on in the
   `online_retail_ii` preset. Second run: 100%.
2. **"174 duplicate product ids" warning on UCI.** Products derived from
   order lines were grouped before ids were upper-cased, so `85123a` and
   `85123A` were two rows. Ids are now normalised first.
3. A test assertion about an unsold Shopify variant was written as a
   conditional that always passed; rewritten to assert the real expectation
   (variant 12 absent after sync 1, present with stock 0 and no cost after
   sync 2).

## Next steps

- First live sync against San's or a test store (Shopify development stores
  and a local WooCommerce via Docker are free).
- Shopify GraphQL adapter if the REST Admin API is retired for custom apps.
- Optional: a `margingraph sync --watch` loop or cron recipe (documented in
  CONNECTORS.md).
