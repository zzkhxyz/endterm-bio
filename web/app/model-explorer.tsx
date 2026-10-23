"use client";

import { useMemo, useState } from "react";
import { line, scaleLinear } from "d3";
import katex from "katex";
import { ResultData, simulate } from "../lib/model";

type Mechanism = "growth" | "drug" | "resistance" | "interaction";
type Curve = { day: number; volume: number }[];

const parts: { id: Mechanism; symbol: string; label: string; title: string; detail: string; change: string }[] = [
  {
    id: "growth", symbol: "g", label: "Growth", title: "Growth slows as the tumor fills its capacity.",
    detail: "Each PDX line has its own growth rate r and capacity K. Both sensitive and resistant volume share this logistic growth term.",
    change: "Illustration: growth rate +25%",
  },
  {
    id: "drug", symbol: "κ", label: "Drug pressure", title: "Treatment removes sensitive volume.",
    detail: "The treatment effect E is multiplied by a fixed kill ceiling κ. Relatively resistant volume receives only a fraction η of that kill.",
    change: "Illustration: kill ceiling +25%",
  },
  {
    id: "resistance", symbol: "R", label: "Resistance", title: "Some volume is less affected by treatment.",
    detail: "The fit starts with 2% resistant volume. The μ term transfers sensitive volume into that state; the comparison below starts with 20% instead.",
    change: "Illustration: initial resistant share 20%",
  },
  {
    id: "interaction", symbol: "ψ", label: "Interaction", title: "The combination can depart from Bliss action.",
    detail: "The fitted ψ adds combination effect beyond Bliss at the assumed BYL719 dose ratio of 0.6. Setting ψ to zero shows the Bliss case without refitting.",
    change: "Illustration: ψ = 0 (Bliss)",
  },
];

function Equation({ tex }: { tex: string }) {
  const html = useMemo(() => katex.renderToString(tex, { displayMode: true, throwOnError: false }), [tex]);
  return <div className="explorer-equation" dangerouslySetInnerHTML={{ __html: html }} />;
}

function MechanismChart({ fitted, scenario, change }: { fitted: Curve; scenario: Curve; change: string }) {
  const width = 660, height = 265, left = 48, right = 16, top = 16, bottom = 39;
  const lastDay = Math.max(1, fitted.at(-1)?.day ?? 1);
  const maxVolume = Math.max(1, ...fitted.map((p) => p.volume), ...scenario.map((p) => p.volume)) * 1.08;
  const x = scaleLinear().domain([0, lastDay]).range([left, width - right]);
  const y = scaleLinear().domain([0, maxVolume]).range([height - bottom, top]);
  const path = line<{ day: number; volume: number }>().x((p) => x(p.day)).y((p) => y(p.volume));
  return <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Modeled combination tumor volume: fitted parameters compared with ${change}`}>
    {[0, .25, .5, .75, 1].map((fraction) => <g key={fraction}>
      <line x1={left} x2={width - right} y1={y(maxVolume * fraction)} y2={y(maxVolume * fraction)} className="grid-line" />
      <text x={left - 8} y={y(maxVolume * fraction) + 4} textAnchor="end" className="axis-text">{Math.round(maxVolume * fraction)}</text>
    </g>)}
    {[0, .5, 1].map((fraction) => <text key={fraction} x={x(lastDay * fraction)} y={height - 15} textAnchor="middle" className="axis-text">{Math.round(lastDay * fraction)}</text>)}
    <path d={path(fitted) ?? ""} className="explorer-line-fitted" />
    <path d={path(scenario) ?? ""} className="explorer-line-scenario" />
    <text x={width / 2} y={height - 1} textAnchor="middle" className="axis-label">Days after baseline</text>
    <text transform={`translate(12 ${height / 2}) rotate(-90)`} textAnchor="middle" className="axis-label">Volume · mm³</text>
  </svg>;
}

export default function ModelExplorer({ results, lineId, lines, onLineChange }: {
  results: ResultData; lineId: string; lines: string[]; onLineChange: (line: string) => void;
}) {
  const [selected, setSelected] = useState<Mechanism>("growth");
  const part = parts.find((item) => item.id === selected)!;
  const fixed = results.fixed_assumptions;
  const effects = { a: results.summary.e_a, b: results.summary.e_b, psi: results.summary.psi_point };
  const initial = results.trajectories.find((p) => p.pdx_id === lineId && p.treatment === "A+B" && p.day === 0)?.observed_mm3 ?? 0;
  const horizon = Math.ceil(Math.max(...results.trajectories.filter((p) => p.pdx_id === lineId).map((p) => p.day)));
  const growth = results.parameters[`r_${lineId}`];
  const capacity = results.parameters[`K1000_${lineId}`] * 1000;
  const fitted = useMemo(() => simulate(initial, growth, capacity, effects, fixed, "A+B", horizon),
    [initial, growth, capacity, effects.a, effects.b, effects.psi, fixed, horizon]);
  const scenario = useMemo(() => {
    if (selected === "growth") return simulate(initial, growth * 1.25, capacity, effects, fixed, "A+B", horizon);
    if (selected === "drug") return simulate(initial, growth, capacity, effects, { ...fixed, kill_ceiling_per_day: fixed.kill_ceiling_per_day * 1.25 }, "A+B", horizon);
    if (selected === "resistance") return simulate(initial, growth, capacity, effects, { ...fixed, initial_resistant_fraction: .20 }, "A+B", horizon);
    return simulate(initial, growth, capacity, { ...effects, psi: 0 }, fixed, "A+B", horizon);
  }, [selected, initial, growth, capacity, effects.a, effects.b, effects.psi, fixed, horizon]);
  const highlight = (tex: string, on: Mechanism) => selected === on ? String.raw`\color{#1683ed}{${tex}}` : tex;
  const sEquation = String.raw`\frac{dS}{dt}=\left[${highlight("g_i(V)", "growth")}-${highlight(String.raw`\kappa E_t`, "drug")}-${highlight(String.raw`\mu`, "resistance")}\right]S`;
  const rEquation = String.raw`\frac{dR}{dt}=\left[${highlight("g_i(V)", "growth")}-${highlight(String.raw`\eta\kappa E_t`, "drug")}\right]R+${highlight(String.raw`\mu S`, "resistance")}`;
  const comboEquation = String.raw`E_{A+B}=e_{A,c}+e_B-e_{A,c}e_B+${highlight(String.raw`\psi e_{A,c}e_B`, "interaction")}`;
  const final = (curve: Curve) => Math.round(curve.at(-1)?.volume ?? 0).toLocaleString("en-US");

  return <div className="model-explorer">
    <div className="explorer-topline"><span className="eyebrow">Explore the mechanism</span>
      <label className="select-wrap">PDX line<select value={lineId} onChange={(event) => onLineChange(event.target.value)}>
        {lines.map((id) => <option key={id} value={id}>{id}</option>)}
      </select></label>
    </div>
    <div className="explorer-tabs" role="group" aria-label="Model components">
      {parts.map((item) => <button key={item.id} type="button" className={`explorer-tab ${selected === item.id ? "is-active" : ""}`}
        aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>
        <span className="explorer-symbol" aria-hidden="true">{item.symbol}</span><span>{item.label}</span>
      </button>)}
    </div>
    <div className="explorer-body">
      <div className="explorer-explanation" aria-live="polite">
        <h3>{part.title}</h3><p>{part.detail}</p>
        <div className="explorer-formulas" aria-label="ODE terms; the selected component is blue">
          <Equation tex={sEquation} /><Equation tex={rEquation} /><Equation tex={comboEquation} />
        </div>
        <a className="explorer-link" href="#simulator">Adjust the full model ↗</a>
      </div>
      <div className="explorer-plot">
        <div className="explorer-plot-title"><span className="eyebrow">What changes?</span><strong>{part.change}</strong></div>
        <MechanismChart fitted={fitted} scenario={scenario} change={part.change} />
        <div className="explorer-legend"><span><i className="explorer-swatch-fitted" />Fitted parameters · {final(fitted)} mm³</span><span><i className="explorer-swatch-scenario" />Changed case · {final(scenario)} mm³</span></div>
        <p className="explorer-caveat">One parameter changes at a time. These curves are model illustrations, not new observations or refitted estimates.</p>
      </div>
    </div>
  </div>;
}
