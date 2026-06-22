"""Spatial interpolation of corrected temperature with honest error reporting.

This module interpolates the corrected-temperature field across the study area
from the sparse well control points. It deliberately treats interpolation as a
claim that must be validated, not a free decoration:

* **Inverse-distance weighting (IDW)** is used as the interpolator. It is
  transparent, parameter-light, and makes no covariance assumptions that a
  31-point dataset cannot support.
* A **leave-one-out cross-validation (LOOCV)** routine quantifies how well the
  interpolation predicts a withheld well, returning RMSE and MAE in deg C.
* The interpolated grid is therefore always accompanied by its own error, so a
  reader can judge where the surface is trustworthy and where it is an
  extrapolation guess.

The screening classification (``gsp.screening``) is based on real well
readings, not on the interpolated surface; the surface is a visual aid whose
limitations are stated, consistent with conservative engineering practice.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "IDWResult",
    "LOOCVResult",
    "idw_interpolate",
    "idw_grid",
    "loocv",
]


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    """Great-circle distance (km) from many points to one point.

    Using true earth distance rather than planar degrees keeps the weighting
    physically meaningful across the ~1.5 deg span of the study area.

    Args:
        lat1: Array of source latitudes (deg).
        lon1: Array of source longitudes (deg).
        lat2: Target latitude (deg).
        lon2: Target longitude (deg).

    Returns:
        Array of distances in kilometres.

    """
    r = 6371.0
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    result: np.ndarray = 2 * r * np.arcsin(np.sqrt(a))
    return result


@dataclass(frozen=True)
class IDWResult:
    """A single interpolated value and the control it relied on.

    Attributes:
        value: Interpolated temperature, deg C.
        nearest_km: Distance to the nearest control point, km (a proxy for how
            much the estimate is supported by nearby data).

    """

    value: float
    nearest_km: float


@dataclass(frozen=True)
class LOOCVResult:
    """Leave-one-out cross-validation summary for the interpolation.

    Attributes:
        rmse_c: Root-mean-square prediction error, deg C.
        mae_c: Mean absolute prediction error, deg C.
        n: Number of points cross-validated.
        power: The IDW power parameter used.
        residuals: Per-point (observed - predicted) errors, deg C.

    """

    rmse_c: float
    mae_c: float
    n: int
    power: float
    residuals: list[float]


def idw_interpolate(
    lats: np.ndarray,
    lons: np.ndarray,
    values: np.ndarray,
    target_lat: float,
    target_lon: float,
    *,
    power: float = 2.0,
) -> IDWResult:
    """Interpolate one target point by inverse-distance weighting.

    Args:
        lats: Control-point latitudes (deg).
        lons: Control-point longitudes (deg).
        values: Control-point values (deg C).
        target_lat: Target latitude (deg).
        target_lon: Target longitude (deg).
        power: IDW power exponent (higher = more local).

    Returns:
        An :class:`IDWResult` with the interpolated value and nearest control
        distance.

    """
    d = _haversine_km(lats, lons, target_lat, target_lon)
    nearest = float(d.min())
    # Exact hit on a control point: return it directly to avoid division by zero.
    if nearest < 1e-9:
        return IDWResult(value=float(values[int(np.argmin(d))]), nearest_km=0.0)
    w = 1.0 / np.power(d, power)
    value = float(np.sum(w * values) / np.sum(w))
    return IDWResult(value=value, nearest_km=nearest)


def idw_grid(
    lats: np.ndarray,
    lons: np.ndarray,
    values: np.ndarray,
    *,
    resolution: int = 80,
    power: float = 2.0,
    margin: float = 0.1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate a regular grid over the bounding box of the control points.

    Args:
        lats: Control-point latitudes (deg).
        lons: Control-point longitudes (deg).
        values: Control-point values (deg C).
        resolution: Number of grid cells per axis.
        power: IDW power exponent.
        margin: Fractional padding added around the data bounding box.

    Returns:
        ``(grid_lon, grid_lat, grid_value, grid_nearest_km)`` as 2-D arrays.
        ``grid_nearest_km`` lets the caller mask or fade cells that sit far
        from any control point (i.e. where the estimate is least reliable).

    """
    lat_pad = (lats.max() - lats.min()) * margin
    lon_pad = (lons.max() - lons.min()) * margin
    grid_lat_axis = np.linspace(lats.min() - lat_pad, lats.max() + lat_pad, resolution)
    grid_lon_axis = np.linspace(lons.min() - lon_pad, lons.max() + lon_pad, resolution)
    grid_lon, grid_lat = np.meshgrid(grid_lon_axis, grid_lat_axis)

    grid_value = np.empty_like(grid_lat)
    grid_nearest = np.empty_like(grid_lat)
    for i in range(resolution):
        for j in range(resolution):
            res = idw_interpolate(lats, lons, values, grid_lat[i, j], grid_lon[i, j], power=power)
            grid_value[i, j] = res.value
            grid_nearest[i, j] = res.nearest_km
    return grid_lon, grid_lat, grid_value, grid_nearest


def loocv(
    lats: np.ndarray,
    lons: np.ndarray,
    values: np.ndarray,
    *,
    power: float = 2.0,
) -> LOOCVResult:
    """Leave-one-out cross-validation of the IDW interpolation.

    For each control point, the interpolator predicts its value from all the
    others; the spread of (observed - predicted) errors measures how much the
    sparse network can be trusted to fill the gaps between wells.

    Args:
        lats: Control-point latitudes (deg).
        lons: Control-point longitudes (deg).
        values: Control-point values (deg C).
        power: IDW power exponent.

    Returns:
        A :class:`LOOCVResult` with RMSE, MAE, and per-point residuals.

    """
    n = len(values)
    residuals: list[float] = []
    for k in range(n):
        mask = np.arange(n) != k
        pred = idw_interpolate(lats[mask], lons[mask], values[mask], lats[k], lons[k], power=power)
        residuals.append(float(values[k] - pred.value))
    arr = np.array(residuals)
    rmse = float(np.sqrt(np.mean(arr**2)))
    mae = float(np.mean(np.abs(arr)))
    return LOOCVResult(
        rmse_c=round(rmse, 2),
        mae_c=round(mae, 2),
        n=n,
        power=power,
        residuals=[round(r, 2) for r in residuals],
    )
