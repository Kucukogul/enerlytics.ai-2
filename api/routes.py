from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from requests import exceptions as requests_exceptions

from services.solar_model_service import analyze_site

router = APIRouter()


class AnalyzeRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AnalyzeResponse(BaseModel):
    annual_energy_kwh: float
    estimated_lcoe: float
    summary: str


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = analyze_site(payload.latitude, payload.longitude)
    except requests_exceptions.Timeout as exc:
        raise HTTPException(status_code=504, detail="Upstream solar data request timed out.") from exc
    except requests_exceptions.ConnectionError as exc:
        raise HTTPException(status_code=503, detail="Could not connect to upstream solar data provider.") from exc
    except requests_exceptions.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Upstream solar data provider returned an error.") from exc
    except requests_exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail="Unexpected upstream request error during analysis.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Analysis validation failed: {exc}") from exc
    return AnalyzeResponse(**result)
