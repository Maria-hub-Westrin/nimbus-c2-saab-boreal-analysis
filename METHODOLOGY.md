# Methodology

## Environment

- **Operating system:** Windows 10/11, PowerShell 5
- **Python:** 3.12.10 (CPython)
- **Key dependencies** (installed via `pip install -e ".[dev]"`):
  - `nimbus-c2` v1.0.0 (imported from `git+https://github.com/Maria-hub-Westrin/nimbus-c2.git@main`, unmodified)
  - `numpy` ≥ 1.24
  - `matplotlib` (for figure rendering in notebooks)
  - `pytest` ≥ 7, `pytest-cov`, `mypy`, `ruff` (dev)
  - `jupyter`, `nbconvert` (for notebook execution)

## Reproducibility protocol

Every notebook in this repository is **deterministic by construction**:

- No calls to `random`, `numpy.random` without an explicit seed.
- No use of wall-clock time as an input.
- No environment-dependent defaults (e.g. locale-sensitive parsing).
- Sort order is explicit wherever order affects output (`sorted()`, `sort_keys=True`).

Running a notebook twice on the same commit of this repository produces byte-identical figures, text output, and JSON reports. If a discrepancy arises, it is a detectable event — either the upstream engine version changed, a dependency introduced non-determinism, or the platform diverged. In any of these cases, the SHA-256 hashes in `results/determinism_report.json` will fail to match.

## What data was used

The only data source in this repository is the two files supplied by Saab:

- `data/saab/Boreal_passage_coordinates.csv` (3597 bytes) — 12 installations + 8 terrain features
- `data/saab/the-boreal-passage-map.svg` (8511 bytes) — reference visualisation for validation

Both files are also bundled inside the package under `src/nimbus_saab_ext/data/` so they are available via `importlib.resources` when the package is installed.

No other data is used. In particular:

- **No OpenSky ADS-B data** is used. The Nimbus-C2 codebase contains an OpenSky adapter for analysing real civilian traffic, but mixing real ADS-B data with a fictitious military scenario would compromise *construct validity*. OpenSky is therefore excluded from this analysis and is listed only as future work below.

## Extension pattern

The extension imports `nimbus-c2` as an unmodified git dependency. This architectural choice is deliberate:

1. **Scientific integrity:** the engine's behaviour seen in this repository is the engine's behaviour as shipped, not a modified version.
2. **Reviewability:** a reviewer can diff this repository against upstream Nimbus-C2 and confirm that no engine code has been copied or altered.
3. **Separability:** failures in this experimental work cannot degrade the engine's main branch, its CI, or its release state.

The extension exposes a small public API (`load_boreal_geography`, `BOREAL_SCENARIOS`, `boreal_scenario_as_engine_inputs`, `build_boreal_scenario`) and nothing else.

## Claims and their supporting evidence

| Claim | Notebook | Machine-readable artefact |
|---|---|---|
| Geography integration is lossless | `01_geography_verification.ipynb` | `results/figures/01_boreal_geography.png` |
| The pipeline is deterministic | `02_pipeline_determinism.ipynb` | `results/determinism_report.json` |
| Autonomy mode grades predictably | `03_scenario_analysis.ipynb` | `results/scenario_outcomes.json` |

See [`SCIENTIFIC_CLAIMS.md`](SCIENTIFIC_CLAIMS.md) for the exact scope of what each claim does and does not cover.

## Future work

The following directions are **out of scope** for this repository but are noted so reviewers can see where the work can be extended:

- **Broader scenario coverage.** Four scenarios are a small sample. More varied geometry, threat structure, and sensor mixes would strengthen the behavioural grading claim.
- **Threshold calibration.** The AUTONOMOUS/ADVISE/DEFER thresholds are engineering defaults. Calibration against operational data is a prerequisite for any production use.
- **Real-data evaluation via OpenSky.** Running the engine against live ADS-B traffic over a geographic region of interest would test behaviour on real data. This is a separate artefact (different construct, different claims) and is not part of the Boreal Passage evaluation.
- **Robustness testing.** Perturbation sensitivity (how small input changes affect output) is orthogonal to determinism and would require its own experimental design.
- **Operator-in-the-loop evaluation.** COA quality and autonomy-mode appropriateness are ultimately operator-validated questions that cannot be answered by offline analysis alone.
