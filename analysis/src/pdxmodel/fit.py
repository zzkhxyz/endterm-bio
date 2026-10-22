"""Two-stage joint parameter estimation and Bliss-null comparison."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import differential_evolution, least_squares
from scipy.stats import chi2

from pdxmodel.config import CONFIG, ModelConfig
from pdxmodel.model import (
    Cohort,
    control_prediction,
    parameter_bounds,
    solve_cohort,
)

LOGGER = logging.getLogger(__name__)
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class FitResult:
    """Full and Bliss-null fit with model-selection diagnostics."""

    growth: str
    parameters: FloatArray
    null_parameters: FloatArray
    residuals: FloatArray
    null_residuals: FloatArray
    jacobian: FloatArray
    predicted: FloatArray
    control_comparison: dict[str, dict[str, float]]
    metrics: dict[str, float]


def residuals(
    parameters: FloatArray,
    cohort: Cohort,
    growth: str,
    config: ModelConfig = CONFIG,
) -> FloatArray:
    """Weighted log-volume residuals for multiplicative caliper error."""
    predicted = solve_cohort(parameters, cohort, growth, config)
    return (np.log(predicted) - np.log(cohort.observed)) / config.sigma_log


def information_criteria(sse: float, n_obs: int, n_params: int) -> dict[str, float]:
    """Gaussian AIC/AICc/BIC up to a model-independent additive constant."""
    base = n_obs * np.log(sse / n_obs)
    aic = base + 2 * n_params
    correction = 2 * n_params * (n_params + 1) / (n_obs - n_params - 1)
    return {
        "sse": float(sse),
        "aic": float(aic),
        "aicc": float(aic + correction),
        "bic": float(base + n_params * np.log(n_obs)),
    }


def fit_controls(cohort: Cohort, config: ModelConfig = CONFIG) -> tuple[str, FloatArray, dict[str, dict[str, float]]]:
    """Compare Gompertz and logistic growth on untreated series only."""
    n = cohort.n_lines
    estimates: dict[str, FloatArray] = {}
    criteria: dict[str, dict[str, float]] = {}
    for growth in ("gompertz", "logistic"):
        per_line: list[FloatArray] = []
        total_sse = 0.0
        total_n = 0
        for line in cohort.lines:
            series = cohort.frame[
                (cohort.frame.pdx_id == line) & (cohort.frame.treatment == "control")
            ]
            days = series["day"].to_numpy(dtype=float)
            observed = series["volume_mm3"].to_numpy(dtype=float)
            baseline = float(observed[0])

            def objective(pair: FloatArray) -> FloatArray:
                predicted = control_prediction(days, baseline, pair[0], 1000.0 * pair[1], growth)
                return (np.log(predicted) - np.log(observed)) / config.sigma_log

            estimate = least_squares(
                objective,
                np.asarray([0.03, 3.0]),
                bounds=(
                    [config.growth_rate_bounds[0], config.carrying_capacity_1000_bounds[0]],
                    [config.growth_rate_bounds[1], config.carrying_capacity_1000_bounds[1]],
                ),
                method="trf",
                x_scale="jac",
            )
            per_line.append(estimate.x)
            total_sse += float(np.sum(estimate.fun**2))
            total_n += len(observed)
        matrix = np.asarray(per_line)
        estimates[growth] = np.concatenate([matrix[:, 0], matrix[:, 1]])
        criteria[growth] = information_criteria(total_sse, total_n, 2 * n)
        LOGGER.info("Control %s: AICc=%.2f", growth, criteria[growth]["aicc"])
    selected = min(criteria, key=lambda key: criteria[key]["aicc"])
    return selected, estimates[selected], criteria


@dataclass(frozen=True)
class GlobalObjective:
    """Picklable effect-only DE objective with control parameters held fixed."""

    cohort: Cohort
    growth: str
    control_parameters: FloatArray
    config: ModelConfig

    def __call__(self, effects: FloatArray) -> float:
        parameters = np.concatenate([self.control_parameters, effects])
        try:
            values = residuals(parameters, self.cohort, self.growth, self.config)
        except RuntimeError:
            return 1e20
        return float(np.sum(values**2))


def fit_joint(
    cohort: Cohort,
    growth: str,
    controls: FloatArray,
    config: ModelConfig = CONFIG,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Global DE for shared effects followed by bounded joint TRF refinement."""
    bounds = [config.drug_effect_bounds] * 2 + [config.interaction_bounds]
    global_result = differential_evolution(
        GlobalObjective(cohort, growth, controls, config),
        bounds,
        popsize=config.de_popsize,
        maxiter=config.de_maxiter,
        tol=config.de_tol,
        seed=config.seed,
        workers=-1,
        updating="deferred",
        polish=False,
    )
    LOGGER.info("DE effect search: SSE=%.2f", global_result.fun)
    start = np.concatenate([controls, global_result.x])
    lower, upper = parameter_bounds(cohort.n_lines, config)
    local = least_squares(
        residuals,
        start,
        args=(cohort, growth, config),
        bounds=(lower, upper),
        method="trf",
        x_scale="jac",
        max_nfev=1000,
    )
    if not local.success:
        LOGGER.warning("Local fit ended without convergence: %s", local.message)
    return local.x, local.fun, local.jac


def fit_bliss_null(
    cohort: Cohort,
    growth: str,
    start_full: FloatArray,
    config: ModelConfig = CONFIG,
) -> tuple[FloatArray, FloatArray]:
    """Refit every other parameter under ψ=0."""
    lower, upper = parameter_bounds(cohort.n_lines, config)

    def objective(free: FloatArray) -> FloatArray:
        return residuals(np.append(free, 0.0), cohort, growth, config)

    result = least_squares(
        objective,
        start_full[:-1],
        bounds=(lower[:-1], upper[:-1]),
        method="trf",
        x_scale="jac",
        max_nfev=1000,
    )
    return np.append(result.x, 0.0), result.fun


def run_fit(cohort: Cohort, config: ModelConfig = CONFIG) -> FitResult:
    """Run growth selection, full joint fit, and nested Bliss-null test."""
    growth, controls, comparison = fit_controls(cohort, config)
    parameters, full_residuals, jacobian = fit_joint(cohort, growth, controls, config)
    null_parameters, null_residuals = fit_bliss_null(cohort, growth, parameters, config)
    n_obs = len(cohort.observed)
    k_full = len(parameters)
    full = information_criteria(float(np.sum(full_residuals**2)), n_obs, k_full)
    null = information_criteria(float(np.sum(null_residuals**2)), n_obs, k_full - 1)
    lr = max(0.0, n_obs * np.log(null["sse"] / full["sse"]))
    metrics = {
        **{f"full_{key}": value for key, value in full.items()},
        **{f"bliss_{key}": value for key, value in null.items()},
        "delta_aic_bliss_minus_full": null["aic"] - full["aic"],
        "delta_bic_bliss_minus_full": null["bic"] - full["bic"],
        "likelihood_ratio": lr,
        "lrt_p_value": float(chi2.sf(lr, 1)),
        "n_observations": n_obs,
        "n_parameters_full": k_full,
    }
    return FitResult(
        growth=growth,
        parameters=parameters,
        null_parameters=null_parameters,
        residuals=full_residuals,
        null_residuals=null_residuals,
        jacobian=jacobian,
        predicted=solve_cohort(parameters, cohort, growth, config),
        control_comparison=comparison,
        metrics=metrics,
    )
