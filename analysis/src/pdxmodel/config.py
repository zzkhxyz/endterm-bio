"""Fixed modeling assumptions and numerical settings in one place."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Assumptions fixed because one mouse per PDX-treatment arm limits identification."""

    seed: int = 42
    sigma_log: float = 0.15
    kill_ceiling_per_day: float = 0.25
    mutation_per_day: float = 0.001
    initial_resistant_fraction: float = 0.02
    resistant_kill_fraction: float = 0.05
    rtol: float = 1e-7
    atol: float = 1e-9
    growth_rate_bounds: tuple[float, float] = (0.001, 0.25)
    carrying_capacity_1000_bounds: tuple[float, float] = (1.5, 10.0)
    drug_effect_bounds: tuple[float, float] = (0.001, 0.999)
    interaction_bounds: tuple[float, float] = (-1.0, 2.0)
    de_popsize: int = 8
    de_maxiter: int = 30
    de_tol: float = 0.01
    bootstrap_replicates: int = 200
    profile_grid_points: int = 17


CONFIG = ModelConfig()
