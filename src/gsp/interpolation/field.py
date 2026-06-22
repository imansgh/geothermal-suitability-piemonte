"""Predicted-temperature field at a reference depth.

Interpolating bottom-hole temperature directly is physically unsound because
temperature is dominated by depth, and the wells span 834-5245 m. The correct
quantity to interpolate spatially is the geothermal *gradient*, which has the
depth dependence removed. This module interpolates the gradient field and then
evaluates a predicted temperature at a user-chosen reference depth:

    T(x, y, z_ref) = T_surface + gradient_interp(x, y) * z_ref

The accompanying LOOCV error is reported on the gradient field (deg C/km), so
the uncertainty is attached to the quantity actually interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gsp.interpolation.idw import idw_grid, loocv
from gsp.interpolation.tuning import tune_power

__all__ = ["GradientField", "build_gradient_field"]


@dataclass(frozen=True)
class GradientField:
    """An interpolated geothermal-gradient surface and its validation.

    Attributes:
        grid_lon: 2-D longitude grid (deg).
        grid_lat: 2-D latitude grid (deg).
        grid_gradient: 2-D interpolated gradient (deg C/km).
        grid_nearest_km: 2-D distance to nearest control point (km).
        best_power: IDW power chosen by LOOCV.
        loocv_rmse_c_per_km: Cross-validated gradient RMSE (deg C/km).
        loocv_mae_c_per_km: Cross-validated gradient MAE (deg C/km).
        surface_temperature_c: Surface temperature used for T prediction.

    """

    grid_lon: np.ndarray
    grid_lat: np.ndarray
    grid_gradient: np.ndarray
    grid_nearest_km: np.ndarray
    best_power: float
    loocv_rmse_c_per_km: float
    loocv_mae_c_per_km: float
    surface_temperature_c: float

    def predicted_temperature(self, depth_m: float) -> np.ndarray:
        """Predicted temperature grid at a reference depth.

        Args:
            depth_m: Reference depth, metres.

        Returns:
            2-D predicted-temperature grid (deg C).

        """
        return self.surface_temperature_c + self.grid_gradient * (depth_m / 1000.0)


def build_gradient_field(
    lats: np.ndarray,
    lons: np.ndarray,
    gradients: np.ndarray,
    *,
    surface_temperature_c: float,
    resolution: int = 80,
) -> GradientField:
    """Build the interpolated gradient field with tuned power and LOOCV.

    Args:
        lats: Well latitudes (deg).
        lons: Well longitudes (deg).
        gradients: Per-well geothermal gradient (deg C/km).
        surface_temperature_c: Surface temperature for T prediction.
        resolution: Grid cells per axis.

    Returns:
        A populated :class:`GradientField`.

    """
    tune = tune_power(lats, lons, gradients)
    power = tune.best_power
    cv = loocv(lats, lons, gradients, power=power)
    grid_lon, grid_lat, grid_grad, grid_near = idw_grid(
        lats, lons, gradients, resolution=resolution, power=power
    )
    return GradientField(
        grid_lon=grid_lon,
        grid_lat=grid_lat,
        grid_gradient=grid_grad,
        grid_nearest_km=grid_near,
        best_power=power,
        loocv_rmse_c_per_km=cv.rmse_c,
        loocv_mae_c_per_km=cv.mae_c,
        surface_temperature_c=surface_temperature_c,
    )
