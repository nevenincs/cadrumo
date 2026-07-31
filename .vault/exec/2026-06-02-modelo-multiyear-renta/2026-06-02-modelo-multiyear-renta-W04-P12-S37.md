---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:60784abb7a3879413a230d8cb03f57aeebc3e152618a7dbe6153ea9e7dcad7d0'
step_id: 'S37'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M390 two-renta annual reconciliation test against four M303 quarterly feeders

## Scope

- `src/aeat/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py`
- `src/aeat/_data/registry/aeat/modelos/390/revisions/2022-y-siguientes/bindings/0001-bindings.toml`

## Description

- Rebaseline stale-open M390 reconciliation-test row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M390 test and binding registry.
- Update the plan row to the actual 390<-303 reconciliation proof.

## Outcome

- `test_modelo_390_303_reconciliation_continuity.py` already proves annual M390 reconciliation against four M303 quarterly feeders for 2025 and 2026.
- The M390 registry declares the `modelo-390-prev-303-*` binding family consumed by the test.
- No product code changed in this step.

## Notes

- This does not claim unsupported non-303 feeder coverage.
