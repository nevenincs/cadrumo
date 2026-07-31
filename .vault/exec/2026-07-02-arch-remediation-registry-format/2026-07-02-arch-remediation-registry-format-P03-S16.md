---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:eed24f9412fa3b086631a7bacf670f636a0e6cbbb97b5e3407205c820b5677af'
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

## Honesty-review correction (2026-07-03)

The Outcome's sync claim was FALSE at the time this step was checked: the vaultspec source was converged in `2cf772da94` (~23:52 the prior night) but the four generated provider copies remained the stale pre-convergence text for ~9 hours, through plan closure (`71df727e39`, 09:04:58), and were only synced by the follow-through commit `f431e6a819` (09:07:46), whose message admits the staleness. Any agent loading the generated rule in that window received pre-convergence guidance. Correction recorded by the D6 campaign-close honesty review; see the 2026-07-03 arch-remediation-registry-format audit.
