"""FastAPI demo: POST a basket, get up to 2 margin-safe add-ons.

Online path = candidate pool -> LightGBM -> calibrated p -> PuLP MILP.
Cost and stock come from the ERP saved with the bundle: the connected store's
own data when it was synced with `margingraph sync`, simulated otherwise.
"""
from __future__ import annotations

import os
import pickle
import time
from functools import lru_cache

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .optimize import Policy, solve_milp


class Request(BaseModel):
    basket: list[str] = Field(..., examples=[["85123A", "71053"]])
    customer_id: str = ""
    overstock_weight: float = 1.0
    lam: float = 1.0
    allow_discounts: bool = False


@lru_cache(maxsize=1)
def bundle() -> dict:
    path = os.path.join(os.environ.get("MARGINGRAPH_ARTIFACTS", "artifacts"), "bundle.pkl")
    with open(path, "rb") as fh:
        return pickle.load(fh)


app = FastAPI(title="MarginGraph", version="0.1.0")


def _note(erp) -> str:
    if "cost_source" not in erp:
        return "cost and stock are simulated; Online Retail II has neither"
    c = float((erp["cost_source"] == "store").mean())
    s = float((erp["stock_source"] == "store").mean())
    return f"store data: unit cost known for {c:.0%} of items (rest assumed), stock for {s:.0%} (rest simulated)"


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/recommend")
def recommend(req: Request) -> dict:
    t0 = time.perf_counter()
    b = bundle()
    gen, rr, erp, cfg = b["generator"], b["reranker"], b["erp"], b["cfg"]
    basket = [s.strip().upper() for s in req.basket]
    known = [s for s in basket if s in gen.index.pos]
    if not known:
        raise HTTPException(422, "none of the basket items are in the catalog")

    feats, _ = gen.generate([known], [req.customer_id])
    score = rr.score(feats)
    p = rr.proba(feats)
    oc = cfg["optimize"]
    top = np.argsort(-score)[: oc["candidates"]]
    items = feats["item_idx"].to_numpy()[top]
    pol = Policy(
        lam=req.lam,
        overstock_weight=req.overstock_weight,
        floor=oc["margin_floor"],
        max_addons=oc["max_addons"],
        discounts=tuple(oc["discounts"]) if req.allow_discounts else (0.0,),
        elasticity=oc["discount_elasticity"],
    )
    price, cost = erp["price"].to_numpy(), erp["unit_cost"].to_numpy()
    over, stock = erp["overstock"].to_numpy(), erp["stock"].to_numpy()
    cost_src = erp["cost_source"].to_numpy() if "cost_source" in erp else None
    stock_src = erp["stock_source"].to_numpy() if "stock_source" in erp else None
    chosen = solve_milp(p[top], price[items], cost[items], over[items], stock[items], pol, b["p_bar"])

    def card(i: int, pa: float, d: float = 0.0) -> dict:
        rev = price[i] * (1 - d)
        return {
            "item": gen.index.items[i],
            "description": gen.description[i],
            "p_accept": round(float(pa), 4),
            "price": round(float(rev), 2),
            "discount": d,
            "margin_pct": round(float((rev - cost[i]) / rev), 3),
            "overstock": bool(over[i]),
            "stock": int(stock[i]),
            **({"cost_source": cost_src[i], "stock_source": stock_src[i]} if cost_src is not None else {}),
        }

    return {
        "basket_known": known,
        "basket_unknown": [s for s in basket if s not in gen.index.pos],
        "addons": [card(items[j], p[top][j], d) for j, d in chosen],
        "ranked_candidates": [card(items[j], p[top][j]) for j in range(min(10, len(top)))],
        "latency_ms": round(1000 * (time.perf_counter() - t0), 1),
        "note": _note(erp),
    }
