---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S79'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P20.S79 Dependency Declaration Drift Verification

Scope: `pyproject.toml`, dependency declaration audit lane.

## Description

- Verify the active dependency audit command from `justfile`.
- Run the production dependency declaration drift gate against `src/aeat`.
- Preserve `pyproject.toml` unchanged because the gate is already green.

## Outcome

`just audit-deps` passed. Deptry scanned 884 production files with
`--known-first-party aeat` and the configured test exclusions, then reported no
dependency issues.

## Notes

No dependency declaration edit was required for this step. The closure is
evidence-only and keeps the dependency lane green without broadening or
weakening the configured audit scope.
