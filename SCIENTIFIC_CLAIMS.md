# Scientific Claims and Limitations

This document states precisely what this repository demonstrates, and — equally importantly — what it does **not** demonstrate. It is the primary reference for anyone evaluating the scientific weight of the results.

## What this repository demonstrates

### Claim 1 — Geography integration is lossless

The `nimbus_saab_ext` adapter loads the Saab-supplied canvas (`Boreal_passage_coordinates.csv`, 12 location records and 8 terrain records) into the Nimbus-C2 engine's existing dataclasses (`Base`, `Threat`, `CommandersIntent`) without loss of information. The CSV-to-engine coordinate transformation (image-space y-down → engine y-up) is explicit and documented in `src/nimbus_saab_ext/scenarios.py`.

**Evidence:** [`notebooks/01_geography_verification.ipynb`](notebooks/01_geography_verification.ipynb) + rendered figure `results/figures/01_boreal_geography.png`.

### Claim 2 — The pipeline is deterministic

Given identical inputs, the engine produces byte-identical output. Across four Boreal Passage scenarios with 100 runs each (400 total `evaluate()` calls), every scenario yields exactly one distinct SHA-256 hash. A third-party reviewer can reproduce the exact hashes on their own machine.

**Evidence:** [`notebooks/02_pipeline_determinism.ipynb`](notebooks/02_pipeline_determinism.ipynb) + machine-readable audit `results/determinism_report.json`.

### Claim 3 — Autonomy mode grades predictably with information quality

For the four scenarios tested, the engine's autonomy-mode decision matches the expected mode in every case. Crucially, the ordering is monotone: as situational-awareness health degrades and situation complexity rises, the engine transitions from AUTONOMOUS to ADVISE to DEFER. The jammed scenario additionally surfaces alerts, which is the mechanism operators rely on to know when not to trust the picture.

| Scenario | Expected | Actual | SA health | Alerts |
|---|---|---|---|---|
| clean   | AUTONOMOUS | AUTONOMOUS | 92.6 | 0 |
| strait  | ADVISE     | ADVISE     | 68.8 | 0 |
| swarm   | ADVISE     | ADVISE     | 64.7 | 0 |
| jammed  | DEFER      | DEFER      | 20.5 | 2 |

**Evidence:** [`notebooks/03_scenario_analysis.ipynb`](notebooks/03_scenario_analysis.ipynb) + `results/scenario_outcomes.json`.

### Claim 4 — The extension does not modify Nimbus-C2

`nimbus-c2` is declared as a git dependency in `pyproject.toml` and imported without modification. The upstream engine's 157 tests remain green. The extension cannot change the engine's behaviour; it can only supply scenario data to it.

**Evidence:** `pyproject.toml` (dependency declaration) + `pip install -e .[dev]` on a clean environment reproduces the setup without touching the upstream repository.

## What this repository does NOT demonstrate

Readers must not over-interpret the evidence above. The following are **explicitly out of scope**.

### Correctness of individual decisions

Determinism guarantees reproducibility, not correctness. We show that the same input always produces the same output, not that the output is tactically right. Correctness would require operational ground truth, which is not available for the fictitious Boreal Passage canvas.

### Threshold calibration

The AUTONOMOUS/ADVISE/DEFER thresholds in the assurance layer are engineering defaults, not operationally calibrated values. Matching expected modes across four scenarios shows the engine is internally consistent, not that the thresholds are placed where an experienced operator or doctrine would place them. Calibration against real operational data is future work.

### Course-of-action quality

The engine proposes three courses of action per scenario. Their tactical merit is not evaluated in this repository. A reviewer can see them in the notebook outputs, but this repository makes no claim about whether they are good tactical choices.

### Robustness to perturbation

Determinism is orthogonal to robustness. Small changes in input (e.g., a threat position shifted by a kilometre) may or may not change the output. This property is not tested here.

### Generalisation beyond four scenarios

Four scenarios is a small sample. The behavioural grading observed on these four may or may not hold on scenarios with very different structure (e.g., simultaneous multi-axis attacks, asymmetric sensor coverage). Broader coverage is future work.

### Production readiness

Nimbus-C2 is at TRL 3–4 (Stage 2b prototype). This extension is a v0.1.0 analysis artefact. Neither is suitable for deployment.

## Maturity statement

- **Engine:** Nimbus-C2 v1.0.0 — Stage 2b prototype, TRL 3–4.
- **Extension:** nimbus-saab-ext v0.1.0 — analysis artefact, not a product.
- **Prepared for:** evaluation by Saab, as a demonstration that the Nimbus-C2 pipeline can be applied to a Saab-supplied scenario canvas.

## How to verify these claims yourself

```bash
git clone https://github.com/Maria-hub-Westrin/nimbus-c2-saab-boreal-analysis.git
cd nimbus-c2-saab-boreal-analysis
pip install -e ".[dev]"
pytest                                          # 53 passed, 1 xfailed
jupyter nbconvert --to notebook --execute notebooks/*.ipynb
cat results/determinism_report.json             # verdict should be ALL_DETERMINISTIC
cat results/scenario_outcomes.json              # all_match_expected should be true
```

If the determinism hashes differ from those committed in this repository, either the Nimbus-C2 version has changed, a dependency has introduced non-determinism, or the underlying platform has diverged. In any of those cases the discrepancy is detectable, which is exactly the property this repository is designed to guarantee.
