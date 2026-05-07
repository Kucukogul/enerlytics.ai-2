from dataclasses import replace
from pathlib import Path

import pandas as pd
import requests_mock

import enerlytics_ai.services.pvgis_data_service as pvgis_mod
from pipelines.province_scan import run_province_scan


def _mrcalc_response(start_year: int = 2015, end_year: int = 2020, monthly_kwh_m2: float = 150.0):
    monthly = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            monthly.append({"year": year, "month": month, "H(h)_m": monthly_kwh_m2})
    return {"outputs": {"monthly": monthly}}


def _disable_pvgis_cache():
    pvgis_mod.settings = replace(pvgis_mod.settings, enable_pvgis_cache=False)


def test_province_pipeline_outputs_81_rows(tmp_path: Path):
    _disable_pvgis_cache()
    cfg = tmp_path / "province_scan.yaml"
    cfg.write_text(
        "\n".join(
            [
                "provinces_file: configs/turkey_provinces_81.csv",
                "provider: pvgis",
                "retries:",
                "  attempts: 1",
                "  initial_wait_seconds: 0.0",
                "  max_wait_seconds: 0.0",
                "weights:",
                "  energy: 0.5",
                "  lcoe: 0.3",
                "  payback: 0.2",
                "output:",
                f"  dir: {tmp_path}",
                "  prefix: test_provinces_81",
                "  write_csv: true",
            ]
        ),
        encoding="utf-8",
    )
    with requests_mock.Mocker() as m:
        m.get("https://re.jrc.ec.europa.eu/api/v5_2/MRcalc", json=_mrcalc_response())
        out = run_province_scan(cfg, progress=False)
    assert out.exists()
    df = pd.read_parquet(out)
    assert len(df) == 81
    assert df["status"].eq("ok").all()
    assert df["score"].between(0.0, 1.0).all()
