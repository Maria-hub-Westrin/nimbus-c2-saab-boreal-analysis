# Nimbus-C2 · Boreal Passage Analysis (Saab Extension)

**What this is:** a separate analysis repository that applies the
[Nimbus-C2](https://github.com/Maria-hub-Westrin/nimbus-c2) reliability-aware
decision engine to the Boreal Passage scenario supplied by Saab.

**What this is NOT:** a modified fork of Nimbus-C2. The underlying engine is
imported as an unmodified dependency. Nimbus-C2''s 157 tests, assurance layer,
and Stage 2b conformal-prediction infrastructure are untouched.

## Scope

- Load the Saab-supplied tactical canvas (CSV + SVG) into Nimbus-C2''s
  existing `Base` / `Threat` / `CommandersIntent` dataclasses.
- Run four doctrine-realistic scenarios (clean / swarm / jammed / strait).
- Demonstrate pipeline determinism (byte-identical output across 100 runs).
- Characterise assurance-layer behaviour (AUTONOMOUS / ADVISE / DEFER) under
  varying information quality.

## What this demonstrates

1. **Geography integration** — Saab''s canvas loads losslessly.
2. **Determinism** — identical input produces identical output.
3. **Behavioural grading** — the assurance layer degrades gracefully as
   sensor quality drops.

## What this does NOT demonstrate

- Correctness of individual engagement decisions (requires ground truth).
- Calibration of assurance thresholds against operational data.
- Production readiness. Nimbus-C2 is at TRL 3-4 (Stage 2b prototype).

See [`SCIENTIFIC_CLAIMS.md`](SCIENTIFIC_CLAIMS.md) for the precise scope of
claims made in this analysis.

## Maturity

- Engine: Nimbus-C2 v1.0.0 — Stage 2b prototype (TRL 3-4)
- Extension: v0.1.0 — analysis artefact, not a product

## License

MIT. Copyright © 2026 Maria Westrin, Ulrika Wennberg.
