"""Request, response and per-store settings models (the public API contract)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Variant(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    weight: float = Field(1.0, gt=0)
    # any StoreSettings policy field can be overridden per variant
    overrides: dict = Field(default_factory=dict)


class Experiment(BaseModel):
    enabled: bool = False
    name: str = "exp1"
    variants: list[Variant] = Field(
        default_factory=lambda: [
            Variant(name="control", overrides={"lam": 0.0}),
            Variant(name="treatment", overrides={"lam": 0.5}),
        ]
    )


POLICY_FIELDS = ("excluded_items", "margin_floor", "max_addons", "lam", "overstock_weight", "discounts", "floor_mode", "candidates", "solver")


class StoreSettings(BaseModel):
    """Business rules for one store. Defaults follow configs/default.yaml."""

    margin_floor: float = Field(0.15, ge=0.0, le=0.95, description="hard minimum gross margin per add-on")
    max_addons: int = Field(2, ge=1, le=5)
    lam: float = Field(0.5, ge=0.0, le=1.0, description="0 = pure relevance, 1 = expected profit")
    overstock_weight: float = Field(1.5, ge=1.0, le=3.0, description="profit multiplier for overstock items")
    floor_mode: Literal["item", "bundle"] = "item"
    discounts: list[float] = Field(default_factory=lambda: [0.0])
    discount_elasticity: float = Field(1.5, ge=0.0, le=10.0, description="ASSUMED p uplift per unit discount")
    candidates: int = Field(20, ge=2, le=100, description="top-N reranked items passed to the optimizer")
    solver: Literal["auto", "milp", "exact"] = "auto"
    latency_budget_ms: int = Field(300, ge=20, le=5000, description="model path deadline before the fallback answers")
    fallback_days: int = Field(90, ge=1, le=3650)
    attribution_hours: int = Field(24, ge=1, le=24 * 30)
    rate_limit_per_minute: int = Field(1200, ge=0, description="0 disables the limit")
    auto_overstock_weeks: float | None = Field(
        12.0, ge=1.0, description="nightly job flags items with more than this many weeks of stock; null = manual flags only"
    )
    min_train_orders: int = Field(500, ge=10)
    excluded_items: list[str] = Field(default_factory=list, description="never recommend these items")
    experiment: Experiment = Field(default_factory=Experiment)

    @field_validator("discounts")
    @classmethod
    def _disc(cls, v: list[float]) -> list[float]:
        v = sorted(set(float(x) for x in v) | {0.0})
        if any(x < 0 or x >= 0.9 for x in v):
            raise ValueError("discounts must be in [0, 0.9)")
        return v

    def for_variant(self, variant: str) -> "StoreSettings":
        if not self.experiment.enabled:
            return self
        for v in self.experiment.variants:
            if v.name == variant:
                bad = set(v.overrides) - set(POLICY_FIELDS)
                if bad:
                    raise ValueError(f"variant {v.name} overrides unknown fields {sorted(bad)}")
                return StoreSettings(**{**self.model_dump(), **v.overrides})
        return self


class StoreCreate(BaseModel):
    store_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]{1,62}$")
    name: str = ""
    settings: StoreSettings = Field(default_factory=StoreSettings)


class StoreCreated(BaseModel):
    store_id: str
    api_key: str = Field(..., description="shown once; store it in your shop backend")
    webhook_secret: str = Field(..., description="HMAC-SHA256 secret for X-MarginGraph-Signature on /v1/orders")


class BasketLine(BaseModel):
    item: str
    quantity: float = 1.0


class RecommendRequest(BaseModel):
    basket: list[str | BasketLine] = Field(..., min_length=1, max_length=200, examples=[["85123A", "71053"]])
    customer_id: str = Field("", max_length=128)
    session_id: str = Field("", max_length=128)
    max_addons: int | None = Field(None, ge=1, le=5, description="optional cap below the store setting")
    exclude: list[str] = Field(default_factory=list, description="items never to suggest in this call")

    def items(self) -> list[str]:
        out = []
        for b in self.basket:
            s = (b if isinstance(b, str) else b.item).strip().upper()
            if s and s not in out:
                out.append(s)
        return out


class Addon(BaseModel):
    item: str
    description: str
    price: float
    discount: float
    margin_pct: float
    p_accept: float | None
    expected_profit: float | None
    overstock: bool
    stock: int
    reason: str


class RecommendResponse(BaseModel):
    request_id: str
    store_id: str
    variant: str
    source: Literal["model", "fallback", "cache"]
    model_version: str
    addons: list[Addon]
    basket_known: list[str]
    basket_unknown: list[str]
    latency_ms: float
    fallback_reason: str = ""


class Product(BaseModel):
    item: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    category: str | None = None
    price: float | None = Field(None, gt=0)
    unit_cost: float | None = Field(None, ge=0)
    stock: int | None = Field(None, ge=0)
    overstock: bool | None = None
    active: bool | None = None


class CatalogUpsert(BaseModel):
    products: list[Product] = Field(..., min_length=1, max_length=50_000)


class StockChange(BaseModel):
    item: str
    stock: int | None = Field(None, ge=0, description="absolute level")
    delta: int | None = Field(None, description="relative change, e.g. -2")

    @model_validator(mode="after")
    def _one(self):
        if (self.stock is None) == (self.delta is None):
            raise ValueError("give exactly one of stock or delta")
        return self


class InventoryUpdate(BaseModel):
    changes: list[StockChange] = Field(..., min_length=1, max_length=50_000)


class OrderLine(BaseModel):
    item: str
    quantity: float = Field(1.0, gt=0)
    price: float = Field(..., ge=0, description="unit price actually paid")


class Order(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=128)
    customer_id: str = ""
    session_id: str = ""
    recommendation_id: str = Field("", description="request_id of the /v1/recommend call shown at checkout, if known")
    ts: datetime | None = None
    lines: list[OrderLine] = Field(..., min_length=1)
    decrement_stock: bool = True


class FeedbackEvent(BaseModel):
    request_id: str
    item: str
    event_type: Literal["click", "add_to_cart"]
