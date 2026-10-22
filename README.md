# Synergy or simple addition?

A mechanistic ODE analysis of combination therapy in patient-derived xenografts, using the Gao et al. PDX screening data. The project is being developed in stages.

## Source

Gao H, Korn JM, Ferretti S, et al. *High-throughput screening using patient-derived tumor xenografts to predict clinical trial drug response.* Nature Medicine 21, 1318–1325 (2015). [doi:10.1038/nm.3954](https://doi.org/10.1038/nm.3954). The official supplementary table is downloaded by the analysis pipeline; its 122 MB raw XLSX file is excluded from Git.

## Decisions

- The repository was empty at project start. This small `main` bootstrap commit establishes a working base for the requested stage branches and pull requests.
- Stage 1 validates the source schema and selects a complete control/A/B/A+B quartet before any model fitting. The dataset's measurement units are checked directly; missing absolute tumor volumes will not be invented.
