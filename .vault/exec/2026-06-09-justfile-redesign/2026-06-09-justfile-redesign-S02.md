---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S02'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# implement programmatic semantic audit checks with silent-on-success assertions

## Scope

- `scripts/audit_semantic.py`

## Description

- Implemented `scripts/audit_semantic.py` to check for domain/registry logic leakages into adapters or entrypoints.
- Configured check health on port 8766 health check first, skipping the audit gracefully if offline or not ready.
- Formulated semantic queries (`"currency rounding"`, `"calculate tax base"`) to discover matches with a score threshold >= 0.50.
- Asserted that zero matches exist in non-canonical paths (ignoring test and locale files).
- Enforced a zero-noise, silent-on-success policy by exiting with code 0 on success.

## Outcome

The script `scripts/audit_semantic.py` was implemented and verified. When run, it correctly pings the local RAG daemon on port 8766, executes the queries with custom timeout budgets, filters out test and locale files, and exits silently with code 0 on success.

## Notes
