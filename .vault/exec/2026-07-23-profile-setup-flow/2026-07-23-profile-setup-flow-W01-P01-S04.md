---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S04'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Refuse modelo work on setup-incomplete profiles in the readiness gate with an instructive refusal naming the resume path

## Scope

- `src/cadrumo/application/modelo/_profile_readiness_gate.py`

## Description

- Refuse `require_profile_ready_for_modelo_work` on
  `UserProfileStatus.SETUP_INCOMPLETE` immediately after the record
  load, before applicability and filing-readiness checks, with an
  instructive suggestion naming the setup verb.
- Add the refusal message key to all four locale catalogues through the
  locales CLI (`application.modelo.errors.profile_readiness_setup_incomplete`).
- Pin with a gate test storing a fully filing-ready fact set under
  setup-incomplete status: the refusal fires on status alone and cites
  the setup-incomplete key.

## Outcome

Committed as `6a8dc1f4d1` (explicit pathspec). Readiness-gate suite
16/16 green.

## Notes

The repo-wide locale parity gate is red with 47 missing `flows.*` keys
in all four catalogues - owned by the substrate landing's pending
locale sweep, not this Step (owner triage per the full-tree-gate
discipline; reported to the coordinator). This Step's key is present in
all four catalogues.
