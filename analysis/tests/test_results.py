"""Verify committed fit exports remain usable by analysis and web."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_results_are_source_aligned_and_shared_with_web() -> None:
    """The future site must read the same complete numerical result as analysis."""
    analysis_bytes = (ROOT / "analysis/outputs/results.json").read_bytes()
    web_bytes = (ROOT / "web/public/data/results.json").read_bytes()
    assert analysis_bytes == web_bytes
    result = json.loads(analysis_bytes)
    selection = json.loads((ROOT / "analysis/data/processed/selection.json").read_text())
    assert len(result["trajectories"]) == selection["selected_measurements"]
    assert result["metrics"]["n_observations"] == selection["selected_measurements"]
    assert result["bootstrap_uncertainty"]["completed_replicates"] >= 200
    assert {"e_A", "e_B", "psi"} <= set(result["profile_likelihood"])
