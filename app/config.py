import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    nasa_power_base_url: str = os.getenv(
        "NASA_POWER_BASE_URL",
        "https://power.larc.nasa.gov/api/temporal/climatology/point",
    )
    nasa_power_parameter: str = os.getenv("NASA_POWER_PARAMETER", "ALLSKY_SFC_SW_DWN")
    nasa_power_community: str = os.getenv("NASA_POWER_COMMUNITY", "RE")
    nasa_power_format: str = os.getenv("NASA_POWER_FORMAT", "JSON")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))

    panel_efficiency: float = float(os.getenv("PANEL_EFFICIENCY", "0.20"))
    system_losses: float = float(os.getenv("SYSTEM_LOSSES", "0.14"))
    default_system_area_m2: float = float(os.getenv("DEFAULT_SYSTEM_AREA_M2", "25"))
    project_lifetime_years: int = int(os.getenv("PROJECT_LIFETIME_YEARS", "25"))

    capex_usd: float = float(os.getenv("CAPEX_USD", "12000"))
    opex_annual_usd: float = float(os.getenv("OPEX_ANNUAL_USD", "180"))


settings = Settings()
