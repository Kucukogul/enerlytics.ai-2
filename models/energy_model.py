from app.config import settings


def estimate_annual_energy_kwh(annual_irradiance_kwh_m2: float) -> float:
    raw_output = annual_irradiance_kwh_m2 * settings.default_system_area_m2 * settings.panel_efficiency
    net_output = raw_output * (1 - settings.system_losses)
    return round(net_output, 2)
