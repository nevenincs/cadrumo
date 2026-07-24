---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-24'
modified: '2026-07-25'
step_id: 'S06'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Prove real zero-clone, clone, unavailable executable, non-zero, timeout, stderr, and unparseable outcomes cannot become false green and that report and direct runner render the same typed result

## Scope

- `src/cadrumo/tests/test_dev_audit_report.py`

## Description

- Delete the two existing tests that protected the false green.
- Prove a real clean subtree scan observes zero and a real production-tree scan reports a measured clone count.
- Prove a missing executable, a bad source path, a non-zero exit, a timeout, and unparseable output each classify as unavailable rather than green.
- Prove an empty scan output is unavailable rather than a zero, and that an observed zero cannot be constructed without inspected files.
- Prove the report and a direct runner invocation render the same typed result for the same tree.

## Outcome

Every invalid-evidence outcome named by the plan has a test asserting it cannot render green, and each carries its diagnostic reason. The two prior tests that had encoded the defect as expected behaviour are gone: one asserted that output carrying no summary reduces to a zero clone count, and the other asserted only that the dimension status was amber or green, which held whatever the report answered.

The proofs landed in `4cd774bdde`. A follow-up, `6c32a9fa90`, replaced the suite's skip and monkeypatch usage with real injection, so the unavailability cases exercise real subprocess outcomes rather than patched ones.

## Notes

The step row names `src/cadrumo/tests/test_dev_audit_report.py` as its scope, but the substantive proofs live beside the runner in `dev/audit/tests/test_duplication.py`; the named module carries the report-side dimension assertions only. The plan's close honesty review raised this scope mismatch, and it is recorded here rather than silently corrected, because the step row is the durable identifier.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the same review.
