---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:f8666f845a6b24461734db8d86335a15210235e79622a97a3dd5a027543446a5'
step_id: 'S14'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Fix the embedded newline in the rd-439-2007 art-76 legal entry notes field, the validator rejects any Unicode C category and a narrower scan for control characters reads as clean

## Scope

- `src/cadrumo/_data/registry/aeat/legal`

## Description

- Restore the line continuations whose absence embedded newlines in legal-entry notes fields.

## Outcome

Landed as `0eb0ef20f0` ("fix(legal): restore the line continuations four notes fields were
missing"), three files, 6 insertions and 6 deletions.

## Verification

    git log --format=%H --grep="restore the line continuations" -1
    git show 0eb0ef20f0 --numstat
    3       3       src/cadrumo/_data/registry/aeat/legal/irpf.toml
    2       2       src/cadrumo/_data/registry/aeat/legal/iva-flow.toml
    1       1       (third legal catalogue)

## Notes

**The landed work is wider than the row, which is the opposite of the failure the closure rule
guards against but is still worth recording.** The row names one entry, the rd-439-2007 art-76
notes field. The commit repairs four notes fields across three catalogues, so the row's entry
is a member of the set fixed rather than the whole of it.

Recorded because a later reader auditing "was art-76 fixed" gets a yes, while one auditing
"what did this row change" would otherwise meet three further edits with no explanation. The
row closes on its own claim being satisfied, not on the row and the commit being coextensive.
