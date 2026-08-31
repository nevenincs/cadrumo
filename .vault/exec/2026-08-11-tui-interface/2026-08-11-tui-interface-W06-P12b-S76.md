---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:176c7c89a5fd75c612f068a8beb8fe8efd1ca4371311dfb2c7d0b0dbeec2c12c'
step_id: 'S76'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Admit editor routes only after the complete ModeloEditCompatibilityTupleV1 matches the pinned Workspace, definition manifest and digests, observation, REVIEW, refresh-target, and financial-operand schema coordinates before any lexeme is accepted

## Scope

- `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_controller.py`
- `M` `src/cadrumo/application/modelo/edit_session.py`
- `verify:` `ruff check` over the package -> `All checks passed`
- `verify:` `pytest entrypoints/tui/modelo/edit` -> `20 passed, 1 failed` BEFORE the refusal fix;
  the failure was the defect described below and the fix is not yet re-run

## Notes

PARTIAL: the module and its tests are written and lint clean, and the one
failure they found is fixed. The full re-run is outstanding and the row stays
open until it is green.

THE ORDERING GUARANTEE IS STRUCTURAL, NOT PROCEDURAL. Until admission succeeds
the controller has no field set, no row set and no gate to hand out, so there
is no object on which a lexeme could be offered. A controller that exposed
controls and checked compatibility when the first key was pressed would have
the same intention and none of the guarantee, and its test would assert a flag
rather than an impossibility.

The tuple is judged by the CONTRACT and not re-checked here. `admit_modelo_edit`
compares every axis and refuses before resolving any secure state; re-comparing
them in the controller would be a second judge of one question, free to
disagree with the first.

A TEST FOUND A REAL DEFECT IN CODE WRITTEN AN HOUR EARLIER, which is the whole
reason to write it. `open_modelo_edit_session` read `refusal.code`, which
exists on ONE of the refusal union's five arms. A stale compatibility tuple
yields `ModeloEditCompatibilityRefusalV1`, which has no `code`, so the facade
raised `AttributeError` instead of returning a refusal outcome -- on exactly
the path a platform upgrade takes, where the operator should be told the editor
is unavailable rather than shown a traceback. The key is now derived from the
`kind` DISCRIMINATOR, which every arm carries by construction.

The test caught it only because it drives a GENUINELY stale tuple through the
contract's own comparison. A test that had simulated the refusal would have
passed against the broken code, never producing the arm the facade could not
handle.

WHY THE RE-RUN IS OUTSTANDING: a `relocation:core` campaign is landing in
batches -- `promote eight more private modules and repoint every consumer` at
06:56 -- and each batch briefly breaks the import graph. Successive attempts
failed on `core.optional_extras`, `core.provenance_stamp`,
`core.model_catalogue` and `core.field_grounding`, each resolving as the next
appeared. A collection-gated wait was tried and still raced: collection passed,
then the tree moved again before the run. Re-run the package once the campaign
lands.

VERIFIED 2026-08-31, once the relocation campaign settled -- churn fell from 39 files per minute to 4.

- `verify:` `pytest entrypoints/tui/modelo/edit + application/modelo/tests/test_edit_session.py` -> `28 passed`

That run covers all five C3 modules together: the application-owned session facade, scalar fields, repeated rows, the review gate and this controller. It is the first green over the whole editor surface, and it is taken against the settled tree rather than the one the modules were written against -- roughly 4,700 files were rewritten underneath them while the campaign ran.

The refusal fix is included in that green. The stale-tuple test now exercises the path that previously raised `AttributeError`, so the defect is proven fixed rather than merely edited.
