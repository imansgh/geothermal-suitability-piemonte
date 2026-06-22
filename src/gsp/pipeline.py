"""End-to-end screening pipeline: the single orchestration seam.

Composes loading, screening, and interpolation into one call that returns
everything a report, map, or dashboard needs. Downstream consumers (CLI,
Streamlit, notebook) import only from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from gsp.data.loader import load_joined
from gsp.data.models import BHTMeasurement, WellScreeningResult
from gsp.interpolation.field import GradientField, build_gradient_field
from gsp.interpolation.tuning import PowerSearchResult, tune_power
from gsp.screening.engine import load_thresholds, screen_wells

__all__ = ["ScreeningOutput", "run_pipeline"]


@dataclass(frozen=True)
class ScreeningOutput:
    """The complete output of one screening run.

    Attributes:
        results: Per-well screening results.
        measurements: All located BHT measurements.
        field: Interpolated gradient field (None if interpolation skipped).
        power_search: IDW power search result (None if interpolation skipped).
        surface_temperature_c: Surface temperature used.

    """

    results: list[WellScreeningResult]
    measurements: list[BHTMeasurement]
    field: GradientField | None
    power_search: PowerSearchResult | None
    surface_temperature_c: float


def run_pipeline(
    *,
    measurements_path: Path | None = None,
    locations_path: Path | None = None,
    interpolate: bool = True,
    grid_resolution: int = 80,
) -> ScreeningOutput:
    """Run the full screening workflow.

    Args:
        measurements_path: Optional override for the measurements CSV.
        locations_path: Optional override for the coordinates CSV.
        interpolate: Whether to build the interpolated gradient field.
        grid_resolution: Grid cells per axis for interpolation.

    Returns:
        A populated :class:`ScreeningOutput`.

    """
    cfg = load_thresholds()
    surface_t = float(cfg["surface_temperature_c"])

    measurements, locations = load_joined(measurements_path, locations_path)
    results = screen_wells(measurements, locations, thresholds=cfg)

    field: GradientField | None = None
    power_search: PowerSearchResult | None = None
    if interpolate and len(results) >= 4:
        lats = np.array([r.lat for r in results])
        lons = np.array([r.lon for r in results])
        grads = np.array([r.gradient_c_per_km for r in results])
        power_search = tune_power(lats, lons, grads)
        field = build_gradient_field(
            lats,
            lons,
            grads,
            surface_temperature_c=surface_t,
            resolution=grid_resolution,
        )

    return ScreeningOutput(
        results=results,
        measurements=measurements,
        field=field,
        power_search=power_search,
        surface_temperature_c=surface_t,
    )
