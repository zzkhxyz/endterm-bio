"use client";

import { useMemo, useState } from "react";
import { line, scaleLinear, interpolateRdBu } from "d3";
import ModelExplorer from "./model-explorer";
import { Arm, Point, ResultData, simulate } from "../lib/model";

const arms: Arm[] = ["control", "A", "B", "A+B"];
const armNames: Record<Arm, string> = { control: "Untreated", A: "BYL719", B: "LJM716", "A+B": "Combination" };
const format = (n: number, digits = 2) => Number(n).toFixed(digits);

function SectionHeading({ label, title, children }: { label: string; title: string; children: React.ReactNode }) {
  return <div className="section-heading"><span className="eyebrow">{label}</span><h2>{title}</h2><p>{children}</p></div>;
}

function SimpleNote({ children }: { children: React.ReactNode }) {
  return <p className="plain-note"><strong>In plain language</strong> {children}</p>;
}

function Legend({ colors, active, onToggle }: { colors: ResultData["treatment_colors"]; active?: Arm[]; onToggle?: (arm: Arm) => void }) {
  return <div className="legend" aria-label="Treatment groups">{arms.map((arm) => <button
    type="button" key={arm} className={`legend-item ${active && !active.includes(arm) ? "muted" : ""}`}
    onClick={() => onToggle?.(arm)} aria-pressed={active?.includes(arm) ?? true}
    disabled={!onToggle}>
    <span className="legend-dot" style={{ background: colors[arm] }} />{armNames[arm]}
  </button>)}</div>;
}

function TumorChart({ points, colors, active, showObserved = true, showPredicted = true, compact = false }: {
  points: Point[]; colors: ResultData["treatment_colors"]; active: Arm[];
  showObserved?: boolean; showPredicted?: boolean; compact?: boolean;
}) {
  const width = 760, height = compact ? 295 : 355;
  const left = 52, right = 16, top = 18, bottom = 42;
  const filtered = points.filter((p) => active.includes(p.treatment));
  const xMax = Math.max(1, ...filtered.map((p) => p.day));
  const yMax = Math.max(1, ...filtered.map((p) => Math.max(p.observed_mm3, p.predicted_mm3))) * 1.08;
  const x = scaleLinear().domain([0, xMax]).range([left, width - right]);
  const y = scaleLinear().domain([0, yMax]).range([height - bottom, top]);
  const path = line<Point>().x((p) => x(p.day)).y((p) => y(p.predicted_mm3));
  return <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Tumor volume over time for selected PDX line">
    {[0, .25, .5, .75, 1].map((fraction) => <g key={fraction}>
      <line x1={left} x2={width - right} y1={y(yMax * fraction)} y2={y(yMax * fraction)} className="grid-line" />
      <text x={left - 10} y={y(yMax * fraction) + 4} textAnchor="end" className="axis-text">{Math.round(yMax * fraction)}</text>
    </g>)}
    {[0, .25, .5, .75, 1].map((fraction) => <text key={fraction} x={x(xMax * fraction)} y={height - 16} textAnchor="middle" className="axis-text">{Math.round(xMax * fraction)}</text>)}
    {arms.filter((arm) => active.includes(arm)).map((arm) => {
      const series = filtered.filter((p) => p.treatment === arm).sort((a, b) => a.day - b.day);
      return <g key={arm}>
        {showPredicted && <path d={path(series) ?? ""} fill="none" stroke={colors[arm]} strokeWidth="2.7" strokeLinecap="round" />}
        {showObserved && series.map((p, index) => <circle key={index} cx={x(p.day)} cy={y(p.observed_mm3)} r="3.3" fill={colors[arm]} stroke="var(--surface)" strokeWidth="1" />)}
      </g>;
    })}
    <text x={width / 2} y={height - 1} textAnchor="middle" className="axis-label">Days after baseline</text>
    <text transform={`translate(13 ${height / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">Tumor volume · mm³</text>
  </svg>;
}

function ResidualChart({ points, colors, sigma }: { points: Point[]; colors: ResultData["treatment_colors"]; sigma: number }) {
  const width = 760, height = 270, left = 52, right = 16, top = 20, bottom = 42;
  const xMax = Math.max(1, ...points.map((p) => p.day));
  const residuals = points.map((p) => p.weighted_log_residual * sigma);
  const bound = Math.max(0.5, ...residuals.map(Math.abs)) * 1.08;
  const x = scaleLinear().domain([0, xMax]).range([left, width - right]);
  const y = scaleLinear().domain([-bound, bound]).range([height - bottom, top]);
  return <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Log-volume model residuals against time">
    {[-1, -.5, 0, .5, 1].map((fraction) => <g key={fraction}>
      <line x1={left} x2={width - right} y1={y(bound * fraction)} y2={y(bound * fraction)} className={fraction === 0 ? "zero-line" : "grid-line"} />
      <text x={left - 10} y={y(bound * fraction) + 4} textAnchor="end" className="axis-text">{format(bound * fraction, 1)}</text>
    </g>)}
    {points.map((p, i) => <circle key={i} cx={x(p.day)} cy={y(residuals[i])} r="2.5" fill={colors[p.treatment]} fillOpacity=".7" />)}
    <text x={width / 2} y={height - 1} textAnchor="middle" className="axis-label">Days after baseline</text>
    <text transform={`translate(13 ${height / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">Log residual</text>
  </svg>;
}

function ProfileChart({ results }: { results: ResultData }) {
  const p = results.profile_likelihood.psi;
  const width = 630, height = 270, left = 42, right = 16, top = 18, bottom = 40;
  const x = scaleLinear().domain([Math.min(...p.fixed_values), Math.max(...p.fixed_values)]).range([left, width - right]);
  const y = scaleLinear().domain([0, Math.max(...p.likelihood_ratio) * 1.04]).range([height - bottom, top]);
  const plot = line<number>().x((_, i) => x(p.fixed_values[i])).y((v) => y(v));
  return <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Profile likelihood for interaction parameter psi">
    <line x1={left} x2={width - right} y1={y(p.threshold_chi2_95)} y2={y(p.threshold_chi2_95)} stroke="var(--warn)" strokeDasharray="5 5" />
    <line x1={x(0)} x2={x(0)} y1={top} y2={height - bottom} className="zero-line" strokeDasharray="4 4" />
    <path d={plot(p.likelihood_ratio) ?? ""} fill="none" stroke="var(--accent)" strokeWidth="3" />
    {p.fixed_values.map((v, i) => <circle key={i} cx={x(v)} cy={y(p.likelihood_ratio[i])} r="3" fill="var(--accent)" />)}
    {[-1, 0, 10, 20, 30, 40, 50].map((v) => <text key={v} x={x(v)} y={height - 15} textAnchor="middle" className="axis-text">{v}</text>)}
    <text x={width / 2} y={height - 1} textAnchor="middle" className="axis-label">Interaction ψ</text>
    <text x={width - right} y={y(p.threshold_chi2_95) - 7} textAnchor="end" className="axis-label">95% threshold</text>
  </svg>;
}

function SensitivityChart({ results }: { results: ResultData }) {
  const items = [...results.sensitivity].sort((a, b) => Math.abs(b.normalized_terminal_sensitivity) - Math.abs(a.normalized_terminal_sensitivity)).slice(0, 8);
  const max = Math.max(.1, ...items.map((item) => Math.abs(item.normalized_terminal_sensitivity)));
  return <div className="sensitivity-bars" role="img" aria-label="Largest local sensitivity coefficients for final combination volume">
    {items.map((item) => <div className="sensitivity-row" key={item.parameter}>
      <span>{item.parameter.replace("K1000_", "K · ").replace("r_", "r · ")}</span>
      <div className="bar-track"><i style={{ width: `${Math.abs(item.normalized_terminal_sensitivity) / max * 100}%`, background: item.normalized_terminal_sensitivity < 0 ? "var(--drug-b)" : "var(--accent)" }} /></div>
      <strong>{format(item.normalized_terminal_sensitivity, 2)}</strong>
    </div>)}
  </div>;
}

function CorrelationChart({ results }: { results: ResultData }) {
  const matrix = results.jacobian_uncertainty.correlation_matrix;
  const names = Object.keys(results.parameters);
  const cell = 17, offset = 28, size = offset + matrix.length * cell + 4;
  return <div className="heatmap-wrap"><svg viewBox={`0 0 ${size} ${size}`} className="heatmap-svg" role="img" aria-label="Full fitted-parameter correlation heatmap">
    {matrix.map((row, i) => row.map((value, j) => <rect key={`${i}-${j}`} x={offset + j * cell} y={offset + i * cell} width={cell - 1} height={cell - 1} fill={interpolateRdBu((1 - value) / 2)} aria-label={`${names[i]} and ${names[j]} correlation ${format(value, 2)}`} />))}
    <text x={0} y={offset + 10 * cell} className="heatmap-label">r</text>
    <text x={0} y={offset + 20 * cell} className="heatmap-label">K</text>
    <text x={offset + 20 * cell} y={18} className="heatmap-label">e, ψ</text>
  </svg></div>;
}

function Simulator({ results, lineId }: { results: ResultData; lineId: string }) {
  const [a, setA] = useState(results.summary.e_a);
  const [b, setB] = useState(results.summary.e_b);
  const [psi, setPsi] = useState(results.summary.psi_point);
  const baseline = results.trajectories.find((p) => p.pdx_id === lineId && p.treatment === "control" && p.day === 0)?.observed_mm3 ?? 0;
  const horizon = Math.ceil(Math.max(...results.trajectories.filter((p) => p.pdx_id === lineId).map((p) => p.day)));
  const r = results.parameters[`r_${lineId}`];
  const capacity = results.parameters[`K1000_${lineId}`] * 1000;
  const simulations = useMemo(() => Object.fromEntries(arms.map((arm) => [arm, simulate(baseline, r, capacity, { a, b, psi }, results.fixed_assumptions, arm, horizon)])) as Record<Arm, { day: number; volume: number }[]>, [baseline, r, capacity, a, b, psi, results.fixed_assumptions, horizon]);
  const width = 760, height = 330, left = 52, right = 16, top = 18, bottom = 40;
  const yMax = Math.max(...arms.flatMap((arm) => simulations[arm].map((p) => p.volume))) * 1.08;
  const x = scaleLinear().domain([0, horizon]).range([left, width - right]);
  const y = scaleLinear().domain([0, yMax]).range([height - bottom, top]);
  const plot = line<{ day: number; volume: number }>().x((p) => x(p.day)).y((p) => y(p.volume));
  const doseA = (results.fixed_assumptions.combo_a_dose_ratio * a / (1 - a)) / (1 + results.fixed_assumptions.combo_a_dose_ratio * a / (1 - a));
  const bliss = doseA + b - doseA * b;
  const combo = bliss + psi * doseA * b;
  return <div className="sim-grid">
    <div className="sim-controls">
      <div className="sim-readout"><span>Try a different interaction</span><strong>ψ {format(psi, 1)}</strong></div>
      {([
        { id: "a", label: "BYL719 effect", value: a, setter: setA, min: 0.01, max: .3, step: .005 },
        { id: "b", label: "LJM716 effect", value: b, setter: setB, min: 0.005, max: .3, step: .005 },
        { id: "psi", label: "Interaction ψ", value: psi, setter: setPsi, min: -1, max: 50, step: .5 },
      ]).map((control) => <label className="slider-control" key={control.id}>
        <span>{control.label}<b>{format(control.value, control.id === "psi" ? 1 : 3)}</b></span>
        <input type="range" min={control.min} max={control.max} step={control.step} value={control.value} onChange={(event) => control.setter(Number(event.target.value))} />
      </label>)}
      <button type="button" className="text-button" onClick={() => { setA(results.summary.e_a); setB(results.summary.e_b); setPsi(results.summary.psi_point); }}>Reset to fitted values ↗</button>
      <div className="sim-equation"><span>Bliss expectation</span><strong>{format(bliss, 3)}</strong><span>With interaction</span><strong>{format(combo, 3)}</strong></div>
    </div>
    <div className="sim-plot"><svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Browser-calculated ODE tumor trajectories with adjustable drug effects">
      {[0, .25, .5, .75, 1].map((f) => <g key={f}><line x1={left} x2={width - right} y1={y(f * yMax)} y2={y(f * yMax)} className="grid-line" /><text x={left - 10} y={y(f * yMax) + 4} textAnchor="end" className="axis-text">{Math.round(f * yMax)}</text></g>)}
      {arms.map((arm) => <path key={arm} d={plot(simulations[arm]) ?? ""} fill="none" stroke={results.treatment_colors[arm]} strokeWidth="3.2" strokeLinecap="round" />)}
      <text x={width / 2} y={height - 1} textAnchor="middle" className="axis-label">Days after baseline · browser RK4</text>
    </svg><Legend colors={results.treatment_colors} /></div>
  </div>;
}

export default function Dashboard({ results }: { results: ResultData }) {
  const lines = [...new Set(results.trajectories.map((p) => p.pdx_id))];
  const [lineId, setLineId] = useState(lines[0]);
  const [active, setActive] = useState<Arm[]>(arms);
  const selectedPoints = results.trajectories.filter((p) => p.pdx_id === lineId);
  const toggleArm = (arm: Arm) => setActive((current) => current.includes(arm) ? (current.length === 1 ? current : current.filter((item) => item !== arm)) : arms.filter((item) => item === arm || current.includes(item)));
  const { summary, dose_assumption_sensitivity: dose, metrics } = results;
  return <>
    <div>
      <section className="section intro" id="pdx"><div className="content"><SectionHeading label="The experiment" title="A patient’s tumor, studied in a mouse.">Patient-derived xenografts, or PDXs, let researchers compare treatments in tumors grown from human tissue. Here, each PDX line contributes four treatment groups.</SectionHeading><div className="pdx-diagram"><div className="diagram-origin"><span className="diagram-symbol">✳</span><strong>Patient tumor</strong><small>tissue sample</small></div><div className="diagram-link" aria-hidden="true" /><div className="diagram-origin"><span className="diagram-symbol">◌</span><strong>PDX line</strong><small>grown in mice</small></div><div className="diagram-link" aria-hidden="true" /><div className="diagram-arms">{arms.map((arm) => <div key={arm} style={{ borderColor: results.treatment_colors[arm] }}><span style={{ background: results.treatment_colors[arm] }} />{armNames[arm]}</div>)}</div></div><SimpleNote>One mouse receives each treatment for each line. That is enough to compare trajectories, but it gives no within-line estimate of biological variation.</SimpleNote></div></section>

      <section className="section section-soft" id="data"><div className="content"><SectionHeading label="The observed data" title="Forty growth curves. Four treatment arms.">The original Gao et al. screening workbook provides measured tumor volumes over time. I selected a complete, consistently filtered BRCA cohort before fitting the model.</SectionHeading><div className="metric-strip"><div><strong>{lines.length}</strong><span>PDX lines</span></div><div><strong>{lines.length * arms.length}</strong><span>mouse trajectories</span></div><div><strong>{metrics.n_observations}</strong><span>volume measurements</span></div><div><strong>mm³</strong><span>tumor volume</span></div></div><div className="chart-card"><div className="card-top"><div><span className="eyebrow">Explore a line</span><h3>Measured tumor growth</h3></div><label className="select-wrap">PDX line<select value={lineId} onChange={(event) => setLineId(event.target.value)}>{lines.map((id) => <option key={id} value={id}>{id}</option>)}</select></label></div><Legend colors={results.treatment_colors} active={active} onToggle={toggleArm} /><TumorChart points={selectedPoints} colors={results.treatment_colors} active={active} showPredicted={false} /><p className="chart-footnote">Each point is a measured mouse tumor volume. Select a line or tap a treatment to isolate it.</p></div><SimpleNote>The colored dots are real measurements. A single line may respond differently from another, which is why the model allows line-specific growth.</SimpleNote></div></section>

      <section className="section" id="model">
        <div className="content">
          <SectionHeading label="The mechanism" title="A small model of growth, treatment, and resistance.">
            I divide each tumor into sensitive (S) and relatively resistant (R) volume. Select a model component to see its equation term and a one-at-a-time comparison for the chosen PDX line.
          </SectionHeading>
          <ModelExplorer results={results} lineId={lineId} lines={lines} onLineChange={setLineId} />
          <SimpleNote>When ψ is zero, the combination follows Bliss independent action at the assumed dose. The chart changes one model setting at a time; it does not replace a full refit or measured data.</SimpleNote>
        </div>
      </section>

      <section className="section section-dark" id="simulator"><div className="content"><SectionHeading label="Try the model" title="Move ψ. Watch the four curves.">The browser solves the same two-population equations with RK4. Adjust either drug effect or the interaction and see how the projected volumes separate.</SectionHeading><Simulator results={results} lineId={lineId} /><SimpleNote>A slider changes a model assumption, not a measured outcome. The simulation starts from the selected PDX line’s actual baseline.</SimpleNote></div></section>

      <section className="section section-soft" id="fit"><div className="content"><SectionHeading label="Fit against reality" title="The model explains some patterns, not every point.">Lines show fitted ODE trajectories; dots show the observed tumor volumes. The residuals reveal where the model misses.</SectionHeading><div className="two-card"><div className="chart-card"><div className="card-top"><div><span className="eyebrow">Model vs data</span><h3>{lineId} · all four arms</h3></div></div><TumorChart points={selectedPoints} colors={results.treatment_colors} active={arms} /><p className="chart-footnote">Solid lines are fitted. Dots are observed.</p></div><div className="chart-card"><div className="card-top"><div><span className="eyebrow">Residual pattern</span><h3>Misses over time</h3></div></div><ResidualChart points={results.trajectories} colors={results.treatment_colors} sigma={results.fixed_assumptions.sigma_log} /><p className="chart-footnote">Across all lines. A flat, random cloud would support the error model; structure remains.</p></div></div><SimpleNote>The log-volume RMSE is {format(summary.rmse_log_volume, 2)}. {summary.capacity_parameters_at_bound} of {lines.length} carrying-capacity estimates sit at a fitting bound, so I do not interpret the fitted parameters as exact biology.</SimpleNote></div></section>

      <section className="section" id="evidence"><div className="content"><SectionHeading label="The evidence" title="A small p-value is only one part of the answer.">With the reported lower BYL719 dose in the combination, a fitted interaction improves the score. Other checks reveal how fragile that result is.</SectionHeading><div className="evidence-grid"><div className="evidence-card emphasis"><span>Assumed BYL719 dose ratio</span><strong>{format(results.fixed_assumptions.combo_a_dose_ratio, 1)}×</strong><p>30 mg/kg in the combination versus 50 mg/kg alone, converted to proportional effective exposure.</p></div><div className="evidence-card"><span>Conditional LRT</span><strong>p = {summary.lrt_p_value.toExponential(1)}</strong><p>The free-ψ fit scores better than the Bliss fit when this exposure ratio is held fixed.</p></div><div className="evidence-card"><span>Equal-dose refit</span><strong>p = {format(dose.equal_dose_lrt_p_value, 2)}</strong><p>With the BYL719 dose ratio set to 1, the signal disappears and AIC/BIC favor Bliss.</p></div></div><div className="confidence-layout"><div className="chart-card"><span className="eyebrow">Profile likelihood</span><h3>How sharply is ψ located?</h3><ProfileChart results={results} /><p className="chart-footnote">All other parameters were refitted at each ψ value. The upper 95% interval meets the search bound.</p></div><div className="ci-card"><span className="eyebrow">95% intervals for ψ</span><div className="ci-row"><span>Jacobian</span><strong>[{format(results.jacobian_uncertainty.ci95.psi[0], 1)}, {format(results.jacobian_uncertainty.ci95.psi[1], 1)}]</strong></div><div className="ci-row"><span>Bootstrap · {results.bootstrap_uncertainty.completed_replicates} refits</span><strong>[{format(summary.psi_bootstrap_ci95[0], 0)}, {format(summary.psi_bootstrap_ci95[1], 0)}]</strong></div><div className="ci-row"><span>Refitted profile</span><strong>[{format(summary.psi_profile_ci95[0], 1)}, {format(summary.psi_profile_ci95[1], 0)}]*</strong></div><p>* The right endpoint reaches the fitting boundary, so it is not a closed upper limit. The bootstrap reaches both boundaries.</p></div></div><div className="two-card diagnostic-row"><div className="chart-card"><span className="eyebrow">±10% local sensitivity</span><h3>Which knobs move the final volume?</h3><SensitivityChart results={results} /><p className="chart-footnote">Normalized final combination-volume sensitivity; pink indicates a negative effect.</p></div><div className="chart-card"><span className="eyebrow">Parameter correlation</span><h3>What trades off in the fit?</h3><CorrelationChart results={results} /><p className="chart-footnote">All 23 fitted parameters. Red is positive and blue is negative; each cell exposes its value to assistive technology.</p></div></div><SimpleNote>The methods disagree about how tightly ψ is known. The dose counterfactual is more decisive: apparent synergy is not robust to a plausible exposure choice.</SimpleNote></div></section>

      <section className="section conclusion" id="conclusion"><div className="content conclusion-layout"><div><span className="eyebrow">What I can say</span><h2>There is a signal.<br /><em>There is not yet a verdict.</em></h2></div><div><p>The fitted ODE suggests excess combination effect under the published differential-dose schedule and a proportional exposure assumption. With equal assumed doses, the evidence favors simple independent action.</p><ul><li>One mouse per line and arm cannot reveal biological replicate variation.</li><li>Drug concentrations, PK, and cell-state fractions were not measured.</li><li>Residual structure and bound-constrained growth parameters limit interpretation.</li></ul><p>Matched dose pairs, repeated mice, and concentration or pathway measurements would make a stronger synergy test possible.</p></div></div></section>

      <section className="section methods" id="methods"><div className="content"><SectionHeading label="Methods & sources" title="Every number has a trail.">The source workbook, selection rule, optimization settings, code, and report are available for inspection.</SectionHeading><div className="method-list"><div><strong>Source</strong><p>Gao et al., <i>Nature Medicine</i> (2015), <a href="https://doi.org/10.1038/nm.3954">doi:10.1038/nm.3954 ↗</a>. PCT raw data from its official supplementary workbook.</p></div><div><strong>Dose schedule</strong><p>Baaz, Cardilin & Jirstrand, <i>Eur. J. Pharm. Sci.</i> (2024), <a href="https://doi.org/10.1016/j.ejps.2024.106901">doi:10.1016/j.ejps.2024.106901 ↗</a>.</p></div><div><strong>Fit</strong><p>Logistic growth selected over Gompertz on control AICc ({format(results.control_growth_comparison.logistic.aicc, 1)} vs {format(results.control_growth_comparison.gompertz.aicc, 1)}). Differential evolution followed by joint bounded least squares; 200 trajectory-block bootstrap refits.</p></div><div><strong>Read the work</strong><p><a href="/report.pdf">Download the seven-page report ↗</a> · <a href="https://github.com/zzkhxyz/endterm-bio">Browse code and processed CSV ↗</a> · <a href="/data/results.json">Inspect site data JSON ↗</a></p></div></div></div></section>
    </div><footer className="site-footer"><div className="content"><span>PDX / interaction</span><span>Reproducible preclinical analysis · {new Date().getFullYear()}</span><a href="#top">Back to top ↑</a></div></footer>
  </>;
}



