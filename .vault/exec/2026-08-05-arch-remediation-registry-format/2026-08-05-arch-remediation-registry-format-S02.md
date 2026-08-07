---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:96023db2ef81eab4310bbff3a039dfbdf3d53507bd47d5b8092197e0d1e855fe'
step_id: 'S02'
related:
  - "[[2026-08-05-arch-remediation-registry-format-plan]]"
---

# Propagate the corrected rule to the generated provider copies with the sync verb, confirming no generated copy carries a hand-edit

## Scope

- `.claude/rules/modelo-export-mirrors-official-structure.md`

## Description

- Confirm no generated provider copy carried a hand-edit before syncing.
- Propagate the corrected rule from its `.vaultspec` source with the sync verb.

## Outcome

Four generated provider copies updated from the single `.vaultspec` source; 344
other rules unchanged. The generated copies are never authored directly, so the
pre-sync check confirms the sync is a clean propagation rather than an overwrite
of someone's edit.

## Verification

The pre-sync hand-edit check compared the generated copy against its committed
form and found them equal:

    generated copy matches HEAD (no hand-edit)

The sync verb then reported its own tally:

    uv run --no-sync vaultspec-core spec rules sync
    4 updated  344 unchanged

## Notes

The hand-edit check is the load-bearing half of this step. A sync silently
overwrites a hand-edit, so running it without first confirming the generated copy
was untouched would destroy an edit and report success.
