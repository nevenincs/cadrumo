---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-crash-window with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Author the hard-delete crash-injection test proving readiness refuses a half-removed bucket and the repair detects partial-directory removal and ## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the hard-delete crash-injection test proving readiness refuses a half-removed bucket and the repair detects partial-directory removal

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`

## Description

Authored the hard-delete crash-injection test: prove a soft tombstone leaves the bucket off every live surface but resolvable by id for repair, and that a partial directory with a torn manifest is detected by the repair-integrity scan and idempotently reclaimed by the removal verb.

## Outcome

Two tests pass, pinning tombstone off-surface behaviour plus partial-directory detection and idempotent removal.

## Notes

None.
