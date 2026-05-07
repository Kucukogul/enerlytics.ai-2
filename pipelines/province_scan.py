from __future__ import annotations

import csv
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd
import yaml
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from tqdm import tqdm

from enerlytics_ai.services.solar_model_service import analyze_site
from pipelines.scoring import DEFAULT_WEIGHTS, compute_composite_score

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RETRYABLE_EXCEPTIONS: Tuple[type[BaseException], ...] = (Exception,)


@dataclass(frozen=True)
class RetryConfig:
    attempts: int = 3
    initial_wait_seconds: float = 1.0
    max_wait_seconds: float = 8.0


@dataclass(frozen=True)
class OutputConfig:
    dir: str
    prefix: str
    write_csv: bool


@dataclass(frozen=True)
class ProvinceScanConfig:
    provinces_file: str
    provider: str
    retries: RetryConfig
    weights: Mapping[str, float]
    output: OutputConfig


def load_config(config_path: Path | str) -> ProvinceScanConfig:
    path = Path(config_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve() if not path.exists() else path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    retries_raw = raw.get("retries", {})
    retries = RetryConfig(
        attempts=int(retries_raw.get("attempts", 3)),
        initial_wait_seconds=float(retries_raw.get("initial_wait_seconds", 1.0)),
        max_wait_seconds=float(retries_raw.get("max_wait_seconds", 8.0)),
    )

    output_raw = raw.get("output", {})
    output = OutputConfig(
        dir=str(output_raw.get("dir", "data/processed/provinces")),
        prefix=str(output_raw.get("prefix", "turkey_provinces_81")),
        write_csv=bool(output_raw.get("write_csv", True)),
    )

    return ProvinceScanConfig(
        provinces_file=str(raw.get("provinces_file", "configs/turkey_provinces_81.csv")),
        provider=str(raw.get("provider", "pvgis")).lower(),
        retries=retries,
        weights=dict(raw.get("weights") or DEFAULT_WEIGHTS),
        output=output,
    )


def _load_provinces(path: str) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = (PROJECT_ROOT / file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Provinces file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    provinces: List[Dict[str, Any]] = []
    for row in rows:
        provinces.append(
            {
                "plate_code": int(row["plate_code"]),
                "province": row["province"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            }
        )
    provinces.sort(key=lambda r: r["plate_code"])
    if len(provinces) != 81:
        logger.warning("Expected 81 provinces, found %d", len(provinces))
    return provinces


def _analyze_province(province_row: Dict[str, Any], provider: str, retries: RetryConfig) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "plate_code": province_row["plate_code"],
        "province": province_row["province"],
        "lat": province_row["lat"],
        "lon": province_row["lon"],
        "provider": provider,
        "annual_energy_kwh": None,
        "lcoe_usd_kwh": None,
        "lcoe_try_kwh": None,
        "simple_payback_years": None,
        "data_source": None,
        "status": "ok",
        "error": None,
    }
    try:
        retrying = Retrying(
            stop=stop_after_attempt(max(1, retries.attempts)),
            wait=wait_exponential(multiplier=retries.initial_wait_seconds, max=retries.max_wait_seconds),
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            reraise=True,
        )
        result = retrying(analyze_site, province_row["lat"], province_row["lon"], provider)
        record["annual_energy_kwh"] = result.get("annual_energy_kwh")
        record["lcoe_usd_kwh"] = result.get("estimated_lcoe")
        record["lcoe_try_kwh"] = result.get("lcoe_try_kwh")
        record["simple_payback_years"] = result.get("simple_payback_years")
        record["data_source"] = result.get("data_source")
    except Exception as exc:
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def _build_output_paths(cfg: ProvinceScanConfig) -> Tuple[Path, Optional[Path]]:
    out_dir = Path(cfg.output.dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    base_name = f"{cfg.output.prefix}_{cfg.provider}_{timestamp}"
    parquet_path = out_dir / f"{base_name}.parquet"
    csv_path = out_dir / f"{base_name}.csv" if cfg.output.write_csv else None
    return parquet_path, csv_path


def run_province_scan(config_path: Path | str, progress: bool = True) -> Path:
    cfg = load_config(config_path)
    provinces = _load_provinces(cfg.provinces_file)

    records: List[Dict[str, Any]] = []
    iterator = provinces
    if progress:
        iterator = tqdm(provinces, total=len(provinces), desc="province scan", unit="province")

    for province in iterator:
        records.append(_analyze_province(province, cfg.provider, cfg.retries))

    df = pd.DataFrame(records).sort_values(["plate_code"]).reset_index(drop=True)
    df = compute_composite_score(df, weights=cfg.weights)
    parquet_path, csv_path = _build_output_paths(cfg)
    df.to_parquet(parquet_path, index=False)
    if csv_path is not None:
        df.to_csv(csv_path, index=False)

    success_count = int((df["status"] == "ok").sum()) if "status" in df.columns else 0
    logger.info("Wrote %s (success=%d / total=%d)", parquet_path, success_count, len(df))
    return parquet_path


__all__ = ["run_province_scan", "_configure_logging"]


def _configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
