---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:01b7fcf0bc4ec1a3cbee8d13cf4d37687979dc82c67e889a26b5e648adc962cc'
step_id: 'S11'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose the sole public operation-platform API without leaking private models or frontend types

## Scope

- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/operations/tests/test_facade.py`

## Description

- Re-ground public application-facade conventions, operation topology, private import hygiene, and approved S06-S10 contracts through live code/vault RAG, accepted ADR/plan, and targeted source checks.
- Promote the complete generic S06-S10 contract through one sorted explicit `__all__` while retaining canonical declaration homes.
- Exclude implementation modules, adapters, entrypoints, frontend types, callbacks, and transport concerns.
- Prove every declared name resolves, no module object/private name is exported, representative contracts retain their canonical declaring modules, and imports are restricted to core plus private sibling owners.

## Outcome

- The former package marker is now the sole `application.operations` public facade.
- All lifecycle axes, capabilities, immutable models, safe events, and exact interactions are available without consumers importing private modules.
- Focused gates passed: pytest reported `3 passed in 3.85s`; Ruff reported `All checks passed!`; basedpyright reported `0 errors, 0 warnings, 0 notes`; the focused relative-import gate exited zero.

## Notes

- Live code/vault semantic searches succeeded on port 8766. Whole public-facade epicenters and import-hygiene authority were read and confirmed with targeted `rg`.
- The facade does not export a supervisor, executor, registry, persistence adapter, or frontend projection before their owning Steps.
- Final review passed. The binding row was CLI-closed. `vault check all` exited zero with `1358 warnings`, including 5 annotation, 40 markdown, 29 schema, 2 modified-stamp, and pre-existing body-schema corpus warnings.
