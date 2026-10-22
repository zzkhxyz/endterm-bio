"""Vectorized two-population PDX growth and treatment ODE."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.integrate import solve_ivp

from pdxmodel.config import CONFIG, ModelConfig

FloatArray = NDArray[np.float64]
ARM_ORDER = ("control", "A", "B", "A+B")


@dataclass(frozen=True)
class Cohort:
    """All 40 trajectories packed into one ODE solve per objective evaluation."""

    lines: tuple[str, ...]
    frame: pd.DataFrame
    days: FloatArray
    observed: FloatArray
    time_grid: FloatArray
    obs_time_index: NDArray[np.int64]
    obs_series_index: NDArray[np.int64]
    line_index: NDArray[np.int64]
    arm_index: NDArray[np.int64]
    initial_volume: FloatArray

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> Cohort:
        """Validate observed data and derive exact time/trajectory indices."""
        required = {"pdx_id", "cancer_type", "treatment", "day", "volume_mm3"}
        if not required <= set(frame):
            raise ValueError(f"Missing data columns: {sorted(required - set(frame))}")
        if frame[list(required)].isna().any().any() or (frame["volume_mm3"] <= 0).any():
            raise ValueError("Observations must have positive volumes and no missing values")
        lines = tuple(sorted(frame["pdx_id"].unique()))
        ordered = frame.copy()
        ordered["pdx_id"] = pd.Categorical(ordered["pdx_id"], lines, ordered=True)
        ordered["treatment"] = pd.Categorical(ordered["treatment"], ARM_ORDER, ordered=True)
        ordered = ordered.sort_values(["pdx_id", "treatment", "day"]).reset_index(drop=True)
        grid = np.sort(ordered["day"].unique().astype(float))
        line_ids: list[int] = []
        arm_ids: list[int] = []
        initials: list[float] = []
        obs_series: list[int] = []
        for line_i, line in enumerate(lines):
            for arm_i, arm in enumerate(ARM_ORDER):
                series = ordered[(ordered.pdx_id == line) & (ordered.treatment == arm)]
                if series.empty or float(series.iloc[0].day) != 0:
                    raise ValueError(f"Incomplete quartet or missing baseline for {line} / {arm}")
                line_ids.append(line_i)
                arm_ids.append(arm_i)
                initials.append(float(series.iloc[0].volume_mm3))
                obs_series.extend([len(line_ids) - 1] * len(series))
        return cls(
            lines=lines,
            frame=ordered,
            days=ordered["day"].to_numpy(dtype=float),
            observed=ordered["volume_mm3"].to_numpy(dtype=float),
            time_grid=grid,
            obs_time_index=np.searchsorted(grid, ordered["day"].to_numpy(dtype=float)),
            obs_series_index=np.asarray(obs_series, dtype=np.int64),
            line_index=np.asarray(line_ids, dtype=np.int64),
            arm_index=np.asarray(arm_ids, dtype=np.int64),
            initial_volume=np.asarray(initials, dtype=float),
        )

    @property
    def n_lines(self) -> int:
        """Number of PDX lines."""
        return len(self.lines)


def parameter_names(lines: tuple[str, ...]) -> list[str]:
    """Stable ordering for fitted parameters and diagnostics."""
    return [*(f"r_{line}" for line in lines), *(f"K1000_{line}" for line in lines), "e_A", "e_B", "psi"]


def parameter_bounds(n_lines: int, config: ModelConfig = CONFIG) -> tuple[FloatArray, FloatArray]:
    """Return biologically constrained lower and upper bounds."""
    lower = np.asarray(
        [config.growth_rate_bounds[0]] * n_lines
        + [config.carrying_capacity_1000_bounds[0]] * n_lines
        + [config.drug_effect_bounds[0]] * 2
        + [config.interaction_bounds[0]],
        dtype=float,
    )
    upper = np.asarray(
        [config.growth_rate_bounds[1]] * n_lines
        + [config.carrying_capacity_1000_bounds[1]] * n_lines
        + [config.drug_effect_bounds[1]] * 2
        + [config.interaction_bounds[1]],
        dtype=float,
    )
    return lower, upper


def bliss_effect(e_a: float, e_b: float, psi: float) -> float:
    """Dimensionless combination effect: ψ=0 is Bliss independence."""
    return e_a + e_b - e_a * e_b + psi * e_a * e_b


def combo_a_effect(e_a: float, config: ModelConfig = CONFIG) -> float:
    """Scale A's Emax concentration ratio for its lower combination dose."""
    concentration_ratio = e_a / (1.0 - e_a)
    scaled = config.combo_a_dose_ratio * concentration_ratio
    return scaled / (1.0 + scaled)


def treatment_effects(
    e_a: float, e_b: float, psi: float, config: ModelConfig = CONFIG
) -> FloatArray:
    """Effect for control, A, B, and A+B in that order."""
    pair_a = combo_a_effect(e_a, config)
    return np.asarray([0.0, e_a, e_b, bliss_effect(pair_a, e_b, psi)], dtype=float)


def solve_cohort(
    parameters: FloatArray,
    cohort: Cohort,
    growth: str,
    config: ModelConfig = CONFIG,
) -> FloatArray:
    """Solve all PDX arms together and return predictions at observed days."""
    n = cohort.n_lines
    r = parameters[:n][cohort.line_index]
    capacity = 1000.0 * parameters[n : 2 * n][cohort.line_index]
    effect = treatment_effects(*parameters[-3:], config=config)[cohort.arm_index]
    kill = config.kill_ceiling_per_day * effect
    resistant_kill = config.resistant_kill_fraction * kill
    sensitive0 = cohort.initial_volume * (1.0 - config.initial_resistant_fraction)
    resistant0 = cohort.initial_volume * config.initial_resistant_fraction
    initial = np.concatenate([sensitive0, resistant0])

    def derivative(_time: float, state: FloatArray) -> FloatArray:
        sensitive = state[: len(r)]
        resistant = state[len(r) :]
        total = np.maximum(sensitive + resistant, 1e-12)
        if growth == "gompertz":
            growth_rate = r * np.log(capacity / total)
        elif growth == "logistic":
            growth_rate = r * (1.0 - total / capacity)
        else:
            raise ValueError(f"Unknown growth model: {growth}")
        d_sensitive = (growth_rate - kill - config.mutation_per_day) * sensitive
        d_resistant = (growth_rate - resistant_kill) * resistant + config.mutation_per_day * sensitive
        return np.concatenate([d_sensitive, d_resistant])

    solution = solve_ivp(
        derivative,
        (0.0, float(cohort.time_grid[-1])),
        initial,
        method="LSODA",
        t_eval=cohort.time_grid,
        rtol=config.rtol,
        atol=config.atol,
    )
    if not solution.success:
        raise RuntimeError(f"ODE solver failed: {solution.message}")
    volumes = solution.y[: len(r)] + solution.y[len(r) :]
    predicted = volumes[cohort.obs_series_index, cohort.obs_time_index]
    if not np.isfinite(predicted).all() or (predicted <= 0).any():
        raise RuntimeError("ODE solver produced non-positive or non-finite volume")
    return predicted


def control_prediction(days: FloatArray, baseline: float, r: float, capacity: float, growth: str) -> FloatArray:
    """Analytic untreated solution used for growth-model AIC selection."""
    if growth == "gompertz":
        return capacity * np.exp(np.log(baseline / capacity) * np.exp(-r * days))
    if growth == "logistic":
        return capacity / (1.0 + (capacity / baseline - 1.0) * np.exp(-r * days))
    raise ValueError(f"Unknown growth model: {growth}")
