---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S06'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace crossperiod-filing-deadlock with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Add the non_official_local_chain_advisory facet on CrossPeriodDependencyEvidence and the has_non_official_local_chain_advisory verdict property and ## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the non_official_local_chain_advisory facet on CrossPeriodDependencyEvidence and the has_non_official_local_chain_advisory verdict property

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the `non_official_local_chain_advisory: bool = False` field on `CrossPeriodDependencyEvidence`, mirroring the existing `unstamped_revision_advisory` facet pattern.
- Add the `has_non_official_local_chain_advisory` aggregate property on `CrossPeriodCleanStateVerdict`.

## Outcome

Landed in commit `84add274d`. The typed marker yields a clean (advisory-only) evidence row idiomatically, following the `NoPriorObligationProvenance` facet shape.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
