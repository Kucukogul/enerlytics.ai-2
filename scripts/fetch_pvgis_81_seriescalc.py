#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

DEFAULT_ENDPOINT = "https://re.jrc.ec.europa.eu/api/seriescalc"
DEFAULT_PROVINCES_FILE = "configs/turkey_provinces_81.csv"
DEFAULT_OUTPUT_FILE = "data/raw/pvgis/turkey_provinces_81_seriescalc_2015_2026.json"
PVGIS_MAX_END_YEAR = 2023


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch PVGIS seriescalc for all 81 provinces and write one raw JSON file."
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--endpoint", type=str, default=DEFAULT_ENDPOINT)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--sleep-seconds", type=float, default=0.15)
    parser.add_argument("--provinces-file", type=str, default=DEFAULT_PROVINCES_FILE)
    parser.add_argument("--output-file", type=str, default=DEFAULT_OUTPUT_FILE)
    return parser.parse_args()


def load_provinces(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    provinces: List[Dict[str, Any]] = []
    for row in rows:
        provinces.append(
            {
                "plate_code": int(row["plate_code"]),
                "province": row["province"],
                "latitude": float(row["lat"]),
                "longitude": float(row["lon"]),
            }
        )
    provinces.sort(key=lambda item: item["plate_code"])
    return provinces


def summarize_monthly(hourly_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    monthly_buckets: Dict[tuple[int, int], Dict[str, float]] = defaultdict(
        lambda: {"sum_ghi_w_m2": 0.0, "hour_count": 0.0}
    )
    for point in hourly_points:
        time_key = str(point.get("time", ""))
        if len(time_key) < 6 or not time_key[:6].isdigit():
            continue
        year = int(time_key[:4])
        month = int(time_key[4:6])
        ghi = float(point.get("G(i)", 0.0))
        key = (year, month)
        monthly_buckets[key]["sum_ghi_w_m2"] += ghi
        monthly_buckets[key]["hour_count"] += 1

    monthly_series: List[Dict[str, Any]] = []
    for (year, month), agg in sorted(monthly_buckets.items()):
        hour_count = int(agg["hour_count"])
        if hour_count <= 0:
            continue
        monthly_series.append(
            {
                "year": year,
                "month": month,
                "avg_ghi_w_m2": round(agg["sum_ghi_w_m2"] / hour_count, 4),
                "hour_count": hour_count,
            }
        )
    return monthly_series


def fetch_province(
    session: requests.Session,
    endpoint: str,
    province: Dict[str, Any],
    start_year: int,
    end_year: int,
    timeout: int,
) -> Dict[str, Any]:
    params = {
        "lat": province["latitude"],
        "lon": province["longitude"],
        "startyear": start_year,
        "endyear": end_year,
        "pvcalculation": 0,
        "outputformat": "json",
    }
    response = session.get(endpoint, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("outputs", {}).get("hourly", [])
    if not isinstance(hourly, list) or not hourly:
        raise ValueError("PVGIS seriescalc response has no hourly data.")

    monthly_series = summarize_monthly(hourly)
    years = sorted({item["year"] for item in monthly_series})
    return {
        "plate_code": province["plate_code"],
        "province": province["province"],
        "latitude": province["latitude"],
        "longitude": province["longitude"],
        "source": "PVGIS",
        "endpoint": endpoint,
        "requested_range": {"start_year": start_year, "end_year": end_year},
        "fetched_range": {
            "start_year": years[0] if years else None,
            "end_year": years[-1] if years else None,
        },
        "monthly_series": monthly_series,
    }


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent.parent
    provinces_file = (project_root / args.provinces_file).resolve()
    output_file = (project_root / args.output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    requested_start_year = int(args.start_year)
    requested_end_year = int(args.end_year)
    fetched_end_year = min(requested_end_year, PVGIS_MAX_END_YEAR)

    provinces = load_provinces(provinces_file)
    session = requests.Session()
    records: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for idx, province in enumerate(provinces, start=1):
        try:
            record = fetch_province(
                session=session,
                endpoint=args.endpoint,
                province=province,
                start_year=requested_start_year,
                end_year=fetched_end_year,
                timeout=args.timeout,
            )
            records.append(record)
            print(f"[{idx:02d}/{len(provinces)}] ok   {province['province']}")
        except Exception as exc:
            errors.append(
                {
                    "plate_code": province["plate_code"],
                    "province": province["province"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"[{idx:02d}/{len(provinces)}] err  {province['province']} -> {exc}")
        time.sleep(max(0.0, float(args.sleep_seconds)))

    records.sort(key=lambda item: item["plate_code"])
    out = {
        "dataset": "Turkey provinces PVGIS seriescalc historical",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "pvgis",
        "endpoint": args.endpoint,
        "province_count": len(provinces),
        "success_count": len(records),
        "error_count": len(errors),
        "requested_range": {"start_year": requested_start_year, "end_year": requested_end_year},
        "fetched_range": {"start_year": requested_start_year, "end_year": fetched_end_year},
        "note": (
            "PVGIS seriescalc supports endyear up to 2023, so later years are clipped."
            if requested_end_year > fetched_end_year
            else ""
        ),
        "provinces": records,
        "errors": errors,
    }

    with output_file.open("w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print(f"\nWrote: {output_file}")
    print(f"Success: {len(records)} / {len(provinces)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
