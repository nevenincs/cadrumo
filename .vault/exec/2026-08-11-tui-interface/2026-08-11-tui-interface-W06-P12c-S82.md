---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:10373cf26546be2184c6ddc8c24f2733e898dc08799ace02c4f854d2d6add5dc'
step_id: 'S82'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S81]]"
---

# Enroll rename only through its canonical lifecycle capability and registered operation, and prove available, refused, terminal effect, typed refresh, focus return, and every supported geometry independently

## Scope

- `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_rename_action.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/action/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/action/rename.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_c4_rename_action.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `verify:` `pytest test_c4_rename_action.py test_actions.py test_work_rename_operation.py test_lifecycle_operation_conformance.py` -> `94 passed`

## Notes

ENROLLED THROUGH THE REGISTERED OPERATION, NEVER THE WRITER. The action builds
a typed `ModeloWorkRenameRequest` addressed to `modelo.work.rename` and submits
it through the composed supervisor, returning the shared `OperationController`
bound to that submission. It never calls `rename_work_unit`.

That distinction carries the whole value, because the wrong path SUCCEEDS.
Calling the lifecycle writer directly would rename the unit and produce an
identical visible outcome, while the run held no lease, entered no journal,
could not be cancelled or resumed, and published no observation. A live
operator path executing outside the platform that governs it is exactly the
defect W07.P16.S340 records against the spreadsheet export. So it is asserted
STRUCTURALLY, against the module's own AST rather than its import block: a
writer reached through a deferred function-local import would not appear in the
header, and a reviewer scanning the file would miss it.

NOTHING WAS REDECLARED. `OperationController` and `present_operation_modal`
already ship; this module contributes only the two rename-specific pieces --
building the request and naming the destination -- and reads that destination
from the S80 dispatch table rather than restating it, so where a settled rename
leaves the operator is declared once.

SUBMITS WITHOUT STARTING, proven on the coroutine's own source: starting
belongs to the modal that presents the run. An action that started the run
itself would execute a rename to completion with no window observing it, which
defeats the point of routing it through the platform.

A REAL DEFECT FOUND BY THE REFUSAL PROOF, and fixed rather than accommodated.
The empty name was refused; the whitespace-only name `"   "` WAS NOT. Cause:
the operation request's `_WORK_UNIT_NAME` carried `Field(min_length=1)` while
the domain's `_DisplayName` carries `StringConstraints(strip_whitespace=True,
min_length=1)`. The REQUEST TYPE WAS LOOSER THAN THE TYPE IT FEEDS, so a
whitespace rename passed the boundary, was journalled, took a lease, and was
scheduled -- then failed at the writer. The platform did real work for a rename
that could never settle, and an operator would see a lease and a journal entry
for it. Aligned to the domain's constraint: `""` and `"   "` now refuse at the
boundary, and `"  Q1 2026  "` is accepted as `"Q1 2026"`, which is what the
domain would have stored anyway.

The test was NOT weakened to match the observed behaviour. Encoding
whitespace-acceptance as the contract would have made this suite assert a
defect, which is worse than not testing it -- the constraint moved instead.
