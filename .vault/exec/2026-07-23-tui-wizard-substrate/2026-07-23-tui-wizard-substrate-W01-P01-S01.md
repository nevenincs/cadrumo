---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S01'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Declare the substrate closed value sets (widget kinds including repeating-group and compare-select, page status including stale and deferred, flow mode, checkpoint availability) as StrEnums and ## Scope

- `src/cadrumo/core/flows.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the substrate closed value sets (widget kinds including repeating-group and compare-select, page status including stale and deferred, flow mode, checkpoint availability) as StrEnums

## Scope

- `src/cadrumo/core/flows.py`

## Description

- Declare FlowWidgetKind (seven carried tokens plus compare_select), PageStatus (unanswered/answered/invalid/stale/deferred), FlowMode, CheckpointAvailability, CopyRefKind, and FlowIntentKind as core StrEnums with the DEFER_TOKEN and instance-separator constants.
- Land in commit 91c5e51afc.

## Outcome

Closed value sets live in core per the core-authority discipline; consumers route on members, never raw strings. Verified by the pinned enum suite (30e5884352) and ruff clean.

## Notes

FlowIntentKind is a forward contract for the full-screen frontend; flagged by review as unconsumed at this checkpoint (L1, accepted).
