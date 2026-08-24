---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5942a70274739ae951330b8611397c7172b4e6657c477637fc15439eab13d8d9'
step_id: 'S20'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Separate read-only settings and path calculation from directory, permission, logging, journal, and topology materialization

## Scope

- `src/cadrumo/core/config.py`

## Description

- Move storage topology creation, occupancy refusal, and root permission hardening from
  read-only config into canonical storage materialization ownership.
- Expose the mutator and mode lazily through the sole core facade and repoint all
  cross-package production and test consumers.
- Prove settings and derived-path reads create no storage state while materialization
  retains the prior security behavior.

## Outcome

`core.config` now owns settings and path calculation only. Filesystem mutation is explicit
and demand-loaded through the core facade. Focused storage/config tests pass and Ruff is
clean; independent review approved the final boundary.

## Notes

No compatibility shim or harness/client change was introduced.
