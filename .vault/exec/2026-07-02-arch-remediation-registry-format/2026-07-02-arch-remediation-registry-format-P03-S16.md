---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S16'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---




# Converge the registry-revision-content-inline-or-fragmented discovery rule at its vaultspec source to record the convergence and retire the dual-format caveat, then run vaultspec-core sync

## Scope

- `.vaultspec/rules/registry-revision-content-inline-or-fragmented.md`

## Description

- Converge the registry-revision-content-inline-or-fragmented discovery rule to fragmented-only and sync.

## Outcome

Rule source at .vaultspec/rules/registry-revision-content-inline-or-fragmented.md is converged (title, Rule, Why, Status all state fragmented-only + the loader refusal, referencing D6). `vaultspec-core sync` reports the generated provider copies up to date.

## Notes

Source converged + committed; generated copies ride the concurrent provider-regen. Substantive convergence complete.
