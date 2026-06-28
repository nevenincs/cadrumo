---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S98'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S98 - extract config bucket history

Scope: `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_bucket_history.py`.

## Description

- Move `config bucket history` and its filter/payload helpers into `_config/_bucket_history.py`.
- Keep event-history storage, event typing, and catalogue semantics in the existing domain services.
- Preserve the package-level `_parse_bucket_event_types` export used by focused parser tests.

## Outcome

The config root now mounts bucket-history through a focused registrar. The extracted module owns CLI parsing, localized parameter errors, event filtering, and envelope projection for the existing `config bucket history` verb.

## Notes

The policy-coverage AST scanner was extended to include `_bucket_history.py`, so `config bucket history` remains discovered from source and checked against the repair-policy catalog.
