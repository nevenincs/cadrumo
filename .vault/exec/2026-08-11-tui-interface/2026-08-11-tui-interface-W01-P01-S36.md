---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:589fa6bdbc160055d34758786edaaf0f02439f4057ef3ee5b98a3aea2e4459ad'
step_id: 'S36'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Build ModeloWorkspaceActionDenominatorV1 from the canonical action catalogue, operation definitions, complete command graph and TuiCapability values, direct effect sites, routes, action views, dispatch rows, and typed exclusions

## Scope

- `dev/quality/modelo_workspace_action_denominator.py`

## Changes

- `A` `dev/quality/modelo_workspace_action_denominator.py`
- `A` `dev/tests/test_modelo_workspace_action_denominator.py`
- `verify:` `uv run --no-sync pytest dev/tests/test_modelo_workspace_action_denominator.py -q` -> `pass` (9 passed)
- `verify:` `uv run --no-sync ty check dev/quality/modelo_workspace_action_denominator.py` -> `pass`

## Notes

Candidates are enumerated only from production imports
(`command_spec_nodes()`, `OPERATOR_ACTION_CATALOGUE`) — never a filesystem
walk — so the artefact cannot ingest a gitignored mirror. The closed
classification table is a hand-reviewed, checked-in constant compared against
a freshly re-observed live signature at validate time; a live candidate
missing from the table, a stale table entry, or a drifted signature field all
red explicitly rather than silently defaulting. Routes, action views, and
dispatch rows are not yet built anywhere in the tree (TUI Workspace read/write
destinations are future C1-C5 work); every current candidate is honestly
classified as pending its future cohort (`C1_OR_C2_READ_PENDING` /
`C4_MUTATION_PENDING`) rather than fabricating a destination that does not
exist. `modelo.work.create` (DEFERRED to work-lifecycle ownership) and the two
wizard commands (FLOW_OWNED) are the only judgement-call rows; every other
disposition follows mechanically from the command's own `write_route`.
