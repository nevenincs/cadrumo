---
tags:
  - '#exec'
  - '#registry-row-width-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
---

# P02.S04 Row-Width Deferrals

Scope: `P02.S04` records near-threshold TOML rows and concurrent dirty paths not edited by this slice.

## Description

- Rechecked the remaining rows at or above 540 characters after S02 and S03.
- Confirmed that no remaining row-width target file is dirty in the scoped worktree diff.
- Recorded deferred M100 completeness-manifest `legal_refs` rows for revisions 2021 through 2024.
- Recorded deferred M100 2020 inline `constraints` row requiring a dedicated TOML-shape equivalence pass.
- Recorded unrelated concurrent dirty registry paths that remain outside this plan's row-width target set.

## Outcome

- Remaining row-width target rows are documented in `2026-06-04-registry-row-width-pressure-audit.md`.
- Unrelated dirty registry paths were not touched.
- This step made no registry data edits.

## Notes

- The deferred M100 rows keep the post-S04 maximum committed registry TOML row length at 552 characters, so S05 can tighten only to a baseline above that value unless the deferred rows are handled in a later pass.
