---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S400'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# author 4 M210 formula TOMLs implementing the TRLIRNR Art 24 base + Art 25 rate composition chain (m210-base-imponible-2025, m210-tipo-gravamen-2025-resolve, m210-cuota-integra-2025, m210-cuota-diferencial-2025) and flip the 4 casillas (base_imponible, tipo_gravamen, cuota_integra, cuota_diferencial) from input_kind=manual to input_kind=computed with their formula references wired

## Scope

- `the formula authoring + casilla flip MUST co-land in one atomic commit because partial state would break registry-load`
- `tipo_gravamen formula reads the m210-tipo-gravamen-2025 baseline parameter and the m210-convenio-rates override parameter via the _resolve_m210_rate dispatch helper per ADR D2.4 override-replaces-baseline contract`
- `Path-B refusal stub stays active until S391 flag flip`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/formulas/ + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `699044acfe` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
