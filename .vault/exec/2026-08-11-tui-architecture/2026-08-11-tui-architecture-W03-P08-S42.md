---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:74db0cc12f62df9f47f6dcde7438c12d759431d4774ea143e50b475103a4b221'
step_id: 'S42'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Expose authentication operation definitions through the authentication application facade

## Scope

- `src/cadrumo/application/auth/__init__.py`

## Description

Audit the live authentication facade against the canonical operation-definition owner.
Confirm that production composition imports both builders only through the public application facade.
Order the operation-definition import and public export entries under the repository style contract without adding aliases, shims, constants, or private implementation exports.

## Outcome

- The facade exposes `build_auth_operation_definitions` and `build_auth_operation_registrations` from their sole owner.
- Production composition and its conformance test consume the public facade; neither imports the private owner module.
- The facade adds no duplicate operation definition, re-export bridge, or legacy compatibility path.

## Verification

- `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/auth/tests/test_operation_definitions.py src/cadrumo/entrypoints/tests/test_operation_composition.py`: 12 passed.
- `uv run ruff check src/cadrumo/application/auth/__init__.py src/cadrumo/application/auth/_operation_definitions.py`: passed.
- `git diff --check -- src/cadrumo/application/auth/__init__.py`: passed.
- Independent read-only review: approved with no findings; semantic RAG and exact census confirmed one private owner reached only through the facade and no aliases, shims, or redeclarations.

## Notes

The operation definitions and public imports already existed after the operation-composition cohort. This step completes the canonical facade contract and its style gate; it does not re-declare the definitions.
