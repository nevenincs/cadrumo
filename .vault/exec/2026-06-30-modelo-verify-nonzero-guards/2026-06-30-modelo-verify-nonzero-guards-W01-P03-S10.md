---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M151 base-liquidable-to-cuota-integra advisory on the loaded 2015-y-siguientes revision snapshot

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_151_registry.py`

## Description

- Added `test_modelo_151_carries_base_liquidable_under_declaration_advisory` to the existing `test_modelo_151_registry.py`, mirroring the M200 `test_modelo_200_carries_manual_handoff_under_declaration_advisory_predicates` shape: load the modelo via the existing `_load_modelo_151()` helper, read `modelo.revisions["2015-y-siguientes"].verification_predicates` directly (no snapshot build needed; `verification_predicates` is a direct field on `ModeloRevision`).
- Asserted the predicate's `predicate_id`, exact `expression` string, `finding_kind == "ADVISORY"`, and `"ley-35-2006:art-93"` membership in `legal_refs`.

## Outcome

`uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_151_registry.py -q` -> 6 passed (5 pre-existing plus the new registry-shape test). Combined run with the gate-behaviour test file (S11): 10 passed.

## Notes

No incidents. No new imports were required; the test reuses the file's existing `_load_modelo_151()` helper.
