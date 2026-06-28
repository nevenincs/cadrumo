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

