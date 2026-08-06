---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:29e93948d37f4020ce416d5db0e09a8a7d986fbfbfc0a6848f272fce4644f63f'
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

## Honesty-review correction (2026-07-03)

The Outcome above cites the wrong commit. Independent verification (`git log -S "_merge_revision_manifest"`) shows the loader inline-parsing deletion landed in `2cf772da94`, not `e99a3a9ad3` (which is the unrelated module-size split of `_loader.py`). Correction recorded by the D6 campaign-close honesty review; see the 2026-07-03 arch-remediation-registry-format audit.
