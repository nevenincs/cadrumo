---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:25a745b6ba90311264e0c0cd5018a2d4bb10e3284484cead1406e657cf28d8ea'
step_id: 'S72'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Compose every exported operation definition into one immutable production registry with concrete operation adapters, journals, resources, and the supervisor in the sole TUI composition root

## Scope

- `src/cadrumo/entrypoints/tui/launcher.py`

## Changes

M src/cadrumo/entrypoints/tui/launcher.py
A src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py
M src/cadrumo/application/modelo/operation_definitions.py
M src/cadrumo/entrypoints/_operation_composition.py
M src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py
M src/cadrumo/application/modelo/tests/test_work_rename_operation.py
- `verify:` production registry composes 19 definitions across all six builder families

## Notes

All six definition-builder families now reach the one production registry:
auth, user-profile, censal, filed-history, Google Sheets export, and the modelo
lifecycle. The last of those was composed in this Step; the other five already
were. The registry carries the concrete journal, leases, operand store and
supervisor through the composed dependency graph.

The modelo family had been exported and never composed, so the registry knew
none of its six definitions: no frontend could submit one and no journal could
record one. Two defects kept it that way, both introduced when those enrolments
were written. Five executors closed over an actor supplied at build time, which
would force a per-actor registry; the actor is a request field now. Three
declared a REVIEW interaction they never performed, and the registry refuses a
REVIEW definition that registers no review schema, projector or reviewed
operand type, so they could never have been registered at all.

## Plan-versus-code

The row places the composition in the launcher. The launcher now owns the scope
that builds it and settles it, but the factory itself stays at
`entrypoints/_operation_composition.py`, shared with the CLI.

Moving the factory into the TUI package would oblige the CLI to import the TUI
to reach it, which is exactly the dependency this plan's own TUI boundary gate
forbids and which the CLI already depends on for its logout path. The row's
intent is that a TUI session has one composition root, and that is what shipped:
the launcher composes, everything else receives.

Two gates hold it. One refuses any TUI module other than the launcher reaching
a composition symbol, with a companion assertion so the sweep cannot pass by
finding no composition anywhere. The other proves every exported modelo
definition reaches the production registry.

A residual gap worth naming: that second gate covers the modelo family only. A
seventh family added later and left uncomposed would not red anything.
