---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S19'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Scaffold the new help, format-hint, and failure-mode key namespaces across all four catalogues through the locales CLI, never hand-editing the yml files

## Scope

- `src/cadrumo/locales/`

## Description

- Scaffold the new help, format-hint, and failure-mode key namespaces across all four catalogues through the locales CLI, never hand-editing the yml files.
- Fix the usage scanner so constructed flow-verdict keys are collected as live usage.
- Keys landed by the coordinator's serialized passes (`9bec9bcffb` and follow-ups); the scanner fix rode `ecc53655e9`.

## Outcome

The substrate help, format-hint, and failure-mode namespaces exist in all four locale catalogues with scaffold --check clean; constructed verdict keys are recognised as live so the honesty gate does not flag them.

## Notes

Locale keys were landed through the coordinator's serialized locale passes to avoid parity races in the shared worktree; the constructed-key scanner fix (`ecc53655e9`) was required before scaffold --check passed.
