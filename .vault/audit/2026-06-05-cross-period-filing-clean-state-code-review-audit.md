---
tags:
  - '#audit'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
---

# `cross-period-filing-clean-state` Code Review

## CROSS-PERIOD-001 | LOW | Grouped dependency proof cannot infer an unstored member roster

`evaluate_cross_period_clean_state` now detects `per_grupo_member` requirements and blocks when no member observations exist. It also compares observed member totals against the persisted aggregate calculation revision when member observations are present. The current domain surface does not expose a declarative expected-member roster for a target grupo filing period, so the proof cannot independently prove that every legal member was captured; it can only prove that the captured member observations are clean, filed, AEAT-accepted, externally evidenced, and internally reconciled. This is a modelling limitation, not a regression in the implemented guard. Future registry/profile work should add an explicit grupo membership calendar if legal completeness must be proven beyond captured source observations.

## CROSS-PERIOD-002 | INFO | No critical or high findings in the filing-grade guard

The review found the filing-grade guard wired through verification, export, and filing using the calculation package export surface and domain package reexports. Preview calculation remains permissive, while verification records blocking findings and export/filing raise `ModeloCrossPeriodCleanStateError` when required prior filings are missing, unaccepted by AEAT, lacking external evidence, unreconciled against local calculation values, or missing complete verification evidence.
