---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S234'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S234 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The R7-ANNA-D3 fix iva.regime defaulting to GENERAL for entity_type=natural_person profiles without actividad_economica and ## Scope

- `field should remain unset or marked no_aplica until user opts in`
- `misleading for salaried-only profiles`
- `src/aeat/application/wizard/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-ANNA-D3 fix iva.regime defaulting to GENERAL for entity_type=natural_person profiles without actividad_economica

## Scope

- `field should remain unset or marked no_aplica until user opts in`
- `misleading for salaried-only profiles`
- `src/aeat/application/wizard/`

## Description

- Gate the `iva-regime` wizard question to legal entities, attribution entities, and natural persons that declare `actividad_economica`.
- Centralise the conditional IVA-regime requirement in profile completeness policy.
- Let profile validation and key-readiness projection omit `iva.regime` for natural-person profiles without economic-activity income.
- Mark non-enrolled natural-person runtime projection as `NO_APLICA` instead of silently defaulting to `GENERAL`.
- Keep explicit IVA declarations for pure-landlord profiles and keep `GENERAL` defaults for legal entities, attribution entities, and economic-activity natural persons.
- Derive operator-facing `--iva-regime` choices from the wizard question choices so the internal `NO_APLICA` sentinel is not exposed.

## Outcome

- Closed W09.P45.S234. A natural-person profile declaring `capital_inmobiliario` can now be created non-interactively without `--activity` or `--iva-regime`; the stored profile has no invented `activities.description` and no invented `iva.regime`.
- `projection_for_taxpayer` and `load_active_taxpayer_profile` now project that profile as `IVARegime.NO_APLICA`, while an explicit `--iva-regime EXENTO` still projects and persists as `EXENTO`.
- Legal-entity, attribution-entity, and natural-person economic-activity paths still receive the wizard `GENERAL` default and remain covered by validation/readiness gates.
- Verification passed: focused S234 CLI integration, full taxpayer-type CLI integration file, user-profile projection/completeness tests, wizard setup/status tests, Modelo applicability tests, setup/taxpayer-model focused tests, IVA choice/exempt tests, and touched-file ruff.

## Notes

- First code-review pass found a high issue: runtime taxpayer projection still defaulted absent `iva.regime` to `GENERAL`. The follow-up patch introduced `IVARegime.NO_APLICA`, added projection/status regression coverage, and kept the sentinel internal to projection rather than an operator wizard choice.
- A second reviewer was spawned but did not return before commit pressure; it was closed to free the agent slot. Local review after the high-finding fix found no remaining S234 blocker.
