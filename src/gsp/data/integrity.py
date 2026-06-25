"""Dataset-integrity checks for the BHT archive.

The Pydantic models validate that each row is *well-formed*; they cannot check
relationships *between* columns or *between* tables. The corrected temperature
shipped in the dataset is produced upstream (analytical / Horner / hybrid
correction), so the in-repo guarantee a reader most needs is that the dataset is
internally consistent with how it says it was built. This module verifies the
invariants that must hold for the corrected column to be trustworthy:

* ``T_corrected_C`` equals the column named by ``correction_method``
  (Hybrid -> ``T_hyb_C``, Horner -> ``T_horn_C``);
* the correction is non-cooling (``T_corrected_C >= T_raw_C``);
* temperatures and depths are physically plausible;
* every measured well has coordinates.

A clean report is a reproducibility statement: anyone re-running the pipeline is
using the same corrected temperatures the methodology describes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from gsp.data.loader import DATASET_DIR

__all__ = [
    "IntegrityIssue",
    "IntegrityReport",
    "check_dataset_integrity",
    "assert_dataset_integrity",
]

# Method -> the dataset column that should equal T_corrected_C for that method.
_METHOD_COLUMN = {"Hybrid": "T_hyb_C", "Horner": "T_horn_C"}

# Physical plausibility envelope for corrected formation temperature, deg C.
_T_MIN_C = -10.0
_T_MAX_C = 400.0

# Tolerance for the corrected==method-column equality check, deg C.
_EQ_TOL_C = 0.01


@dataclass(frozen=True)
class IntegrityIssue:
    """A single dataset-integrity violation.

    Attributes:
        row: Zero-based row index in the measurements table (-1 for table-level
            or cross-table issues).
        well: Well name associated with the issue (empty if not row-scoped).
        problem: Human-readable description of the violation.

    """

    row: int
    well: str
    problem: str


@dataclass(frozen=True)
class IntegrityReport:
    """Result of a dataset-integrity scan.

    Attributes:
        ok: True iff no issues were found.
        n_rows: Number of measurement rows scanned.
        issues: All violations found (empty when ``ok``).

    """

    ok: bool
    n_rows: int
    issues: list[IntegrityIssue] = field(default_factory=list)


def check_dataset_integrity(
    measurements_path: Path | None = None,
    locations_path: Path | None = None,
) -> IntegrityReport:
    """Scan the shipped dataset for internal-consistency violations.

    Args:
        measurements_path: Optional override for the measurements CSV.
        locations_path: Optional override for the coordinates CSV.

    Returns:
        An :class:`IntegrityReport`. The scan never raises on a *data* problem;
        it records it as an issue. Use :func:`assert_dataset_integrity` to turn
        a non-clean report into an exception.

    """
    m_path = measurements_path or (DATASET_DIR / "bht_measurements.csv")
    c_path = locations_path or (DATASET_DIR / "well_coordinates.csv")
    df = pd.read_csv(m_path)
    coords = pd.read_csv(c_path)
    known_wells = {str(w).strip() for w in coords["well"]}

    issues: list[IntegrityIssue] = []
    for i, (_, row) in enumerate(df.iterrows()):
        well = str(row["well"]).strip()
        t_raw = float(row["T_raw_C"])
        t_corr = float(row["T_corrected_C"])
        method = str(row["correction_method"]).strip()

        if method not in _METHOD_COLUMN:
            issues.append(IntegrityIssue(i, well, f"unknown correction_method '{method}'"))
        else:
            col = _METHOD_COLUMN[method]
            src = row.get(col)
            if pd.isna(src):
                issues.append(
                    IntegrityIssue(i, well, f"{method} row has empty source column {col}")
                )
            elif abs(float(src) - t_corr) > _EQ_TOL_C:
                issues.append(
                    IntegrityIssue(
                        i,
                        well,
                        f"T_corrected_C ({t_corr}) != {col} ({float(src)}) for {method}",
                    )
                )

        if t_corr < t_raw - _EQ_TOL_C:
            issues.append(
                IntegrityIssue(i, well, f"corrected ({t_corr}) below raw ({t_raw}): cooling")
            )
        if not (_T_MIN_C < t_corr < _T_MAX_C):
            issues.append(IntegrityIssue(i, well, f"corrected T {t_corr} outside physical range"))
        if float(row["depth_m"]) <= 0:
            issues.append(IntegrityIssue(i, well, f"non-positive depth {row['depth_m']}"))
        if well not in known_wells:
            issues.append(IntegrityIssue(i, well, "no coordinates for well"))

    return IntegrityReport(ok=not issues, n_rows=len(df), issues=issues)


def assert_dataset_integrity(
    measurements_path: Path | None = None,
    locations_path: Path | None = None,
) -> None:
    """Raise ``ValueError`` if the dataset fails any integrity check.

    Args:
        measurements_path: Optional override for the measurements CSV.
        locations_path: Optional override for the coordinates CSV.

    Raises:
        ValueError: If one or more integrity issues are found, listing them.

    """
    report = check_dataset_integrity(measurements_path, locations_path)
    if not report.ok:
        lines = "\n".join(
            f"  row {iss.row} [{iss.well}]: {iss.problem}" for iss in report.issues
        )
        raise ValueError(
            f"Dataset integrity check failed ({len(report.issues)} issue(s)):\n{lines}"
        )
