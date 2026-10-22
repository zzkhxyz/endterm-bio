export type Arm = "control" | "A" | "B" | "A+B";

export interface Point {
  pdx_id: string;
  treatment: Arm;
  day: number;
  observed_mm3: number;
  predicted_mm3: number;
  weighted_log_residual: number;
}

export interface Profile {
  fixed_values: number[];
  likelihood_ratio: number[];
  ci95: number[];
  threshold_chi2_95: number;
  ci_touches_grid_edge: boolean;
}

export interface ResultData {
  parameters: Record<string, number>;
  trajectories: Point[];
  treatment_colors: Record<Arm, string>;
  metrics: Record<string, number>;
  summary: {
    conclusion: string;
    psi_point: number;
    psi_bootstrap_ci95: number[];
    psi_profile_ci95: number[];
    lrt_p_value: number;
    e_a: number;
    e_a_at_combo_dose: number;
    e_b: number;
    bliss_effect: number;
    fitted_combo_effect: number;
    rmse_log_volume: number;
    capacity_parameters_at_bound: number;
  };
  dose_assumption_sensitivity: {
    equal_dose_psi_point: number;
    equal_dose_lrt_p_value: number;
    equal_dose_delta_aic_bliss_minus_full: number;
    equal_dose_delta_bic_bliss_minus_full: number;
  };
  fixed_assumptions: {
    sigma_log: number;
    kill_ceiling_per_day: number;
    mutation_per_day: number;
    initial_resistant_fraction: number;
    resistant_kill_fraction: number;
    combo_a_dose_ratio: number;
  };
  bootstrap_uncertainty: { completed_replicates: number; ci95: Record<string, number[]> };
  jacobian_uncertainty: { ci95: Record<string, number[]>; correlation_matrix: number[][] };
  profile_likelihood: Record<"e_A" | "e_B" | "psi", Profile>;
  sensitivity: {
    parameter: string;
    normalized_terminal_sensitivity: number;
    normalized_sse_sensitivity: number;
  }[];
  control_growth_comparison: Record<string, { aicc: number }>;
}

type State = [number, number];

export function simulate(
  initialVolume: number,
  r: number,
  capacity: number,
  effects: { a: number; b: number; psi: number },
  fixed: ResultData["fixed_assumptions"],
  arm: Arm,
  horizon = 84,
): { day: number; volume: number }[] {
  const odds = effects.a / Math.max(1e-6, 1 - effects.a);
  const aCombo = (fixed.combo_a_dose_ratio * odds) / (1 + fixed.combo_a_dose_ratio * odds);
  const exposure = arm === "control" ? 0 : arm === "A" ? effects.a : arm === "B" ? effects.b
    : aCombo + effects.b - aCombo * effects.b + effects.psi * aCombo * effects.b;
  const deriv = ([s, resistant]: State): State => {
    const growth = r * (1 - (s + resistant) / capacity);
    return [
      (growth - fixed.kill_ceiling_per_day * exposure - fixed.mutation_per_day) * s,
      (growth - fixed.resistant_kill_fraction * fixed.kill_ceiling_per_day * exposure) * resistant
        + fixed.mutation_per_day * s,
    ];
  };
  const add = (x: State, y: State, scale: number): State => [x[0] + y[0] * scale, x[1] + y[1] * scale];
  const step = 0.25;
  let state: State = [initialVolume * (1 - fixed.initial_resistant_fraction), initialVolume * fixed.initial_resistant_fraction];
  const output = [{ day: 0, volume: initialVolume }];
  for (let i = 1; i <= horizon / step; i++) {
    const k1 = deriv(state);
    const k2 = deriv(add(state, k1, step / 2));
    const k3 = deriv(add(state, k2, step / 2));
    const k4 = deriv(add(state, k3, step));
    state = [
      Math.max(0, state[0] + step * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6),
      Math.max(0, state[1] + step * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6),
    ];
    if (i % 4 === 0) output.push({ day: i * step, volume: state[0] + state[1] });
  }
  return output;
}
