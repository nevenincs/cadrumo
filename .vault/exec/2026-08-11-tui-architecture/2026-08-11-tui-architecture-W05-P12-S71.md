---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9dc42b1190488e2141fe6c033b0faf80ece580146d0a13bd686bcf8cd3f4a718'
step_id: 'S71'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove filed-history progress, scoped errors, viewable logs, child provenance, and partial outcomes remain visible through settlement

## Scope

- `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`
- `verify:` `pytest src/cadrumo/entrypoints/tui/profile/tests/ -m integration` -> `pass` (9 passed)

## Notes

Closed after W05.P12.S255/S256. Progress and refusal visibility through
real terminal settlement was already proven; this Step adds a proof that
`resolve_filed_history_result` reaches the real typed result-projection
door (refusal path here, since a REFUSED settlement is the only one
reachable offline in this package). The SUCCEEDED path -- resolving real
evidence, IVA-wallet, notificaciones, and provenance detail without
importing the private result type -- is proven in
`src/cadrumo/application/live/tests/test_filed_history_operation.py::test_frontend_projects_the_public_result_without_the_private_type`,
which needs the routed AEAT-register test fixtures that live in that
package, not this one. "Scoped errors" and "viewable logs" remain covered
generically by W05.P11's `logs.py`/`interactions.py`.
