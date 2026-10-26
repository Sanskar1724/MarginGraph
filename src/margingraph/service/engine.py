"""The live recommendation path for one request.

    basket -> candidate pool (EASE, ItemKNN, co-purchase, ALS, repeat, popularity)
           -> LightGBM score -> isotonic p(accept)
           -> keep sellable items (active, known cost, in stock)
           -> Stage 2 optimizer under the store's margin floor
           -> add-on cards with a short reason

Cost, stock and overstock flags always come from the store's live catalog in
the database, never from the training bundle, so a stock webhook takes effect
on the next request.
"""
from __future__ import annotations

import hashlib
import logging
import pickle
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from ..optimize import Policy, check_constraints, solve_enum, solve_milp
from . import db
from .schemas import StoreSettings

log = logging.getLogger("margingraph.engine")


# ---- model bundles -------------------------------------------------------
@dataclass
class Bundle:
    version: str
    generator: object
    reranker: object
    meta: dict


def load_bundle(path: str | Path, version: str) -> Bundle:
    with open(path, "rb") as fh:
        b = pickle.load(fh)
    # research bundles from `margingraph run` have no meta; both carry generator + reranker
    return Bundle(version=version, generator=b["generator"], reranker=b["reranker"], meta=b.get("meta", {}))


class ModelRegistry:
    """LRU of loaded bundles so a multi-store instance stays within RAM."""

    def __init__(self, max_loaded: int = 4):
        self.max_loaded = max_loaded
        self._models: OrderedDict[tuple[str, str], Bundle] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, store_id: str, version: str, path: str) -> Bundle:
        key = (store_id, version)
        with self._lock:
            if key in self._models:
                self._models.move_to_end(key)
                return self._models[key]
        b = load_bundle(path, version)  # outside the lock: loading can take a second
        with self._lock:
            self._models[key] = b
            # drop older versions of this store and the least recently used stores
            for k in [k for k in self._models if k[0] == store_id and k != key]:
                del self._models[k]
            while len(self._models) > self.max_loaded:
                self._models.popitem(last=False)
        log.info("loaded model %s for store %s", version, store_id)
        return b

    def loaded(self) -> list[tuple[str, str]]:
        with self._lock:
            return list(self._models)


# ---- live catalog snapshot -------------------------------------------------
@dataclass
class Snapshot:
    """Catalog arrays aligned to the model's item index (or to the catalog alone)."""

    items: list[str]
    pos: dict[str, int]
    description: np.ndarray
    price: np.ndarray
    cost: np.ndarray  # NaN where unknown
    stock: np.ndarray
    overstock: np.ndarray
    active: np.ndarray
    sellable: np.ndarray  # active, priced, cost known, in stock
    p_bar: float
    catalog_only: bool
    as_of: datetime | None = None

    def finish(self) -> "Snapshot":
        self.sellable = self.active & (self.price > 0) & np.isfinite(self.cost) & (self.stock > 0)
        prof = (self.price - np.nan_to_num(self.cost))[self.sellable]
        self.p_bar = float(prof.clip(min=0).mean()) if len(prof) else 1.0
        return self


def build_snapshot(products: pd.DataFrame, items: list[str] | None) -> Snapshot:
    p = products.set_index("item")
    catalog_only = items is None
    items = list(p.index) if catalog_only else list(items)
    a = p.reindex(items)
    return Snapshot(
        items=items,
        pos={it: i for i, it in enumerate(items)},
        description=a["description"].fillna("").to_numpy(object),
        price=np.nan_to_num(a["price"].to_numpy(float)),
        cost=a["unit_cost"].to_numpy(float),
        stock=a["stock"].fillna(0).to_numpy(int),
        overstock=a["overstock"].fillna(False).astype(bool).to_numpy(),
        active=a["active"].fillna(False).astype(bool).to_numpy(),
        sellable=np.zeros(len(items), bool),
        p_bar=1.0,
        catalog_only=catalog_only,
    ).finish()


def apply_changes(snap: Snapshot, changed: pd.DataFrame) -> Snapshot | None:
    """Copy of ``snap`` with changed product rows applied; None if a full rebuild is needed.

    A stock webhook touches a handful of rows, so this replaces reloading the
    whole catalog on every order.
    """
    if snap.catalog_only and len(changed) and not changed["item"].isin(snap.pos).all():
        return None  # a new product: rebuild
    changed = changed[changed["item"].isin(snap.pos)]
    new = Snapshot(**{k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in snap.__dict__.items()})
    if len(changed):
        idx = changed["item"].map(snap.pos).to_numpy()
        new.description[idx] = changed["description"].fillna("").to_numpy(object)
        new.price[idx] = np.nan_to_num(changed["price"].to_numpy(float))
        new.cost[idx] = changed["unit_cost"].to_numpy(float)
        new.stock[idx] = changed["stock"].fillna(0).to_numpy(int)
        new.overstock[idx] = changed["overstock"].fillna(False).astype(bool).to_numpy()
        new.active[idx] = changed["active"].fillna(False).astype(bool).to_numpy()
    return new.finish()


# ---- policy ----------------------------------------------------------------
def policy_from(s: StoreSettings, max_addons: int | None = None) -> Policy:
    return Policy(
        lam=s.lam,
        overstock_weight=s.overstock_weight,
        floor=s.margin_floor,
        floor_mode=s.floor_mode,
        discounts=tuple(s.discounts),
        elasticity=s.discount_elasticity,
        max_addons=min(s.max_addons, max_addons or s.max_addons),
    )


def solve(p, price, cost, over, stock, pol: Policy, p_bar: float, solver: str) -> list[tuple[int, float]]:
    # Exact enumeration is proven equal to the PuLP MILP for <= 2 add-ons (E9 and
    # tests) and is ~10x faster; PuLP handles larger bundles.
    if solver == "exact" or (solver == "auto" and pol.max_addons <= 2):
        return solve_enum(p, price, cost, over, stock, pol, p_bar)
    return solve_milp(p, price, cost, over, stock, pol, p_bar)


def assign_variant(s: StoreSettings, store_id: str, unit: str) -> str:
    """Deterministic, sticky A/B bucket from a hash of the customer or session id."""
    if not s.experiment.enabled or not s.experiment.variants:
        return "default"
    h = hashlib.sha256(f"{store_id}:{s.experiment.name}:{unit}".encode()).digest()
    u = int.from_bytes(h[:8], "big") / 2**64
    total = sum(v.weight for v in s.experiment.variants)
    acc = 0.0
    for v in s.experiment.variants:
        acc += v.weight / total
        if u < acc:
            return v.name
    return s.experiment.variants[-1].name


def _card(snap: Snapshot, i: int, d: float, pa: float | None, reason: str) -> dict:
    rev = float(snap.price[i] * (1 - d))
    profit = rev - float(snap.cost[i])
    return {
        "item": snap.items[i],
        "description": str(snap.description[i]),
        "price": round(rev, 2),
        "discount": float(d),
        "margin_pct": round(profit / rev, 4) if rev > 0 else 0.0,
        "p_accept": None if pa is None else round(float(pa), 4),
        "expected_profit": None if pa is None else round(float(pa) * profit, 4),
        "overstock": bool(snap.overstock[i]),
        "stock": int(snap.stock[i]),
        "reason": reason,
    }


def model_recommend(
    bundle: Bundle,
    snap: Snapshot,
    basket: list[str],
    customer_id: str,
    s: StoreSettings,
    max_addons: int | None,
    exclude: set[str],
) -> tuple[list[dict], list[str]]:
    """Return (add-on cards, basket items the model knows)."""
    gen, rr = bundle.generator, bundle.reranker
    known = [b for b in basket if b in gen.index.pos]
    if not known:
        return [], known
    feats, _ = gen.generate([known], [customer_id])
    score = rr.score(feats)
    p = rr.calibrator.predict(score)  # same as rr.proba(feats) without a second LightGBM pass
    items = feats["item_idx"].to_numpy()
    # model index -> snapshot index (snapshot is aligned to gen.index.items)
    ok = snap.sellable[items] & ~np.isin(np.asarray(snap.items, dtype=object)[items], list(exclude | set(basket)))
    if not ok.any():
        return [], known
    cand = np.flatnonzero(ok)
    top = cand[np.argsort(-score[cand], kind="stable")[: s.candidates]]
    it = items[top]
    pol = policy_from(s, max_addons)
    chosen = solve(p[top], snap.price[it], snap.cost[it], snap.overstock[it], snap.stock[it], pol, snap.p_bar, s.solver)
    # defence in depth: the optimizer already enforces these, a violation here is a bug
    viol = check_constraints([(int(it[j]), d) for j, d in chosen], snap.price, snap.cost, pol)
    if viol:
        raise RuntimeError(f"optimizer returned {viol} rule violations")
    C = gen.scorers["copurchase"].C
    kn = gen.index.encode(known)
    cards = []
    for j, d in sorted(chosen, key=lambda x: -p[top][x[0]]):
        i = int(it[j])
        co = C[kn, i]
        if co.max() > 0:
            src = known[int(np.argmax(co))]
            reason = f"Often bought with {str(snap.description[gen.index.pos[src]]).title() or src}"
        else:
            reason = "Popular with baskets like this one"
        cards.append(_card(snap, i, d, p[top][j], reason))
    return cards, known


def fallback_recommend(
    sellers: list[tuple[str, int]],
    snap: Snapshot,
    basket: list[str],
    s: StoreSettings,
    max_addons: int | None,
    exclude: set[str],
) -> list[dict]:
    """Best sellers that are in stock and clear the margin floor (no model needed)."""
    k = min(s.max_addons, max_addons or s.max_addons)
    skip = set(basket) | exclude
    count = {snap.pos[it]: n for it, n in sellers if it in snap.pos}
    # a store with no order history yet still gets suggestions: every sellable
    # item competes, best sellers first, then by unit profit
    floor_ok = snap.price - np.nan_to_num(snap.cost) >= s.margin_floor * snap.price - 1e-9
    ok = np.flatnonzero(snap.sellable & floor_ok)
    w = np.where(snap.overstock, s.overstock_weight, 1.0)
    profit = snap.price - np.nan_to_num(snap.cost)
    scored = sorted(
        ((count.get(i, 0) * w[i], profit[i] * w[i], i) for i in ok if snap.items[i] not in skip),
        key=lambda x: (-x[0], -x[1]),
    )[:k]
    labels = {True: "Best seller", False: "Suggested add-on"}
    return [_card(snap, i, 0.0, None, labels[n > 0]) for n, _, i in scored]


def cache_key(store_id: str, cv: int, mv: str, variant: str, basket: list[str], customer: str, max_addons, exclude) -> str:
    h = hashlib.sha1(
        "|".join([",".join(sorted(basket)), customer, str(max_addons), ",".join(sorted(exclude))]).encode()
    ).hexdigest()
    return f"rec:{store_id}:{cv}:{mv}:{variant}:{h}"


class StoreCache:
    """Per-process catalog snapshots, one per (store, model version).

    When the catalog version moves, only rows updated since the snapshot was
    taken are read and applied.
    """

    def __init__(self):
        self._snaps: dict[tuple[str, str], tuple[int, Snapshot]] = {}
        self._lock = threading.Lock()

    def snapshot(self, engine: Engine, store_id: str, cv: int, mv: str, items: list[str] | None) -> Snapshot:
        key = (store_id, mv)
        with self._lock:
            hit = self._snaps.get(key)
        if hit and hit[0] == cv:
            return hit[1]
        # 2 s overlap so a write committed during the previous read is not missed
        as_of = db.utcnow() - timedelta(seconds=2)
        snap = None
        if hit and hit[1].as_of is not None:
            snap = apply_changes(hit[1], db.load_products(engine, store_id, since=hit[1].as_of))
        if snap is None:
            snap = build_snapshot(db.load_products(engine, store_id), items)
        snap.as_of = as_of
        with self._lock:
            # keep only the newest model's snapshot plus the catalog-only one
            for k in [k for k in self._snaps if k[0] == store_id and k[1] not in (mv, "#catalog")]:
                del self._snaps[k]
            cur = self._snaps.get(key)
            if cur is None or cur[0] <= cv:
                self._snaps[key] = (cv, snap)
        return snap
