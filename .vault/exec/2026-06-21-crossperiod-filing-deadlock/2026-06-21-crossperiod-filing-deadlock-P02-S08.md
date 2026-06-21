---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S08'
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
     The S08 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Emit the non-blocking WARNING non-official-local-chain advisory finding from the cross-period clean-state findings builder and ## Scope

- `src/aeat/application/modelo/_verification_actions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit the non-blocking WARNING non-official-local-chain advisory finding from the cross-period clean-state findings builder

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Add `_cross_period_non_official_local_chain_advisory_finding` building an `ADVISORY`/`WARNING` `ModeloVerificationFinding` that discloses the same-year locally-filed, AEAT-unevidenced basis and a file-externally next_action.
- Emit it from `_cross_period_clean_state_findings` when `evidence.non_official_local_chain_advisory` is set, alongside the existing unstamped-revision and operator-declared-suppression advisories.

## Outcome

Landed in commit `84add274d`. A WARNING is non-blocking, so `_classify_verification_outcome` keeps the verify grant open and export proceeds; the non-official basis is disclosed rather than granted silently (`no-silent-under-declaration`).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
