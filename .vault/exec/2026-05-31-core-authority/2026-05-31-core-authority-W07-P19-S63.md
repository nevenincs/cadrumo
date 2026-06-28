---
tags:
  - '#exec'
  - '#core-authority'
step_id: S63
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W07.P19.S63 - domain.calculations passthrough caller 1 verified pre-migrated

## Outcome

Grep of all source files confirms: no production caller imports the 6 passthrough symbols
(RegistryCatalogues, RegistrySnapshot, RegistryValidator, build_snapshot, load_modelo_file,
load_registry_tree) via `from aeat.domain.calculations import <symbol>` or relative
equivalent. All callers already use `domain.calculations.registry.*` direct imports.
Migration was completed in prior campaign work. No code change required for this step.

The passthrough symbols are removed in S67.

## Commit

`33eac6da5` — shared with S64-S67 (single removal commit)

## Verification

`grep -rn "from.*domain\.calculations import [A-Z]" src/aeat/` returned 0 results
outside of domain/calculations/ itself.
