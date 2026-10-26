"""scripts/public_datasets.py on tiny files shaped like each public dataset."""
import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_datasets", ROOT / "scripts" / "public_datasets.py")
pdx = importlib.util.module_from_spec(spec)
sys.modules["public_datasets"] = pdx
spec.loader.exec_module(pdx)

BASKETS = [(k, k % 7, [k % 10, 10 + k % 10, 20 + k % 3]) for k in range(60)]  # (order, customer, items)


def write_raw(name: str, d: Path) -> None:
    d.mkdir(parents=True)
    if name == "instacart":
        pd.DataFrame([dict(order_id=k, user_id=c, eval_set="prior", order_number=k // 7 + 1, order_hour_of_day=10,
                           days_since_prior_order=None if k < 7 else 3.0) for k, c, _ in BASKETS]).to_csv(d / "orders.csv", index=False)
        lines = pd.DataFrame([dict(order_id=k, product_id=i) for k, _, b in BASKETS for i in b])
        lines.iloc[:100].to_csv(d / "order_products__prior.csv", index=False)
        lines.iloc[100:].to_csv(d / "order_products__train.csv", index=False)
        pd.DataFrame(dict(product_id=range(30), product_name=[f"P{i}" for i in range(30)], department_id=1)).to_csv(d / "products.csv", index=False)
    elif name == "dunnhumby":
        pd.DataFrame([dict(household_key=c, BASKET_ID=k, DAY=1 + k, PRODUCT_ID=i, QUANTITY=2, SALES_VALUE=3.0, TRANS_TIME=1230)
                      for k, c, b in BASKETS for i in b]).to_csv(d / "transaction_data.csv", index=False)
        pd.DataFrame(dict(PRODUCT_ID=range(30), DEPARTMENT="GROCERY", COMMODITY_DESC="C", SUB_COMMODITY_DESC="S")).to_csv(d / "product.csv", index=False)
    elif name == "olist":
        pd.DataFrame([dict(order_id=f"o{k}", customer_id=f"c{k}", order_status="delivered",
                           order_purchase_timestamp=f"2017-01-{1 + k % 28:02d} 10:00:00") for k, _, _ in BASKETS]).to_csv(d / "olist_orders_dataset.csv", index=False)
        pd.DataFrame([dict(order_id=f"o{k}", order_item_id=j + 1, product_id=f"p{i:04d}xx", price=10.0)
                      for k, _, b in BASKETS for j, i in enumerate(b)]).to_csv(d / "olist_order_items_dataset.csv", index=False)
        pd.DataFrame([dict(customer_id=f"c{k}", customer_unique_id=f"u{c}", customer_state="SP") for k, c, _ in BASKETS]).to_csv(d / "olist_customers_dataset.csv", index=False)
        pd.DataFrame(dict(product_id=[f"p{i:04d}xx" for i in range(30)], product_category_name="beleza")).to_csv(d / "olist_products_dataset.csv", index=False)
    else:
        pd.DataFrame([dict(TRANSACTION_DT=f"11/{1 + k % 28}/2000", CUSTOMER_ID=f"{c:05d}", PRODUCT_SUBCLASS=1, PRODUCT_ID=f"47{i:05d}",
                           AMOUNT=2, ASSET=1.2, SALES_PRICE=4.0) for k, c, b in BASKETS for i in b]).to_csv(d / "ta_feng_all_months_merged.csv", index=False)


@pytest.mark.parametrize("name", sorted(pdx.CONVERTERS))
def test_convert_writes_connector_schema(tmp_path, name):
    write_raw(name, tmp_path / "raw")
    pdx.cmd_convert(Namespace(name=name, src=str(tmp_path / "raw"), out=str(tmp_path / "out"), max_customers=None,
                              top_items=25, seed=0, asset_as_cost=name == "tafeng"))
    orders = pd.read_csv(tmp_path / "out" / "orders.csv", dtype=str)
    products = pd.read_csv(tmp_path / "out" / "products.csv", dtype={"product_id": str})
    assert list(orders.columns) == pdx.ORDER_COLS
    assert orders["product_id"].nunique() <= 25
    assert set(orders["product_id"]) <= set(products["product_id"])
    assert (orders["unit_price"].astype(float) > 0).all()
    assert pd.to_datetime(orders["ordered_at"]).notna().all()
    assert orders.groupby("order_id")["product_id"].nunique().max() >= 2
    assert ("cost" in products) == (name == "tafeng")
