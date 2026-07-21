---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S27'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Migrate the reset family help and risk metadata to the accepted grammar

## Scope

- `src/cadrumo/application/operator_surface/_help.py`

## Description

- Add `config reset start --yes`, `config reset status`, and `config reset resume --yes` entries to the curated config help surface (`_help.py`) diagnostics section, alongside `repair quarantine` / `repair reset-progress`.
- Risk metadata for `config.reset.start` / `.status` / `.resume` was already migrated to the accepted grammar in S26 (`_risk_table.py`); confirmed start/resume are `destructive=True` and status is read-only, no stale flat `config.reset` entry remains.

## Outcome

The reset lifecycle is discoverable on the operator help surface with confirmation flags shown, matching sibling destructive verbs. Harness rule-surface conformance, documented-command conformance, and operator-surface suites green (354 passed). Locale keys wired in S28 (co-committed).

## Notes

Help descriptions reuse the accepted reset verb copy; new keys `cli.operator_surface.help.config.reset_{start,status,resume}` are wired through the locales CLI in S28.
