---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:9f7e79ce146df8b25d0665e3e4c3eae29932ba15b3a272335e1107cd57e9b21e'
step_id: 'S42'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Split the repair-integrity family, whose two halves differ: the metadata-only reports are superseded because the live config repair verb imports exclusively from application diagnostics, which already performs the same per-namespace integrity probe, and nothing in production imports repair integrity at all; but the remediation decision repository has no replacement, since diagnostics carries no remediation handling while the secure-object namespace registry declares an encrypted namespace for exactly those decisions, so the store stands ready and an operator decision about a damaged row leaves no record

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting"` -> `pass` (the three tests a new symbol cluster can affect, including the staleness check against the live audit; the full nine-test file was run twice and killed under machine contention before reporting)

## Notes

`RepairRemediationDecisionRepository` is the finding worth an owner's attention.
The secure-object namespace `cadrumo.application.repair_integrity.decisions` is
registered for it, so an encrypted store is declared and provisioned, and
nothing writes or reads it. `application/diagnostics.py`, which the live
`config repair` verb uses instead, has no remediation-decision handling at all,
so this is not a displaced implementation with a survivor -- the capability has
no other home.
