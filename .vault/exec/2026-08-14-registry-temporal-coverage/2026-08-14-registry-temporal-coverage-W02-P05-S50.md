---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e033f093c036eedae0b333d3f27b9615fe97d8ca6c7993c46bf9de9687ad3688'
step_id: 'S50'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Acquire Modelo 763 opening-period and design-era authority, then split the revision at the evidenced 2012, 2015, and 4T-2018 boundaries with period-aware selectors and complete deadlines without inventing unsupported windows or promoting authority grade.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/763/`
- `src/cadrumo/_data/registry/aeat/legal/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_763/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Replace the broad Modelo 763 revision with six period-aware revisions at the evidenced 2012, 2015, and 4T-2018 boundaries.
- Declare only the selected quarterly deadline windows through the registry's declared 2026 support horizon.
- Validate the loaded registry, revision selection, exact deadline bounds, applicability grade, and unsupported-period refusals.

## Outcome

Modelo 763 selects `2012-2t-3t` only for 2012 2T and 3T; `2013-2014`; `2015-2017`; `2018-1t-3t`; `2018-4t`; and `2019-y-siguientes` thereafter. All revisions retain `applicability` authority. The registry refuses 2011 and the unsupported 2012 1T and 4T periods instead of inferring a filing-capable revision.

## Notes

- The focused Modelo 763 registry test passed. The broader unsupported-design-span test exposed an unrelated Modelo 200 assertion whose expected error text no longer matches the current grade-boundary message.
- The shared worktree implementation commit also included an unrelated Modelo 182 census change; this record preserves the Modelo 763 provenance without modifying that peer-owned content.
