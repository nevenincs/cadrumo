---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:df589f7852fc4ca178951774e2e5e08aec220387e2233dc8f277ccbbaf57941d'
step_id: 'S18'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Replace the eager workflow facade with an explicit PEP 562 lazy export map preserving public symbols and direction

## Scope

- `src/cadrumo/application/workflow/__init__.py`

## Description

- Replace eager workflow facade imports with an explicit closed PEP 562 export map.
- Preserve all 94 canonical public names, cache first resolution, and expose supported
  names through `__dir__` without importing owner modules.
- Add fresh-process import and canonical-owner identity parity gates.

## Outcome

Cold import of the workflow facade loads zero workflow-owned submodules. Every public
name resolves from its declared canonical owner with stable identity and caching. Three
focused tests and Ruff pass; independent review found no blocking issue.

## Notes

No compatibility alias or fallback was added, and no harness or external-client file was
modified.
