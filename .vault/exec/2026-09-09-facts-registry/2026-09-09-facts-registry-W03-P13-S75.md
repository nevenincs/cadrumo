---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:937a916c2b82b748a2384ee2d3f7e2752400e364c97973c745cd30b1620f1df3'
step_id: 'S75'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete retired legal-parameter provider implementations after governed facts replace every live resolver and consumer path

## Scope

- `dev/registry/compiler/legal_parameters.py and dev/registry/tests/test_legal_parameter_provider.py and src/cadrumo/domain and src/cadrumo/application`

## Changes

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

- `A` `.vault/reference/2026-09-11-facts-registry-reference.md`
- `M` `dev/audit/tests/test_legal_excerpt_vintage_screen.py`
- `M` `dev/registry/compiler/_loader_internals.py`
- `M` `dev/registry/compiler/fact_validation.py`
- `M` `dev/registry/compiler/loader.py`
- `M` `dev/registry/compiler/validator.py`
- `M` `dev/registry/tests/test_loader_directory_mode.py`
- `M` `dev/registry/tests/test_modelo_100_2024_profile_surface.py`
- `R` `dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` -> `dev/registry/tests/test_retired_fact_provider_gate.py`
- `M` `src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-95.html`
- `M` `src/cadrumo/core/tipos_actividad.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_exports.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_references.py`
- `M` `src/cadrumo/domain/transactions/tipo_actividad_partitions.py`
- `verify:` `uv run pytest -q dev/registry/tests/test_loader_directory_mode.py::test_catalogue_rejects_the_retired_global_parameters_section dev/registry/tests/test_retired_fact_provider_gate.py` -> `pass`

## Notes

`dev/registry/tests/test_modelo_100_2024_profile_surface.py` remains blocked by the pre-existing expired `ley-35-2006:art-23-2021` legal window for the 2024 revision.
