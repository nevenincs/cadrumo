---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:2ce8501059f70c921795a7b054efd2019f3a01cec7a8c8c8e3d93b2add57e2b1'
step_id: 'S61'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Remove local redeclarations of the canonical modelo repositories fixture

## Scope

- `src/cadrumo/application/modelo/tests`

## Description

- Remove the file-flow wrapper already substituted by the modelo test conftest owner.
- Adjudicate the import-flow fixtures as lifecycle-distinct from file-flow but mutually substitutable.
- Promote one import-flow-specific fixture owner and bind its exact object directly in four consumer modules.
- Preserve both encrypted profile identities, seeded facts, repository tuples, scopes, and teardown.

## Outcome

The file-flow lifecycle has one conftest owner, while the distinct import-flow lifecycle has one support-module owner shared by its four consumers. Five redundant fixture definitions are removed without merging the two incompatible storage setups.

## Notes

Focused collection found 39 tests and fixture discovery resolved each lifecycle to its intended owner. Ruff, diff integrity, exact census checks, and independent review passed. Representative behavior remains blocked by concurrent profile-capsule work's pre-existing `LEGACY_CUSTODY_DETECTED` setup failure, so no broad green claim is made. The ownership manifest will be refreshed atomically with the remaining registry fixtures in this phase to avoid repeated full-tree census cost.
