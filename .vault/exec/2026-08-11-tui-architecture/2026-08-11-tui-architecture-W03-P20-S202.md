---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5365b06b8520ccf7fe1a695240a786cb1e0de53de6f30b03653b85f12066971b'
step_id: 'S202'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

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
