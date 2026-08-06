---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:81a6c5a79994c258d2b2f25c06897474cf80f597a7ea58416e723aa94ea9d2de'
step_id: 'S42'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Make the labelled-issue alert path survive a repository carrying no release-alert label

## Scope

- `dev/release/alerting.py`
- `dev/release/tests/test_release_alerting.py`

## Description

- Add `ensure_alert_label`, creating the label when absent and never raising.
- Fall back to an UNLABELLED issue when the labelled creation is refused, reporting which path was taken.
- Make the existing-alert lookup fall back to an unlabelled query and, failing that, to "no existing alert" rather than aborting.
- Pass issue bodies via `--body-file` rather than an argv element.
- Add the refusal test and a control proving the fallback has not become the only path.

## Outcome

18 passed in the alerting suite; 478 passed across `dev/release/tests`, the derivation suite, `dev/deploy/tests`, and `dev/ci/tests`.

## Notes

The audit measured this on the live forge and it is the worst kind of defect: a mechanism that visibly exists, is fully tested, and delivers nothing. Every default-path alert was refused because the repository carries no `release-alert` label, so the emitter raised, the entry point caught it as designed, and the alert became a run-log warning - which is precisely the surface S30's exec record already identified as reaching nobody.

The ordering principle now stated in the code: DELIVERY OUTRANKS FILING. The label is how an operator subscribes to one stream instead of the whole tracker, which is a convenience. The alert is the deliverable that pays for the removed approval click. So a repository without the label, or a token that cannot create one, still receives the alert - unlabelled, and the return value says so rather than pretending otherwise.

The test stub is deliberately STRICTER than the live forge: it refuses every call naming the label, where the forge refuses only the labelled creation. That strictness earned its keep immediately - it exposed that the existing-alert LOOKUP also passes the label, so on a label-less repository the alert would have died before it ever reached creation. The lookup now degrades to an unlabelled query, and then to "no existing alert found", because a duplicate alert is a far better outcome than no alert.

## A production improvement the test forced, and it is a real one

Issue bodies now ride `--body-file` instead of `--body`. The multi-line body was breaking argv handling in the test stub, and the honest reading is that this is not a test artifact: an alert body is multi-line and unbounded, a Windows command line caps at roughly 8k characters, and embedded newlines are quoted differently by every shell in the chain. The file form sidesteps all of it. I took this rather than weakening the stub, because the stub was reporting a real fragility.
