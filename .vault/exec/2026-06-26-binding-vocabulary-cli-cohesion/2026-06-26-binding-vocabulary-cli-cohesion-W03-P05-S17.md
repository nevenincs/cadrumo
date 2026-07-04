---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Prefix the oracle-tier Observation carriers where the bare stem collides (RentaWebOpenObservation, GroiObservation, AeatNifIvaObservation and ## Scope

- `OracleModeloObservation stays as the oracle-marked calc-tier anchor)`
- `one atomic relocation commit per renamed carrier tagged relocation:<symbol>`
- `each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before each commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py`
- `src/aeat/domain/calculations/registry/_groi_oracle.py`
- `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prefix the oracle-tier Observation carriers where the bare stem collides (RentaWebOpenObservation, GroiObservation, AeatNifIvaObservation

## Scope

- `OracleModeloObservation stays as the oracle-marked calc-tier anchor)`
- `one atomic relocation commit per renamed carrier tagged relocation:<symbol>`
- `each regenerating docs-scaffold + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before each commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py`
- `src/aeat/domain/calculations/registry/_groi_oracle.py`
- `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`

## Description

- Ground the oracle tier via RAG then grep-confirm the three carriers `RentaWebOpenObservation` (`_renta_web_open_oracle.py`), `GroiObservation` (`_groi_oracle.py`), and `AeatNifIvaObservation` (`_aeat_nif_iva_oracle.py`).
- Assert each already leads with its oracle-source domain word (`RentaWebOpen`, `Groi`, `Aeat`), matching the target names named in the Step, and that `OracleModeloObservation` remains the oracle-marked calc-tier anchor and is not renamed.
- Confirm `AeatNifIvaObservation` (oracle) is disambiguated from `SedeNifIvaCheckObservation` (sede tier) by its `Aeat` prefix, so the NIF-IVA concept no longer collides across tiers.

## Outcome

The oracle tier prefix discipline is satisfied with no rename needed: the three carriers already carry the exact discriminating names the Step lists as targets, and `OracleModeloObservation` stays as the anchor. No two oracle-tier `*Observation` carriers collide by class name. Verified no-shift: `pytest --collect-only -q` clean and the oracle carrier tests green (`test_groi_oracle.py`, `test_renta_web_open_oracle.py`).

## Notes

Deliberate no-op-rename closure: the Step's parenthetical lists the carriers by their already-correct target names. All three oracle modules were clean of peer WIP. No production code was modified in this Step.
