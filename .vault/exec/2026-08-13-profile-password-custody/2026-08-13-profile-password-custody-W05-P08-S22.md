---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:272c673cf4d428161e9e3689f00ede4fa198bdafd62884c4910da0123f145343'
step_id: 'S22'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh add real filesystem and subprocess custody matrices for isolation, calibration, supervision, crash recovery, deletion, and destructive reset

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/tests/`

## Description

Add real custody isolation, destructive-reset subprocess, and supervision-orphan matrices, reusing rather than duplicating the already-covered lifecycle axes.

## Outcome

Three real-behaviour matrix modules landed (commit `115f2908c8`, 6 cases, all green): `test_custody_isolation_matrix.py` — A's password envelope refuses B's passphrase at the real unlock door, and A's recovery artifact refuses to republish B's capsule at the identity check while restoring A from the same artifact succeeds (the refusal is the artifact's identity, not a broken path); `test_custody_reset_subprocess_matrix.py` — fresh-interpreter prepare/confirm/delete through the production reset authority, a legacy-member DESTRUCTIVE_RESET refusal in a fresh interpreter, and a crash mid-erase leaving an INCOMPLETE journal that blocks a second destructive sweep and resumes into a VISIBLE PAUSED state naming the drifted target (the fail-closed no-lost-half-state shape); `test_custody_supervision_orphan_matrix.py` — the supervised child's parent killed mid-hash; the next run reaps the orphaned worker tree and re-acquires the lease.

## Notes

The axes already covered at HEAD (supervision lifecycle, calibration, crash recovery at each durable boundary, deletion) were inventoried first and NOT duplicated. The crash-resume case was re-founded on the OBSERVED fail-closed pause (TARGET_STATE_CHANGED naming the drifted target) rather than a forced COMPLETE — the pause IS the designed no-lost-half-state behaviour. Three executor runs died on prompt overflow mid-step; the lead completed grounding, the crash-test re-found and the gate runs.
