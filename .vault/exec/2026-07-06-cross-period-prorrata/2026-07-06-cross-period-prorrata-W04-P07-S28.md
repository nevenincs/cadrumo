---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:362685ab32350cabdb4f62ec7835ad868adaa3cb51e8f534f2622782d529c3cb'
step_id: 'S28'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# bundle AEAT prorrata regularizacion oracle

## Scope

- `src/aeat/_data/corpus/manual_oracles/modelo-303-prorrata-general-regularizacion.json`

## Description

- Re-read the live plan status after peer commits landed and confirmed the next
  authoritative open row remained `W04.P07.S28`.
- Re-grounded the step through semantic search, the cross-period prorrata ADR,
  the W04/P07 plan row, the existing manual-oracle corpus shape, and the
  external-oracle enrollment gate.
- Sourced the AEAT Manual practico IVA 2025 prorrata-general worked example from
  the bundled IVA manual, pages 137-138.
- Added the plan-named manual-oracle payload with `filing_year` 2025, local raw
  evidence locator, the manual's stated annual volumes, definitive percentage,
  and fourth-quarter regularizacion amount.
- Kept the promotion boundary intact: no source kind, source resolver, validator
  convention, registry selector, or `_source_mesh.py` path was edited.

## Outcome

- S28 is complete: the AEAT manual prorrata-general regularizacion worked
  example is bundled under `manual_oracles` for the S29 end-to-end oracle proof.
- The payload records the manual's stated annual total volume `45000.00`,
  annual con-derecho volume `25000.00`, definitive prorrata percentage `56`,
  Modelo 303 casilla 44 standalone regularizacion amount `-217.60`, and the
  manual's net fourth-quarter deduction effect `-128.00` in the notes.
- The current Modelo 303 registry still treats the volume fields and casilla 44
  as manual at this point, so this step does not promote or enroll the live mesh
  binding; that remains the planned S30 change after the S29 proof lands.

## Notes

- Verification passed: JSON parsing and canonical casilla-id validation for the
  new payload.
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\domain\calculations\registry\tests\test_external_oracle_grounding_enrolled.py
  -n 0 -m integration` (2 passed).
- Initial unmarked pytest invocation of the same integration module was
  deselected by the repository's default `-m unit` configuration; it was rerun
  with `-m integration`.
