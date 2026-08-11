---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:4bc51326b5e5adab9bef4493e8fbd19cb5faf465d325bc29be9530f9df590867'
step_id: 'S16'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Add the canonical operator action axis

## Scope

- `src/cadrumo/core/_operator_action_enums.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/tests/test_operator_action_axis.py`

## Description

- Add the core-owned `OperatorActionAxis` string enum with the twelve action classes accepted by the blocker-spine ADR.
- Export the exact enum identity through the core facade without aliases, bridges, or premature projection mappings.
- Prove exact alias-sensitive member names, wire values, facade identity, and sole source declaration.

## Outcome

- The blocker projection steps can now target one closed operator-action vocabulary while retaining their native blocker codes.
- One focused test passes; Ruff, format, BasedPyright, AST sole-declaration, runtime identity, and diff gates are green.
- Formal review reports PASS with no findings.

## Notes

- Projection mappings deliberately remain owned by S17-S20; S16 introduces vocabulary only.
- The bite proof temporarily removed `REVIEW_ADVISORY`, observed the exact membership test fail, and restored the accepted member in the same session.
