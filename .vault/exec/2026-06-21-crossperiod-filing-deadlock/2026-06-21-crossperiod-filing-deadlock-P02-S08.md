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




# Emit the non-blocking WARNING non-official-local-chain advisory finding from the cross-period clean-state findings builder

## Scope

- `src/aeat/application/modelo/_verification_actions.py`

## Description

- Add `_cross_period_non_official_local_chain_advisory_finding` building an `ADVISORY`/`WARNING` `ModeloVerificationFinding` that discloses the same-year locally-filed, AEAT-unevidenced basis and a file-externally next_action.
- Emit it from `_cross_period_clean_state_findings` when `evidence.non_official_local_chain_advisory` is set, alongside the existing unstamped-revision and operator-declared-suppression advisories.

## Outcome

Landed in commit `84add274d`. A WARNING is non-blocking, so `_classify_verification_outcome` keeps the verify grant open and export proceeds; the non-official basis is disclosed rather than granted silently (`no-silent-under-declaration`).

## Notes

