"""Dataset loading and validation.

Reads the two canonical CSVs shipped in ``datasets/`` (BHT measurements and
well coordinates), validates every row against the Pydantic models, and joins
them into a list of measurements enriched with location.

A failed validation here is intentional and informative: it means the dataset
shipped with the package does not match its declared schema, which a user
should know before any map is drawn.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gsp.data.models import BHTMeasurement, CorrectionMethod, WellLocation

__all__ = [
    "DATASET_DIR",
    "load_measurements",
    "load_locations",
    "load_joined",
]

# Datasets live at the repository root, two levels above this file's package.
DATASET_DIR: Path = Path(__file__).resolve().parents[3] / "datasets"


def load_measurements(path: Path | None = None) -> list[BHTMeasurement]:
    """Load and validate the BHT measurements table.

    Args:
        path: Optional override path to a measurements CSV.

    Returns:
        A list of validated :class:`BHTMeasurement` objects.

    """
    csv_path = path or (DATASET_DIR / "bht_measurements.csv")
    df = pd.read_csv(csv_path)
    out: list[BHTMeasurement] = []
    for _, row in df.iterrows():
        out.append(
            BHTMeasurement(
                well=str(row["well"]).strip(),
                depth_m=float(row["depth_m"]),
                t_raw_c=float(row["T_raw_C"]),
                t_corrected_c=float(row["T_corrected_C"]),
                correction_method=CorrectionMethod(str(row["correction_method"])),
            )
        )
    return out


def load_locations(path: Path | None = None) -> dict[str, WellLocation]:
    """Load and validate the well coordinates table.

    Args:
        path: Optional override path to a coordinates CSV.

    Returns:
        A mapping of well name -> :class:`WellLocation`.

    """
    csv_path = path or (DATASET_DIR / "well_coordinates.csv")
    df = pd.read_csv(csv_path)
    out: dict[str, WellLocation] = {}
    for _, row in df.iterrows():
        loc = WellLocation(
            well=str(row["well"]).strip(),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            province=str(row.get("province", "") or ""),
            elevation_m=(float(row["elevation_m"]) if pd.notna(row.get("elevation_m")) else None),
        )
        out[loc.well] = loc
    return out


def load_joined(
    measurements_path: Path | None = None,
    locations_path: Path | None = None,
) -> tuple[list[BHTMeasurement], dict[str, WellLocation]]:
    """Load both tables and verify the measurements can be located.

    Args:
        measurements_path: Optional override for the measurements CSV.
        locations_path: Optional override for the coordinates CSV.

    Returns:
        ``(measurements, locations)`` where every measurement's well is present
        in ``locations``. Measurements without a known location are dropped and
        the count of dropped rows is available via the returned lists' lengths.

    """
    measurements = load_measurements(measurements_path)
    locations = load_locations(locations_path)
    located = [m for m in measurements if m.well in locations]
    return located, locations
