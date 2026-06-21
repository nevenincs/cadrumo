---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S07'
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
     The S07 and 2026-06-21-crossperiod-filing-deadlock-plan placeholders are machine-filled by
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
     The Add _relax_same_year_local_chain admitting a same-year app_filing dependency whose blockers are a subset of the official-evidence-delta set, clearing those blockers and stamping the advisory facet and ## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add _relax_same_year_local_chain admitting a same-year app_filing dependency whose blockers are a subset of the official-evidence-delta set, clearing those blockers and stamping the advisory facet

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the `_OFFICIAL_EVIDENCE_DELTA_BLOCKERS` frozenset (`MISSING_AEAT_ACCEPTANCE`, `MISSING_EXTERNAL_EVIDENCE`, `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`).
- Add `_relax_same_year_local_chain`: returns the evidence unchanged unless `requirement.filing_year == target_filing_year`, `observation_source_kind == "app_filing"`, blockers non-empty, and `set(blockers) <= _OFFICIAL_EVIDENCE_DELTA_BLOCKERS`; otherwise `model_copy` clears the blockers and sets `non_official_local_chain_advisory=True`.
- Map every in-scope dependency through it in `evaluate_cross_period_clean_state`, passing `target_filing_year=snapshot.filing_year`.

## Outcome

Landed in commit `84add274d`. Cross-year deps, `operator_manual` sources, value/revision divergence, and missing observation/filing keep their blockers; the source stays non-official.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
