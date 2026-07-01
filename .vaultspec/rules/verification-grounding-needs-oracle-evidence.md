---
name: verification-grounding-needs-oracle-evidence
---

# Verification grounding needs bundled oracle evidence and engine reproduction

## Rule

A verification grounding claim — a casilla listed in a verification expectation's
`externally_grounded_casilla_ids` — MUST be backed by a bundled AEAT-authoritative
oracle payload that carries the expected figure (a Renta WEB Open replay under
`corpus/parity_replays/renta_web_open/`, or an AEAT manual worked-example oracle
under `corpus/manual_oracles/`, both keyed by `expected_by_casilla_id`), AND the
registry engine MUST independently reproduce that figure in a parity test. Never
fabricate a grounding figure, never hand-compute it from the registry formula
under test, and never declare `externally_grounded_casilla_ids` without both the
bundled evidence and the engine-reproduction test. Enrollment in a
`verification_expectation` (coverage-gated or reconcile-when-present) is NOT
grounding — it only means the casilla is reconciled filed-vs-engine; grounding is
the stronger claim that the engine value itself is checked against an independent
AEAT authority.

## Why

The verification-power campaign found enrollment reached 100% of computed casillas
while external per-casilla AEAT grounding was ~1% (research
`2026-07-01-verification-power-research`). A grounding claim with no independent
oracle behind it is a false confidence signal: a filed value reconciled only
against the app's own engine cannot catch a systematic engine error the filing
matches. ADR `2026-07-01-verification-power-adr` made grounding tier a declared,
build-time-validated registry field surfaced on the verdict as
`independently_grounded_fraction`, and the symmetric honesty gate
(`test_external_oracle_grounding_enrolled.py`) enforces evidence in BOTH
directions — every bundled oracle figure must be enrolled, and every declared
`externally_grounded_casilla_ids` must have a bundled oracle figure for its filing
year. This is the verification-surface companion to
`legal-grounding-verifies-bundled-authoritative-corpus` (verify figures against
bundled authoritative text) and `no-tautological-calculation-tests` (never assert
engine output against a number hand-computed from the same formula).

## How

- **Good:** M100 2024 `0226` is declared `externally_grounded` only after (1) a
  bundled `corpus/manual_oracles/modelo-100-2024-estimacion-directa-simplificada.json`
  carries `expected_by_casilla_id.0226 = "58100.00"` quoted verbatim from the AEAT
  manual's caso práctico (with a `raw_evidence_locator` line anchor), and (2)
  `test_m100_2024_estimacion_directa_manual_worked_example.py` seeds the manual's
  raw inputs and proves the engine independently computes `0226 = 58100.00`. Both
  the honesty gate and an anti-tautology companion test pass.
- **Good:** when the bundled manual states a contradictory figure (an OCR/footnote
  artefact), ground on the figure the manual states repeatedly and that the engine
  re-derives bottom-up, and document the discrepancy in the test — never silently
  pick one number.
- **Bad:** adding a casilla id to `externally_grounded_casilla_ids` because the
  engine happens to emit a plausible value, with no bundled oracle payload — the
  symmetric honesty gate fails, and the "grounding" is unfounded.
- **Bad:** authoring a manual-oracle `expected_by_casilla_id` figure by running the
  registry formula and copying its output — that is tautological; the figure must
  be the AEAT manual/replay literal, and the engine must reproduce it independently.
