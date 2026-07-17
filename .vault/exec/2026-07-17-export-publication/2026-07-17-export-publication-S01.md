---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
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
     The S01 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export_contracts.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_contracts.py`

## Description

- Create `_bundle_export_contracts.py` owning the closed value sets and typed envelopes for the sole export service.
- Declare `ProfileBundleExportPurpose` (portable transfer, subject access) and `ProfileBundleExportTransport` (cleartext-local, passphrase-encrypted) as core-style StrEnums.
- Move `ProfileBundleExportRequest` and `ProfileBundleExportResult` out of the service module into the contract surface.
- Add a `ProfileBundleExportTarget` model whose computed `identity` resolves the destination to a canonical absolute path for same-target locking and operation-state keying.
- Add `bundle_data_categories`, deriving categories from the serialized `UserProfilePortableExport` field names and the coverage manifest's carried registry namespaces, never a static list.
- Keep the sealed recovery archive out of this surface entirely.

## Outcome

Contracts module compiles and lints clean. `export_profile_bundle` and both purposes now share one typed contract source; category derivation traces to real schema fields plus carried namespaces. Committed in `a9251f5fa2` with steps S02-S04.

## Notes

Sealed recovery archive semantics deliberately excluded per the ADR; this surface is portable-export only.
