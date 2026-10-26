# Store connectors

Pull a store's products and orders into a folder that `margingraph run` can train on.

```bash
margingraph sync csv --orders orders.xlsx --preset online_retail_ii --out data/store
margingraph sync shopify --out data/store        # needs SHOPIFY_SHOP, SHOPIFY_ACCESS_TOKEN
margingraph sync woocommerce --out data/store    # needs WC_STORE_URL, WC_CONSUMER_KEY, WC_CONSUMER_SECRET
margingraph --config data/store/config.yaml run
```

| File | Role |
| --- | --- |
| `schema.py` | Common store schema, validation, conversion to pipeline input |
| `csv_source.py` | CSV / TSV / Excel with YAML column mappings and presets |
| `shopify.py`, `woocommerce.py` | REST API clients |
| `http.py` | Small JSON-over-HTTPS client (standard library), honours `Retry-After` |
| `sync.py` | Writes the store folder and its config; orders sync incrementally from a saved watermark |

Missing cost is filled as price × 0.6 and flagged `cost_source=assumed`. Full guide: [`docs/CONNECTORS.md`](../../../docs/CONNECTORS.md). Tests: `tests/test_connectors.py`.
