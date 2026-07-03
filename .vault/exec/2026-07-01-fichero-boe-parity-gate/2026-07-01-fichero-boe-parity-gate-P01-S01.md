---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S01'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Add a completeness_manifest field to RegistryModeloSubview

## Scope

- `src/aeat/application/filing/runtime.py`

## Description

- Import `CalculationCompletenessManifest` into the filing runtime registry import block.
- Add a `completeness_manifest: CalculationCompletenessManifest | None` field to the frozen `RegistryModeloSubview` dataclass.
- Add a `has_completeness_manifest()` accessor reporting manifest presence, so the export path can route to a coverage advisory when a revision carries no manifest.

## Outcome

Landed in commit `807a55eb9`. The export subview now carries the revision manifest field; `ruff` clean; the sole subview construction site updated in the same change (S02).

## Notes

Shared-worktree index churn caused two transient commit failures (a mangled heredoc, then a peer bare-commit racing the index); resolved by an explicit-pathspec commit after verifying the staged set carried zero foreign markers. No peer work was swept.
