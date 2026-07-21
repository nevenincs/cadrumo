---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Confirm the existing session-lifecycle and profile-navigation suites pass with the scattered disposals removed and the use-time readiness guards untouched

## Scope

- `src/aeat/entrypoints/cli/tests`

## Description

- Run the stripped navigation/rename suites plus the session-lifecycle and profile-navigation suites with real adapters.
- Distinguish owner-surface results from pre-existing peer churn per the full-tree-gate discipline.

## Outcome

Owner suites pass; the use-time readiness and session-freshness guards are untouched.

Landed in commit `38e62c216`.

## Notes

Seven sweep failures (config-switch/show, apoderado status, modelo-303 defaulted-profile preflight) are pre-existing peer churn: they fail at CLI arg-validation and registry-applicability, upstream of every changed line, and were proven HEAD-independent by re-running them with HEAD copies of the profile-adjacent files swapped in (identical failures). Owned by other campaigns (profile-create required flags `--entity-type/--name/--surnames`; not fixed here).
