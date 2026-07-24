---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-24'
modified: '2026-07-25'
step_id: 'S03'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Make the health report consume the typed duplication result and classify zero observed clones as green, observed clones as amber, and unavailable, failed, timed-out, non-zero, or unparseable execution as explicit amber-unavailable

## Scope

- `dev/audit/report.py`

## Description

- Make the health report consume the typed duplication result instead of interpreting raw scanner output.
- Classify a proven zero-clone observation as green.
- Classify observed clone groups as amber carrying the measured count.
- Classify an unavailable, failed, timed-out, non-zero-exit, or unparseable execution as an explicit amber-unavailable naming its reason.

## Outcome

The duplication dimension of the health report is derived from the typed result rather than re-parsed, so the report cannot reach a verdict the runner did not authorise. Invalid evidence renders as amber-unavailable with its diagnostic reason rather than collapsing into green, and a measured clone count renders as amber rather than being suppressed.

The landing commit is `4cd774bdde`, which reduced `dev/audit/report.py` by 126 lines net.

## Notes

Green is now reachable only when the runner demonstrably inspected the production tree and found no clone clusters. Per the governing decision record the clone count remains advisory debt, so an amber verdict carrying a measured count is an acceptable close rather than a failure.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the plan's fresh-context close honesty review.
