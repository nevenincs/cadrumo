---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S09'
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
     The S09 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Attach cross-period dependency legal grounding (LGT art 119/120, LIVA art 99 for compensacion, RGAT art 9 for activity-start) to every cross-period and iva-wallet finding and ## Scope

- `src/aeat/application/modelo/_verification_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Attach cross-period dependency legal grounding (LGT art 119/120, LIVA art 99 for compensacion, RGAT art 9 for activity-start) to every cross-period and iva-wallet finding

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Add the legal-grounding constants `_CROSS_PERIOD_DEPENDENCY_LEGAL_REFS` (LGT art-119/art-120), `_IVA_COMPENSATION_CARRY_LEGAL_REF` (LIVA art-99), and `_CROSS_PERIOD_ACTIVITY_START_LEGAL_REFS` (RGAT RD-1065-2007 art-9).
- Add `_cross_period_dependency_legal_refs(origin_ids)` that appends LIVA art-99 when an origin id names a compensacion balance.
- Attach `legal_refs` to the blocking cross-period finding, the unstamped-revision and operator-declared-suppression advisories, the missing-activity-start finding, and the two iva-wallet findings.

## Outcome

Landed in commit `84add274d`. Every cross-period finding now surfaces its legal basis (`aeat-calculation-grounding`). Refs are catalogue ids, not invented prose.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
