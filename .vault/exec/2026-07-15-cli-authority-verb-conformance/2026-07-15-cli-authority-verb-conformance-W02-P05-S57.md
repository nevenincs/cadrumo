---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S57'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove deletion assessment reports real retention blockers without mutating the bucket

## Scope

- `src/cadrumo/application/bucket_maintenance/tests/test_service_retention_floor.py`

## Description

- Prove assessment reads a recent filing and reports the retention floor as blocking, against real persisted filing records rather than a synthesised assessment.
- Prove the public deletion assessment reports a real blocker while leaving the durable bucket unmutated, comparing the bucket's durable state across the assessment call.
- Prove the deletion fingerprint changes when authoritative filing content changes, so the fingerprint genuinely tracks deletion-relevant bytes rather than a timestamp or counter.
- Prove assessment reads an old filing, outside the retention window, and allows erase.
- Prove enforcement refuses without an override, allows with an acknowledged override carrying a reason, refuses an acknowledgement supplied without a reason, and allows when nothing is retained.

## Outcome

- The retention floor is proven to block against real filing records inside the four-year window, and to allow once the window has passed, so the block is grounded in persisted evidence rather than a flag.
- Assessment is proven read-only: the durable bucket is unchanged across the assessment, which is the precondition that lets an operator inspect a destructive operation safely.
- The fingerprint is proven sensitive to authoritative content change, which is what makes the resume-time recheck meaningful rather than decorative.
- The override is proven to require both an acknowledgement and a reason, with neither alone sufficient.
- Focused gate green: the retention-floor, delete, and reset-journal suites ran together at `HEAD` with 26 passed and 0 failed in 175.49 seconds, collected count non-zero and explicitly confirmed.
- Landed in commit `11356b4792`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The proofs use real filing persistence, real bucket directories, and real fingerprint computation; no mock, fake, stub, patch, monkeypatch, skip, or xfail is used, and no assertion restates a value taken from the code under test.
