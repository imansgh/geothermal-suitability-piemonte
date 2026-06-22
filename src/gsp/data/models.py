"""Immutable data contracts for wells, measurements, and screening results.

All models are Pydantic v2 ``frozen`` models: they represent observed facts or
computed artefacts that must not mutate after construction. Keeping the schema
explicit means a malformed dataset fails loudly at load time rather than
producing a silently wrong map.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CorrectionMethod",
    "SuitabilityClass",
    "BHTMeasurement",
    "WellLocation",
    "WellScreeningResult",
]


class CorrectionMethod(StrEnum):
    """How a bottom-hole temperature was corrected to static formation T."""

    HORNER = "Horner"
    HYBRID = "Hybrid"


class SuitabilityClass(StrEnum):
    """Geothermal reuse category assigned to a well.

    The categories follow the conventional direct-use / power thresholds used
    in low-enthalpy geothermal screening. Values are ordered by resource grade.
    """

    POWER_GENERATION = "Power Generation"
    DIRECT_USE = "Direct Use"
    GROUND_SOURCE_HP = "Ground Source Heat Pump"
    BELOW_THRESHOLD = "Below Threshold"


class BHTMeasurement(BaseModel):
    """A single bottom-hole temperature observation at one depth.

    Attributes:
        well: Well name (matches the coordinates table).
        depth_m: Measured depth of the reading, in metres.
        t_raw_c: Uncorrected bottom-hole temperature, deg C.
        t_corrected_c: Static formation temperature after correction, deg C.
        correction_method: Which correction produced ``t_corrected_c``.

    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    well: str = Field(..., min_length=1)
    depth_m: float = Field(..., gt=0)
    t_raw_c: float = Field(..., description="Uncorrected BHT, deg C.")
    t_corrected_c: float = Field(..., description="Corrected static T, deg C.")
    correction_method: CorrectionMethod = Field(default=CorrectionMethod.HYBRID)


class WellLocation(BaseModel):
    """Surface location and elevation of a well.

    Attributes:
        well: Well name (join key).
        lat: Latitude, WGS84 decimal degrees.
        lon: Longitude, WGS84 decimal degrees.
        province: Administrative province (for grouping/labels).
        elevation_m: Ground elevation above sea level, in metres.

    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    well: str = Field(..., min_length=1)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    province: str = Field(default="")
    elevation_m: float | None = Field(default=None)


class WellScreeningResult(BaseModel):
    """The geothermal screening outcome for one well.

    Built from the deepest credible measurement per well (the deepest reading
    is the most representative of the recoverable thermal resource).

    Attributes:
        well: Well name.
        lat: Latitude, WGS84.
        lon: Longitude, WGS84.
        province: Administrative province.
        depth_m: Depth of the governing (deepest) measurement, metres.
        t_raw_c: Raw BHT at that depth, deg C.
        t_corrected_c: Corrected static T at that depth, deg C.
        gradient_c_per_km: Apparent geothermal gradient from surface, deg C/km.
        suitability: Assigned geothermal reuse class.
        n_measurements: Number of BHT readings available for the well.

    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    well: str
    lat: float
    lon: float
    province: str
    depth_m: float
    t_raw_c: float
    t_corrected_c: float
    gradient_c_per_km: float
    suitability: SuitabilityClass
    n_measurements: int
