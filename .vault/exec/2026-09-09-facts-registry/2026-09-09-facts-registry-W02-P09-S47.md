---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:df477babd015d3aa448cf302484eaea8f54d8c332a85c890229852e3f74f2790'
step_id: 'S47'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Run both dead-code audits at the Wave 2 handoff

## Scope

- `dev/audit/dead_code.py and dev/audit/unreachable_code.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/convenio.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/modelo_projections.py`
- `M` `src/cadrumo/domain/categories/registry.py`
- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P09-S47.md`
- `verify:` `just audit-dead-code` -> `pass`
- `verify:` `just audit-unreachable-code` -> `fail`

## Notes

The final exact reachability search reports no Wave 2 provider finding and zero unreachable shipped modules. The repository-wide command still reports 480 unused symbols outside this campaign.

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
