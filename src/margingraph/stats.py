"""Ranking metrics and bootstrap confidence intervals."""
from __future__ import annotations

import numpy as np


def target_rank(scores: np.ndarray, target: np.ndarray) -> np.ndarray:
    """1-based rank of each row's target column (ties broken pessimistically).

    target == -1 (item unseen in train) gets rank = inf.
    """
    out = np.full(len(target), np.inf)
    ok = target >= 0
    t = scores[ok, target[ok]]
    out[ok] = (scores[ok] >= t[:, None]).sum(1)
    return out


def ranking_metrics(rank: np.ndarray, ks=(5, 10, 20, 50)) -> dict[str, np.ndarray]:
    """Per-event arrays: hit@k, ndcg@10, mrr (single held-out target)."""
    m = {f"hit@{k}": (rank <= k).astype(float) for k in ks}
    m["ndcg@10"] = np.where(rank <= 10, 1.0 / np.log2(rank + 1), 0.0)
    m["mrr"] = np.where(np.isfinite(rank), 1.0 / rank, 0.0)
    return m


def _boot_means(x: np.ndarray, n_boot: int, rng, chunk: int = 200) -> np.ndarray:
    out = []
    for s in range(0, n_boot, chunk):
        idx = rng.integers(0, len(x), size=(min(chunk, n_boot - s), len(x)))
        out.append(x[idx].mean(1))
    return np.concatenate(out)


def bootstrap_ci(x: np.ndarray, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    means = _boot_means(x, n_boot, rng)
    return float(x.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, seed: int = 0) -> dict:
    """CI for mean(a - b) over the same events, plus a two-sided bootstrap p-value."""
    d = np.asarray(a, float) - np.asarray(b, float)
    mean, lo, hi = bootstrap_ci(d, n_boot, seed)
    rng = np.random.default_rng(seed + 1)
    boots = _boot_means(d, n_boot, rng)
    p = 2 * min((boots <= 0).mean(), (boots >= 0).mean())
    return {"diff": mean, "ci_low": lo, "ci_high": hi, "p_boot": float(min(p, 1.0))}
