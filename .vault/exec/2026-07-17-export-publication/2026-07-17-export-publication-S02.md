---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
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
     The S02 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Persist non-secret profile export operation states atomically outside the target artifact and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Persist non-secret profile export operation states atomically outside the target artifact

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`

## Description

- Create `_bundle_export_operation.py` holding the durable, credential-free operation state for one publication.
- Declare `ProfileBundleExportOperationStatus` (prepared, completed) and the `ProfileBundleExportOperation` model carrying the resolved target identity, purpose, transport, schema version, derived categories, and UTC-validated timestamps, but no bundle bytes, passphrase, or raw tax id.
- Add `derive_export_operation_id`, a clock-free sha256 over profile, target identity, and purpose so a retried export to the same target reconciles to one journal.
- Add `ProfileBundleExportJournalRepository` persisting atomic per-file journals under `<storage-root>/profile-export-operations`, outside bucket directories, with restrictive `0700`/`0600` modes, link-like-path refusal, and `save`/`load`/`delete`/`list`/`prepared` accessors.
- Register the three journal error classes in the application error-code registry.

## Outcome

Operation-state store mirrors the proven reset-operations journal shape while staying a separate surface. Error codes bind; the package imports clean. Committed in `a9251f5fa2`.

## Notes

Journal directory name `profile-export-operations` is distinct from the reset journal and from any sealed-archive location; no reset-owned files were touched.
