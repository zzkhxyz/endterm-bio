"""One-at-a-time ±10% local sensitivity for fitted parameters."""

from __future__ import annotations

import numpy as np

from pdxmodel.config import CONFIG, ModelConfig
from pdxmodel.fit import FitResult
from pdxmodel.model import Cohort, parameter_names, solve_cohort


def local_sensitivity(
    fit: FitResult,
    cohort: Cohort,
    config: ModelConfig = CONFIG,
) -> list[dict[str, float | str]]:
    """Quantify SSE and terminal A+B volume changes for every fitted parameter."""
    group = cohort.frame.reset_index(drop=True)
    terminal_indices = []
    for _, line_rows in group.groupby("pdx_id", observed=True):
        combo_rows = line_rows[line_rows["treatment"] == "A+B"]
        terminal_indices.append(int(combo_rows.index[-1]))

    def statistics(parameters: np.ndarray) -> tuple[float, float]:
        predicted = solve_cohort(parameters, cohort, fit.growth, config)
        sse = float(np.sum(((np.log(predicted) - np.log(cohort.observed)) / config.sigma_log) ** 2))
        terminal = float(np.mean(predicted[terminal_indices]))
        return sse, terminal

    base_sse, base_terminal = statistics(fit.parameters)
    output: list[dict[str, float | str]] = []
    for index, name in enumerate(parameter_names(cohort.lines)):
        minus = fit.parameters.copy()
        plus = fit.parameters.copy()
        minus[index] *= 0.9
        plus[index] *= 1.1
        low_sse, low_terminal = statistics(minus)
        high_sse, high_terminal = statistics(plus)
        output.append(
            {
                "parameter": name,
                "sse_minus_10pct": low_sse,
                "sse_plus_10pct": high_sse,
                "terminal_combo_mm3_minus_10pct": low_terminal,
                "terminal_combo_mm3_plus_10pct": high_terminal,
                "normalized_sse_sensitivity": (high_sse - low_sse) / (0.2 * base_sse),
                "normalized_terminal_sensitivity": (high_terminal - low_terminal)
                / (0.2 * base_terminal),
            }
        )
    return output
