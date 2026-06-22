"""Select the IDW power parameter by minimising cross-validated error.

Rather than hard-coding an IDW power exponent, this module sweeps a range of
candidate powers and picks the one with the lowest leave-one-out RMSE. This
makes the interpolation choice data-driven and reproducible instead of an
arbitrary default, and the search itself becomes part of the reported
methodology.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gsp.interpolation.idw import LOOCVResult, loocv

__all__ = ["PowerSearchResult", "tune_power"]


@dataclass(frozen=True)
class PowerSearchResult:
    """Outcome of the IDW power search.

    Attributes:
        best_power: The power exponent with the lowest LOOCV RMSE.
        best: The :class:`LOOCVResult` at ``best_power``.
        sweep: List of ``(power, rmse_c)`` pairs over the search grid.

    """

    best_power: float
    best: LOOCVResult
    sweep: list[tuple[float, float]]


def tune_power(
    lats: np.ndarray,
    lons: np.ndarray,
    values: np.ndarray,
    *,
    candidates: tuple[float, ...] = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0),
) -> PowerSearchResult:
    """Find the IDW power that minimises leave-one-out RMSE.

    Args:
        lats: Control-point latitudes (deg).
        lons: Control-point longitudes (deg).
        values: Control-point values (deg C).
        candidates: Power exponents to evaluate.

    Returns:
        A :class:`PowerSearchResult` with the best power and the full sweep.

    """
    sweep: list[tuple[float, float]] = []
    best_result: LOOCVResult | None = None
    best_power = candidates[0]
    for p in candidates:
        res = loocv(lats, lons, values, power=p)
        sweep.append((p, res.rmse_c))
        if best_result is None or res.rmse_c < best_result.rmse_c:
            best_result = res
            best_power = p
    assert best_result is not None
    return PowerSearchResult(best_power=best_power, best=best_result, sweep=sweep)
