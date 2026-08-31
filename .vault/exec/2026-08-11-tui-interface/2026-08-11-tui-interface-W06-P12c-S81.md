---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:99ccb191223099828a718d7ba6b70f5387dac0cd1c2c4c62ade9ce64370518b6'
step_id: 'S81'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12c-S80]]"
---

# Regenerate the complete action denominator and fail missing, duplicate, stale, or unclassified action-catalogue, operation, command-graph, effect-site, route, view, dispatch, flow-owned, deferred, and non-visual candidates

## Scope

- `dev/quality/modelo_workspace_action_denominator.py`

## Changes

- `M` `dev/quality/modelo_workspace_action_denominator.py`
- `M` `dev/tests/test_modelo_workspace_action_denominator.py`
- `verify:` `pytest test_modelo_workspace_action_denominator.py test_actions.py` -> `21 passed`

## Notes

A SECOND CANDIDATE STREAM, which is what this row's "dispatch" candidates
required. Discovery previously observed ONE source: the CLI command graph. It
now also observes `discover_dispatchable_modelo_action_identities`, imported
from the shipped package rather than re-listed, so a dispatch row added to the
surface enters this gate automatically instead of when somebody remembers a
parallel list.

THE TWO STREAMS HAVE DIFFERENT DENOMINATORS, and that is the finding rather
than a defect. Measured: 7 dispatchable, 79 command-graph live, 6 overlapping.
The command graph answers "what commands exist"; the dispatch table answers
"what can a workspace surface invoke". They disagree in both directions -- a
command can exist with no surface reaching it, and `modelo.edit.apply` is
dispatchable while not being a command-graph candidate at all. A test pins the
non-convergence, so a future change that made the two coincide would have to
widen the rule deliberately rather than by accident.

THE ENFORCEABLE RULE IS THE INTERSECTION ONLY, and arriving there meant
retracting a stronger rule I had already written. The first version flagged
every action classified `C4_MUTATION_PENDING` that appears in the dispatch
table -- six of them -- as "a classification describing a state the tree has
left". THAT IS FALSE. W06.P12c.S80 declares WHERE an action would dispatch; it
does not enrol it. Enrolment is S82 through S87, all still open, so those six
are correctly still pending and the rule asserted something S80 never
established. A gate encoding that would have forced six classifications to be
rewritten to describe a state that does not exist.

The second wrong shape was subtler and worth recording: requiring every
dispatchable action to be classified would demand a table row for
`modelo.edit.apply`, which the EXISTING stale-classification rule would then
reject, because that rule fires on any classification absent from the live
command graph. The two rules would contradict each other on one identity, each
correct in isolation. Widening the classification table's denominator to cover
non-CLI registered operations is a scope decision belonging to that table's
owner, not to this check.

PROVEN TO BITE, not merely green: removing one intersection member
(`modelo.export`) from an injected classification table raises the violation
naming it. Driven through the validator's own `denominator` argument -- which
exists so a candidate table can be checked without mutating the module
constant -- so nothing on disk is broken to test the gate. That matters here
specifically: this worktree is shared, and a peer's broad landing commit could
otherwise capture a deliberately corrupted table.
