---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S10'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Expose the substrate public facade with an explicit __all__ consumed only via top-level re-exports

## Scope

- `src/cadrumo/application/flows/__init__.py`

## Description

- Expose the package facade with an explicit sorted __all__; consumers import from the facade only.
- Land in commit 91c5e51afc, extended across subsequent substrate commits.

## Outcome

Import-hygiene discipline holds: no cross-package private reach into or out of the substrate (reviewer invariant 7 PASS).

## Notes

Facade grew with each substrate lane (copy, scripted, checkpoint, resume, line frontend, bridge).
