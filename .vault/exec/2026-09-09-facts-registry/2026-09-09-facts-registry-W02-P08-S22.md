---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4d0ac1b56e58b5b32947631a8952f69061c36b39957f668ece820e024d6801f0'
step_id: 'S22'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Project modelo-owned facts without moving parameter files

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

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

- `A` `src/cadrumo/domain/calculations/registry/facts/modelo_projections.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P08-S22.md`
- `verify:` `uv run pytest -q src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/modelo_projections.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py src/cadrumo/domain/calculations/registry/authority.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/domain/calculations/registry/facts/modelo_projections.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/tests/test_modelo_projections.py src/cadrumo/domain/calculations/registry/authority.py` -> `pass`
- `verify:` `uv run python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; a=bundled_authority(); print(sorted(k for k in a.catalogues.facts.facts if k.startswith(('declarations.m347','renta.maternity'))))"` -> `pass`
