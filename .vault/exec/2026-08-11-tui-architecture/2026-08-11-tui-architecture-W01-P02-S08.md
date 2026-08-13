---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0e33bf45b8fa3260183fba45fe46f639e17d34a9fb7426019e4412db8cc3ec23'
step_id: 'S08'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define validated per-operation capability declarations and forbidden capability combinations

## Scope

- `src/cadrumo/application/operations/_capabilities.py`

## Description

- Ground capability vocabulary and invalid combinations in the accepted operation-platform ADR, its research evidence, the completed S06 lifecycle axes, and a focused source census.
- Define one strict, frozen `OperationCapabilities` authority with explicit durability, cancellation, deadline, replay, baseline, sensitive-input, conflict-scope, resource, effect, and close-policy declarations.
- Refuse unsafe durability/replay, lease, effect, cancellation, deadline, resource-ownership, and close-policy combinations at model validation.
- Prove required declarations, strictness, immutability, forbidden combinations, and valid recorded and resumable configurations through direct real-model tests.

## Outcome

- `OperationCapabilities` is the single per-definition capability authority; no existing semantic owner or duplicate implementation was found.
- Application-local closed policies cover replay, baseline binding, sensitive operand custody, conflict scope, and supervisor-owned task/process resources without redeclaring the S06 core axes.
- Ephemeral operations cannot conceal governed effects or promise durable replay, durable operations require lease scope, resumability is symmetric with replay, and stopping promises require truthful cancellation/resource support.
- Focused verification passed: `uv run pytest src/cadrumo/application/operations/tests/test_models.py src/cadrumo/application/operations/tests/test_capabilities.py -q` reported `31 passed in 4.68s`; `uv run ruff check src/cadrumo/application/operations/_capabilities.py src/cadrumo/application/operations/tests/test_capabilities.py` reported `All checks passed!`; `uv run basedpyright src/cadrumo/application/operations/_capabilities.py src/cadrumo/application/operations/tests/test_capabilities.py` reported `0 errors, 0 warnings, 0 notes`.

## Notes

- Semantic RAG was attempted for the complete capability concept and canonical owner, but the service refused both code and vault queries with `quiesce_admission_closed`. Grounding continued from the full accepted ADR/research already read, exact targeted searches, and whole S06/S07 epicenters.
- The source census found unrelated service, frontend, filing, and registry capability models, but no supervised-operation declaration authority; none were duplicated or bridged.
- S08 remains open and uncommitted pending independent review.
