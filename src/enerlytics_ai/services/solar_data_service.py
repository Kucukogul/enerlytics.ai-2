import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from enerlytics_ai.app.config import settings
from enerlytics_ai.utils.helpers import monthly_to_annual_irradiance


def _cache_file_path(latitude: float, longitude: float) -> Path:
    cache_key = f"{latitude:.4f}_{longitude:.4f}_{settings.nasa_power_parameter}".replace("-", "m")
    return Path(settings.nasa_cache_dir) / f"{cache_key}.json"


def _read_cached_monthly_data(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    if not settings.enable_nasa_cache:
        return None

    cache_path = _cache_file_path(latitude, longitude)
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
    ttl_seconds = settings.nasa_cache_ttl_hours * 3600
    if ttl_seconds <= 0 or (time.time() - fetched_at) > ttl_seconds:
        return None

    monthly_daily_ghi = payload.get("monthly_daily_ghi")
    if not isinstance(monthly_daily_ghi, dict):
        return None
    return monthly_daily_ghi


def _write_cache_payload(latitude: float, longitude: float, monthly_daily_ghi: Dict[str, Any]) -> None:
    if not settings.enable_nasa_cache:
        return

    cache_path = _cache_file_path(latitude, longitude)
    os.makedirs(cache_path.parent, exist_ok=True)

    with cache_path.open("w", encoding="utf-8") as cache_file:
        json.dump(
            {
                "fetched_at_unix": int(time.time()),
                "monthly_daily_ghi": monthly_daily_ghi,
            },
            cache_file,
        )


def fetch_annual_ghi_kwh_m2(latitude: float, longitude: float) -> Dict[str, Any]:
    cached_monthly_data = _read_cached_monthly_data(latitude=latitude, longitude=longitude)
    if cached_monthly_data is not None:
        annual_ghi = monthly_to_annual_irradiance(cached_monthly_data)
        return {
            "source": "NASA POWER (cache)",
            "annual_irradiance_kwh_m2": round(annual_ghi, 2),
            "monthly_daily_ghi": cached_monthly_data,
        }

    params = {
        "parameters": settings.nasa_power_parameter,
        "community": settings.nasa_power_community,
        "longitude": longitude,
        "latitude": latitude,
        "format": settings.nasa_power_format,
    }

    response = requests.get(
        settings.nasa_power_base_url,
        params=params,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    monthly_data = (
        payload.get("properties", {})
        .get("parameter", {})
        .get(settings.nasa_power_parameter, {})
    )
    _write_cache_payload(latitude=latitude, longitude=longitude, monthly_daily_ghi=monthly_data)
    annual_ghi = monthly_to_annual_irradiance(monthly_data)

    return {
        "source": "NASA POWER",
        "annual_irradiance_kwh_m2": round(annual_ghi, 2),
        "monthly_daily_ghi": monthly_data,
    }


def fetch_historical_monthly_ghi_kwh_m2(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
) -> Dict[str, Any]:
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year.")

    params = {
        "parameters": settings.nasa_power_parameter,
        "community": settings.nasa_power_community,
        "longitude": longitude,
        "latitude": latitude,
        "format": settings.nasa_power_format,
        "start": str(start_year),
        "end": str(end_year),
    }

    response = requests.get(
        settings.nasa_power_monthly_base_url,
        params=params,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    monthly_data = (
        payload.get("properties", {})
        .get("parameter", {})
        .get(settings.nasa_power_parameter, {})
    )
    if not isinstance(monthly_data, dict):
        raise ValueError("Historical solar data format is invalid.")

    monthly_series = []
    for key, value in monthly_data.items():
        if not (isinstance(key, str) and len(key) == 6 and key.isdigit()):
            continue
        year = int(key[:4])
        month = int(key[4:])
        if year < start_year or year > end_year or month < 1 or month > 12:
            continue
        monthly_series.append(
            {
                "year": year,
                "month": month,
                "ghi_kwh_m2_day": float(value),
            }
        )

    monthly_series.sort(key=lambda item: (item["year"], item["month"]))
    if not monthly_series:
        raise ValueError("No historical monthly solar data returned for requested range.")

    annual_summary_map: Dict[int, Dict[str, float]] = {}
    for point in monthly_series:
        year = point["year"]
        annual_summary_map.setdefault(year, {"sum_ghi_kwh_m2_day": 0.0, "month_count": 0})
        annual_summary_map[year]["sum_ghi_kwh_m2_day"] += point["ghi_kwh_m2_day"]
        annual_summary_map[year]["month_count"] += 1

    annual_summary = []
    for year in sorted(annual_summary_map):
        year_total = annual_summary_map[year]["sum_ghi_kwh_m2_day"]
        month_count = annual_summary_map[year]["month_count"]
        annual_summary.append(
            {
                "year": year,
                "total_ghi_kwh_m2_day": round(year_total, 4),
                "average_ghi_kwh_m2_day": round(year_total / month_count, 4),
            }
        )

    return {
        "source": "NASA POWER",
        "parameter": settings.nasa_power_parameter,
        "latitude": latitude,
        "longitude": longitude,
        "start_year": start_year,
        "end_year": end_year,
        "monthly_series": monthly_series,
        "annual_summary": annual_summary,
    }
