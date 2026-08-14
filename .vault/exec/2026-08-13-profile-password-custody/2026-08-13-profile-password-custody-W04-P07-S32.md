---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ddabe0f80da84231ddc9283d67129030cca78e9748016dc9c66eaadcdb108119'
step_id: 'S32'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium triage the fifteen auth test modules deleted under the discovery step against the twenty-two production auth modules still live, then restore the coverage that still applies or consciously retire each module with its reason recorded

## Scope

- `src/cadrumo/application/auth/tests/`

## Description

- Triage each deleted module against the production surface that still exists,
  rather than restoring the corpus wholesale.
- Re-site the coverage that still applies onto the per-profile capsule helpers,
  since the deleted modules were written against the shared-master surface the
  cutover removed.
- Record a reason for each module not restored, so a deliberate retirement is
  distinguishable from an oversight.

## Outcome

Five modules were restored: blank-identity refusal, certificate secret backend,
certificate sources check, clave credential resolution, and session identity
comparison. They are re-sited onto the capsule helpers rather than transplanted,
because the originals authenticated through a shared master key that no longer
exists; a transplant would have restored the line count without restoring the
proof.

The restored suite is green and was verified by an independent run rather than
accepted from the authoring agent: 227 passed, 0 failed, 63 seconds, with the
default marker filter disabled so integration-marked cases could not hide.

## Notes

The deletion that caused this step removed fifteen modules and roughly six
thousand lines in a single commit whose subject described a feature. That commit
is now the traced origin of eight distinct defects in this campaign, of which
this is one. The lesson recorded against it is not that deletion is wrong but
that a deletion of this size inside a feature commit is invisible to review, and
the module coverage gate did not object because one import from any surviving
test kept every module reported as covered.

The count of live production modules is carried from the plan row and was not
re-derived here; the restoration decisions were made per module against the
surface each one tests, which does not depend on that total.
