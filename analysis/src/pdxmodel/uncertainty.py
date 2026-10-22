"""Jacobian, block-wild bootstrap, and refitted profile-likelihood intervals."""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares
from scipy.stats import chi2, norm

from pdxmodel.config import CONFIG, ModelConfig
from pdxmodel.fit import FitResult, residuals
from pdxmodel.model import Cohort, parameter_bounds, parameter_names, solve_cohort

LOGGER = logging.getLogger(__name__)
FloatArray = NDArray[np.float64]


def jacobian_diagnostics(fit: FitResult, cohort: Cohort) -> dict[str, object]:
    """Approximate Wald CIs and correlations, noting practical singularity."""
    jac = fit.jacobian
    scale = float(np.sum(fit.residuals**2) / (len(fit.residuals) - len(fit.parameters)))
    covariance = np.linalg.pinv(jac.T @ jac) * scale
    standard_error = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    threshold = norm.ppf(0.975)
    names = parameter_names(cohort.lines)
    denominator = np.outer(standard_error, standard_error)
    correlation = np.divide(covariance, denominator, out=np.zeros_like(covariance), where=denominator > 0)
    return {
        "ci95": {
            name: [float(value - threshold * error), float(value + threshold * error)]
            for name, value, error in zip(names, fit.parameters, standard_error, strict=True)
        },
        "standard_errors": dict(zip(names, standard_error.tolist(), strict=True)),
        "correlation_matrix": correlation.tolist(),
        "jacobian_condition_number": float(np.linalg.cond(jac)),
        "residual_variance_scale": scale,
    }


def block_wild_bootstrap(
    fit: FitResult,
    cohort: Cohort,
    config: ModelConfig = CONFIG,
) -> dict[str, object]:
    """Flip whole-trajectory log residuals and refit ≥200 times."""
    rng = np.random.default_rng(config.seed + 1)
    fitted_log = np.log(fit.predicted)
    raw_log_residual = np.log(cohort.observed) - fitted_log
    raw_log_residual = raw_log_residual.copy()
    raw_log_residual[cohort.days == 0] = 0.0
    lower, upper = parameter_bounds(cohort.n_lines, config)
    samples: list[FloatArray] = []
    failures = 0
    for replicate in range(config.bootstrap_replicates):
        signs = rng.choice([-1.0, 1.0], size=len(cohort.line_index))
        target_log = fitted_log + signs[cohort.obs_series_index] * raw_log_residual

        def objective(parameters: FloatArray) -> FloatArray:
            prediction = solve_cohort(parameters, cohort, fit.growth, config)
            return (np.log(prediction) - target_log) / config.sigma_log

        try:
            result = least_squares(
                objective,
                fit.parameters,
                bounds=(lower, upper),
                method="trf",
                x_scale="jac",
                max_nfev=150,
            )
        except RuntimeError:
            failures += 1
            continue
        if not result.success:
            failures += 1
        samples.append(result.x)
        if (replicate + 1) % 25 == 0:
            LOGGER.info("Bootstrap %s/%s", replicate + 1, config.bootstrap_replicates)
    matrix = np.asarray(samples)
    names = parameter_names(cohort.lines)
    intervals = np.quantile(matrix, [0.025, 0.975], axis=0)
    return {
        "method": "trajectory-block wild bootstrap on log residuals, day-zero baseline fixed",
        "requested_replicates": config.bootstrap_replicates,
        "completed_replicates": len(matrix),
        "nonconverged_or_failed": failures,
        "ci95": {
            name: [float(intervals[0, index]), float(intervals[1, index])]
            for index, name in enumerate(names)
        },
        "psi_samples": matrix[:, -1].tolist(),
    }


def profile_likelihood(
    fit: FitResult,
    cohort: Cohort,
    config: ModelConfig = CONFIG,
) -> dict[str, object]:
    """Refit every nuisance parameter at each fixed effect/ψ grid value."""
    lower, upper = parameter_bounds(cohort.n_lines, config)
    baseline_sse = float(np.sum(fit.residuals**2))
    threshold = float(chi2.ppf(0.95, 1))
    names = parameter_names(cohort.lines)
    variance_scale = baseline_sse / (len(fit.residuals) - len(fit.parameters))
    covariance = np.linalg.pinv(fit.jacobian.T @ fit.jacobian) * variance_scale
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    profiles: dict[str, object] = {}
    for index in (len(names) - 3, len(names) - 2, len(names) - 1):
        name = names[index]
        value = fit.parameters[index]
        if name == "psi":
            grid = np.linspace(lower[index], upper[index], config.profile_grid_points)
        else:
            radius = max(0.03, 4 * standard_errors[index])
            grid = np.linspace(
                max(lower[index], value - radius),
                min(upper[index], value + radius),
                config.profile_grid_points,
            )
        grid = np.sort(np.unique(np.append(grid, value)))
        sse: list[float] = []
        free_mask = np.ones(len(names), dtype=bool)
        free_mask[index] = False
        for fixed in grid:

            def objective(free: FloatArray) -> FloatArray:
                parameters = fit.parameters.copy()
                parameters[free_mask] = free
                parameters[index] = fixed
                return residuals(parameters, cohort, fit.growth, config)

            estimate = least_squares(
                objective,
                fit.parameters[free_mask],
                bounds=(lower[free_mask], upper[free_mask]),
                method="trf",
                x_scale="jac",
                max_nfev=250,
            )
            sse.append(float(np.sum(estimate.fun**2)))
        likelihood_ratio = len(cohort.observed) * np.log(np.maximum(sse, baseline_sse) / baseline_sse)
        center = int(np.argmin(abs(grid - value)))

        def crossing(indices: range, edge: float) -> tuple[float, bool]:
            inner = center
            for outer in indices:
                if likelihood_ratio[outer] > threshold >= likelihood_ratio[inner]:
                    x0, x1 = grid[inner], grid[outer]
                    y0, y1 = likelihood_ratio[inner], likelihood_ratio[outer]
                    return float(x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)), False
                inner = outer
            return edge, True

        left, left_open = crossing(range(center - 1, -1, -1), float(grid[0]))
        right, right_open = crossing(range(center + 1, len(grid)), float(grid[-1]))
        profiles[name] = {
            "fixed_values": grid.tolist(),
            "refitted_sse": sse,
            "likelihood_ratio": likelihood_ratio.tolist(),
            "threshold_chi2_95": threshold,
            "ci95": [left, right],
            "ci_touches_grid_edge": left_open or right_open,
        }
        LOGGER.info("Profile %s complete", name)
    return profiles
