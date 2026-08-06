---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d216b0a4ba6945df978bb2073ece52fac109a0f0da43c02d0b19237fbb8c59c1'
step_id: 'S18'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Make the readiness probes no-session contract the subject of a test, asserting the profile read is declined rather than merely survived

## Scope

- `src/cadrumo/application/auth/tests`

## Description

- Establish what already holds the contract by removing the guard and running the suite that reported the defect, finding four cases go red.
- Write the obvious no-session test first and discover it passes with the guard removed, so it pins nothing.
- Diagnose why: an isolated file-backed secret store decrypts without a bucket session, and where it does refuse it raises an error the existing except clause already catches.
- Assert instead that the profile read is declined, which is what the code guarantees and holds on every backend.
- Build the condition rather than simulating it, creating a real profile and leaving its session span while keeping the active-profile pointer set.
- Assert the fixture itself first, since a profile that is absent or unreadable would let every later case pass for the wrong reason.
- Restore the guard and confirm it is byte-identical to the committed version.

## Outcome

Six tests in `src/cadrumo/application/auth/tests/test_probe_survives_without_a_session.py`.

`uv run --no-sync pytest` over the new file and the preflight suite reported `22 passed in 32.62s` at the committed HEAD.

With the guard removed locally, `uv run --no-sync pytest` over the preflight suite reported `4 failed, 12 passed in 20.23s`, naming the same four cases the defect was reported against. The guard was then restored and verified byte-identical to HEAD before anything was committed.

`uv run --no-sync ruff check` and `uv run --no-sync ty check` both reported `All checks passed!`.

## Notes

The premise that nothing pinned the guard was not quite right, and checking it first changed what was worth building. Four preflight cases do go red without the guard, so a refactor removing it would not pass today. What was missing is that those cases assert row contents and fail for this reason only as a side effect, so the contract was stated nowhere as a subject.

The stronger claim cannot be pinned deterministically and the attempt is the useful record. A test asserting the probe does not raise passes on an isolated file-backed store whether or not the guard exists, because that backend decrypts without a bucket session, and where it does refuse it raises an error the pre-existing except clause catches. Only a locked keychain produces the driver-wrapped refusal that defeats that clause. So a "never raises" case would have been green throughout the original defect. Asserting the declined read is weaker in wording and stronger in practice, since it holds on every backend.

Two fixture details are load-bearing and would be easy to remove as noise. The profile has to exist, or a probe that lost its guard returns empty for the wrong reason. And the active-profile pointer has to be set: the isolation helper defaults it to absent, and with no pointer nothing downstream attempts to open the profile, which would make the guard look unnecessary.

The whole worktree's git index was locked for roughly eleven minutes during this Step, with zero commits landing from any agent and the lock file frozen at zero bytes. It was reported rather than cleared, since removing another agent's lock risks corrupting an in-flight index write, and it resolved without intervention.
