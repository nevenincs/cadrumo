---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S22'
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
     The S22 and 2026-07-07-iva-prorrata-complexity-plan placeholders are machine-filled by
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
     The Add the prorrata register CLI verb group (elect-especial, elect-general, list) writing GENERAL/ESPECIAL ProrrataRegisterEntry rows through ProrrataRegisterService.declare, and preserve sector_definitions across entry upsert and settlement write and ## Scope

- `src/aeat/entrypoints/cli/_prorrata_register_cli.py`
- `src/aeat/entrypoints/cli/_prorrata_register_payloads.py`
- `src/aeat/adapters/persistence/profile/prorrata_register.py`
- `src/aeat/application/modelo/_revision_persistence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the prorrata register CLI verb group (elect-especial, elect-general, list) writing GENERAL/ESPECIAL ProrrataRegisterEntry rows through ProrrataRegisterService.declare, and preserve sector_definitions across entry upsert and settlement write

## Scope

- `src/aeat/entrypoints/cli/_prorrata_register_cli.py`
- `src/aeat/entrypoints/cli/_prorrata_register_payloads.py`
- `src/aeat/adapters/persistence/profile/prorrata_register.py`
- `src/aeat/application/modelo/_revision_persistence.py`

## Description

- Add the `aeat app ledger prorrata` verb group mounted on the ledger app, mirroring the sibling `bienes-inversion` register CLI shape.
- Add `elect-especial` and `elect-general` verbs that build a `ProrrataRegisterEntry` (regime, provisional percentage, art. 105 provenance, optional `--sector`) and persist it through the existing `ProrrataRegisterService.declare` single write path.
- Restrict `--provenance` to the three operator-declarable art. 105 provenances (carried-prior default, aeat-autorizada, inicio-actividad) with the referenced ones requiring `--reference`; refuse the computed interrumpida-tres-ultimos provenance.
- Add a `list` verb that reads the register (entries plus declared sector definitions) back.
- Register two distinct typed schema keys (`ledger.prorrata.elect_especial`, `ledger.prorrata.elect_general`, `ledger.prorrata.list`) so each CLI leaf binds to its own OutputSchema for the conformance gate.
- Preserve `sector_definitions` across `ProrrataRegisterRepository.upsert_entry` and the settlement write-back in `_build_prorrata_settlement_write`, which previously dropped them by reconstructing the register from entries only.

## Outcome

The especial and sectores apportionment engines now have their first production writer: an operator can elect an `ESPECIAL` register entry from a real CLI flow so `_apply_especial_apportionment` becomes reachable, and the per-sector entries needed by `_apply_sector_apportionment` can be declared. A taxpayer who elects nothing is unaffected (fail-closed to the settlement auto-seed). Six real-behavior tests pass under `-n0` (CLI elect-especial/elect-general/sector-scoping/list verified by reading back through the `list` verb under the same session, provenance refusals, and a repository-level proof that `upsert_entry` preserves an operator-declared sector partition). Gates: ruff, ruff format, json-schema conformance, documented-command conformance, and registry collect-only all green; 35 prorrata roundtrip + revision-persistence tests unaffected.

## Notes

- The percentage the operator supplies is the art. 106.Uno regla-3.ª common-use percentage (= the art. 104.Dos general prorrata); its provenance defaults to carried-prior, the normal art. 105.Uno case. The election flips the regime axis; the percentage provenance is orthogonal.
- `declare-sector` (the SectorDefinition partition verb) is deferred to S23 to keep this commit self-consistent; the payload/service method it needs is added there.
- Pre-existing `ty` diagnostics at `_settled_prorrata_register_entry` (`**settlement_fields` Decimal unpack) are present identically on HEAD and mine — not introduced by this Step.
