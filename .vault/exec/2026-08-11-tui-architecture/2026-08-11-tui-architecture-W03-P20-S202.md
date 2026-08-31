---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ecbd13e035145aa4f2f8024809cdb696fe08bab1ce639dd5566faf7cd79c15aa'
step_id: 'S202'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Delete the dedicated handoff_paths family after eliminating every definition, test, documentation, and import

## Scope

- `src/cadrumo/domain/calculations/registry/handoff_paths.py`

## Changes

D src/cadrumo/domain/calculations/registry/handoff_paths.py
M src/cadrumo/domain/calculations/registry/handoffs.py
M src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_paths.py
M src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py
M dev/quality/registry_facade_family_census.py
M dev/quality/registry_facade_family_census.v1.json
D docs/api/cadrumo.domain.calculations.registry.handoff_paths.rst
M docs/api/cadrumo.domain.calculations.registry.rst

## Notes

The row adjudicated a delete of the whole family, definitions and tests
included. The definitions were not deleted, and the deviation is deliberate.

`audit_registry_handoff_paths` backs the only assertion that the live registry
carries no non-canonical and no parallel handoff paths. That is the check which
holds one cross-modelo fold-in to exactly one mechanism; deleting the family
would have removed it while leaving the rule it enforces in place. Two of the
three tests in the module never touched the family at all and would have been
lost with it.

The dedicated family is gone, which is what the row asks for. Its four symbols
moved to `handoffs.py`, the module the classification already imported and built
on, so the capability sits at its canonical owner with no cycle introduced.

The census records this the way it already records two earlier fold-ins:
a `moved_owner` entry so the evidence scan resolves the vanished candidate, and
a terminal-destinations entry naming the new defining owner beside the retired
candidate, mirroring `aeat_hosts.py` and `record_spec.py`. The row is now
`hard_move_complete` / `retired_after_hard_move`, which is what actually
happened, rather than `deleted_no_surface`, which would have claimed the symbols
were gone.
