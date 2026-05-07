import math

import numpy as np
import pandas as pd
import pytest

from pipelines.scoring import compute_composite_score


def _sample_df():
    return pd.DataFrame(
        [
            {"lat": 36.0, "lon": 30.0, "annual_energy_kwh": 9000, "lcoe_usd_kwh": 0.05, "simple_payback_years": 6.0,  "status": "ok"},
            {"lat": 39.0, "lon": 32.0, "annual_energy_kwh": 7500, "lcoe_usd_kwh": 0.07, "simple_payback_years": 8.0,  "status": "ok"},
            {"lat": 41.0, "lon": 28.0, "annual_energy_kwh": 6000, "lcoe_usd_kwh": 0.10, "simple_payback_years": 12.0, "status": "ok"},
        ]
    )


def test_score_columns_added_and_in_unit_range():
    out = compute_composite_score(_sample_df())
    for col in ("energy_score", "lcoe_score", "payback_score", "score"):
        assert col in out.columns
    assert out["score"].between(0.0, 1.0).all()


def test_best_row_gets_highest_score_with_default_weights():
    out = compute_composite_score(_sample_df())
    assert out["score"].idxmax() == 0
    assert out["score"].idxmin() == 2


def test_failed_rows_get_nan_score():
    df = _sample_df()
    df.loc[1, "status"] = "error"
    out = compute_composite_score(df)
    assert math.isnan(out.loc[1, "score"])
    assert not math.isnan(out.loc[0, "score"])


def test_constant_metric_yields_full_normalized_value():
    df = pd.DataFrame(
        [
            {"annual_energy_kwh": 5000, "lcoe_usd_kwh": 0.08, "simple_payback_years": 9.0, "status": "ok"},
            {"annual_energy_kwh": 5000, "lcoe_usd_kwh": 0.08, "simple_payback_years": 9.0, "status": "ok"},
        ]
    )
    out = compute_composite_score(df)
    assert (out["score"] == 1.0).all()


def test_weights_must_sum_positive():
    with pytest.raises(ValueError):
        compute_composite_score(_sample_df(), weights={"energy": 0.0, "lcoe": 0.0, "payback": 0.0})


def test_missing_required_column_raises():
    df = _sample_df().drop(columns=["lcoe_usd_kwh"])
    with pytest.raises(ValueError):
        compute_composite_score(df)


def test_negative_or_zero_lcoe_treated_as_missing_in_normalization():
    df = _sample_df()
    df.loc[2, "lcoe_usd_kwh"] = 0.0
    out = compute_composite_score(df)
    assert math.isnan(out.loc[2, "lcoe_score"])
    assert 0.0 <= out.loc[2, "score"] <= 1.0


def test_empty_dataframe_returns_empty_with_score_column():
    df = pd.DataFrame(columns=["annual_energy_kwh", "lcoe_usd_kwh", "simple_payback_years", "status"])
    out = compute_composite_score(df)
    assert out.empty
    assert "score" in out.columns


def test_all_failures_yields_all_nan_scores():
    df = _sample_df()
    df["status"] = "error"
    out = compute_composite_score(df)
    assert out["score"].isna().all()
