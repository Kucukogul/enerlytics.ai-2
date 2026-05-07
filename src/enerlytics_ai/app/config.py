import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    solar_data_provider: str = os.getenv("SOLAR_DATA_PROVIDER", "nasa").lower()
    nasa_power_base_url: str = os.getenv(
        "NASA_POWER_BASE_URL",
        "https://power.larc.nasa.gov/api/temporal/climatology/point",
    )
    nasa_power_monthly_base_url: str = os.getenv(
        "NASA_POWER_MONTHLY_BASE_URL",
        "https://power.larc.nasa.gov/api/temporal/monthly/point",
    )
    nasa_power_parameter: str = os.getenv("NASA_POWER_PARAMETER", "ALLSKY_SFC_SW_DWN")
    nasa_power_community: str = os.getenv("NASA_POWER_COMMUNITY", "RE")
    nasa_power_format: str = os.getenv("NASA_POWER_FORMAT", "JSON")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
    enable_nasa_cache: bool = os.getenv("ENABLE_NASA_CACHE", "true").lower() == "true"
    nasa_cache_dir: str = os.getenv("NASA_CACHE_DIR", "data/raw/nasa_power")
    nasa_cache_ttl_hours: int = int(os.getenv("NASA_CACHE_TTL_HOURS", "720"))
    pvgis_base_url: str = os.getenv("PVGIS_BASE_URL", "https://re.jrc.ec.europa.eu/api/v5_2/MRcalc")
    pvgis_start_year: int = int(os.getenv("PVGIS_START_YEAR", "2015"))
    pvgis_end_year: int = int(os.getenv("PVGIS_END_YEAR", "2020"))
    enable_pvgis_cache: bool = os.getenv("ENABLE_PVGIS_CACHE", "true").lower() == "true"
    pvgis_cache_dir: str = os.getenv("PVGIS_CACHE_DIR", "data/raw/pvgis")
    pvgis_cache_ttl_hours: int = int(os.getenv("PVGIS_CACHE_TTL_HOURS", "720"))

    panel_efficiency: float = float(os.getenv("PANEL_EFFICIENCY", "0.20"))
    system_losses: float = float(os.getenv("SYSTEM_LOSSES", "0.14"))
    default_system_area_m2: float = float(os.getenv("DEFAULT_SYSTEM_AREA_M2", "25"))
    project_lifetime_years: int = int(os.getenv("PROJECT_LIFETIME_YEARS", "25"))

    capex_usd: float = float(os.getenv("CAPEX_USD", "12000"))
    opex_annual_usd: float = float(os.getenv("OPEX_ANNUAL_USD", "180"))
    usd_try: float = float(os.getenv("USD_TRY", "32.0"))
    discount_rate_tr: float = float(os.getenv("DISCOUNT_RATE_TR", "0.30"))
    land_cost_try: float = float(os.getenv("LAND_COST_TRY", "0"))
    electricity_sale_price_try_kwh: float = float(os.getenv("ELECTRICITY_SALE_PRICE_TRY_KWH", "2.5"))


settings = Settings()
