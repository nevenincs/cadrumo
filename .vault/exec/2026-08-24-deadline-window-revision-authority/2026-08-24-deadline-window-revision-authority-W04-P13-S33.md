---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:51cd0b80c117202104e48c1ae0680b68d31fbd2eefa8073fcec68150100cf66e'
step_id: 'S33'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Run the bundled-registry invariant proving zero ownership, identity, uniqueness, qualifier, period, and completeness violations

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/domain/deadlines/tests/`

## Outcome

The bundled registry invariant cohort passes with zero ownership, semantic-identity, ID uniqueness, qualifier-expansion, period-year, projection, or periodic-completeness violations. The run includes cold authority construction and the planted missing-cell refusal.

## Verification

`uv run pytest -q` over deadline semantic coordinate, authority projection, loader, ownership, qualifier, uniqueness, supported-year catalogue, repaired M303/M322/M349/M353 registry modules, and the deadline engine: `207 passed in 94.23s`.
