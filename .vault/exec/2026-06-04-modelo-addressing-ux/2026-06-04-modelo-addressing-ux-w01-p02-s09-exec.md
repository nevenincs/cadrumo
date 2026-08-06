---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:b638dd0f2cc2274c3a2c2ba4b7d68dfe5c6ac258117c76075609cd3e954e8f10'
step_id: 'S09'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P02.S09 duplicate draft current-pointer advancement

Scope:
- `src/aeat/application/modelo/_revision_persistence.py`

## Description

- Update duplicate calculation persistence so an existing draft revision is restored as `current_calculation_revision_id` when reused.
- Leave non-draft duplicate revisions unchanged so the system does not pretend an old verified or filed revision is a fresh draft.
- Preserve filed and current filing pointers while updating the current calculation pointer.

## Outcome

Re-running a calculation that resolves to an existing draft can still make that draft the current revision for later verify/file/export defaults.

## Notes

- Covered by `test_duplicate_draft_calculation_reuse_advances_current_pointer`.
