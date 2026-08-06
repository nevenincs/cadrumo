---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:af64e203c5268cb339d819330dbcc04a8730e116ea41eb5cc9640817bbc249e0'
step_id: 'S07'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a registry-shape test asserting predicate_id, expression, finding_kind, and legal_refs for the new M123 06-to-09 advisory on the loaded 2024-y-siguientes revision snapshot

## Scope

- `src/aeat/domain/calculations/registry/tests/test_modelo_123_registry.py`

## Description

- Read `test_verification_m131_advisory.py` and the existing `test_modelo_200_registry.py` predicate-shape assertion as topology reference.
- Added `test_m123_2024_carries_base_total_implies_retenciones_total_advisory` to `src/aeat/domain/calculations/registry/tests/test_modelo_123_registry.py`, reusing the file's existing `_snapshot_2024()` helper to load the M123 2024-y-siguientes snapshot off the registry authority.
- Asserted the predicate's `predicate_id`, `expression == 'implies_nonzero(["06", "09"])'`, `finding_kind == "ADVISORY"`, and both `legal_refs` members (`rd-439-2007:art-90`, `ley-35-2006:art-101`) on the loaded snapshot.
- Ran `ruff format` on the file (auto-reformatted unrelated pre-existing spacing in the same pass) and re-ran the full `test_modelo_123_registry.py` suite to confirm no regression.

## Outcome

Test passes; the predicate is confirmed to load correctly off the validated registry authority with the expected shape and legal grounding. Full command: `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_123_registry.py -q` -> all 7 collected tests pass (6 pre-existing plus the new shape test).

## Notes

No incidents.
