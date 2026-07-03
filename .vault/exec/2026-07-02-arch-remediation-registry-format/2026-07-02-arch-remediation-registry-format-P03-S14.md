---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S14'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---




# Delete the loader inline-parsing branches now that no revision declares bindings or formulas inline

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Delete the loader inline-section-parsing branches so revision.toml is scalar-only.

## Outcome

Done in `e99a3a9ad3` (peer registry refactor): `_merge_revision_manifest` reads revision.toml as scalar-only metadata; per-section array-of-tables no longer parse inline. Full registry tree loads clean.

## Notes

Landed by a peer alongside the module split; verified at HEAD, not re-implemented.
