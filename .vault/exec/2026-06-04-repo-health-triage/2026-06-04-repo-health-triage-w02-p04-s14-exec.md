---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S14'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W02.P04.S14`

Scope: `src/aeat/domain/calculations/registry/_bindings.py`.

## Description

- Removed the registry-local `CounterpartSourceKind` alias.
- Reused the core counterpart source-kind subset for registry binding handling.
- Updated the retired `invoice` wildcard regression test to assert empty
  resolution against canonical counterpart observations.

## Outcome

Registry counterpart callers now use enum-backed source-kind values from the
shared core taxonomy.

## Notes

The focused aggregation and registry tests passed after the stricter retired
`invoice` behavior was asserted.
