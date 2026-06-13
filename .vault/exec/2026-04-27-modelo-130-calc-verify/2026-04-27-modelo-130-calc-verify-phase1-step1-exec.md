---
tags:
  - '#exec'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-130-calc-verify` phase-1 step-1: 2024 + 2025 back-fill

Phase-1 of issue `#321` audited the existing 2024 + 2025 rulesets
against the `#339` mandatory-citation invariant and back-filled the
casilla-13 minoración helper with external-anchored threshold-edge
test cases.

## Audit outcome

Citation coverage on `modelo_130.2024` and `modelo_130.2025` was
already at 100 % (9 of 9 `computed=True` casillas carry non-empty
`legal_basis` pointing at RIRPF art. 110 + LIRPF art. 99). No
back-fill was required for citation completeness.

## Files modified

- `src/aeat/domain/formulas/_rulesets/test_modelo_130_2024.py` — added 11
  parametrised threshold-edge cases for the casilla-13 minoración
  helper (`compute_casilla_13_minoracion`). Cases enumerate the four
  RIRPF art. 110.3.c bracket boundaries (9 000 / 10 000 / 11 000 /
  12 000 €) at one ε below + one ε above each boundary plus
  zero-floor and out-of-range. Expected values come from the statute
  verbatim (100 / 75 / 50 / 25 / 0 €), not from the helper's
  `_CASILLA_13_BRACKETS` table — a typo in the table would fail one
  of these cases.
- `src/aeat/domain/formulas/_rulesets/test_modelo_130_2025.py` — same
  parametrised case-set wired via the 2025 import path. Confirms the
  no-drift invariant the 2025 ruleset relies on.

## Files created

- `.vault/research/2026-04-27-modelo-130-calc-verify-research.md`
- `.vault/adr/2026-04-27-modelo-130-calc-verify-adr.md`
- `.vault/plan/2026-04-27-modelo-130-calc-verify-plan.md`

## Tests added / extended

22 parametrised cases (11 per year × 2 years) on the casilla-13
minoración brackets. All green.

## Out of scope at this step

The 2026 ruleset itself, the rule-delta manifest, the extractor
expansion, the integration 4th case, and the docs-coverage flip
land in subsequent steps.
