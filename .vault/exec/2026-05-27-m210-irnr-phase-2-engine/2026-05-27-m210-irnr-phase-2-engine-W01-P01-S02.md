---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:439c514c50c5c50575a7e10b4c96e6a73ad55959b27f6d2bea586ee119c79a95'
step_id: 'S02'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# author the code-to-`TipoRentaIrnr` projection plus a registry-build parity gate that refuses at build any declared code with no mapping and any unmapped code

## Scope

- `src/aeat/core/_irnr.py`

## Description

- Author the code-to-`TipoRentaIrnr` projection in core `_irnr.py`: a `TipoRentaGroundingTier` enum, an `OfficialTipoRentaCode` record carrying `(code, concept, rate_legal_ref, grounding_tier)`, the 26-entry `OFFICIAL_M210_TIPO_RENTA_CODES` tuple, the derived `M210_TIPO_RENTA_CODE_PROJECTION` mapping, and `project_m210_tipo_renta_code`.
- Add a registry-build parity gate `validate_m210_tipo_renta_code_projection_parity` (in `_validate_revision_rules.py`) wired into `RegistryValidator._validate_modelo`, refusing at build in BOTH directions: a registry-declared code with no core projection, and a core-projected code the registry does not declare.
- Ground the per-code rate concept: 17 `rate_verified` (art 25.1.b pension → 18; art 25.1.f dividend/interest/ganancia; art 13.1.h inmobiliaria → 02) and 9 `residual` (art 25.1.a general → 01/03/14/15/16/17/21/22/35), each carrying a typed tier so a later full-art-25 fetch revealing a special rate is a correction, not a contradiction.

## Outcome

The core code axis and the registry-declared code set are bound by a bidirectional build-time parity gate proven to fire in both directions (injected-divergence tests). The grounding is registry-resident (S01) and validated by the canonical registry legal-grounding gate — a stronger anti-fabrication posture than moving grounding into core. Landed in commit `0ce6abfafc` (Slice A S01+S02); 52 tests pass (16 core + 4 gate + 18 catalogue regression + 14 test_irnr); ruff + ty clean.

## Notes

Representation was finalised as (B) registry-resident grounding after an A↔B design cycle (coordinator churn crossing checkpoints in flight); both shapes were built green each time. The final (B) keeps the code SET as a core StrEnum-style projection while the GROUNDING lives in the registry where the canonical gate validates it.
