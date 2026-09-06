---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:f333777870887820251c55203c56d9eaa08161042cbe5409d4cfceedd54b6d8c'
step_id: 'S64'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Wire the flow checkpoint discard and reverse the custody record bound: the line frontend offers save-and-exit which writes a checkpoint while its submit path returned without clearing one, so an operator who saved, resumed and submitted left the checkpoint on disk and a later run would offer to resume an already-submitted flow, and submit now discards once eligibility is asserted under the same store guard as save-and-exit; and the four megabyte custody bound is orphaned rather than an unenforced safety limit, because no profile-record file exists in that package and the only profile_record in the tree is a record-format label on an encrypted secure-object namespace, to which a file-read byte cap does not apply

## Scope

- `src/cadrumo/application/flows/line_frontend.py`

## Changes

- `M` `src/cadrumo/application/flows/line_frontend.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/flows` -> `pass`
- `verify:` flows module imports clean

## Notes

The restart path was checked first and is NOT the leak: a confirmed restart is
followed by saves that overwrite the checkpoint. The leak is submission, where
the run loop returned the projection and left the saved state behind. The
discard is placed after `assert_submit_eligible` has run, so a refused submit
does not destroy a resumable checkpoint.
