from typing import Any, Dict

import requests

from app.config import settings
from utils.helpers import monthly_to_annual_irradiance


def fetch_annual_ghi_kwh_m2(latitude: float, longitude: float) -> Dict[str, Any]:
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
    annual_ghi = monthly_to_annual_irradiance(monthly_data)

    return {
        "source": "NASA POWER",
        "annual_irradiance_kwh_m2": round(annual_ghi, 2),
        "monthly_daily_ghi": monthly_data,
    }
