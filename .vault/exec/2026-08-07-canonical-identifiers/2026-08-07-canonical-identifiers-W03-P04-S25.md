---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c3da3a22880892878e3e07c415a5b1e243680b81d2361da7cdc34f8b536abad0'
step_id: 'S25'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# drop resolver-only coverage after the resolver is ruled out

## Scope

- `src/cadrumo/core/identity/tests/test_namespace.py`

## Description

- Consume the S64 decision that no production resolver is justified.
- Remove enum-only catalogue coverage alongside the dormant enum.
- Author no resolver tests because no resolver implementation or production contract remains.

## Outcome

S25 closed as dropped-without-resolver-tests under S64. Resolver-only coverage would test a manufactured API that production does not consume. The landed deletion removed enum/catalogue tests while retaining direct alias constraint coverage and facade import proof.

The focused identity suite passed with 18 tests, and the retired-name census reported zero `IdentifierNamespace` occurrences across production and developer Python sources.

## Notes

This record supplies the missing per-step traceability for the already-landed S64 deletion commit. It records deliberate test deletion, not an omitted test implementation.
