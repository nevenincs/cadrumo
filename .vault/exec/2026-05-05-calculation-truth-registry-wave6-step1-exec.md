---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `wave6` `step1`

Modelo 180 authority audit.

- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Created: `.vault/exec/2026-05-05-calculation-truth-registry-wave6-step1.md`

## Description

Repository scans enumerated Modelo 180 surfaces before continuing rebuild work.
The scan did not find surviving `src/aeat/domain/rulesets`,
`src/aeat/domain/casillas`, generated-export, hydrate, or standalone
filing-builder authority for Modelo 180.

Retained Modelo 180 surfaces are registry/corpus definitions, registry-backed
calculation/export/relation tests, Sede filed-data behaviour tests, CLI registry
reporting, and endpoint-only portal metadata linked from registry application
links. Numeric false positives outside Modelo 180 were ignored.

## Tests

- `rg -n "180|modelo[-_ ]?180|Modelo 180" src tests -g "*.py" | rg -v "calculations/registry|portals|test_declarations|test_filing|test_export|test_workbook|test_relation|test_formula|test_committed"`
- `fd "180|modelo_180|modelo-180" src tests registry corpus .vault`
- `rg -n "180|modelo[-_ ]?180|Modelo 180" src/aeat/domain/rulesets src/aeat/domain/casillas src/aeat/domain/modelos src/aeat/application/filing src/aeat/entrypoints tests/fixtures -g "*.py" -g "*.json" -g "*.toml"`
