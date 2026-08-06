---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c15c78233fa13a8d9d3ca52b284557fdd5b695c03f68d162f0cdbac6b23bf043'
step_id: 'S04'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Purge dead-module ignore entries

## Scope

- `.importlinter`

## Description

- Rechecked each audited dead module against the filesystem at `HEAD` before deletion.
- Purged all ignore lines naming the absent normatives, fincas, workflow live-test, and stale test modules.
- Continued removing unmatched stale entries surfaced by the alerting flip until Import Linter reported no unmatched ignore imports.

## Outcome

Fourteen ignore lines naming the eight dead modules were removed. The final ratchet test confirms every remaining ignored source and target module resolves on disk.

## Notes

Additional stale entries exposed only after alerting became fatal were removed as ledger drift, not as architecture fixes.
