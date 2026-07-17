---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata and ## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export.py`

## Description

- Add `test_bundle_export.py` proving both purposes resolve through one `export_profile_bundle` service and one bundle schema against real secure storage.
- Prove data categories derive from the serialized bundle fields and, via a pure-logic case over a real coverage manifest, from carried registry namespaces.
- Prove distinct purpose metadata survives the shared service (two `PROFILE_EXPORTED` events with distinct purposes, identical categories and schema).
- Retain the encrypted-transport roundtrip and the real-trigger event-failure compensation proofs from the superseded authority test.

## Outcome

Six real-behavior cases pass with real profile creation, real secure SQL storage, and a real SQLite constraint trigger for the compensation case. No mocks, stubs, or tautologies. Committed in `ac097a53a7`.

## Notes

Supersedes and removes the prior `test_bundle_export_authority.py`; all its real assertions were folded in, so no coverage was lost.
