from app.config import settings


def estimate_lcoe_usd_per_kwh(annual_energy_kwh: float) -> float:
    if annual_energy_kwh <= 0:
        raise ValueError("Annual energy must be greater than zero.")
    if settings.project_lifetime_years <= 0:
        raise ValueError("Project lifetime must be greater than zero years.")
    if settings.capex_usd < 0 or settings.opex_annual_usd < 0:
        raise ValueError("CAPEX and annual OPEX cannot be negative.")

    total_cost = settings.capex_usd + (settings.opex_annual_usd * settings.project_lifetime_years)
    total_energy_output = annual_energy_kwh * settings.project_lifetime_years
    lcoe = total_cost / total_energy_output
    return round(lcoe, 4)
