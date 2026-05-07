import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from enerlytics_ai.app.config import settings


def _cache_file_path(latitude: float, longitude: float, start_year: int, end_year: int) -> Path:
    cache_key = (
        f"{latitude:.4f}_{longitude:.4f}_{start_year}_{end_year}".replace("-", "m")
    )
    return Path(settings.pvgis_cache_dir) / f"{cache_key}.json"


def _read_cached_payload(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> Optional[Dict[str, Any]]:
    if not settings.enable_pvgis_cache:
        return None

    cache_path = _cache_file_path(latitude, longitude, start_year, end_year)
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        try:
            cache_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    fetched_at = float(payload.get("fetched_at_unix", 0))
    ttl_seconds = settings.pvgis_cache_ttl_hours * 3600
    if ttl_seconds <= 0 or (time.time() - fetched_at) > ttl_seconds:
        return None

    monthly_entries = payload.get("monthly_entries")
    if not isinstance(monthly_entries, list) or not monthly_entries:
        return None
    return monthly_entries


def _write_cache_payload(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    monthly_entries: List[Dict[str, Any]],
) -> None:
    if not settings.enable_pvgis_cache:
        return

    cache_path = _cache_file_path(latitude, longitude, start_year, end_year)
    os.makedirs(cache_path.parent, exist_ok=True)

    with cache_path.open("w", encoding="utf-8") as cache_file:
        json.dump(
            {
                "fetched_at_unix": int(time.time()),
                "monthly_entries": monthly_entries,
            },
            cache_file,
        )


def _request_monthly_entries(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> List[Dict[str, Any]]:
    params = {
        "lat": latitude,
        "lon": longitude,
        "horirrad": 1,
        "outputformat": "json",
        "startyear": start_year,
        "endyear": end_year,
    }

    response = requests.get(
        settings.pvgis_base_url,
        params=params,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    monthly_entries = payload.get("outputs", {}).get("monthly", [])
    if not isinstance(monthly_entries, list) or not monthly_entries:
        raise ValueError("PVGIS MRcalc response missing monthly entries.")
    return monthly_entries


def _annual_irradiance_from_monthly_entries(monthly_entries: List[Dict[str, Any]]) -> float:
    yearly_totals: Dict[int, float] = defaultdict(float)
    yearly_month_counts: Dict[int, int] = defaultdict(int)

    for entry in monthly_entries:
        try:
            year = int(entry["year"])
            value = float(entry["H(h)_m"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("PVGIS monthly entry has invalid format.") from exc
        yearly_totals[year] += value
        yearly_month_counts[year] += 1

    complete_years = [y for y, count in yearly_month_counts.items() if count == 12]
    if not complete_years:
        raise ValueError("PVGIS response has no complete-year monthly coverage.")

    yearly_sums = [yearly_totals[year] for year in complete_years]
    return sum(yearly_sums) / len(yearly_sums)


def fetch_annual_ghi_kwh_m2(latitude: float, longitude: float) -> Dict[str, Any]:
    start_year = settings.pvgis_start_year
    end_year = settings.pvgis_end_year
    if start_year > end_year:
        raise ValueError("PVGIS_START_YEAR must be less than or equal to PVGIS_END_YEAR.")

    cached_entries = _read_cached_payload(latitude, longitude, start_year, end_year)
    if cached_entries is not None:
        annual_ghi = _annual_irradiance_from_monthly_entries(cached_entries)
        return {
            "source": "PVGIS (cache)",
            "annual_irradiance_kwh_m2": round(annual_ghi, 2),
            "monthly_entries": cached_entries,
            "start_year": start_year,
            "end_year": end_year,
        }

    monthly_entries = _request_monthly_entries(latitude, longitude, start_year, end_year)
    _write_cache_payload(latitude, longitude, start_year, end_year, monthly_entries)
    annual_ghi = _annual_irradiance_from_monthly_entries(monthly_entries)

    return {
        "source": "PVGIS",
        "annual_irradiance_kwh_m2": round(annual_ghi, 2),
        "monthly_entries": monthly_entries,
        "start_year": start_year,
        "end_year": end_year,
    }
