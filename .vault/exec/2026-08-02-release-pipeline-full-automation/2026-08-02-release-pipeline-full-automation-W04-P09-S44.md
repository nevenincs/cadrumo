---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:28b1c49e46972154bfeaa41894080439d2f02932519b9e53d987650d3dc45a20'
step_id: 'S44'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Make the promoter exit status distinguish an ordinary quiet tick from an invalidated candidate so a cohort whose readiness gate reds during its soak reaches the failure-guarded alert instead of reporting to nobody

## Scope

- `dev/release/soak_promoter.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Carry the `invalidated` flag on the decision (added structurally in S41) through to the CLI exit status.
- Return non-zero and emit a workflow error annotation when a candidate was refused on re-verification.
- Keep every other decided outcome at zero.
- Add two tests: the invalidated case, and a control asserting both quiet cases stay un-invalidated while the regressed one differs.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q` reports 22 passed. Lint, format, `ty check` clean.

## Notes

The failure this closes is a coupling that is invisible from either side alone. The promoter's alert step is failure-guarded, and the entry point returned zero for every decided tick - so the one outcome that most needs a human, a real cohort refusing to publish because its evidence regressed during the soak, was reported by a print statement into an unread log and by nothing else. Each half looks correct in isolation: an alert guarded on failure is right, and a promoter that does not treat "nothing to do" as an error is right. The defect is only visible when you ask which outcomes actually reach the guard.

The exit status is deliberately narrow. Only an invalidated candidate is non-zero; a tick where every window is still open, or where no candidate is sealed at all, stays zero. Widening it would fire an alert on nearly every scheduled run, and an alerting channel that fires constantly is one the operator filters - which lands back at nobody looking, by the same route the flooding argument in S29 describes.

The control test asserts all three outcomes together rather than only the positive one, so a change that made every decision invalidated would red rather than passing the new assertion.
