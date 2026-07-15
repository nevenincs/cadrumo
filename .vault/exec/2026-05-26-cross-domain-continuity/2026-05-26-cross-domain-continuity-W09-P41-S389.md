---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S389'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# author m210-convenio-rates parameter keyed on country tipo_renta with Phase 1 seed rows for ES-UK ES-MA ES-AR per the testimonial personas

## Scope

- `wire dispatch in formula composition so profile.convenio_doble_imposicion_country triggers treaty-rate lookup replacing the TRLIRNR baseline`
- `emit BLOCKING ModeloVerificationFinding when country is set but no rate row exists per ADR D2.4`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/records/parameters.toml + src/aeat/application/modelo/_actions.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `d0b1cf0cbf` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
