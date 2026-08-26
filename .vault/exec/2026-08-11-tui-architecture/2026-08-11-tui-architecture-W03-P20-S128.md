---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2ee2b4e08c107aa12f23013ddc6688419aa721dbb84f44775b9dc642a3f81edb'
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
- `M` `src/cadrumo/domain/calculations/registry/static_inspection.py` (separate commit `822642adbc`: enrolled `review_status` on `RegistryRevisionInspection`)
- `M` `src/cadrumo/application/modelo/workspace.py`, `workspace_producers.py`, `tests/test_workspace.py` (commit `be5384912c`: made revision-axis mismatch non-raising typed data; added `resolve_modelo_workspace_target` and `ModeloWorkspaceRegistryProjectionV1.review_status`)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (32 passed)

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

Update: the `review_status` gap is resolved. Team lead ruled against sourcing
it from a second structural read off `ModeloDefinition` (a fresh
`authority.validate_modelo(...)` is a second, unsynchronized observation of
registry state -- the exact inconsistency the epoch/ABA capture machinery
exists to rule out, even though it would have been cheap). Instead
`RegistryRevisionInspection` was enrolled with the field itself (own commit
`822642adbc`, kept separate from assembly work per instruction): it is a
governance stamp, not filing-grade content, so it stays in scope for a static
inspection. `RegistryRevisionInspection` is constructed only through
`from_revision()` across the tree, so no consumer needed updating.

While building on top of this, self-caught a second real defect before it
shipped: the axis computation originally re-raised
`assert_work_target_revision` on any mismatch, which would have destroyed the
per-axis `MISMATCHED` disposition the moment a caller tried to build
`ModeloWorkspaceRevisionMismatchRefusalV1` from it -- that refusal is built
FROM the mismatched axes, not from a caught exception. Corrected to always
return typed data; the pure assertion remains available, unused by the
non-raising path, for a caller that wants the canonical raised text (proven by
a dedicated test). `resolve_modelo_workspace_target` now assembles the full
`ModeloWorkspaceResolvedTargetV1`, including a resolved mismatch case.

Still NOT built here: request/admission dispatch, and the STATIC_INSPECTION
and GRADED_SNAPSHOT projection assemblies (schema walk, materialization,
provenance, capability denominator, baseline, facets/cursors, evidence
horizon, locale summary, family dispositions, readiness/closure
integration). Per the agreed order, next is the STATIC_INSPECTION vertical
slice, then sizing GRADED_SNAPSHOT's remaining facets from inside the code,
stopping again (not inferring) if the capability denominator's dispositions
turn out undocumented for any of the five capability members.
