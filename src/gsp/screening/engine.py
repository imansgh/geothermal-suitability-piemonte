"""Geothermal suitability screening engine.

Turns located BHT measurements into per-well :class:`WellScreeningResult`
objects. The governing reading for each well is its deepest measurement, since
that is the most representative of the recoverable thermal resource; the
apparent geothermal gradient is derived from that reading and the configured
surface temperature.

Every threshold is read from ``thresholds.yaml`` so the classification policy
is auditable and tunable without code changes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from gsp.data.models import (
    BHTMeasurement,
    SuitabilityClass,
    WellLocation,
    WellScreeningResult,
)

__all__ = [
    "CONFIG_PATH",
    "load_thresholds",
    "classify",
    "geothermal_gradient",
    "screen_wells",
]

CONFIG_PATH: Path = Path(__file__).resolve().parent / "thresholds.yaml"


@lru_cache(maxsize=1)
def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    """Load and cache the screening thresholds.

    Args:
        path: Optional override path to a thresholds YAML.

    Returns:
        The parsed thresholds document.

    """
    cfg_path = path or CONFIG_PATH
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Thresholds root must be a mapping: {cfg_path}")
    return data


def geothermal_gradient(
    t_corrected_c: float,
    depth_m: float,
    *,
    surface_temperature_c: float,
) -> float:
    """Apparent geothermal gradient from a single corrected reading.

    Computed as ``(T_corrected - T_surface) / depth`` and expressed in
    deg C per kilometre. This is a first-order estimate: it assumes a linear
    profile from surface to the reading depth and does not resolve
    intra-section gradient variation.

    Args:
        t_corrected_c: Corrected static formation temperature, deg C.
        depth_m: Depth of the reading, metres.
        surface_temperature_c: Assumed mean annual surface temperature, deg C.

    Returns:
        Apparent gradient in deg C per kilometre.

    """
    if depth_m <= 0:
        return 0.0
    return (t_corrected_c - surface_temperature_c) / (depth_m / 1000.0)


def classify(
    t_corrected_c: float,
    depth_m: float,
    *,
    thresholds: dict[str, Any] | None = None,
) -> SuitabilityClass:
    """Assign a geothermal suitability class to a single reading.

    Gates are evaluated highest-grade first; the well takes the first class
    whose temperature and depth conditions are both satisfied.

    Args:
        t_corrected_c: Corrected static formation temperature, deg C.
        depth_m: Depth of the governing reading, metres.
        thresholds: Optional pre-loaded thresholds (defaults to the config).

    Returns:
        The matching :class:`SuitabilityClass`.

    """
    cfg = thresholds or load_thresholds()
    classes = cfg["classes"]

    power = classes["power_generation"]
    if t_corrected_c >= power["min_temperature_c"] and depth_m >= power["min_depth_m"]:
        return SuitabilityClass.POWER_GENERATION

    direct = classes["direct_use"]
    if t_corrected_c >= direct["min_temperature_c"] and depth_m >= direct["min_depth_m"]:
        return SuitabilityClass.DIRECT_USE

    gshp = classes["ground_source_hp"]
    if t_corrected_c >= gshp["min_temperature_c"] and depth_m >= gshp["min_depth_m"]:
        return SuitabilityClass.GROUND_SOURCE_HP

    return SuitabilityClass.BELOW_THRESHOLD


def screen_wells(
    measurements: list[BHTMeasurement],
    locations: dict[str, WellLocation],
    *,
    thresholds: dict[str, Any] | None = None,
) -> list[WellScreeningResult]:
    """Screen every well from its deepest measurement.

    Args:
        measurements: Located BHT measurements (one or more per well).
        locations: Well name -> location mapping.
        thresholds: Optional pre-loaded thresholds (defaults to the config).

    Returns:
        One :class:`WellScreeningResult` per well, sorted by corrected
        temperature, highest first.

    """
    cfg = thresholds or load_thresholds()
    surface_t = float(cfg["surface_temperature_c"])

    # Group measurements by well.
    by_well: dict[str, list[BHTMeasurement]] = {}
    for m in measurements:
        by_well.setdefault(m.well, []).append(m)

    results: list[WellScreeningResult] = []
    for well, readings in by_well.items():
        if well not in locations:
            continue
        governing = max(readings, key=lambda r: r.depth_m)
        loc = locations[well]
        gradient = geothermal_gradient(
            governing.t_corrected_c,
            governing.depth_m,
            surface_temperature_c=surface_t,
        )
        suitability = classify(governing.t_corrected_c, governing.depth_m, thresholds=cfg)
        results.append(
            WellScreeningResult(
                well=well,
                lat=loc.lat,
                lon=loc.lon,
                province=loc.province,
                depth_m=round(governing.depth_m, 2),
                t_raw_c=round(governing.t_raw_c, 2),
                t_corrected_c=round(governing.t_corrected_c, 2),
                gradient_c_per_km=round(gradient, 2),
                suitability=suitability,
                n_measurements=len(readings),
            )
        )

    results.sort(key=lambda r: r.t_corrected_c, reverse=True)
    return results
