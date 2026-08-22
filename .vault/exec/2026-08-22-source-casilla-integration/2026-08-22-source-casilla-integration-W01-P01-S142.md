---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7939d0f5ed4d428f5bcf9d1e89fbcff1648321801852d1fd88fa31b6a41a8df9'
step_id: 'S142'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# attach canonical calculation-route identity to reconciled supported operator workflows

## Scope

- `src/cadrumo/application/operator_surface`

## Description

- Define the canonical modelo-work calculation route as a closed core identity and
  make the production modelo route consume it.
- Require every supported workflow row to carry that route with no default.
- Project calculate, wizard, and quickfile only from reconciled live leaves whose
  command and canonical path exactly agree.
- Require catalogue lookup to match entrypoint, command, route, and path together.
- Add missing/wrong route, command/path swap, unrelated leaf, deleted leaf, and exact
  support mutation tests.
- Keep registry integration compile-only until S143 binds route-aware authority.

## Outcome

Supported workflow rows now join a reconciled live CLI leaf to the shared canonical
modelo calculation route. No row can be invented by the route declaration alone,
and a command/path swap is refused during catalogue construction.

## Notes

The initial independent review found two medium issues: duplicate route authority
and unclosed command/path coherence. Both were corrected and independently re-reviewed
as resolved. The final independent focused set reported 88 passing tests; the local
focused set reported 41 passing tests. Ruff, compilation, import hygiene, and diff
checks passed. The date rollover did not rename the feature artifacts: Vault CLI
retained the canonical plan date and step display path.
