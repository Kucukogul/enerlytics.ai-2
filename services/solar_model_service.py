from models.energy_model import estimate_annual_energy_kwh
from models.lcoe_model import estimate_lcoe_usd_per_kwh
from services.solar_data_service import fetch_annual_ghi_kwh_m2


def analyze_site(latitude: float, longitude: float) -> dict:
    solar_data = fetch_annual_ghi_kwh_m2(latitude=latitude, longitude=longitude)
    annual_energy_kwh = estimate_annual_energy_kwh(solar_data["annual_irradiance_kwh_m2"])
    estimated_lcoe = estimate_lcoe_usd_per_kwh(annual_energy_kwh)

    return {
        "annual_energy_kwh": annual_energy_kwh,
        "estimated_lcoe": estimated_lcoe,
        "summary": (
            f"Estimated annual production is {annual_energy_kwh} kWh with "
            f"an LCOE of {estimated_lcoe} USD/kWh."
        ),
    }
