# Verification grounding needs bundled oracle evidence and engine reproduction

A verification grounding claim — a casilla listed in a verification expectation's
`externally_grounded_casilla_ids` — MUST be backed by a bundled AEAT-authoritative
oracle payload carrying the expected figure (a Renta WEB Open replay under
`corpus/parity_replays/renta_web_open/`, or an AEAT manual worked-example oracle
under `corpus/manual_oracles/`, both keyed by `expected_by_casilla_id`), AND the
registry engine MUST independently reproduce that figure in a parity test.

Never fabricate a grounding figure, never hand-compute it from the registry
formula under test, and never declare `externally_grounded_casilla_ids` without
both.

**Enrollment in a verification expectation is NOT grounding.** Enrollment only
reconciles filed-versus-engine; grounding is the stronger claim that the engine
value itself is checked against an independent AEAT authority. Enrollment sat at
100% of computed casillas while external per-casilla grounding was about 1%, and
a value reconciled only against the app's own engine cannot catch a systematic
engine error the filing matches.

## How

- **Good:** an id is declared grounded only after the bundled oracle carries the
  AEAT literal figure with a raw-evidence locator, AND a test proves the engine
  independently computes it. Where a manual states contradictory figures, ground
  on the one it states repeatedly and the engine re-derives bottom-up, and
  document the discrepancy — never silently pick one.
- **Bad:** adding an id because the engine emits a plausible value, with no
  bundled oracle; or authoring an expected figure by copying the registry
  formula's own output.

**The oracle must follow the fix, never precede it.** Building an oracle that
asserts a currently-wrong figure converts a live defect into verified behaviour
behind an AEAT-branded test name, which is harder to find later than the open
gap. And never force a figure with an override that reaches beneath a guard every
real filing passes through — a fixture proving a chain works in a configuration
no filing can reach reads as coverage.

Source: ADR `2026-07-01-verification-power-adr`; honesty gate
`test_external_oracle_grounding_enrolled.py`. Companions:
`no-tautological-calculation-tests`,
`legal-grounding-verifies-bundled-authoritative-corpus`.
