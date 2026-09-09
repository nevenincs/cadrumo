---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:dccabd633ed8899f9b847553eac2566235442e288daa7f9599c25e3cc888101a'
step_id: 'S43'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Run canonical strict production type checking at the Wave 1 handoff

## Scope

- `justfile check-types and dev/quality/types.py`

## Changes

- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P23-S43.md`
- `verify:` `just check-types` -> `fail`

## Notes

The boundary command reports 50 existing `ty` diagnostics outside the facts-registry surfaces; `pyrefly` and `basedpyright` report zero diagnostics. No Wave 1 facts path appears in the detailed output.
