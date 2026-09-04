---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:68201f757ad322ab836558fcfa9a734db74a145c228c923ad29f06aa7c65198b'
step_id: 'S15'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Record the design-time-authority modules as intentional in the module ratchet with their conformance-gate reader named, rather than relocating product declarations into dev

## Scope

- `dev/quality`

## Changes

- `M` `dev/quality/unreachable_module_ratchet.toml`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync python -m dev.quality.unreachable_module_ratchet` -> `pass`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

The four design-time authorities moved from the ratchet's `allowed` backlog to typed
`[[intentional]]` dispositions, each naming the conformance gate that reads it. `allowed`
shrank from 14 to 10; the list only ever shrinks, and this is a real shrink rather than a
relabel because the modules are endorsed with a stated reason rather than carried as debt.
The closed `kind` vocabulary already had exactly the member these need,
`design_time_authority`, so no vocabulary was widened to admit them.

Teeth proven against the live gate, all three directions: dropping an `allowed` entry -
which is what a newly unreachable module looks like - exits 1; adding an entry the tree
does not report exits 1; and an `[[intentional]]` entry whose rationale is blank is
refused outright by the disposition type before any comparison runs.

The teeth probe initially reported a false pass. `$?` after a pipeline reports the last
command in it, so `ratchet | tail -3; echo $?` was reporting tail's status rather than the
gate's. Re-run with the output redirected and the exit code read directly, the gate fails
exactly as designed. The lesson is recorded in the cadence memory because it invalidates
any teeth result gathered the first way.

`cadrumo.application.modelo.edit_session` was reclassified from `staged-capability` to
`deferred-by-ownership`. The ratchet's own deferral report names four TUI edit modules as
its importers, so while the accepted edit-contract decision governs the capability, the
operative fact for this campaign is that its consumers belong to the TUI campaign. The
classification ledger now records that, with the importers named.
