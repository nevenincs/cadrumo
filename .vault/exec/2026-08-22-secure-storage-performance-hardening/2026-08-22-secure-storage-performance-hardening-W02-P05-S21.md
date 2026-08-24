---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6be29531452a3b6b860790108b769355260271d567c85713f1c4ab290ee0e226'
step_id: 'S21'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Add facade parity, cycle, forbidden-import, and read-only-materialization gates

## Scope

- `src/cadrumo/tests/`

## Description

- Add fresh-process workflow facade parity and canonical-owner checks.
- Add dynamic static/literal-import cycle detection across module-level compound bodies
  with adversarial relative, absolute, and dynamic edges.
- Add forbidden write-boundary import plants, isolated-parent filesystem equality,
  unloaded writer census, and a real materialization bite.

## Outcome

The workflow facade maps every public symbol to its canonical lazy owner, the live
workflow module graph is acyclic, and config/path reads leave the complete isolated
filesystem unchanged without loading write-side modules. Eight focused tests and Ruff
pass; independent review approved the gates.

## Notes

The new parity gate exposed and corrected several re-export-owner mappings. No harness or
external-client file was modified.
