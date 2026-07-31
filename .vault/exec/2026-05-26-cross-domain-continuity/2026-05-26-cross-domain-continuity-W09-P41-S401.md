---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:c3c9c216becad1a99c267f0e2aebb28b01d5070aea70c65a6acd48af33a41c88'
step_id: 'S401'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# patch M210 rate resolution to proceed to Convenio dispatch when a treaty override is available, with currentized `interest` baseline at 0.19 under unconditional TRLIRNR Art 25.1.f.2 and pension delegated to the Art 25.1.b tariff table

## Scope

- `revise S389c synthetic-snapshot test workarounds to exercise real Convenio-override behavior`
- `preserves anti-tautology mutation pattern`
- `unblocks S400 formula-authoring which consumes the helper output`
- `src/aeat/application/modelo/_m210_rate.py + src/aeat/application/modelo/_verification_actions.py + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0001-m210-tipo-gravamen-2025.toml + src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `bc13eca50d` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
