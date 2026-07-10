---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-08'
step_id: 'S13'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Confirm zero inline revisions remain by grep before deleting inline support

## Scope

- `src/aeat/_data/registry/aeat/modelos`

## Description

- Confirm zero inline revisions remain (`git grep '^\[\[revisions.' over revision.toml` returns 0).
- Beyond the 6 planned, also migrated the revisions the plan undercounted: 136, 189, 280, 289, 345, 379, 296 (in `55a6de58aa`) and 303/2023-y-siguientes — the unquoted-key hybrid needing 0000-prefixed fragments — in `4d96df8136`.

## Outcome

Zero inline revisions remain; the equality harness carries 21 green baselines; the registry tree loads clean. P03 loader-closeout (S14-S17) remains for the registry-format agent.

## Notes

The plan undercounted the inline set (14 real vs 6 planned migration steps); the 8 extras have no plan steps — the agent should add them or note the coverage on reconciliation.
