---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f2b1f22d72da42eeeddb1705230924bfa0fb85532c8832ff0296fb39f6ca65fb'
step_id: 'S185'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the dedicated constructs family after eliminating every definition, test, documentation, and import

## Scope

- `src/cadrumo/domain/calculations/registry/constructs.py`

## Changes

D src/cadrumo/domain/calculations/registry/constructs.py
M src/cadrumo/domain/calculations/registry/tests/test_modelo_100_registry_constructs.py
M src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py
M dev/quality/registry_facade_family_census.py
M dev/quality/registry_facade_family_census.v1.json
M dev/tests/test_registry_facade_family_census.py
D docs/api/cadrumo.domain.calculations.registry.constructs.rst
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

The reader had no production caller. The census recorded one, but that module
does not import it. Registry build already resolves construct members through
`validate_construct_closure`, which checks member existence and the legal- and
source-ref coverage the grounding rule requires, so the reader duplicated that
work for callers that do not exist.

Three of its tests existed only to drive the reader, including a runtime
defence-in-depth check whose own docstring records that the pre-flight
validator normally catches the case. With no caller, that runtime gate guarded
nothing; the validator's own tests remain and are the real protection.

The remaining tests assert registry data rather than reader behaviour. They now
read the construct definitions directly, driven by the validator's kind-to-field
mapping rather than a copy of it, so a new member kind reaches them as soon as
production learns it.

The census had no representation for an outright deletion: every row was
assumed to have a current defining site, and five sites raised when it was
absent. Those now skip locator and span resolution for a row adjudicated
`delete` and whose path is genuinely gone. The guard is keyed on the
disposition rather than on mere absence, so an accidental deletion anywhere
else still reds.
