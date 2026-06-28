---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P03.S07'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P03.S07`

Executor-discovered scope addition: updated the
`aeat.application.operator_surface` backend contract to advertise the
`repair` command family in place of the retired `doctor` family.

- Modified: `src/aeat/application/operator_surface/_contract.py`
- Modified: `src/aeat/application/operator_surface/_help.py`

## Description

P01's executor flagged this as a follow-up because the
`test_apex_workflow_verification` test asserts that every backend-
declared command family is mounted in the CLI, and the apex
verification grid asserts `required_children` matches the set of
mounted children. Until the contract was updated, the apex verification
test fixed `required_children=("init", "profile", "auth", "doctor")`
even though the CLI mounts `repair`, leaving the contract grid out of
sync with the live CLI surface.

This step folds the contract update in alongside the `reset-state`
implementation since adding `reset-state` is a new sub-command on the
same `repair` family the contract advertises:

- `ACCEPTED_ROOTS[CONFIG].required_children` now reads
  `("init", "profile", "auth", "repair")`.
- `MOUNTED_COMMAND_FAMILIES[DIAGNOSTICS].child` flips from `"doctor"`
  to `"repair"` and the commands tuple flips from
  `("doctor", "logs", "quarantine", "connectivity")` to the
  ADR-mandated `("connectivity", "integrity", "list", "quarantine",
  "reset-state", "logs")` to match apex ADR §3.6's grammar.
- `_help.py` root- and config-help sections now name `aeat config
  repair` and surface the `aeat config repair reset-state` entry; the
  audit help surface contains no leftover `aeat config doctor`
  reference.

The diagnostics service still owns the family; only the surface
naming and the advertised sub-command set changed. The plan does not
have a P03.S07 row; this step is recorded for the controller to
either append the row to the plan or absorb it under P06's contract
sweep.

## Tests

`test_required_children_match_mounted_command_families` and
`test_help_command_rows_are_backed_by_mounted_command_families` in
`application/operator_surface/test_contract.py` both pass after the
contract and help-document updates land. The apex verification suite
in `entrypoints/cli/test_apex_workflow_verification.py` also passes
end-to-end.
