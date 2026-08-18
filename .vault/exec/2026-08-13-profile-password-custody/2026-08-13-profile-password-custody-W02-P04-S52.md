---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:a973e38afe3ccbb6de2db53622f599613fe82997024b33140bf7cbbc3365301a'
step_id: 'S52'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh bring the login-handover suite back under the storage-test time bar, since twenty-six tests now take three minutes forty-five seconds and the crash-recovery matrix dominates it, which is the same per-test supervised-child cost already removed from enrolment and must not be paid again per durable phase

## Scope

- `src/cadrumo/application/user_profile/tests/test_login_handover.py`

## Description

- Re-measured the suite at HEAD: 28 tests collected, 7 pre-existing
  keyring-environment failures, 21 passed in 104.42s, of which the five-phase
  crash-recovery matrix was 42.7s of call time.
- Added a module-scoped `_registered_handover_profiles` fixture that registers
  both handover profiles once through the production credential door inside
  `isolated_profile_storage_root`, then asserts the durable pointer
  materialised so a broken registration fails loudly at fixture time.
- Converted the five crash-phase parametrisations and
  `test_crash_after_b_handover_recovers_only_durable_b_pointer` to copy the
  pristine template root into their own `tmp_path` root with
  `shutil.copytree` before running.
- Left `test_same_profile_relogin_in_a_new_process_keeps_its_own_session_material`
  untouched: its pointer-name assumptions and single-profile shape do not fit
  the two-profile template.
- Verified the secret substrate is a sibling of the storage root, never inside
  it, so a copied tree is complete for every spawned child that rebuilds its
  settings from the root it is handed.

## Outcome

Suite after the change: 28 tests collected, the identical 7 failures, 21 passed
in 96.46s. Matrix call time fell from 42.7s to 36.2s across its five phases and
`test_crash_after_b_handover_recovers_only_durable_b_pointer` from 9.2s to
7.3s; the remaining matrix cost is the crash, recovery and probe child
processes themselves, which are the security property and must not be skipped,
batched or weakened. `ruff check` on the touched file is clean, and the
before/after failure sets are byte-identical (same seven test ids, same
assertion lines).

The improvement is real but about half the size the dispatch projected. The
row's "twenty-six tests" figure is stale -- the suite collects 28 -- and the
HEAD baseline on this host (104.42s) is already far below the row's three
minutes forty-five seconds, so the prep-projected 152s-to-136s band did not
apply to the measured starting point. The measured saving is ~1.4s per
converted pair-registration against the projected 2s.

## Notes

The per-test child cost the row cites is the same supervised-worker KDF price
already removed from enrolment: the calibration grid stays off in
`_child_settings` on every spawned child (process-boundary cascade lesson), and
wraps and unwraps remain real Argon2id derivations through supervised workers.
No wall-clock assertions were added anywhere; timings are record-only.

Carry-forward, out of scope for this row: the remaining ~25-30s lever is moving
the seven child targets into a slim sibling module so each spawned interpreter
skips the sqlalchemy and secure_sql import cost. The row names only
`src/cadrumo/application/user_profile/tests/test_login_handover.py`, and a
child-module move changes spawn targets, so it needs its own row.

Landing: commit `af90ab622f` carries the change alone; this record was authored
and attested after it.
