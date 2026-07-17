---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
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
     The S03 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`

## Description

- Rewrite `_bundle_export.py` to consume the typed contracts and the operation-state journal.
- Split publication into `prepare_profile_export` (resolve profile, serialize under the profile storage session, stage a restrictive `0o600` sibling temp via an `O_EXCL` staging helper, fsync it, then write the durable `PREPARED` journal) and `publish_prepared_export` (capture any prior target, atomic replace, parent-directory fsync, then the post-publish `PROFILE_EXPORTED` event, restoring the target and clearing the journal if the event fails).
- Compose both under `export_profile_bundle`, holding one exclusive lock on the resolved target across the whole publication for same-target exclusion.
- Add `reconcile_prepared_exports`, which reports every `PREPARED` operation as prepared, removes its orphan staged temp, and clears its journal, never emitting a completion event.

## Outcome

The completion event fires only after a durable atomic replace; a crash between `PREPARED` and publication recovers honestly. The pre-existing event-failure compensation semantics are preserved. Committed in `a9251f5fa2`; proven green by the S05/S06 suites.

## Notes

The staged-temp helper deliberately does not reuse the one-shot `atomic_write_hardened_*` primitive because the durable `PREPARED` journal must land between the fsynced temp and the atomic replace; the helper stages and fsyncs only, leaving the replace to publish.
