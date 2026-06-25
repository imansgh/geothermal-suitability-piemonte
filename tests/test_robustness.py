"""Tests for classification robustness under BHT-correction uncertainty."""

from __future__ import annotations

from gsp.data.models import SuitabilityClass
from gsp.pipeline import run_pipeline
from gsp.screening.engine import load_thresholds
from gsp.screening.robustness import (
    classification_robustness,
    robustness_report,
)

_DT = float(load_thresholds()["bht_uncertainty_c"])


def test_deep_interior_well_is_robust() -> None:
    # Well far above the power gate (120 C) and deep: stable in both directions.
    r = classification_robustness(160.0, 4000.0)
    assert r.suitability is SuitabilityClass.POWER_GENERATION
    assert r.is_robust
    assert r.class_low is SuitabilityClass.POWER_GENERATION
    assert r.class_high is SuitabilityClass.POWER_GENERATION


def test_well_on_power_gate_is_not_robust() -> None:
    # Sitting exactly on the 120 C power gate at adequate depth: dropping by dT
    # falls to Direct Use, so the class is fragile.
    r = classification_robustness(120.0, 2000.0)
    assert r.suitability is SuitabilityClass.POWER_GENERATION
    assert not r.is_robust
    assert r.class_low is SuitabilityClass.DIRECT_USE
    assert r.temperature_margin_c == 0.0


def test_margin_is_distance_to_nearest_eligible_gate() -> None:
    # At 2000 m all three gates (40, 60, 120) are depth-eligible; nearest to 100
    # is 120 -> margin 20.
    r = classification_robustness(100.0, 2000.0)
    assert r.temperature_margin_c == 20.0


def test_shallow_well_depth_gate_respected() -> None:
    # Hot but shallow: power/direct require >=1000 m, so it can only be GSHP and
    # the only eligible gate is 40 C -> robustly GSHP well above it.
    r = classification_robustness(130.0, 500.0)
    assert r.suitability is SuitabilityClass.GROUND_SOURCE_HP
    assert r.is_robust


def test_robustness_report_covers_every_well() -> None:
    out = run_pipeline(interpolate=False)
    report = robustness_report(out.results)
    assert len(report) == len(out.results)
    assert {r.well for r in report} == {r.well for r in out.results}
    # Nominal class in the report matches the screening result.
    nominal = {r.well: r.suitability for r in report}
    for res in out.results:
        assert nominal[res.well] is res.suitability


def test_uncertainty_band_recorded() -> None:
    r = classification_robustness(80.0, 2000.0)
    assert r.bht_uncertainty_c == _DT
