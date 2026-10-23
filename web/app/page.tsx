import results from "../public/data/results.json";
import LazyStory from "./lazy-story";
import ResearchPath from "./research-path";
import ThemeToggle from "./theme-toggle";

export default function Home() {
  const lineIds = new Set(results.trajectories.map((point) => point.pdx_id));
  const replicatesPerArm = results.trajectories.filter((point) => point.pdx_id === results.trajectories[0].pdx_id && point.treatment === "control" && point.day === 0).length;
  return <>
    <header className="site-header">
      <a className="brand" href="#top" aria-label="Synergy study, back to top"><span className="brand-icon">S/R</span><span>PDX / interaction</span></a>
      <nav aria-label="Main navigation"><a href="#data">Data</a><a href="#model">Model</a><a href="#evidence">Evidence</a><a href="#methods">Methods</a></nav>
      <div className="header-actions">
        <a className="github-link" href="https://github.com/zzkhxyz/endterm-bio" target="_blank" rel="noopener noreferrer" aria-label="Open project repository on GitHub (opens in a new tab)">GitHub <span aria-hidden="true">↗</span></a>
        <ThemeToggle />
      </div>
    </header>
    <main id="top"><section className="hero"><div className="hero-inner"><div className="hero-kicker"><span className="pulse" /> A preclinical combination, examined closely</div><h1>Stronger together?<br /><span>The answer depends on dose.</span></h1><p className="hero-lede">In {lineIds.size} breast-cancer PDX lines, BYL719 + LJM716 looks synergistic under one exposure assumption. Change that assumption, and the statistical signal disappears.</p><p className="hero-author"><span>Research by</span><strong>Zhan Tabuldinov</strong><span aria-hidden="true">·</span><strong>BDA-2401</strong></p><div className="hero-actions"><a className="button-primary" href="#evidence">Explore the evidence <span aria-hidden="true">↗</span></a><a className="button-ghost" href="/report.pdf">Read the PDF report ↗</a></div><div className="hero-stat-row"><div><span>Conditional interaction</span><strong>ψ = {results.summary.psi_point.toFixed(1)}</strong></div><div><span>Equal-dose refit</span><strong>ψ = {results.dose_assumption_sensitivity.equal_dose_psi_point.toFixed(1)}</strong></div><div><span>Biological replicates per arm</span><strong>{replicatesPerArm}</strong></div></div></div></section><ResearchPath /><LazyStory /></main>
  </>;
}
