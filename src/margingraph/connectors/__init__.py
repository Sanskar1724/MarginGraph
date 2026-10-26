"""Store data connectors: CSV/Excel upload, Shopify, WooCommerce."""
from .csv_source import PRESETS, load_csv_store, load_mapping
from .schema import StoreData, normalise, to_pipeline, validate
from .shopify import ShopifySource
from .sync import SyncError, sync
from .woocommerce import WooCommerceSource

__all__ = [
    "PRESETS", "load_csv_store", "load_mapping", "StoreData", "normalise", "to_pipeline", "validate",
    "ShopifySource", "WooCommerceSource", "SyncError", "sync",
]
