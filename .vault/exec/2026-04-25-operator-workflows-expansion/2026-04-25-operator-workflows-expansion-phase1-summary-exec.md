---
tags:
  - '#exec'
  - '#operator-workflows-expansion'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-operator-workflows-expansion-research]]"
  - "[[2026-04-25-operator-workflows-expansion-adr]]"
  - "[[2026-04-25-operator-workflows-expansion-plan]]"
---

# `operator-workflows-expansion` exec phase1 summary

Implementation summary for wgergely/aeat#340. Closes the audit-finding
gap surfaced in EPIC #316: Tier-L modelo CLI integration coverage.

## Outcome

- 10 new test classes added to `tests/integration/test_kent_workflows.py`:
  `TestKentImportsModelo100SummaryBorrador`,
  `TestKentImportsModelo111Declaracion`,
  `TestKentImportsModelo115Declaracion`,
  `TestKentImportsModelo123Declaracion`,
  `TestKentImportsModelo131Declaracion`,
  `TestKentImportsModelo180Declaracion`,
  `TestKentImportsModelo200Declaracion`,
  `TestKentImportsModelo202Declaracion`,
  `TestKentImportsModelo303Declaracion`,
  `TestKentImportsModelo390Declaracion`.
- 38 new pytest cases, all green locally.
- `docs/coverage/modelos.md` updated with a "kent CLI integration
  coverage" section + provenance refresh.
- No new generators required; existing `_generic_quarterly_generator.py`,
  `modelo_303_generator.py`, and `modelo_100_generator.py` reused.
- Module-level marker preserved:
  `[unit, domain_financial_input, fixture_tier_l3]`.

## Year choice per modelo

Every modelo tested at 2025; the only landed extractor year (Modelo 130
also covers 2024 but is the pre-existing template — not changed here).
Modelo 200's 2025 PDF parses cleanly but cannot ruleset-verify (only
2024 ruleset on main); the test class locks in the
`Verification status: UNVERIFIABLE` Kent-observable behaviour.

## Discrepancy-case status

Discrepancy verdict (`Verification status: NEEDS_REVIEW`) tested for
9 of the 10 modelos:
- Eight declaracion classes (111 / 115 / 123 / 131 / 180 / 202 / 303 /
  390) include `test_discrepancy_classified_correctly`, asserting
  `cause=CORRECTNESS_DIVERGENCE` plus the affected casilla id.
- Modelo 100-summary's third method `test_discrepancy_triggers_needs_review`
  exercises the borrador-equivalent path (drifted computed casilla
  flagged through `Engine.audit_against`). The borrador CLI emits no
  `Extraction status:` line so the canonical partial-extraction case
  is not meaningful — the discrepancy case substitutes for it.

Skipped for Modelo 200: no 2025 ruleset → verdict is UNVERIFIABLE
regardless of formula coherence; no formula can diverge.

## Local gates

| Gate                                  | Result                       |
| ------------------------------------- | ---------------------------- |
| `just lint`                           | pass                         |
| `just typecheck`                      | pass                         |
| `just hooks` (prek)                   | pass                         |
| `tests/integration/test_kent_workflows.py` | 44/44 pass (~7s)        |
| Full pytest suite                     | 3002 pass + 3 pre-existing failures unrelated to #340 (`auth/_clave_movil` 5-minute live timeouts + `cli/workflow/_test_doubles.py` marker_integrity — Thread 1 territory) |
| `just test-cov` 60% floor             | preserved (test additions never reduce source coverage) |

## Forward-compat notes

- All assertions are stable-marker substring matches (`Extraction status:`,
  `Verification status:`, `cause=...`, `casilla XX`). #398 (error-emission
  decorator) and #399 (--json envelope) merges should not break this
  file; a routine rebase suffices if any chrome shifts.
- The Modelo 200 UNVERIFIABLE assertion is the only test that needs a
  deliberate update when a 2025 Modelo 200 ruleset lands.

## Follow-ups

- None blocking. The Modelo 200 UNVERIFIABLE lock-in becomes a
  per-modelo calc issue update (#322 family — Tier-L Modelo 200
  calc-verify-roundtrip) when that ruleset year lands.
