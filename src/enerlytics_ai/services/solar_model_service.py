from enerlytics_ai.models.energy_model import estimate_annual_energy_kwh
from enerlytics_ai.models.lcoe_model import estimate_lcoe_usd_per_kwh
from enerlytics_ai.app.config import settings
from enerlytics_ai.services import pvgis_data_service, solar_data_service


def _fetch_solar_data(latitude: float, longitude: float, provider: str | None = None) -> dict:
    selected = (provider or settings.solar_data_provider).lower()
    if selected == "nasa":
        return solar_data_service.fetch_annual_ghi_kwh_m2(latitude=latitude, longitude=longitude)
    if selected == "pvgis":
        return pvgis_data_service.fetch_annual_ghi_kwh_m2(latitude=latitude, longitude=longitude)
    raise ValueError("Invalid solar data provider. Supported values: nasa, pvgis.")


def analyze_site(latitude: float, longitude: float, provider: str | None = None) -> dict:
    solar_data = _fetch_solar_data(latitude=latitude, longitude=longitude, provider=provider)
    annual_energy_kwh = estimate_annual_energy_kwh(solar_data["annual_irradiance_kwh_m2"])
    estimated_lcoe_usd = estimate_lcoe_usd_per_kwh(annual_energy_kwh)
    lcoe_try_kwh = round(estimated_lcoe_usd * settings.usd_try, 4)
    annual_revenue_try = annual_energy_kwh * settings.electricity_sale_price_try_kwh
    total_investment_try = (settings.capex_usd * settings.usd_try) + settings.land_cost_try
    simple_payback_years = round(total_investment_try / annual_revenue_try, 2) if annual_revenue_try > 0 else None

    return {
        "data_source": solar_data["source"],
        "annual_energy_kwh": annual_energy_kwh,
        "estimated_lcoe": estimated_lcoe_usd,
        "lcoe_try_kwh": lcoe_try_kwh,
        "simple_payback_years": simple_payback_years,
        "summary": (
            f"Estimated annual production is {annual_energy_kwh} kWh with "
            f"an LCOE of {estimated_lcoe_usd} USD/kWh ({lcoe_try_kwh} TRY/kWh)."
        ),
    }
