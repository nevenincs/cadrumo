---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:7a9e54585b4dc23b86ea5d88afff17353c8e6a9494f65d991f5a3c2e1f31f104'
step_id: 'S16'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Replace hidden first-party function-local coupling with owned lazy public handler and schema boundaries referenced only by CommandSpec targets

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

- Move executable-root and app-root handlers from the CLI assembly facade to an owned
  lazy public target module.
- Move the complete root helper cluster to one canonical support owner and remove the
  facade-to-handler cycle without aliases or duplicate implementations.
- Repoint CommandSpec handler targets and enroll every dynamic handler module in a
  static facade-import prohibition covering direct, aliased, relative, and literal
  dynamic import forms.

## Outcome

Every current root, group, and leaf handler resolves through an owned public target;
none targets or imports the CLI package facade. The graph-import test has no bootstrap
escape hatch. Six focused tests and Ruff pass, and independent re-review confirms the
original architectural finding is resolved.

## Notes

The first implementation moved the public callbacks but still imported six private
facade helpers. Review blocked that cosmetic split. The final implementation relocates
the helpers themselves and adds an executable regression gate. Harness and client
shipping surfaces were not modified.
