"""Integrity checks for the committed, observed Part A cohort."""

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_processed_cohort_has_complete_quartets() -> None:
    """Every selected line must have four usable measured trajectories."""
    data = pd.read_csv(ROOT / "data/processed/pdx_combo.csv")
    metadata = json.loads((ROOT / "data/processed/selection.json").read_text(encoding="utf-8"))
    assert list(data.columns) == ["pdx_id", "cancer_type", "treatment", "day", "volume_mm3"]
    assert len(data) == metadata["selected_measurements"]
    assert set(data["pdx_id"]) == set(metadata["selected_pdx_ids"])
    assert set(data["cancer_type"]) == {metadata["cancer_type"]}
    assert set(data["treatment"]) == {"control", "A", "B", "A+B"}
    assert not data.isna().any().any()
    assert not data.duplicated(["pdx_id", "treatment", "day"]).any()
    assert (data["volume_mm3"] > 0).all()
    for _, series in data.groupby(["pdx_id", "treatment"]):
        assert len(series) >= 6
        assert series["day"].min() == 0
