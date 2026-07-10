---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S23'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-07-07-iva-prorrata-complexity-plan placeholders are machine-filled by
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
     The Add the declare-sector CLI verb writing a SectorDefinition partition (sector id, art-9.1.c letra, member activity codes) through a new ProrrataRegisterService.declare_sector over an entries-preserving repository upsert and ## Scope

- `src/aeat/entrypoints/cli/_prorrata_register_cli.py`
- `src/aeat/application/prorrata_register/__init__.py`
- `src/aeat/adapters/persistence/profile/prorrata_register.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the declare-sector CLI verb writing a SectorDefinition partition (sector id, art-9.1.c letra, member activity codes) through a new ProrrataRegisterService.declare_sector over an entries-preserving repository upsert

## Scope

- `src/aeat/entrypoints/cli/_prorrata_register_cli.py`
- `src/aeat/application/prorrata_register/__init__.py`
- `src/aeat/adapters/persistence/profile/prorrata_register.py`

## Description

- Add the `declare-sector` verb to the `aeat app ledger prorrata` group: it builds a `SectorDefinition` (sector id, art. 9.1.c letra, repeatable member activity codes) and persists it through a new service method.
- Add `ProrrataRegisterService.declare_sector`, delegating to a new `ProrrataRegisterRepository.upsert_sector_definition` that replaces-or-adds the definition by `sector_id` while preserving the existing per-ejercicio entries.
- Register the `ledger.prorrata.declare_sector` typed schema for the verb's envelope.

## Outcome

An operator can now declare the differentiated-sector partition from a real CLI flow, which sets `register.is_sectorized` true and makes the arts. 9.1.c / 101 per-sector apportionment (`_apply_sector_apportionment`) reachable. Four real-behavior tests pass under `-n0` (CLI declare-sector verified by reading back through `list`, the missing-activity-code refusal, and a repository-level proof that `upsert_sector_definition` preserves existing entries). Gates: ruff, ruff format, ty, and json-schema conformance all green; the full prorrata register CLI + service slice is 169 passed.

## Notes

- The sector partition is ejercicio-agnostic (the art. 9.1.c judgment); per-sector provisional percentages are declared per ejercicio with `elect-especial`/`elect-general --sector` (S22), so the two verbs compose over the one register.
- Fail-closed preserved: an empty `sector_definitions` tuple keeps the register whole-entity, so a non-declaring taxpayer is unaffected.
