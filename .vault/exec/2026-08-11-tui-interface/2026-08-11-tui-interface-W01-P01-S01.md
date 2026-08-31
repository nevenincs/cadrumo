---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b691878295be65e2b6783992e1d2862363ea93480e9de7976975a562c6879b1e'
step_id: 'S01'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Record the C1 cohort-open governance fact citing the C1 conformance module and the commit it was proven against

## Scope

- `dev/quality/modelo_workspace_action_denominator.py`
- `dev/tests/test_modelo_workspace_action_denominator.py`

## Changes

- `M` `.vault/exec/2026-08-11-tui-interface/2026-08-11-tui-interface-W01-P01-S01.md`
- `verify:` `pytest dev/tests/test_modelo_workspace_action_denominator.py` -> `9 passed`

## Notes

THE C1 COHORT-OPEN FACT. The C1 conformance module is
`dev/quality/modelo_workspace_action_denominator.py`, and the retained validator
the 2026-08-28 amendment preserved is
`validate_modelo_workspace_action_denominator` at
`dev/quality/modelo_workspace_action_denominator.py:1161`. Its gate
`dev/tests/test_modelo_workspace_action_denominator.py` was run on 2026-08-31
and reported 9 passed, 0 failed.

COMMIT PROVEN AGAINST, stated precisely because the row's whole point is that a
reader must be able to verify it: HEAD was
`604a9c1bd4669fb0ae6d95aa5e9e3e5beb9b0934`. THE RUN WAS AGAINST THE WORKING
TREE AT THAT HEAD, NOT AGAINST A CLEAN CHECKOUT OF IT. This worktree is shared
and carried uncommitted changes from several concurrent lanes at the time, so
"proven at 604a9c1b" would overstate what was measured. A reader reproducing
this should expect the gate to pass at that commit, and should treat a
divergence as a question about the intervening working-tree state rather than
as a contradiction of this record.

WHY THIS RECORD WAS REWRITTEN RATHER THAN AUTHORED FRESH. A record already
existed at this path, dated 2026-08-26, headed "Record the C1 entrance receipt
with the accepted companion stem, accepting commit and body hash, canonical
Casilla review evidence, and architecture migration-lane commit ancestry". That
is the vocabulary of the CODE-RESIDENT ENTRANCE RECEIPT, which the 2026-08-28
amendment retired -- the same amendment that rewrote this Step row into its
current form. So the artifact existed while describing a design that no longer
applies, and the row stayed open. That is the recorded-but-not-implemented
shape: a file present at the expected path reads as done to anything that
checks for presence, and only reading it reveals that it answers a superseded
question.

STANDING GOAL NOT COVERED, restated from the row so it is not lost on closure:
the retired receipt bound the Casilla review evidence and the architecture
migration-lane commit ancestry as MACHINE-CHECKED fields. This record states
the conformance module and commit as prose. Nothing recomputes them, and
nothing will fail if they drift -- a reader must verify them by hand. That is a
real reduction in guarantee against the retired design, accepted by the
amendment rather than by this row.
