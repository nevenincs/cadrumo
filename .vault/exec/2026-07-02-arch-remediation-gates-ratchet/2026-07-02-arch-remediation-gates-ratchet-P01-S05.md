---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S05'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Flip unmatched ignore alerting to error

## Scope

- `.importlinter`

## Description

- Set `unmatched_ignore_imports_alerting = error` on every Import Linter contract.
- Used the resulting fatal Import Linter output to remove stale and misfiled ignore entries until the gate passed.

## Outcome

All four contracts now use `error` alerting. The final inventory has 4 error settings and 0 warn settings.

## Notes

This step intentionally made latent ledger drift visible before the wildcard replacement landed.
