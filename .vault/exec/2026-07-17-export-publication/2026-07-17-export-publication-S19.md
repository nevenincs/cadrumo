---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S19'
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
     The S19 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Classify a journal that vanished mid-scan as a skip rather than a failure so a peer process completing normally cannot make the sweep tell an operator that an unencrypted file may remain, gated on a test removing a journal between scan and reconcile and ## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Classify a journal that vanished mid-scan as a skip rather than a failure so a peer process completing normally cannot make the sweep tell an operator that an unencrypted file may remain, gated on a test removing a journal between scan and reconcile

## Scope

- `src/cadrumo/application/user_profile/_bundle_export_operation.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Classify a journal that vanished between the directory walk and the load as a skip,
  ahead of the general unreadable-journal handler it was being caught by.
- Add a proof that reconciliation reports no failure for that state while still
  reconciling the healthy operation beside it.

## Outcome

A peer export completing normally no longer looks like a fault. Because the
not-found error subclasses the general journal error, the isolating handler was
catching it and producing a failure row -- telling the operator an unencrypted file may
remain when in fact a peer simply succeeded and cleaned up after itself. That is the
kind of false alarm that trains an operator to ignore the warning that matters.

The classification now matches the lock-held case: healthy concurrent work is a skip,
in neither the reconciled nor the failed bucket.

## Notes

The first version of this proof was vacuous and was caught by its own negative control.
It deleted the journal before the sweep began, so the directory walk never saw it and
the race was never exercised; it passed with the fix removed. It was rewritten around a
repository subclass that pins only the walk, so the real scan classification, the real
load, and the real filesystem all run and the journal genuinely is absent. The rewritten
proof fails with the classification removed, reporting the not-found failure row.

That miss is worth recording plainly: a passing test written for a race is the easiest
kind of false gate to ship, and only the removed-fix control surfaced it.
