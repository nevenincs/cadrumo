---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2fed0216c76e86bccad7b6061b4bf1703810ab4bf9a4fa36ae9775e8bacaa536'
step_id: 'S276'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build the detail-row edit surface on the natural-key whole-set reconstruction, admitting each modelo's own detail-row kinds through the established owning-modelo table, and prove a detail-row edit end to end: drive a real add, update, delete and move through apply_modelo_edit against a live modelo revision with real profile setup, assert the reconstructed rows reach the persisted calculation revision, and assert a mismatched or unknown natural key refuses without writing

## Scope

- `src/cadrumo/application/modelo/_edit_services.py detail-row surface entries`
- `_edit_execution.py`
- `and a real-registry end-to-end detail-row edit test through apply_modelo_edit`

## Changes

- `A` `src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py -q -n 0 -m integration` -> `pass` (3 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py src/cadrumo/application/modelo/tests/test_edit_detail_row_reconstruction.py src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py -q -n 0 -m "integration or unit"` -> `pass` (69 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py` -> `pass`

## Notes

`_edit_services.py`'s detail-row surface entries (`_writable_detail_row_entries`)
and `_edit_execution.py`'s reconstruction (`_reconstruct_detail_rows`) were
already built and committed in S288; neither needed further changes for
S276. This Step's real deliverable was the missing end-to-end proof S288
honestly flagged as not yet built: a real ADD, UPDATE, and DELETE
`Modelo347ContraparteRow` edit driven through `apply_modelo_edit` against a
live modelo 347 revision with real profile setup, asserting the
reconstructed rows reach the persisted `CalculationRevision.detail_rows`
after each step, plus a real proof that an unknown natural key refuses
(`ModeloEditExecutionNoEffectV1`) without writing any revision at all
(`calculation_repository.load().revisions == {}`).

The Step's own text says "drive a real add, update, delete and move" --
MOVE was retired in the S288 follow-up (`000649150f`) because the
calculation revision's content address is order-blind, so a pure reorder
would be silently absorbed by the guarded duplicate-result branch rather
than persist. Only ADD/UPDATE/DELETE are proven here; `ModeloEditDetailRowIntentKind`
no longer has a MOVE member to drive. Same pattern as the seven prior
Step-text-vs-code mismatches this campaign has corrected from the tree
rather than building to the stale text.
