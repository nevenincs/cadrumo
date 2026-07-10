---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S08'
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
     The S08 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The add the strict save/load/equality roundtrip test with every defaultable field populated non-default, using the real EphemeralMasterKeyProvider and SQLite engine (aeat-roundtrip-discipline) and ## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the strict save/load/equality roundtrip test with every defaultable field populated non-default, using the real EphemeralMasterKeyProvider and SQLite engine (aeat-roundtrip-discipline)

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`

## Description

- Add the strict save/load/equality roundtrip test in `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py` using the real `EphemeralMasterKeyProvider` and SQLite engine via `isolated_runtime_profile`.
- Populate every defaultable field across the register with a non-default value: a fully-settled carried entry (provisional percentage + provenance + source-observation identity + definitive percentage + both volume inputs) and a second AEAT-authorised especial entry carrying a sector id and authorisation reference.
- Assert `loaded == original` field-for-field, plus an upsert-replaces-by-key roundtrip.

## Outcome

The register survives the encrypted SQL cycle field-for-field; the upsert path replaces a key's entry in place. Real adapters throughout (no mocks), per the roundtrip discipline.

## Notes

None.
