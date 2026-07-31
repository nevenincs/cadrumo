---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:ce2334041de1c545544dd2f088f7d722dc19d4c8f658ea354a089da0a1d3d616'
step_id: 'S388'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# author keyed tipo-renta parameter `m210-tipo-gravamen-2025`: `general` 0.24 under TRLIRNR Art 25.1.a, `ue_residente` 0.19 under Art 25.1.a's EU/EEE reduced general-rate branch, `interest` 0.19 under unconditional Art 25.1.f.2, `ganancia_patrimonial` 0.19 under Art 25.1.f.3, and `inmobiliaria` 0.24 under Art 25.1.a

## Scope

- `current registry handles `pension` through separate Art 25.1.b bracket table `m210-pension-tarifa-2025`
- `not a sentinel`
- `extend _validate_revision_rules.py to accept the new string-keyed bracket_table shape`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0001-m210-tipo-gravamen-2025.toml + src/aeat/_data/registry/aeat/modelos/210/revisions/2025/parameters/0004-m210-pension-tarifa-2025.toml + src/aeat/domain/calculations/registry/_validate_revision_rules.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `8dbd72ee8e` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
