from typing import Dict, Mapping

import numpy as np
import pandas as pd


DEFAULT_WEIGHTS: Mapping[str, float] = {
    "energy": 0.5,
    "lcoe": 0.3,
    "payback": 0.2,
}


def _min_max_normalize(series: pd.Series) -> pd.Series:
    finite = series.dropna()
    if finite.empty:
        return pd.Series(np.nan, index=series.index)

    min_v = float(finite.min())
    max_v = float(finite.max())
    span = max_v - min_v
    if span == 0:
        return pd.Series(np.where(series.isna(), np.nan, 1.0), index=series.index)
    return (series - min_v) / span


def _normalize_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    if not weights:
        raise ValueError("weights must not be empty.")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Sum of weights must be positive.")
    return {key: float(value) / total for key, value in weights.items()}


def compute_composite_score(
    df: pd.DataFrame,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
    energy_col: str = "annual_energy_kwh",
    lcoe_col: str = "lcoe_usd_kwh",
    payback_col: str = "simple_payback_years",
    status_col: str = "status",
    success_value: str = "ok",
) -> pd.DataFrame:
    if df.empty:
        out = df.copy()
        out["score"] = pd.Series(dtype=float)
        return out

    if status_col not in df.columns:
        raise ValueError(f"Missing status column: {status_col}")
    for col in (energy_col, lcoe_col, payback_col):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    out = df.copy()
    success_mask = out[status_col] == success_value

    energy = pd.to_numeric(out[energy_col], errors="coerce").where(success_mask)
    lcoe = pd.to_numeric(out[lcoe_col], errors="coerce").where(success_mask)
    payback = pd.to_numeric(out[payback_col], errors="coerce").where(success_mask)

    inv_lcoe = lcoe.where(lcoe > 0).rdiv(1.0)
    inv_payback = payback.where(payback > 0).rdiv(1.0)

    energy_score = _min_max_normalize(energy)
    lcoe_score = _min_max_normalize(inv_lcoe)
    payback_score = _min_max_normalize(inv_payback)

    weights_norm = _normalize_weights(weights)
    score = (
        weights_norm.get("energy", 0.0) * energy_score.fillna(0)
        + weights_norm.get("lcoe", 0.0) * lcoe_score.fillna(0)
        + weights_norm.get("payback", 0.0) * payback_score.fillna(0)
    )

    has_any_component = (
        energy_score.notna() | lcoe_score.notna() | payback_score.notna()
    )
    score = score.where(success_mask & has_any_component)

    out["energy_score"] = energy_score
    out["lcoe_score"] = lcoe_score
    out["payback_score"] = payback_score
    out["score"] = score
    return out
