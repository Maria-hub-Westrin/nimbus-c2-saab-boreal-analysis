# Nimbus-C2 · Boreal Passage Analysis (Saab Extension)

[![CI](https://github.com/Maria-hub-Westrin/nimbus-c2-saab-boreal-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/Maria-hub-Westrin/nimbus-c2-saab-boreal-analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

**What this is:** a separate analysis repository that applies the
[Nimbus-C2](https://github.com/Maria-hub-Westrin/nimbus-c2) reliability-aware
decision engine to the Boreal Passage scenario supplied by Saab.

**What this is NOT:** a modified fork of Nimbus-C2. The underlying engine is
imported as an unmodified git dependency. Nimbus-C2's 157 tests, assurance layer,
and Stage 2b conformal-prediction infrastructure are untouched.

## Results at a glance

| Artefact | Claim | Evidence |
|---|---|---|
| 1 | Saab's geography loads losslessly into the engine's dataclasses | [Notebook 01](notebooks/01_geography_verification.ipynb) |
| 2 | The engine is deterministic (100 runs × 4 scenarios → 4 unique hashes) | [Notebook 02](notebooks/02_pipeline_determinism.ipynb) + [`results/determinism_report.json`](results/determinism_report.json) |
| 3 | Autonomy mode grades predictably with sensor quality | [Notebook 03](notebooks/03_scenario_analysis.ipynb) + [`results/scenario_outcomes.json`](results/scenario_outcomes.json) |

**See [`SCIENTIFIC_CLAIMS.md`](SCIENTIFIC_CLAIMS.md) for what this repository does and does not demonstrate.**

## Scope

- Load the Saab-supplied tactical canvas (CSV + SVG) into Nimbus-C2's existing `Base` / `Threat` / `CommandersIntent` dataclasses.
- Run four doctrine-realistic scenarios (clean / swarm / jammed / strait).
- Demonstrate pipeline determinism (byte-identical output across 100 runs).
- Characterise assurance-layer behaviour (AUTONOMOUS / ADVISE / DEFER) under varying information quality.

## Reproducing the analysis

```bash
git clone https://github.com/Maria-hub-Westrin/nimbus-c2-saab-boreal-analysis.git
cd nimbus-c2-saab-boreal-analysis
pip install -e ".[dev]"
pytest                                   # 53 passed, 1 xfailed
jupyter nbconvert --to notebook --execute notebooks/*.ipynb
```

Then open `results/determinism_report.json` and `results/scenario_outcomes.json` for the machine-readable results. See [`METHODOLOGY.md`](METHODOLOGY.md) for the full methodology, environment, and the explicit list of what is and is not in scope.

## Maturity

- **Engine:** Nimbus-C2 v1.0.0 — Stage 2b prototype (TRL 3–4)
- **Extension:** v0.1.0 — analysis artefact, not a product

## License

MIT. Copyright © 2026 Team Ruby: Maria Westrin, Ulrika Wennberg, Dhiraj Kumar, Adam Chahoud, Mousumi, Hitesh.
