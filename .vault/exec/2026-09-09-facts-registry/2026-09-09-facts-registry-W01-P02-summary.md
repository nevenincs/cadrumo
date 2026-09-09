---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8ccaa4ff3000e9b7ba7bd264218676fd440786bdb1e16be907b329b3305bab87'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: filename and frontmatter, scaffolded by
     `vaultspec-core vault add exec`; never hand-edit. Add no frontmatter
     fields. Wiki-links belong in `related:` only, never in the body.

     Rolls up every Step Record (S##) of one Phase. -->

# `facts-registry` `W01.P02` summary

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `M` `src/cadrumo/domain/calculations/registry/_validation_memoization.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/validation.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_catalogue.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_authority_enrollment.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`

<!-- MECHANICAL LOG. The union of paths touched across the Phase, deduplicated,
     one line per path, same grammar as a Step Record:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     No prose. Do not restate the Step Records; this is their union, not a
     narrative of them.

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception (see the Step Record
     template). Omit it otherwise. -->
