---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S99'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove config lock and its weaker session-only execution path without an alias

## Scope

- `src/cadrumo/entrypoints/cli/_config/__init__.py`

## Description

- Remove the root `config lock` registration and transport handler without an alias.
- Remove its output schema, risk row, bootstrap exemption, locale nodes, operator-contract family, generated terminology entries, tests, and current documentation references.
- Regenerate the affected documentation sequence and terminology coverage from their source authorities.

## Outcome

No active source, schema, locale, generated inventory, test expectation, or user guide exposes the duplicate lock command.

## Notes

Historical ADR, research, audit, and execution records retain the removed spelling as supersession evidence.
