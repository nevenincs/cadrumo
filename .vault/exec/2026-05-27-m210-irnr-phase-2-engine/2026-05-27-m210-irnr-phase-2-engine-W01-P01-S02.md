---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S02'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m210-irnr-phase-2-engine with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-05-27-m210-irnr-phase-2-engine-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The author the code-to-`TipoRentaIrnr` projection plus a registry-build parity gate that refuses at build any declared code with no mapping and any unmapped code and ## Scope

- `src/aeat/core/_irnr.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
