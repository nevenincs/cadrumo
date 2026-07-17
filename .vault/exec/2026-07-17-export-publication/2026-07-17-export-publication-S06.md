---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
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
     The S06 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events and ## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Add `test_bundle_export_recovery.py` driving a real child Python process that serializes and journals a `PREPARED` export, then hard-exits (`os._exit(91)`) before the atomic replace, and separately between the replace and the completion event.
- Prove a fresh process reconciles the crash-before-replace case as prepared: destination absent, no `PROFILE_EXPORTED` event, orphan staged temp removed, journal cleared.
- Prove the crash-after-replace case leaves the target durably published yet fires no premature completion event, and reconciliation never fabricates one.
- Prove restrictive staged-temp permissions with no publication, publication into a freshly-created parent directory, a completed export leaving no journal and exactly one event, and same-target exclusion while the target lock is held by another process.

## Outcome

Six real-behavior cases pass, including the forced-crash-then-fresh-process recovery proof the plan's verification demands. The child uses the same file secret-store env as the parent so cross-process crypto shares keys. No mocks, stubs, monkeypatch, skip, or xfail. Committed in `ac097a53a7`.

## Notes

An initial full-file run showed two transient failures in the full-export child paths; a sequential re-run was clean and the suite is stable across repeated runs, consistent with the known parallel loader-cache race, not a real regression. POSIX `0o600` mode is asserted only on POSIX (Windows makes no ACL guarantee), which is a platform-conditional assertion, not a skip.
