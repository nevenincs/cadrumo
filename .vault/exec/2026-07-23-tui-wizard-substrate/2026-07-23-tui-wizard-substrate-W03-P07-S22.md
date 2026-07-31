---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:917055433b9134b293bde876de25961da268d09eab4e7f19b4cca33c5c56ace6'
step_id: 'S22'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Implement the resume projection rebuilding FlowState from persisted canonical values with current-definition re-validation, stale landing for mismatches, and cursor at first unanswered visible question

## Scope

- `src/cadrumo/application/flows/_resume.py`

## Description

- Rebuild FlowState from persisted canonical values, re-validating against the current definition and landing mismatches as stale.
- Place the cursor at the first unanswered visible question after the rebuild.
- Landed in `91a5d0cc28`; per-mode no-op honesty hardened alongside S21 in `2b2c93bf90`.

## Outcome

Resume reconstitutes a walk from stored canonical answers, re-validates against today's definition so drifted answers land stale, and resumes at the first open question.

## Notes

None.
