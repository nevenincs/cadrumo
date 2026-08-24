---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:88c1f662d1c8e924a5103db50a803a4ef1c0766770436d7d207c97ff0f88bf8a'
step_id: 'S74'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh remove the latent hazard in the persisted profile record whose setup-state field defaults to the completed value, so a record constructed without stating it silently claims completion, noting that all three production construction sites state it explicitly today which makes this latent rather than live, and that changing a persisted-model default is a shape change wanting its own deliberate commit

## Scope

- `src/cadrumo/application/user_profile/_capsule_record.py`

## Description

Remove the completed-state default from the strict profile record, require every construction site to state setup state, and verify the missing-field refusal and existing round trips.

## Outcome

The hazard is removed at the shape itself (commit `8af8766858`): `UserProfileRecord.setup_state` no longer carries the COMPLETE default — it is a required field on the strict-frozen model, so a record constructed without stating it fails at construction instead of silently claiming completion. The write-path guard `_assert_setup_state_was_stated` became unreachable and was deleted with its call site. Every in-tree construction now states the field explicitly (125 files swept; the batch stated the previous default COMPLETE, so observable behaviour is unchanged), and the anti-tautology roundtrip now proves the missing-field refusal at the model boundary.

## Notes

The sweep was executed while peer campaigns were editing test files in the same tree; several files were briefly held open by peers (Windows sharing locks), and two import-repair passes were needed to converge the sweep to compile-clean. Ruff clean on the swept set; collect-only on the touched packages clean; the record-boundary and roundtrip suites green. The tree-wide AttributeError red seen during the sweep belongs to a peer's in-flight registry refactor, not this row.
