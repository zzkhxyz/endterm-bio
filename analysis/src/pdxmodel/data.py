"""Download and select real PDX tumor-volume trajectories."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)
ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
SOURCE_URL = (
    "https://static-content.springer.com/esm/art%3A10.1038%2Fnm.3954/"
    "MediaObjects/41591_2015_BFnm3954_MOESM10_ESM.xlsx"
)
SOURCE_SHA256 = "c4b9a6903a4d1f76e3ddca4199039776d56bb99970aa5b7abe4f3abd732a0c6d"
RAW_PATH = ANALYSIS_ROOT / "data/raw/gao_2015_supplementary_table_1.xlsx"
CSV_PATH = ANALYSIS_ROOT / "data/processed/pdx_combo.csv"
SELECTION_PATH = ANALYSIS_ROOT / "data/processed/selection.json"
BIOMARKER_PATH = ANALYSIS_ROOT / "data/processed/selected_biomarkers.csv"
SOURCE_COLUMNS = {
    "Model": "pdx_id",
    "Tumor Type": "cancer_type",
    "Treatment": "treatment",
    "Days Post T0": "day",
    "Volume (mm3)": "volume_mm3",
}
MIN_POINTS = 6
MAX_LINES = 10


def sha256(path: Path) -> str:
    """Calculate a file digest without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_source(path: Path = RAW_PATH) -> Path:
    """Download the official, unmodified Nature supplementary workbook."""
    if path.exists():
        if sha256(path) != SOURCE_SHA256:
            raise ValueError(f"Existing source file has unexpected SHA-256: {path}")
        LOGGER.info("Using verified source file: %s", path)
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".xlsx.part")
    LOGGER.info("Downloading %s", SOURCE_URL)
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response, partial.open("wb") as out:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                out.write(chunk)
        if sha256(partial) != SOURCE_SHA256:
            raise ValueError("Downloaded source failed SHA-256 verification")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return path


def load_source(path: Path) -> pd.DataFrame:
    """Read original measurements and preserve the stated mm³ units."""
    data = pd.read_excel(path, sheet_name="PCT raw data", engine="openpyxl")
    missing = set(SOURCE_COLUMNS) - set(data.columns)
    if missing:
        raise ValueError(f"Source workbook is missing columns: {sorted(missing)}")
    data = data.rename(columns=SOURCE_COLUMNS)
    data["day"] = pd.to_numeric(data["day"], errors="coerce")
    data["volume_mm3"] = pd.to_numeric(data["volume_mm3"], errors="coerce")
    return data[list(SOURCE_COLUMNS.values())]


def eligible_groups(data: pd.DataFrame) -> dict[tuple[str, str, str], pd.DataFrame]:
    """Keep complete, positive series with unique days and a day-zero baseline."""
    accepted: dict[tuple[str, str, str], pd.DataFrame] = {}
    for key, group in data.groupby(["pdx_id", "cancer_type", "treatment"], dropna=False):
        if any(pd.isna(value) for value in key):
            continue
        series = group.sort_values("day").reset_index(drop=True)
        if len(series) < MIN_POINTS or series["day"].duplicated().any():
            continue
        if series[["day", "volume_mm3"]].isna().any().any():
            continue
        if not math.isclose(float(series.loc[0, "day"]), 0.0):
            continue
        if (series["volume_mm3"] <= 0).any():
            continue
        accepted[tuple(str(value) for value in key)] = series
    return accepted


def rank_combinations(
    groups: dict[tuple[str, str, str], pd.DataFrame],
) -> list[dict[str, object]]:
    """Rank all two-drug combinations by complete control/A/B/A+B quartets."""
    treatments = {key[2] for key in groups}
    rankings: list[dict[str, object]] = []
    for combo in sorted(t for t in treatments if " + " in t):
        agents = combo.split(" + ")
        if len(agents) != 2 or any(agent not in treatments for agent in agents):
            continue
        complete = [
            (pdx_id, cancer)
            for pdx_id, cancer, treatment in groups
            if treatment == combo
            and all((pdx_id, cancer, arm) in groups for arm in ("untreated", *agents))
        ]
        by_cancer = dict(sorted(Counter(cancer for _, cancer in complete).items()))
        rankings.append(
            {"combination": combo, "agents": agents, "quartets": len(complete), "by_cancer": by_cancer}
        )
    return sorted(rankings, key=lambda item: (-int(item["quartets"]), str(item["combination"])))


def select_lines(
    groups: dict[tuple[str, str, str], pd.DataFrame], ranking: dict[str, object]
) -> tuple[str, list[str]]:
    """Choose one cancer, then rank lines by coverage without looking at response."""
    by_cancer = ranking["by_cancer"]
    if not isinstance(by_cancer, dict) or not by_cancer:
        raise ValueError("No complete quartet exists")
    cancer = sorted(by_cancer, key=lambda name: (-by_cancer[name], name))[0]
    agents = ranking["agents"]
    combo = ranking["combination"]
    if not isinstance(agents, list) or not isinstance(combo, str):
        raise ValueError("Invalid ranking record")
    arms = ("untreated", *agents, combo)
    candidates = {
        pdx_id
        for pdx_id, tumor, treatment in groups
        if tumor == cancer and treatment == combo and all((pdx_id, cancer, arm) in groups for arm in arms)
    }

    def coverage(pdx_id: str) -> tuple[int, float, str]:
        series = [groups[(pdx_id, cancer, arm)] for arm in arms]
        return (
            min(len(part) for part in series),
            min(float(part["day"].max()) for part in series),
            pdx_id,
        )

    lines = sorted(candidates, key=lambda pdx_id: (-coverage(pdx_id)[0], -coverage(pdx_id)[1], pdx_id))
    return cancer, lines[:MAX_LINES]


def prepare_data(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select the leading combination and return a tidy observed-volume CSV."""
    groups = eligible_groups(data)
    rankings = rank_combinations(groups)
    if not rankings or not rankings[0]["quartets"]:
        raise ValueError("No complete control/A/B/A+B quartet passed the data filters")
    winner = rankings[0]
    cancer, lines = select_lines(groups, winner)
    agents = winner["agents"]
    combo = winner["combination"]
    if not isinstance(agents, list) or not isinstance(combo, str):
        raise ValueError("Invalid winning combination")
    labels = {"untreated": "control", agents[0]: "A", agents[1]: "B", combo: "A+B"}
    output = []
    for line in lines:
        for raw_treatment, treatment in labels.items():
            series = groups[(line, cancer, raw_treatment)].copy()
            series["treatment"] = treatment
            output.append(series)
    selected = pd.concat(output, ignore_index=True)[
        ["pdx_id", "cancer_type", "treatment", "day", "volume_mm3"]
    ]
    selected = selected.sort_values(["pdx_id", "treatment", "day"]).reset_index(drop=True)
    metadata: dict[str, object] = {
        "source_url": SOURCE_URL,
        "source_doi": "10.1038/nm.3954",
        "source_sha256": SOURCE_SHA256,
        "source_rows": len(data),
        "filter": "At least six measurements, complete positive volumes, unique days, day-zero baseline",
        "selection_rule": (
            "Largest quartet count across all cancers; cancer with most quartets; "
            "ten lines ranked by minimum group point count, then minimum last day, then PDX ID"
        ),
        "combination": combo,
        "treatment_labels": labels,
        "cancer_type": cancer,
        "eligible_quartets_in_cancer": winner["by_cancer"][cancer],
        "selected_pdx_ids": lines,
        "selected_lines": len(lines),
        "selected_mouse_trajectories": len(lines) * 4,
        "selected_measurements": len(selected),
        "candidate_rankings": rankings,
        "units": {"day": "days", "volume_mm3": "mm^3"},
    }
    return selected, metadata


def extract_selected_biomarkers(path: Path, pdx_ids: list[str]) -> pd.DataFrame:
    """Extract selected pathway alterations; missing records are not wild-type calls."""
    annotations = pd.read_excel(path, sheet_name="pdxe_mut_and_cn2", engine="openpyxl")
    required = {"Sample", "Gene", "Category", "Details"}
    if not required.issubset(annotations.columns):
        raise ValueError(f"Biomarker sheet is missing {sorted(required - set(annotations.columns))}")
    pathway_genes = {"PIK3CA", "PTEN", "AKT1", "ERBB2", "ERBB3"}
    selected = annotations.loc[
        annotations["Sample"].isin(pdx_ids) & annotations["Gene"].isin(pathway_genes),
        ["Sample", "Gene", "Category", "Details"],
    ].copy()
    selected.columns = ["pdx_id", "gene", "category", "details"]
    return selected.sort_values(["pdx_id", "gene", "category"]).reset_index(drop=True)


def main() -> None:
    """Run the reproducible Part A extraction pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Use a manually downloaded original XLSX")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    path = args.source if args.source else download_source()
    if sha256(path) != SOURCE_SHA256:
        raise ValueError("Source SHA-256 does not match the published workbook used here")
    selected, metadata = prepare_data(load_source(path))
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(CSV_PATH, index=False, float_format="%.6f")
    SELECTION_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    biomarkers = extract_selected_biomarkers(path, metadata["selected_pdx_ids"])
    biomarkers.to_csv(BIOMARKER_PATH, index=False)
    LOGGER.info("Saved %s rows from %s PDX lines to %s", len(selected), metadata["selected_lines"], CSV_PATH)
    LOGGER.info("Saved %s selected biomarker records to %s", len(biomarkers), BIOMARKER_PATH)


if __name__ == "__main__":
    main()
