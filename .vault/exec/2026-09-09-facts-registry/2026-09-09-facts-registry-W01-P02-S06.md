---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:45867e0a365b7c1bd343f270dc241eab6fbc07c249080f602ac2c0ca20e6ad0d'
step_id: 'S06'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Enroll facts in fingerprints authority identity memoisation validation and resets

## Scope

- `src/cadrumo/domain/calculations/registry`

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

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `M` `src/cadrumo/domain/calculations/registry/_validation_memoization.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/validation.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P02-S06.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py -q` -> `pass`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py::test_validated_authority_exposes_the_attached_fact_catalogue -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/domain/calculations/registry/_validate.py src/cadrumo/domain/calculations/registry/_validation_memoization.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/calculations/registry/authority.py src/cadrumo/domain/calculations/registry/_validate.py src/cadrumo/domain/calculations/registry/_validation_memoization.py src/cadrumo/domain/calculations/registry/facts/providers.py src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py` -> `pass`
