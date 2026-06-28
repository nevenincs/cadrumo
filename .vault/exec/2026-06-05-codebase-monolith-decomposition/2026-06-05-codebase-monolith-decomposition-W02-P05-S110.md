---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S110'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S110 - extract modelo audit commands

Scope: `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/entrypoints/cli/_modelo_audit_cli.py`.

## Description

- Move `aeat app modelo audit {show,check,export,replay}` command bodies out of `_modelo.py`.
- Keep `audit_app` and `register_audit_commands` in the focused audit registrar.
- Preserve the public command paths and typed output envelopes.
- Keep `_modelo.py` as the composition surface that mounts the audit app.

## Outcome

The modelo root no longer owns evidence-bundle audit command bodies. Audit behavior continues to delegate to `EvidenceBundleService` and preserve existing operator command paths.

## Notes

This slice is transport-only. Evidence bundle storage, verification, export, and replay semantics remain in the application evidence service.
