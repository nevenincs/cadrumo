---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:06a07c8e9c946eadffda7cf434357c6678c9461676ed1dfe7850a5fa599a1200'
step_id: 'S204'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh close the split between active-profile and named-profile resolution, since a record written in one process is found by the active-profile path in a fresh interpreter and reported present with its keys, while the named-profile path refuses the same record as missing and reports zero present keys and no source, which means the cold-process problem is a resolution defect rather than the durability or key-digest failure two earlier investigations were framed around

## Scope

- `src/cadrumo/application/user_profile/ and src/cadrumo/application/workflow/`

## Description

- Trace the split to the CLI root callback, which returns early for a verb naming an explicit profile target and so skips the session resume that the active-profile path receives.
- Establish that the early return rests on a false premise: the explicit-target predicate documented those verbs as resolving AND unlocking their own target, while the read helper only checked whether a session already served the bucket and raised otherwise.
- Confirm by search that no resume or login call existed anywhere on the named-profile read path.
- Hand the diagnosis to the CLI owner, who added the resume through the shared authority and corrected the predicate's docstring.
- Rename the resume authority from an active-scoped name to one naming what it does, atomically with every call site across the application layer, the CLI root callback, the named-profile read path and their tests.

## Outcome

The defect was resolution, not durability and not the key digest, which is why two earlier investigations framed around those found nothing. The active-profile path was resumed by the root callback and reported the record present with its keys; the named-profile path skipped that resume, found no session serving its bucket, and reported the same record on the same disk as missing.

The authority's former name asserted "active" while its parameter took an explicit bucket. That mismatch is the most likely origin of the false premise: an author reading it would reasonably conclude it could not serve a target resolved elsewhere. The name now states that it binds a resumed session for an explicit target, and is distinct from the substrate primitive that resumes material without binding.

Both resolution paths now ask the identical question, because the record authority also requires a live and unsealed custody session serving the exact profile.

## Notes

**A regression test is owed and is deliberately absent.** The scenario requires cross-process session resumption, which requires the operating system credential store. On the machine this Step was executed on, that store is saturated: credential writes fail with a not-enough-memory error, session minting raises, and any cross-process resume reports itself unresumable. The defect could therefore be neither reproduced nor a fix verified here.

Authoring the test blind was considered and rejected. A test written against a host that cannot execute it can never be watched to fail, so it would assert only that its author believed the fix correct - which is weaker than recording the absence. The owner of a working credential store takes it.

The diagnosis in this record is derived from the code path and is explicitly not a measured result. The same impediment accounts for the majority of the failing tests in this lane and makes the lane's failure set vary between runs, which is the more damaging effect: a non-deterministic suite means a red result cannot be trusted on its own. Reaping the orphaned session credentials is a destructive action on the operator's own machine and was escalated rather than performed.

## Closed, 2026-08-16: the owed test exists, and the diagnosis is now measured

**The escalation was answered and the impediment is gone.** The operator authorised reaping the retired credential generation; 317 entries were deleted, the 179 current-generation entries deliberately left because one may be a live login. Credential writes succeed again, so the scenario this record could not execute is now executable.

**The owed regression is landed:** `entrypoints/cli/tests/test_named_profile_resolution_cross_process.py`. A profile is registered in-process, then `config profile show NAME` runs in a FRESH interpreter against the same storage root. A cold process is not stylistic — the fix binds a session resumed from persisted material, so an in-process runner would find a session already bound by an earlier test and could not observe the regression at all. Two cases: the named path reaches the record, and the named and active paths agree on the decrypted content rather than on a presence flag.

**The diagnosis in this record is no longer derived — it is confirmed by experiment.** The fix was disabled at runtime from a script OUTSIDE the repository, replacing the session-binding authority with a no-op so nothing tracked was mutated and no crashed run could leave residue. With the fix: the record resolves, exit zero, facts present. With it disabled: `profile_record_present = False`, `valid = None`, and NO facts — while `display_name` is still carried, and `status` stays `None` on both sides.

**That measurement changed the test.** The assertions originally written against `status` would have passed on the broken build, because `status` does not discriminate; and a check on the label would have passed too. Facts and `valid` are what separate the two states, which is exactly the defect restated: resolution located the capsule in both cases, and only the fixed build bound a session able to OPEN it. Facts exist only when something did. Had the proof not been run, this module would have shipped as a test that could never fail — the shape the quality rules name specifically, and one that reads as coverage.

**A distinct lesson for the campaign record:** an anti-tautology proof is not only a check that the gate bites. It told me WHICH assertion bites, and two of the three I had written did not. Running it is how a plausible test becomes a real one.
