---
tags:
  - '#exec'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:595bcf268bac1e1d09ee6c57122eee31df9998d0be4e183f5a3ddbf906eff5d5'
step_id: 'S13'
related:
  - "[[2026-07-14-google-optional-adapter-boundary-plan]]"
---

# Regenerate the Google OAuth feature index after both Google reconciliations land

## Scope

- `.vault/index/google-oauth.index.md`

## Description

- Confirm the legacy Google plan and all four ledger-Google records exist only at their archive destinations.
- Record the protected archived legacy-plan and parent-plan blobs before regeneration.
- Run `uv run vaultspec-core vault feature index -f google-oauth --json` from the repository root.
- Inspect the complete generated-index diff and verify it reflects both reconciliations.
- Run `uv run vaultspec-core vault check features --feature google-oauth --json`, `uv run vaultspec-core vault check links -f google-oauth --json`, and `uv run vaultspec-core vault check dangling -f google-oauth --json`.
- Recheck the protected blobs and leave the plan checkbox, shared index, and Git history unchanged.

## Outcome

The canonical index command exited successfully with `status: updated` and generated only `.vault/index/google-oauth.index.md`. The complete diff removes the archived legacy plan from the live feature index, adds the `2026-07-14-google-oauth-audit`, adds the 39 reconciliation execution records, and changes the six superseded May ADR entries from `accepted` to `superseded`.

The regenerated index has blob `79100aa696c7e32ec2fa24ef500360d0cfead055`. The supported `features` check reported `status: unchanged`, zero diagnostics, and `fixed_count: 0`. The scoped `links` and `dangling` checks each reported zero diagnostics, confirming that its live and archive-aware stems resolve.

## Notes

The archived legacy Google plan remained at blob `88a085b9ab5edf5ec75454d8fe39d474dce7d5af`, and the parent optional-adapter plan remained at blob `3637d1e73af49db3d8b491417c4d4f0625f968ea`. Neither file was edited.

The CLI emitted inherited repository-wide stem-collision warnings unrelated to the generated target. This Step did not change the parent checkbox, stage files, or create a commit.
