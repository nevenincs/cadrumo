---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S259'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# Make the health report consume the typed duplication result and classify zero observed clones as green, observed clones as amber, and unavailable, failed, timed-out, non-zero, or unparseable execution as explicit amber-unavailable

## Scope

- `dev/audit/report.py`

## Description

- Establish that this step duplicates a step already closed under a rescoped successor plan.
- Read the report's duplication dimension and confirm it delegates the whole measurement rather than building a second scanner invocation.
- Confirm each outcome maps to the severity the step requires, and that green is reachable only from an observed zero.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

This step's action text is word-for-word identical to the third step of the duplication-evidence-repair successor plan, which is closed.

Verified by reading the report's duplication dimension at the current commit. It delegates the entire measurement to the runner and only maps the returned typed outcome onto its own severity vocabulary; there is no second scanner invocation and no second parser in that module. The mapping is the one the step requires. An unavailable result is AMBER carrying the reason, and it states explicitly that no duplication evidence was produced this cycle and that this is not a clean-tree signal. An observed zero is GREEN. Clones are AMBER carrying the measured count, which matches the governing decision to keep the clone count advisory rather than a gate.

The structural point worth recording is that green is reachable from exactly one outcome. Unavailable, failed, timed-out, non-zero, and unparseable all converge on amber, so there is no path from a scan that proved nothing to a green verdict. That is stronger than a set of assertions about the mapping, because it is a property of the branch structure rather than of the tests over it.

## Notes

Semantic CODE search was degraded and reported itself healthy: 188 indexed sections against roughly 4546 tracked files, with an empty degraded-reasons list. Verification here was by direct read of the report module, which is the appropriate instrument for a branch-structure property in any case.

The VAULT index was healthy at 16121 documents and surfaced the successor plan that closed this step.
