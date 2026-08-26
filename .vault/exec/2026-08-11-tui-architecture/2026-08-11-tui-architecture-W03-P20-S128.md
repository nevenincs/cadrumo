---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:4ba3ab8f5cfd797757a06ad03d5cd39322471ec6fb3751a502dd772003ece698'
step_id: 'S128'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement the sole Workspace assembly and dispatch directly in the public application/modelo/workspace.py defining module by capturing WORK exactly once before REGISTRY exactly once, deriving the REGISTRY coordinate only from the captured ModeloWorkResolution, evaluating the independent requested and stored axes through the sole pure S159-backed assertion, then capturing locale-catalogue and field-manifest for static admission or all remaining public S126 registrations for graded admission, with epoch-v2 same-domain two-pass validation, contributor_epoch_digest-consistent process-incarnation-scoped baselines, facets, and typed cursors, bounded materialization, and no _workspace_projection.py path, pre-capture work read, owner reread, or registry grammar

## Scope

- `src/cadrumo/application/modelo/workspace.py and focused assembly/dispatch/admission/consistency tests`

## Changes

- `A` `src/cadrumo/application/modelo/workspace.py`
- `A` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q` -> `pass` (5 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (23 passed, no regression from the added `revision_id` property)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`

## Notes

Partial landing; Step NOT checked. Only the WORK-then-REGISTRY
capture-and-assertion core is built and tested:
`capture_modelo_workspace_target_axes` captures WORK exactly once through
`ModeloWorkspaceWorkPortV1`, derives the REGISTRY coordinate solely from the
captured `ModeloWorkResolution`'s `(modelo, filing_year, period)` (never from
the target's own operands, which for an exact-work-unit target carry none),
captures REGISTRY exactly once through `ModeloWorkspaceRegistryPortV1`, and
judges the requested and stored revision axes independently against that one
capture through the existing pure `assert_work_target_revision`. Covered by
real integration tests over actual encrypted-SQL-backed repositories and the
bundled registry authority, including a genuine stale-stored-revision refusal
(constructed the same way `test_work_addressing.py` reproduces a
generation-superseding write, since `create_work_unit` itself re-confirms the
law-selected pairing at write time and refuses a hand-picked mismatch).

Added `ModeloWorkspaceRegistryProjectionV1.revision_id` (workspace_producers.py)
to read the law-selected revision uniformly off either admission shape
(`RegistryRevisionInspection.revision_id` or `RegistrySnapshot.revision.id`)
without a second registry read.

NOT built here, and explicitly deferred pending a ruling: request/admission
dispatch, the STATIC_INSPECTION and GRADED_SNAPSHOT projection assemblies, and
`ModeloWorkspaceResolvedTargetV1` construction. That record's required
`review_status: RevisionReviewStatus` field cannot currently be sourced for
the STATIC_INSPECTION admission -- `RegistryRevisionInspection` (the static
admission's own projection shape) carries no `review_status` field at all,
unlike `RegistrySnapshot`. Reported to the team lead rather than inferring a
resolution (e.g. a second structural read off `ModeloDefinition`, or enrolling
the field onto `RegistryRevisionInspection`); awaiting a ruling before
proceeding to the STATIC_INSPECTION vertical slice and, beyond that, sizing
GRADED_SNAPSHOT's remaining facets (schema walk, materialization, provenance,
capability denominator) from inside the code as previously agreed.
