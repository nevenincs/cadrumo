---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:37dda96a197069b5cfdfa856df147a609cc71c488b4a95854279943de0f18bda'
step_id: 'S46'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Run canonical strict production type checking at the Wave 2 handoff

## Scope

- `justfile check-types and dev/quality/types.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/convenio.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_rate_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_iva_recargo_provider.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py`
- `M` `src/cadrumo/domain/categories/tests/test_fact_provider.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_fact_provider.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P09-S46.md`
- `verify:` `just check-types` -> `fail`

## Notes

Wave 2's 12 type diagnostics were fixed. The final boundary run reports diagnostics outside the facts-registry campaign while concurrent repository work is active; no Wave 2 provider path remains in the detailed result.

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
