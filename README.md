# Synergy or simple addition?

A mechanistic ODE analysis of combination therapy in patient-derived xenografts, using the Gao et al. PDX screening data. The repository includes the complete analysis, report, and interactive site.

**Live site:** [endterm-bio.vercel.app](https://endterm-bio.vercel.app) · **Report:** [report.pdf](report/report.pdf)

## Reproduce and submit

With Python 3.11+, Node.js 24+, npm, GNU Make, and internet access, run `make all` at the repository root. This installs the pinned Python and Node dependencies, verifies or downloads the official source XLSX, regenerates the processed data and fitted results, compiles the PDF with a pinned Tectonic release, refreshes site assets, builds the static site, and creates ignored `submission.zip`. The first run downloads about 122 MB of source data and TeX support files and takes substantially longer than later runs. On Windows, use GNU Make from Git Bash or an equivalent installation.

Individual commands: `make data`, `make fit`, `make report`, `make web-data`, `make web-build`, and `make zip`. The ZIP contains `report/report.pdf`, `README.md`, and the `analysis/` code, notebook, processed CSV, figures, and results. Raw XLSX and the ZIP are excluded from Git.

## Stage 1: data

The official spreadsheet contains **67,445 measurement rows** in its `PCT raw data` sheet, including absolute `Volume (mm3)` and `Days Post T0`. We kept series with at least six measurements, no missing day or volume, positive volumes, unique measurement days, and a day-zero baseline. A complete quartet has untreated, each single agent, and their combination for the same PDX line.

`BYL719 + LJM716` has the most eligible quartets: **52** across BRCA and GC. BRCA has **29**. To meet the intended compact 1×1×1 analysis size, the committed [CSV](analysis/data/processed/pdx_combo.csv) contains ten BRCA lines: **X-3450, X-1383, X-3873, X-1008, X-3468, X-5502, X-5355, X-3697, X-1468, X-4888**. It has **40 mouse trajectories and 838 measured time points**, with no missing volumes or duplicate line/treatment/day keys. The [selection record](analysis/data/processed/selection.json) includes the full combination ranking and source checksum.

In the CSV, `control = untreated`, `A = BYL719`, `B = LJM716`, and `A+B = BYL719 + LJM716`. Time is in days and observed tumor volume is in mm³.

To regenerate from the original source:

```bash
python -m pip install -e 'analysis[dev]'
make data
```

`make data` downloads the 122 MB official XLSX only if absent, verifies its SHA-256, and writes the committed CSV, selection record, and [selected pathway annotations](analysis/data/processed/selected_biomarkers.csv). To supply an already downloaded copy, run `python -m pdxmodel.data --source /path/to/original.xlsx` after installation.

## Stage 2: model and fit

Run `make fit` after `make data`. The pipeline selects growth form on untreated curves, jointly fits the four treatment arms with a two-population ODE, refits a Bliss-null model, computes 200 bootstrap fits and refitted profiles, and saves [numerical results](analysis/outputs/results.json) plus [PNG/SVG diagnostics](analysis/outputs/figures). The same JSON is copied to `web/public/data/` for the site. Equations, units, fixed assumptions, and optimizer details are in [MODEL.md](analysis/MODEL.md); the [notebook](analysis/notebooks/main.ipynb) is a compact inspection entry point.

**Current result:** logistic growth beats Gompertz on controls (AICc −102.30 versus −67.89). A published reanalysis reports a lower BYL719 dose in the combination than alone; under a dose-proportional Emax scaling assumption, the conditional free fit estimates `ψ=26.73` and outperforms Bliss (likelihood-ratio `p=2.4×10⁻⁶`). Yet the 200-replicate trajectory-block bootstrap interval spans the full `[-1, 50]` search range, and the fit has log-volume RMSE 0.52 with 8 of 10 carrying capacities at a bound. Under an equal-dose counterfactual, refitting gives `ψ=1.81`, `p=0.63`, and AIC/BIC favor Bliss. Thus **apparent synergy depends on dose scaling and is not robustly identified**. The divergent profile/bootstrap intervals and structured residuals must be considered when interpreting this model.

## Stage 3: report

The [seven-page report](report/report.pdf) covers Parts A–F, equations, parameters, figures, limitations, and references. Its editable [LaTeX source](report/report.tex) compiles with [Tectonic](https://tectonic-typesetting.github.io/) using `make report` after `make fit`. The report's numeric results come from the committed `results.json`; it states the 0.6 dose-exposure assumption and the equal-dose refit separately. The raw source has four selected PI3K/HER2-pathway alteration records; missing records are not treated as wild type.

## Stage 4: interactive site

The [Next.js App Router site](web/) exports to static HTML and uses the same [results JSON](web/public/data/results.json) as the report. It has a research-path navigator, an interactive mechanism map that highlights ODE terms and compares one-at-a-time model scenarios, a shared PDX selector, treatment-group chart, measured-versus-fitted comparison, residuals, a browser RK4 simulator, profile likelihood, local sensitivity, and a full parameter-correlation heatmap. The hero is statically rendered; data-heavy charts load when the reader scrolls or follows a section link. This keeps the initial page fast while preserving all interactive analysis. It supports light and dark themes and mobile layouts. The seven-page PDF is copied to `web/public/report.pdf` by `make web-data`.

Vercel project `zzkhxyz/endterm-bio` is connected to this GitHub repository with Root Directory `web` and the Next.js framework preset. The production branch is `main`; Git integration supplies preview builds for pull requests.

The local static export scored **96 Performance** and **100 Accessibility** in Lighthouse's mobile audit. The production site and PDF were checked in a browser with no console errors; a production Lighthouse run was inconclusive in this environment because headless Chrome displayed a network interstitial.

## Source

Gao H, Korn JM, Ferretti S, et al. *High-throughput screening using patient-derived tumor xenografts to predict clinical trial drug response.* Nature Medicine 21, 1318–1325 (2015). [doi:10.1038/nm.3954](https://doi.org/10.1038/nm.3954). [Official supplementary table 1](https://static-content.springer.com/esm/art%3A10.1038%2Fnm.3954/MediaObjects/41591_2015_BFnm3954_MOESM10_ESM.xlsx). Its 122 MB raw XLSX file is excluded from Git. The paper reports the 1×1×1 screening design; the workbook supplies individual absolute tumor volumes.

## Decisions

- The repository was empty at project start. This small `main` bootstrap commit establishes a working base for the requested stage branches and pull requests.
- Source verification uses the exact SHA-256 of the official XLSX to detect changed or partial downloads.
- Series with any missing day/volume or duplicate measurement day are excluded, a stricter rule than only requiring the first three points to be complete.
- The combination is chosen by the largest number of complete quartets across the full source. BRCA is chosen because it has more quartets for that combination than GC. Within BRCA, ten lines are selected by the **minimum number of measurements across the four groups**, then the **minimum last day across groups**, then PDX ID. This rule does not inspect response magnitude.
- The 1×1×1 design provides one trajectory per line and treatment. The variation between lines is biological heterogeneity, not a within-line replicate error estimate.
- We scale BYL719 Emax exposure by 0.6 in the combination, based on reported 50 versus 30 mg/kg dosing. This is an assumed dose-to-concentration relation; an equal-dose refit shows that the synergy conclusion is sensitive to it.
- The 0.15 log-volume scale is a caliper-error weighting proxy, not an estimated PDX cohort variance. The bootstrap preserves whole-trajectory residual patterns but cannot supply missing biological replicates.
- Selected pathway annotations are extracted from the official mutation/copy-number worksheet solely for context; their sparsity precludes a genotype-response test.
- Website colors use the treatment-color map exported with `results.json`. The site avoids a definitive synergy headline because the equal-dose refit and bootstrap do not support one.
- The report PDF is committed under `report/` and copied into the site's public folder for a direct download. The `submission.zip` archive remains untracked.
