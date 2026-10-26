<div align="center">

# MarginGraph · Store connectors

**Pull a real store's products and orders (CSV/Excel, Shopify, WooCommerce) into a folder the pipeline trains on.**

![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-green) ![Shopify](https://img.shields.io/badge/Shopify-REST-7AB55C?logo=shopify&logoColor=white) ![WooCommerce](https://img.shields.io/badge/WooCommerce-REST-96588A?logo=woocommerce&logoColor=white) ![CSV / Excel](https://img.shields.io/badge/CSV%20%2F%20Excel-presets-lightgrey)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Store connectors** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

`margingraph sync` maps any store into one schema, validates it, and writes the files `margingraph run` expects. Orders sync incrementally. Missing cost is filled as price × 0.6 and flagged `cost_source=assumed`. Verified: UCI data through the CSV adapter matches the core cleaner exactly (991,910 lines).

## What's in this branch

| Path | What it is |
| --- | --- |
| `src/margingraph/connectors/` | schema, csv_source, shopify, woocommerce, http, sync |
| `tests/test_connectors.py` | Adapter, mapping, validation and CLI tests |
| `docs/CONNECTORS.md` | Full guide: credentials, mappings, presets |
| `docs/worklog/connectors.md` | Work log |

## Run it

```bash
margingraph sync csv --orders orders.xlsx --preset online_retail_ii --out data/store
margingraph sync shopify --out data/store       # SHOPIFY_SHOP, SHOPIFY_ACCESS_TOKEN
margingraph --config data/store/config.yaml run
```

Needs the core package from `main`.

## License

[MIT](LICENSE)
