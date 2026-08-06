---
name: verification-grounding-needs-oracle-evidence
trigger: always_on
---

# Verification grounding needs bundled oracle evidence and engine reproduction

## Rule

A verification grounding claim — a casilla listed in a verification expectation's
`externally_grounded_casilla_ids` — MUST be backed by a bundled AEAT-authoritative
oracle payload carrying the expected figure (a Renta WEB Open replay under
`corpus/parity_replays/renta_web_open/`, or an AEAT manual worked-example oracle under
`corpus/manual_oracles/`, both keyed by `expected_by_casilla_id`), AND the registry
engine MUST independently reproduce that figure in a parity test. Never fabricate a
grounding figure, never hand-compute it from the registry formula under test, and never
declare `externally_grounded_casilla_ids` without both. Enrollment in a
`verification_expectation` is NOT grounding — it only reconciles filed-vs-engine;
grounding is the stronger claim that the engine value itself is checked against an
independent AEAT authority.

## Why

The verification-power campaign found enrollment at 100% of computed casillas while
external per-casilla AEAT grounding was ~1% (research
`2026-07-01-verification-power-research`): a value reconciled only against the app's own
engine cannot catch a systematic engine error the filing matches. ADR
`2026-07-01-verification-power-adr` made grounding a build-time-validated registry field
surfaced as `independently_grounded_fraction`, and the symmetric honesty gate
`test_external_oracle_grounding_enrolled.py` enforces evidence in BOTH directions (every
bundled oracle figure enrolled; every declared id backed by a bundled figure for its
filing year). Companion to `legal-grounding-verifies-bundled-authoritative-corpus` and
`no-tautological-calculation-tests`.

## How

- **Good:** M100 2024 `0226` is declared `externally_grounded` only after (1)
  `corpus/manual_oracles/modelo-100-2024-estimacion-directa-simplificada.json` carries
  `expected_by_casilla_id.0226 = "58100.00"` quoted verbatim from the AEAT manual (with
  a `raw_evidence_locator` anchor), and (2)
  `test_m100_2024_estimacion_directa_manual_worked_example.py` proves the engine
  independently computes `0226 = 58100.00`. When the manual states a contradictory
  figure (OCR/footnote artefact), ground on the figure it states repeatedly and the
  engine re-derives bottom-up, documenting the discrepancy — never silently pick one.
- **Bad:** adding an id because the engine emits a plausible value, with no bundled
  oracle (the honesty gate fails); or authoring an `expected_by_casilla_id` figure by
  copying the registry formula's own output (tautological — it must be the AEAT literal,
  independently reproduced).
