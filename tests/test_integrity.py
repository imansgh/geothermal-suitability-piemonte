"""Tests for the dataset-integrity checks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gsp.data.integrity import (
    assert_dataset_integrity,
    check_dataset_integrity,
)


def test_shipped_dataset_is_clean() -> None:
    report = check_dataset_integrity()
    assert report.ok, [iss.problem for iss in report.issues]
    assert report.n_rows > 0
    assert report.issues == []


def test_assert_passes_on_clean_dataset() -> None:
    # Should not raise.
    assert_dataset_integrity()


def _write_pair(tmp_path: Path, df: pd.DataFrame) -> tuple[Path, Path]:
    m = tmp_path / "m.csv"
    c = tmp_path / "c.csv"
    df.to_csv(m, index=False)
    coords = pd.DataFrame(
        {"well": df["well"].unique(), "lat": 45.0, "lon": 8.0, "province": "X"}
    )
    coords.to_csv(c, index=False)
    return m, c


def _base_row() -> dict[str, object]:
    return {
        "well": "W1",
        "depth_m": 2000.0,
        "T_raw_C": 60.0,
        "T_bench_C": 70.0,
        "T_anal_C": 65.0,
        "T_hyb_C": 65.0,
        "T_horn_C": "",
        "T_corrected_C": 65.0,
        "correction_method": "Hybrid",
    }


def test_detects_corrected_mismatch(tmp_path: Path) -> None:
    row = _base_row()
    row["T_corrected_C"] = 99.0  # no longer equals T_hyb_C
    m, c = _write_pair(tmp_path, pd.DataFrame([row]))
    report = check_dataset_integrity(m, c)
    assert not report.ok
    assert any("!=" in iss.problem for iss in report.issues)


def test_detects_cooling_correction(tmp_path: Path) -> None:
    row = _base_row()
    row["T_hyb_C"] = 50.0
    row["T_corrected_C"] = 50.0  # below raw 60 -> cooling
    m, c = _write_pair(tmp_path, pd.DataFrame([row]))
    report = check_dataset_integrity(m, c)
    assert any("cooling" in iss.problem for iss in report.issues)


def test_detects_unknown_method(tmp_path: Path) -> None:
    row = _base_row()
    row["correction_method"] = "Magic"
    m, c = _write_pair(tmp_path, pd.DataFrame([row]))
    report = check_dataset_integrity(m, c)
    assert any("unknown correction_method" in iss.problem for iss in report.issues)


def test_assert_raises_on_bad_dataset(tmp_path: Path) -> None:
    row = _base_row()
    row["T_corrected_C"] = 99.0
    m, c = _write_pair(tmp_path, pd.DataFrame([row]))
    with pytest.raises(ValueError, match="integrity check failed"):
        assert_dataset_integrity(m, c)
