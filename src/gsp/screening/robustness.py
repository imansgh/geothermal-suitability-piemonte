"""Robustness of the suitability classification to BHT-correction uncertainty.

The nominal classification (:func:`gsp.screening.engine.classify`) maps a
corrected temperature and depth to a single :class:`SuitabilityClass` using
hard gates. Near a gate, a small error in the corrected temperature can flip the
class — a well screened at 119 deg C is "Direct Use", at 121 deg C it is "Power
Generation". Because archive BHT data carry a residual correction uncertainty of
several deg C, reporting the bare class without its fragility would overstate
what the data support.

This module makes that fragility explicit and **deterministic**. It does not
change the nominal classification. For each well it:

* re-classifies at ``T - dT`` and ``T + dT`` (``dT`` = configured 1-sigma BHT
  uncertainty), holding depth fixed, and
* computes the signed temperature margin to the nearest depth-eligible gate.

A well is ``robust`` only if its class is unchanged across the whole
``[T - dT, T + dT]`` band. The depth gates are respected exactly, so a hot but
shallow well that cannot reach a depth-gated class is handled correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gsp.data.models import SuitabilityClass, WellScreeningResult
from gsp.screening.engine import classify, load_thresholds

__all__ = [
    "ClassificationRobustness",
    "classification_robustness",
    "robustness_report",
]


@dataclass(frozen=True)
class ClassificationRobustness:
    """Fragility of one well's suitability class under BHT uncertainty.

    Attributes:
        well: Well name.
        suitability: Nominal class at the reported corrected temperature.
        class_low: Class at ``T - bht_uncertainty_c``.
        class_high: Class at ``T + bht_uncertainty_c``.
        temperature_margin_c: Distance (deg C, non-negative) from the corrected
            temperature to the nearest depth-eligible class boundary. Smaller
            means closer to a gate. ``inf`` when no gate boundary applies.
        bht_uncertainty_c: The 1-sigma band used (deg C).
        is_robust: True iff the class is unchanged across the full band.

    """

    well: str
    suitability: SuitabilityClass
    class_low: SuitabilityClass
    class_high: SuitabilityClass
    temperature_margin_c: float
    bht_uncertainty_c: float
    is_robust: bool


def _eligible_temperature_gates(depth_m: float, classes: dict[str, Any]) -> list[float]:
    """Temperature thresholds of classes whose depth gate is met at ``depth_m``."""
    gates: list[float] = []
    for spec in classes.values():
        if depth_m >= float(spec["min_depth_m"]):
            gates.append(float(spec["min_temperature_c"]))
    return gates


def classification_robustness(
    t_corrected_c: float,
    depth_m: float,
    *,
    thresholds: dict[str, Any] | None = None,
    well: str = "",
) -> ClassificationRobustness:
    """Assess how fragile a single well's class is to BHT-correction error.

    Args:
        t_corrected_c: Corrected static formation temperature, deg C.
        depth_m: Depth of the governing reading, metres.
        thresholds: Optional pre-loaded thresholds (defaults to the config).
        well: Optional well name to carry into the result.

    Returns:
        A :class:`ClassificationRobustness` for the reading.

    """
    cfg = thresholds or load_thresholds()
    dt = float(cfg["bht_uncertainty_c"])

    nominal = classify(t_corrected_c, depth_m, thresholds=cfg)
    low = classify(t_corrected_c - dt, depth_m, thresholds=cfg)
    high = classify(t_corrected_c + dt, depth_m, thresholds=cfg)

    gates = _eligible_temperature_gates(depth_m, cfg["classes"])
    margin = min((abs(t_corrected_c - g) for g in gates), default=float("inf"))

    return ClassificationRobustness(
        well=well,
        suitability=nominal,
        class_low=low,
        class_high=high,
        temperature_margin_c=round(margin, 2) if margin != float("inf") else margin,
        bht_uncertainty_c=dt,
        is_robust=(low == nominal == high),
    )


def robustness_report(
    results: list[WellScreeningResult],
    *,
    thresholds: dict[str, Any] | None = None,
) -> list[ClassificationRobustness]:
    """Robustness assessment for every screened well.

    Args:
        results: Per-well screening results (from ``screen_wells``).
        thresholds: Optional pre-loaded thresholds (defaults to the config).

    Returns:
        One :class:`ClassificationRobustness` per well, in the input order.

    """
    cfg = thresholds or load_thresholds()
    return [
        classification_robustness(
            r.t_corrected_c, r.depth_m, thresholds=cfg, well=r.well
        )
        for r in results
    ]
