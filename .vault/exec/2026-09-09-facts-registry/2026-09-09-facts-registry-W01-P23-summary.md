---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a118007bfb1971ab78bd243d5c853cf8a4688aa0b05e81baba18330d479d33d3'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: filename and frontmatter, scaffolded by
     `vaultspec-core vault add exec`; never hand-edit. Add no frontmatter
     fields. Wiki-links belong in `related:` only, never in the body.

     Rolls up every Step Record (S##) of one Phase. -->

# `facts-registry` `W01.P23` summary

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/providers.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/tests/test_providers.py`
- `A` `src/cadrumo/domain/calculations/registry/facts/tests/test_resolution.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `verify:` `just check-types` -> `fail`
- `verify:` `just audit-dead-code` -> `pass`
- `verify:` `just audit-unreachable-code` -> `fail`

## Notes

The failed commands contain no remaining Wave 1 facts-registry finding. Type checking reports 50 existing `ty` diagnostics outside the campaign; reachability reports 31 unreachable modules and 787 unused symbols outside the campaign.

<!-- MECHANICAL LOG. The union of paths touched across the Phase, deduplicated,
     one line per path, same grammar as a Step Record:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     No prose. Do not restate the Step Records; this is their union, not a
     narrative of them.

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception (see the Step Record
     template). Omit it otherwise. -->
