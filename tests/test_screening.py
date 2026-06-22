"""Tests for the geothermal screening package."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from gsp.data.loader import load_joined, load_locations, load_measurements
from gsp.data.models import SuitabilityClass
from gsp.interpolation.idw import idw_interpolate, loocv
from gsp.interpolation.tuning import tune_power
from gsp.pipeline import run_pipeline
from gsp.screening.engine import classify, geothermal_gradient, screen_wells


def test_datasets_load_and_validate() -> None:
    measurements = load_measurements()
    locations = load_locations()
    assert len(measurements) > 0
    assert len(locations) > 0
    # Every measurement temperature is physical.
    for m in measurements:
        assert -10 < m.t_corrected_c < 400
        assert m.depth_m > 0


def test_join_keeps_only_locatable_wells() -> None:
    measurements, locations = load_joined()
    for m in measurements:
        assert m.well in locations


def test_gradient_is_positive_and_reasonable() -> None:
    g = geothermal_gradient(80.0, 3000.0, surface_temperature_c=15.0)
    # (80-15)/3 = 21.67 C/km, a typical continental gradient.
    assert 20 < g < 23


def test_gradient_zero_depth_guard() -> None:
    assert geothermal_gradient(80.0, 0.0, surface_temperature_c=15.0) == 0.0


@pytest.mark.parametrize(
    ("temp", "depth", "expected"),
    [
        (140.0, 4000.0, SuitabilityClass.POWER_GENERATION),
        (90.0, 3000.0, SuitabilityClass.DIRECT_USE),
        (50.0, 1500.0, SuitabilityClass.GROUND_SOURCE_HP),
        (30.0, 1000.0, SuitabilityClass.BELOW_THRESHOLD),
        # Hot but shallow: fails power/direct depth gate, drops to GSHP.
        (130.0, 500.0, SuitabilityClass.GROUND_SOURCE_HP),
    ],
)
def test_classify(temp: float, depth: float, expected: SuitabilityClass) -> None:
    assert classify(temp, depth) == expected


def test_screen_wells_uses_deepest_measurement() -> None:
    measurements, locations = load_joined()
    results = screen_wells(measurements, locations)
    by_well = {}
    for m in measurements:
        by_well.setdefault(m.well, []).append(m.depth_m)
    for r in results:
        assert r.depth_m == pytest.approx(max(by_well[r.well]))


def test_screen_results_sorted_descending() -> None:
    measurements, locations = load_joined()
    results = screen_wells(measurements, locations)
    temps = [r.t_corrected_c for r in results]
    assert temps == sorted(temps, reverse=True)


def test_idw_exact_hit_returns_control_value() -> None:
    lats = np.array([45.0, 45.5, 44.5])
    lons = np.array([8.0, 8.5, 7.5])
    vals = np.array([20.0, 25.0, 30.0])
    res = idw_interpolate(lats, lons, vals, 45.0, 8.0)
    assert res.value == pytest.approx(20.0)
    assert res.nearest_km == pytest.approx(0.0)


def test_idw_interpolation_within_value_range() -> None:
    lats = np.array([45.0, 45.5, 44.5])
    lons = np.array([8.0, 8.5, 7.5])
    vals = np.array([20.0, 25.0, 30.0])
    res = idw_interpolate(lats, lons, vals, 45.1, 8.1)
    assert 20.0 <= res.value <= 30.0


def test_loocv_returns_sane_error() -> None:
    measurements, locations = load_joined()
    results = screen_wells(measurements, locations)
    lats = np.array([r.lat for r in results])
    lons = np.array([r.lon for r in results])
    grads = np.array([r.gradient_c_per_km for r in results])
    cv = loocv(lats, lons, grads, power=1.0)
    assert cv.n == len(results)
    assert cv.rmse_c > 0
    assert cv.mae_c <= cv.rmse_c  # MAE is always <= RMSE


def test_tune_power_selects_minimum_rmse() -> None:
    measurements, locations = load_joined()
    results = screen_wells(measurements, locations)
    lats = np.array([r.lat for r in results])
    lons = np.array([r.lon for r in results])
    grads = np.array([r.gradient_c_per_km for r in results])
    ps = tune_power(lats, lons, grads)
    rmses = [rmse for _, rmse in ps.sweep]
    assert ps.best.rmse_c == pytest.approx(min(rmses))


def test_pipeline_end_to_end() -> None:
    out = run_pipeline(interpolate=True, grid_resolution=20)
    assert len(out.results) >= 30
    assert out.field is not None
    assert out.field.loocv_rmse_c_per_km > 0
    # Grid predicted-temperature is physical everywhere.
    temp = out.field.predicted_temperature(2000.0)
    assert np.all(temp > 0)
    assert np.all(temp < 300)


def test_pipeline_without_interpolation() -> None:
    out = run_pipeline(interpolate=False)
    assert out.field is None
    assert out.power_search is None
    assert len(out.results) >= 30


def test_results_immutable() -> None:
    out = run_pipeline(interpolate=False)
    with pytest.raises(ValidationError):
        out.results[0].t_corrected_c = 99.0  # type: ignore[misc]
