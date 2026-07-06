---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S02'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The declare the strict ProrrataRegisterEntry pydantic model (ejercicio, regime, sector axis, provisional percentage + provenance + optional authorisation reference, definitive percentage + volume inputs once settled, source-observation identity) mirroring domain/bienes_inversion shapes and ## Scope

- `src/aeat/domain/prorrata_register/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# declare the strict ProrrataRegisterEntry pydantic model (ejercicio, regime, sector axis, provisional percentage + provenance + optional authorisation reference, definitive percentage + volume inputs once settled, source-observation identity) mirroring domain/bienes_inversion shapes

## Scope

- `src/aeat/domain/prorrata_register/__init__.py`

## Description

- Declare the strict frozen `ProrrataRegisterEntry` pydantic model in `src/aeat/domain/prorrata_register/__init__.py`, mirroring the `domain.bienes_inversion` record shape.
- Carry the full per-ejercicio slot set from birth: `ejercicio`, `regime`, `sector_id`, provisional (`provisional_percentage` + `provisional_provenance` + `authorisation_reference`), settlement (`definitive_percentage` + `definitive_volume_con_derecho` + `definitive_volume_sin_derecho`), `source_observation_ref`, and `schema_version`.
- Enforce the field-coupling invariants in one model validator: provisional percentage and provenance travel together; `authorisation_reference` is required iff the provenance is AEAT-authorised or inicio-actividad and forbidden otherwise; the three settlement fields travel together; `source_observation_ref` is permitted only for a carried entry.
- Add the `ProrrataRegisterError` / `ProrrataRegisterValidationError` pair and register both in the domain error-code shard `src/aeat/core/errors/registry/_domain_part3.py` with locale message keys.

## Outcome

Strict model validates a fully-populated carried entry and rejects every coupling violation. The two error codes carry translated messages in all four locales (added through the locale CLI). `ruff` / `ruff format` / `ty` clean; error-registry gate green.

## Notes

The provenance and regime enums are consumed from `aeat.core` (their canonical home); the domain package does not re-export them. Settlement, seed, and override fields exist from birth but are optional here — they are populated by the seed (W02) and settlement (W04) waves so those land without a schema migration.
