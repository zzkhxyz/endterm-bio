"""Run the fitted analysis and export source-backed numerical results."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import replace

import numpy as np
import pandas as pd

from pdxmodel.config import CONFIG
from pdxmodel.data import ANALYSIS_ROOT, CSV_PATH
from pdxmodel.fit import run_fit
from pdxmodel.model import Cohort, bliss_effect, combo_a_effect, parameter_names
from pdxmodel.plots import (
    COLORS,
    plot_correlation,
    plot_fit,
    plot_profiles,
    plot_residuals,
    plot_sensitivity,
)
from pdxmodel.sensitivity import local_sensitivity
from pdxmodel.uncertainty import block_wild_bootstrap, jacobian_diagnostics, profile_likelihood

RESULT_PATH = ANALYSIS_ROOT / "outputs/results.json"
FIGURE_DIR = ANALYSIS_ROOT / "outputs/figures"
WEB_DATA_PATH = ANALYSIS_ROOT.parent / "web/public/data/results.json"


def add_summary(result: dict[str, object]) -> None:
    """Add a cautious, machine-readable interpretation from fitted diagnostics."""
    parameters = result["parameters"]
    metrics = result["metrics"]
    bootstrap = result.get("bootstrap_uncertainty")
    profiles = result.get("profile_likelihood")
    if not isinstance(parameters, dict) or not isinstance(metrics, dict):
        raise ValueError("Missing fitted result fields")
    e_a = float(parameters["e_A"])
    e_b = float(parameters["e_B"])
    psi = float(parameters["psi"])
    pair_a = combo_a_effect(e_a)
    psi_ci = bootstrap["ci95"]["psi"] if isinstance(bootstrap, dict) else None
    profile_ci = profiles["psi"]["ci95"] if isinstance(profiles, dict) else None
    p_value = float(metrics["lrt_p_value"])
    scenario = result.get("dose_assumption_sensitivity")
    unstable_dose = isinstance(scenario, dict) and scenario["equal_dose_lrt_p_value"] >= 0.05
    if unstable_dose:
        conclusion = "Dose-sensitive apparent synergy; interaction not robustly identified"
    elif psi_ci is None or profile_ci is None or p_value >= 0.05 or (psi_ci[0] <= 0 <= psi_ci[1]):
        conclusion = "Interaction sign not identified; no evidence for synergy over Bliss"
    else:
        conclusion = "Synergy supported" if psi > 0 else "Antagonism supported"
    trajectories = result.get("trajectories", [])
    weighted = np.asarray([row["weighted_log_residual"] for row in trajectories], dtype=float)
    capacities = np.asarray([value for key, value in parameters.items() if key.startswith("K1000_")])
    result["summary"] = {
        "conclusion": conclusion,
        "psi_point": psi,
        "psi_bootstrap_ci95": psi_ci,
        "psi_profile_ci95": profile_ci,
        "lrt_p_value": p_value,
        "e_a": e_a,
        "e_a_at_combo_dose": pair_a,
        "e_b": e_b,
        "bliss_effect": bliss_effect(pair_a, e_b, 0.0),
        "fitted_combo_effect": bliss_effect(pair_a, e_b, psi),
        "drug_a_kill_per_day": CONFIG.kill_ceiling_per_day * e_a,
        "drug_b_kill_per_day": CONFIG.kill_ceiling_per_day * e_b,
        "fitted_combo_kill_per_day": CONFIG.kill_ceiling_per_day * bliss_effect(pair_a, e_b, psi),
        "rmse_log_volume": float(np.sqrt(np.mean((weighted * CONFIG.sigma_log) ** 2))),
        "capacity_parameters_at_bound": int(
            np.count_nonzero(
                np.isclose(capacities, CONFIG.carrying_capacity_1000_bounds[0], atol=1e-5)
                | np.isclose(capacities, CONFIG.carrying_capacity_1000_bounds[1], atol=1e-5)
            )
        ),
        "warning": "Structured residuals and bound-constrained capacities limit inference",
    }


def add_dose_sensitivity(result: dict[str, object], cohort: Cohort) -> None:
    """Refit under equal A dose to expose dependence on dose extrapolation."""
    equal_dose_fit = run_fit(cohort, replace(CONFIG, combo_a_dose_ratio=1.0))
    result["dose_assumption_sensitivity"] = {
        "description": "Alternative equal A dose assumption; all parameters refitted",
        "equal_dose_ratio": 1.0,
        "equal_dose_psi_point": float(equal_dose_fit.parameters[-1]),
        "equal_dose_lrt_p_value": equal_dose_fit.metrics["lrt_p_value"],
        "equal_dose_delta_aic_bliss_minus_full": equal_dose_fit.metrics[
            "delta_aic_bliss_minus_full"
        ],
        "equal_dose_delta_bic_bliss_minus_full": equal_dose_fit.metrics[
            "delta_bic_bliss_minus_full"
        ],
    }


def main() -> None:
    """Run the data-backed ODE analysis."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fit-only", action="store_true", help="Skip slow uncertainty diagnostics")
    mode.add_argument("--profiles-only", action="store_true", help="Recompute profiles, reuse saved bootstrap")
    mode.add_argument("--dose-only", action="store_true", help="Recompute dose scenario, reuse saved diagnostics")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cohort = Cohort.from_frame(pd.read_csv(CSV_PATH))
    fit = run_fit(cohort, CONFIG)
    if args.profiles_only:
        result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        result["profile_likelihood"] = profile_likelihood(fit, cohort, CONFIG)
        add_summary(result)
        plot_profiles(result["profile_likelihood"], FIGURE_DIR)
        plot_fit(fit, cohort, FIGURE_DIR)
        payload = json.dumps(result, indent=2) + "\n"
        for path in (RESULT_PATH, WEB_DATA_PATH):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        return
    if args.dose_only:
        result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        add_dose_sensitivity(result, cohort)
        add_summary(result)
        payload = json.dumps(result, indent=2) + "\n"
        for path in (RESULT_PATH, WEB_DATA_PATH):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        return
    covariance = jacobian_diagnostics(fit, cohort)
    sensitivity = local_sensitivity(fit, cohort)
    trajectories = []
    for row, prediction, standardized_residual in zip(
        cohort.frame.itertuples(index=False), fit.predicted, fit.residuals, strict=True
    ):
        trajectories.append(
            {
                "pdx_id": str(row.pdx_id),
                "treatment": str(row.treatment),
                "day": float(row.day),
                "observed_mm3": float(row.volume_mm3),
                "predicted_mm3": float(prediction),
                "weighted_log_residual": float(standardized_residual),
            }
        )
    result: dict[str, object] = {
        "growth_model": fit.growth,
        "control_growth_comparison": fit.control_comparison,
        "parameters": dict(zip(parameter_names(cohort.lines), fit.parameters.tolist(), strict=True)),
        "bliss_null_parameters": dict(
            zip(parameter_names(cohort.lines), fit.null_parameters.tolist(), strict=True)
        ),
        "metrics": fit.metrics,
        "jacobian_uncertainty": covariance,
        "sensitivity": sensitivity,
        "trajectories": trajectories,
        "treatment_colors": COLORS,
        "fixed_assumptions": {
            "sigma_log": CONFIG.sigma_log,
            "kill_ceiling_per_day": CONFIG.kill_ceiling_per_day,
            "mutation_per_day": CONFIG.mutation_per_day,
            "initial_resistant_fraction": CONFIG.initial_resistant_fraction,
            "resistant_kill_fraction": CONFIG.resistant_kill_fraction,
            "combo_a_dose_ratio": CONFIG.combo_a_dose_ratio,
        },
    }
    if not args.fit_only:
        result["bootstrap_uncertainty"] = block_wild_bootstrap(fit, cohort, CONFIG)
        result["profile_likelihood"] = profile_likelihood(fit, cohort, CONFIG)
        add_dose_sensitivity(result, cohort)
        plot_fit(fit, cohort, FIGURE_DIR)
        plot_residuals(fit, cohort, FIGURE_DIR)
        plot_correlation(covariance["correlation_matrix"], cohort, FIGURE_DIR)
        plot_sensitivity(sensitivity, FIGURE_DIR)
        plot_profiles(result["profile_likelihood"], FIGURE_DIR)
    add_summary(result)
    payload = json.dumps(result, indent=2) + "\n"
    for path in (RESULT_PATH, WEB_DATA_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        logging.info("Wrote %s", path)


if __name__ == "__main__":
    main()
