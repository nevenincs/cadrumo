---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:c8e0d627c6ced37d5f5ffcf8a38b0fddf786da734103b923836e3a8cd4a42b29'
step_id: 'S02'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Introduce the setup-incomplete lifecycle marker on the persisted profile record with schema and typed-model plumbing

## Scope

- `src/cadrumo/domain/user_profile/`

## Description

- Add `UserProfileStatus.SETUP_INCOMPLETE` with the live-but-not-workable
  semantics documented on the enum.
- Generalise the record lifecycle validator: every non-tombstoned status
  refuses `removed_at`; tombstoned still requires it.
- Add the one-way `UserProfileRecord.complete_setup` transition
  (SETUP_INCOMPLETE -> ACTIVE), refusing active and tombstoned sources.
- Add `BucketEventType.PROFILE_SETUP_COMPLETED` for the transition's
  audit record; the emission site lands with the lifecycle-service arm.
- Pin the arm with six domain transition tests (live-without-removed_at,
  refusal-with-removed_at, transition, two refusal sources,
  tombstone-on-discard).

## Outcome

Committed as `ea3a4e21d8` (explicit pathspec: `_values.py`, `_event.py`,
`test_lifecycle_transitions.py`). Transition tests 6/6, application
lifecycle suite 18/18, event-emission contract and bucket suites 21/21.

## Notes

Consumer-sweep decisions (readiness gate, listings, overview) are owned
by the sibling Steps; `_refuse_duplicate_tax_id` already treats every
non-tombstoned profile as live, so a setup-incomplete profile reserves
its tax id with no change - to be pinned by a repository test in the
early-mint Step.
