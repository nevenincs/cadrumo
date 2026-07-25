---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S260'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# Replace the shell pipeline with a direct Python duplication runner invocation so Windows and POSIX execute the same authority and retain stdout, stderr, return code, and timeout evidence

## Scope

- `justfile`

## Description

- Establish that this step duplicates a step already closed under a rescoped successor plan.
- Read the build recipe and confirm it invokes the runner module directly with no shell pipeline.
- Check whether the second pinned scanner version literal an earlier close review found in the environment-check recipe still exists.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

This step's action text is word-for-word identical to the fifth step of the duplication-evidence-repair successor plan, which is closed.

Verified by reading the build recipe at the current commit. The duplication recipe invokes the runner module directly as a Python module invocation, with no shell pipeline, so Windows and POSIX execute the same authority and the runner retains stdout, stderr, return code, and timeout evidence rather than losing it to a pipe.

A second finding from the successor plan's close review is also confirmed closed, and this one was worth checking rather than assuming. That review found the environment-check recipe running a scanner version probe carrying a second hardcoded version literal that could drift from the runner's pinned specification. A search of the build recipe now returns the scanner name only inside a comment, and that comment records that the runner owns both the invocation and its parsing. The second version literal is gone, so the pinned specification exists once.

## Notes

Semantic CODE search was degraded and reported itself healthy: 188 indexed sections against roughly 4546 tracked files, with an empty degraded-reasons list. Verification was by direct read and targeted search over the build recipe.

The second-version-literal check was run rather than assumed. An earlier close review recorded that literal as present, and a stale finding actioned without re-checking is how a closed item gets reopened by mistake.
