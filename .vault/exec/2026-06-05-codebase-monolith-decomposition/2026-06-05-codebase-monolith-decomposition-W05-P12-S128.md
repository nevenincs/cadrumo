---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S128'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S128 Registry Test Split

Scope: split oversized registry tests by schema and referential-integrity concern.

## Description

- Split registry schema tests into focused sibling modules with shared schema support.
- Split referential-integrity tests into focused sibling modules with shared integrity support.
- Preserved the domain hex marker and real registry-authority fixtures.

## Outcome

The registry schema and referential-integrity test modules are below the hard line budget while preserving real validation behavior.

## Notes

Ruff passed. Focused registry split lane passed with 136 tests.
