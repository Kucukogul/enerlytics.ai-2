from typing import Dict

from utils.constants import DAYS_IN_YEAR, MONTHS_IN_YEAR, NASA_MONTH_KEYS


def monthly_to_annual_irradiance(monthly_daily_ghi: Dict[str, float]) -> float:
    values = [float(monthly_daily_ghi[m]) for m in NASA_MONTH_KEYS if m in monthly_daily_ghi]
    if len(values) != MONTHS_IN_YEAR:
        raise ValueError("Incomplete monthly GHI data from NASA POWER.")
    average_daily_ghi = sum(values) / MONTHS_IN_YEAR
    return average_daily_ghi * DAYS_IN_YEAR
