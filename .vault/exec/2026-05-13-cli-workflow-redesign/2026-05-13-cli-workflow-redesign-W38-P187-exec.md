---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W38.P187'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W38.P187`

Shadow-duplicate removal phase. Two boundary tests pin the
canonical surface for the modelo work-unit concept.

## Description

`test_no_parallel_work_unit_model_outside_canonical_module` walks
`src/aeat/`, skips the canonical
`aeat.domain.modelos._work_unit` module and test files, and
asserts no other module declares a class named `WorkUnit(`.

`test_no_parallel_work_unit_storage_namespace` searches the
source tree for the namespace string
`"aeat.domain.modelos.work_units"` outside the canonical
repository module. Any other source file mentioning that
namespace would compete with the canonical storage location.

Both tests currently pass because the wave's deliverable is the
only declaration of either pattern.

Closed plan rows: `W38.P187.S1117`, `W38.P187.S1118`,
`W38.P187.S1119`, `W38.P187.S1120`, `W38.P187.S1121`,
`W38.P187.S1122`.

## Tests

Boundary tests pass as part of the 21-test
`src/aeat/domain/modelos/test_work_unit.py` suite.
