# Model and parameterization

For each PDX line and arm, observed tumor volume is `V(t) = S(t) + R(t)` in mm³. `S` and `R` are treatment-sensitive and relatively resistant tumor volumes. With the selected logistic growth law,

```text
g_i(V) = r_i (1 - V / K_i)
dS/dt = [g_i(V) - κ E_t - μ] S
dR/dt = [g_i(V) - η κ E_t] R + μ S
E_control = 0; E_A = e_A; E_B = e_B
q_A = e_A / (1 - e_A); e_A,combo = (0.6 q_A) / (1 + 0.6 q_A)
E_A+B = e_A,combo + e_B - e_A,combo e_B + ψ e_A,combo e_B
```

The requested Bliss expression is applied at **matched combination doses**. `ψ=0` is the Bliss independent-action null, `ψ>0` enhances combination killing, and `ψ<0` reduces it. `e_A` and `e_B` are dimensionless effective Emax occupancies at constant exposure, each of the form `C/(EC50+C)` with the drug-specific concentration ratio absorbed into the fitted effect. A published reanalysis of the Gao PDX trials reports BYL719 at **50 mg/kg daily alone versus 30 mg/kg daily in the combination**, while LJM716 is **25 mg/kg every other day** in both arms ([study and dosing table](https://www.sciencedirect.com/science/article/pii/S0928098724002136)). The source workbook itself does not contain dose columns. We use the 0.6 BYL719 dose ratio as a **dose-proportional concentration assumption**, then apply Emax at that scaled exposure. Their conversion to kill rate is `κE` in day⁻¹. The model does not identify actual `C`, `EC50`, or a PK time course from tumor volume alone. An equal-dose counterfactual is refitted as a structural sensitivity check.

The fitted parameters are ten line-specific `r_i` (day⁻¹) and `K_i` (mm³), shared `e_A`, `e_B`, and `ψ`. Each trajectory starts at its own **observed** day-zero volume. Fixed assumptions are `κ=0.25 day⁻¹`, `μ=0.001 day⁻¹`, `η=0.05`, and an initial resistant fraction of 0.02. The fit bounds for ψ are `[-1, 50]`: the large positive range avoids artificially truncating an interaction parameter multiplied by two small Emax occupancies, while the lower bound keeps the combined effect nonnegative. These fixed values constrain a model that cannot identify separate exposure, resistance, and maximal-killing parameters from one mouse per line and arm; they are assumptions, not direct measurements. Identical growth kinetics are assumed for S and R, with no fitness cost of resistance. Tumors are homogeneous, mice are immunodeficient, exposure is constant, and spatial/immune effects are omitted.

Control trajectories determine whether logistic or Gompertz growth has lower AICc, using a separate two-parameter fit per line. The selected growth law is then jointly fitted to all ten lines and four arms. A global differential-evolution search (`popsize=8`, `maxiter=30`, `tol=0.01`, `seed=42`, `workers=-1`, `polish=False`) finds shared effect starting values with control-derived growth parameters. Bounded trust-region `least_squares` (`method='trf'`, `x_scale='jac'`) then jointly refits all 23 parameters. The Bliss-null fit fixes `ψ=0` and refits the other 22.

The objective is `sum[(log(V_model) - log(V_observed))/0.15]^2`. The 0.15 log-scale error is an approximate measurement-error weighting assumption based on the reported ~15% mean interobserver difference in caliper-derived xenograft volumes [Euhus et al., 1986](https://pubmed.ncbi.nlm.nih.gov/3724177/). It is **not** an independently estimated CV for this PDX study. Relative rather than absolute errors are appropriate for caliper volumes, but the model residual variance is estimated again for inference; model mismatch can greatly exceed 15%.

The Jacobian CI uses a scaled pseudoinverse of `JᵀJ`. The 200-replicate trajectory-block wild bootstrap flips the sign of whole-trajectory log residuals, retains measured baselines, and refits the model; it preserves within-trajectory error patterns but cannot replace biological replicates. Profile likelihood fixes each of `e_A`, `e_B`, and `ψ` on a grid and **refits all other parameters**. Its 95% cutoff is a one-degree-of-freedom χ² likelihood-ratio threshold. Correlation and ±10% sensitivity diagnostics report practical identifiability.

Drug mechanisms: BYL719 (alpelisib) inhibits PI3Kα; LJM716 is an anti-HER3 antibody that locks HER3 in an inactive conformation. See [Garrett et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3790862/) and [Garner et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3924863/). These mechanisms make the combination biologically motivated but do not establish synergy in this PDX cohort.
