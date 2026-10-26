"""E5: LightGBM LambdaRank reranker over the candidate pool, plus E7 calibration."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from .features import feature_columns


def split_events(feats: pd.DataFrame, fractions=(0.7, 0.15)) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Time-ordered split of val events: fit / early-stop / calibrate."""
    ids = np.sort(feats["event_id"].unique())
    a = int(len(ids) * fractions[0])
    b = int(len(ids) * (fractions[0] + fractions[1]))
    return (
        feats[feats["event_id"].isin(ids[:a])],
        feats[feats["event_id"].isin(ids[a:b])],
        feats[feats["event_id"].isin(ids[b:])],
    )


def _groups(df: pd.DataFrame) -> np.ndarray:
    return df.groupby("event_id", sort=False).size().to_numpy()


class Reranker:
    def __init__(self, cfg: dict, seed: int):
        r = cfg["rerank"]
        self.model = lgb.LGBMRanker(
            objective="lambdarank",
            num_leaves=r["num_leaves"],
            learning_rate=r["learning_rate"],
            n_estimators=r["n_estimators"],
            random_state=seed,
            verbose=-1,
        )
        self.es = r["early_stopping_rounds"]
        self.calibrator: IsotonicRegression | None = None
        self.columns: list[str] = []

    def fit(self, fit_df: pd.DataFrame, es_df: pd.DataFrame) -> "Reranker":
        # events whose target is not in the pool carry no ranking signal
        fit_df = fit_df[fit_df.groupby("event_id")["label"].transform("max") > 0]
        es_df = es_df[es_df.groupby("event_id")["label"].transform("max") > 0]
        self.columns = feature_columns(fit_df)
        self.model.fit(
            fit_df[self.columns],
            fit_df["label"],
            group=_groups(fit_df),
            eval_set=[(es_df[self.columns], es_df["label"])],
            eval_group=[_groups(es_df)],
            eval_at=[5, 10],
            callbacks=[lgb.early_stopping(self.es, verbose=False)],
        )
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        return self.model.predict(df[self.columns])

    def calibrate(self, cal_df: pd.DataFrame) -> dict:
        """Isotonic map from raw score to P(candidate is the held-out item).

        Fit on all candidate rows of held-out events, including events whose
        target missed the pool, so the probability is honest about recall.
        """
        s = self.score(cal_df)
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(s, cal_df["label"])
        p = self.calibrator.predict(s)
        return {"brier": float(np.mean((p - cal_df["label"]) ** 2)), "base_rate": float(cal_df["label"].mean())}

    def proba(self, df: pd.DataFrame) -> np.ndarray:
        assert self.calibrator is not None, "call calibrate() first"
        return self.calibrator.predict(self.score(df))

    def importance(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"feature": self.columns, "gain": self.model.booster_.feature_importance("gain")}
        ).sort_values("gain", ascending=False)


def pool_ranks(feats: pd.DataFrame, score: np.ndarray) -> pd.Series:
    """1-based rank of the target inside each event's pool (inf if not in pool)."""
    df = feats[["event_id", "label"]].copy()
    df["score"] = score
    df["rank"] = df.groupby("event_id")["score"].rank(ascending=False, method="max")
    r = df[df["label"] == 1].set_index("event_id")["rank"]
    all_ids = feats["event_id"].unique()
    return r.reindex(all_ids).fillna(np.inf)


def reliability_table(p: np.ndarray, y: np.ndarray, bins: int = 10) -> pd.DataFrame:
    q = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    b = np.clip(np.searchsorted(q, p, side="right") - 1, 0, len(q) - 2)
    return (
        pd.DataFrame({"bin": b, "p": p, "y": y})
        .groupby("bin")
        .agg(mean_pred=("p", "mean"), frac_pos=("y", "mean"), n=("y", "size"))
        .reset_index()
    )
