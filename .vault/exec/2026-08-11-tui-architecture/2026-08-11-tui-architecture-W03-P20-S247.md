---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:15601440b01178f0209b83bb6f2b07ea4b7260b75c4eb608b232cf5717fcd64b'
step_id: 'S247'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Privatize the validate implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/validate.py`

## Changes

R src/cadrumo/domain/calculations/registry/validate.py -> _validate.py
R src/cadrumo/application/modelo/tests/test_modelo_303_verification_source_snapshot_resolution.py -> domain/calculations/registry/tests/
M 24 registry modules and tests repointed onto the relative private path
M dev/quality/registry_facade_family_census.v1.json
D docs/api/cadrumo.domain.calculations.registry.validate.rst
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

The row asks for privatisation after eliminating every external consumer. There
was exactly one: a test in the application tree constructing `RegistryValidator`
to assert a registry validation refusal. Every import in that file resolved to
the registry or to core, so it was misplaced rather than a genuine cross-package
contract. It moved to the registry's own tests, which eliminates the reach and
puts the file at its owning boundary; deleting it would have dropped a real
refusal assertion.

The public-API gate caught the failure mode this rename invites: repointing
consumers while preserving their absolute import form turns each one into an
absolute import of a private module. Twenty-four files now name the module
relatively.

The census row was re-adjudicated onto the private path and refreshed, and the
row left the fixed-point gate's outstanding table because its terminal state is
now reached.
