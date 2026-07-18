---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S20'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence and ## Scope

- `dev/docs/tests`
- `docs/locales` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence

## Scope

- `dev/docs/tests`
- `docs/locales`

## Description

- Run the full `docs-check` lane (docs pytest lane under the docs marker, plus doc8 and interrogate) at HEAD against the real translated content.
- Run the per-language nitpicky warnings-as-errors user-scope build matrix for the first time against real translations (the earlier green was English fallback).
- Run the localization gate module and collect-only on the docs test tree.
- Build the Spanish site end to end as a human-eyeball artifact.

## Outcome

`docs-check`: 148 passed, 3 failed in 32m52s. Triage of the three failures:
- Noncanonical docs build root gate: an infra defect of this campaign - two localization test helpers pinned their storage root under the repository build tree, and the new build-driver help text embedded a literal build path that the gate's regex mis-read. Fixed by moving the test storage to an OS temp dir and rewording the help text (this campaign's own commit).
- Spanish and Catalan nitpicky user-scope builds pass clean. The Hungarian nitpicky build fails on two broken glossary cross-references in the file-at-aeat page: the Hungarian translation accented the invariant AEAT domain stems inside term roles, so the term targets no longer resolve. A translation-markup defect routed to the coordinator for a translator fix.
- Em-dash prose ratchet: two em dashes in the English import-export-and-evidence reference page, introduced by an unrelated docs commit outside this campaign, exceed the baseline. Routed to the coordinator; it is not a localization defect and correcting the English source would require a catalogue reconciliation.

Localization completeness (es/ca/hu) and parity gates all pass; the three completeness gates confirm 2994/2994 entries per language with zero untranslated and zero fuzzy. Collect-only on the docs test tree is clean. The Spanish end-to-end build succeeds; the eyeball artifact renders at the canonical HTML output root (`lang="es"`).

## Notes

This step is NOT closed: the matrix is not fully green. Two reds remain, both owned outside this executor - the Hungarian term-target defect (translator fix) and the unrelated English em-dash ratchet (source/reconciliation decision). The campaign's own infra defect is fixed and committed. The step closes once both routed reds land and the matrix reruns green.
