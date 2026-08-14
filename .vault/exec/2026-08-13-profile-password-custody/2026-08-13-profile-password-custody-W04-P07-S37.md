---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1bc40c18dc6119bfb1a3d06afa64e065523aa6107eb26c9104df05a524d653fe'
step_id: 'S37'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh stop the custody key-derivation calibration from measuring its cost grid on hosts that enrol a profile per test

## Scope

- `src/cadrumo/core/config.py and src/cadrumo/adapters/persistence/storage/custody/_kdf_supervision.py`

## Description

- Profile the enrolment path and attribute its cost, rather than acting on the
  suspected causes.
- Add one deployment setting governing whether the calibration measures the
  host, defaulting to measuring so no operator behaviour changes.
- Short-circuit the calibration to the fixed point the function already returns
  when the grid cannot be measured before its deadline, reached through the
  same return and carrying the same declared fallback source.
- Set that setting false in the three isolated test fixtures that enrol
  profiles.

## Outcome

Enrolment falls from seventeen and a half seconds to one and a half. A
representative fixture-heavy module falls from roughly eighty seconds of setup
across four tests to sixteen and a half seconds in total. The custody suite
passes its thirty-six tests throughout.

The measured attribution: ninety-one per cent of enrolment sat inside the
calibration, which walked a finite cost grid with one warmup and five real
samples per point until one landed inside its target band. That is ten
supervised child processes and about fourteen seconds blocked reading their
pipes, per enrolment. Correct for an operator enrolling once; wrong for a host
that enrols constantly.

No wrap weakens. The fixed point is stronger than production's measured
parameters, so the key derivation exercised in tests is harder than the one
operators get, not cheaper. Only the host measurement is skipped; every wrap
and unwrap still runs the real derivation through the same supervised worker.
There is one parameter surface, one return path and one declared source — no
test-only derivation and no fast path beside the real one.

Three hypotheses were ruled out by measurement rather than argument: the
derivation cost itself is twenty-three milliseconds and was never the problem;
the retired provider seam in shared test support resolves in about a tenth of a
second, so it is a correctness and duplication concern rather than a
performance one; and worker spawn cost is real but secondary.

## Notes

The originally reported forty-five minute figure was inflated by the
measurement, not only by the defect. The command that produced it replaced the
default options wholesale and so dropped parallel distribution; the same
directory completes in about ninety seconds on the ordinary lane. The
underlying calibration cost was real and is now fixed, but the headline number
was partly an artefact of how it was measured, and the correction belongs on
the record beside it.

Two tests in the profile service suite remain slow at roughly forty seconds
each, unexamined here and not calibration — they compile registry snapshots.
The same two currently fail, along with eighteen tree-wide collection errors,
because a concurrent campaign leaves several modelo revisions below
filing-grade review status. Neither is attributable to this campaign.

Wall-clock measurement is unreliable while sibling agents saturate this host
and its backing share: one run of the same scope took twice its baseline purely
from contention. Timing runs need to be serialised to be trusted.
