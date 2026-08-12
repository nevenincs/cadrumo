---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:51704ae8016fc8db1381ba54db6b0043d1757f5a18f2edc2ccda7d99ae697e3c'
step_id: 'S17'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Enroll app live deudas pull in PROFILE_BOUND_WRITE_VERB_PATHS with a comment stating it persists a captured snapshot to bucket storage, verified by test_root_fallback_guard_predicate_covers_profile_bound_mutations extended with the new entry

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Not implemented. Blocked on S16's verb existing to be enrolled.

## Outcome

**DEFERRED CARRY-FORWARD. No write-policy entry was added.**

`PROFILE_BOUND_WRITE_VERB_PATHS` names verb paths. The verb this row would
enroll does not exist, and an entry naming a non-existent path is dead config:
it guards nothing, and its own gate
(`test_root_fallback_guard_predicate_covers_profile_bound_mutations`) would be
asserting against a leaf no operator can invoke.

**The fail-closed direction is the safe one here, and it holds.** An unenrolled
verb that does not exist cannot write. The risk this row protects against — a
profile-bound mutation escaping the guard — arrives with the verb, not before
it.

## Notes

This enrollment must land in the SAME commit as the verb. A verb that persists a
snapshot to bucket storage while absent from the write-policy allowlist drops
out of the profile-bound write guard, which then fails open — the failure the
CLI contract rule names explicitly.
