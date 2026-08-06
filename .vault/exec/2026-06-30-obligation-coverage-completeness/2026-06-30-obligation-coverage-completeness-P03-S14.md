---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:047e2bba208bc886592b2d19d8b122d6c1227c9ccada873b06175c5a55e66ba8'
step_id: 'S14'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Wire coverage onto overview status, explain, and the undeclared-profile path.

## Scope

- `src/aeat/entrypoints/cli/_overview.py`

## Description

- Wire `overview explain` to recognize the unmodeled set: a recognized-but-unmodeled
  modelo now returns an informative "recognized AEAT obligation, not modeled yet —
  investigate (coverage: registry_unmodeled)" answer instead of a "not registered"
  typo error, keyed off a code-indexed view of `UNMODELED_OBLIGATIONS`.
- Wire `overview status` to reconcile the active profile's coverage over the current
  year and emit the same default advisory Notice the calendar does.
- (The undeclared-profile path was wired in S15.)

## Outcome

All six `overview` surfaces that answer "what must I file" now carry the coverage
reconciliation: single-profile calendar / agenda / backlog, `--all-profiles`, status,
explain, and the undeclared path. `explain` distinguishes recognized-unmodeled
(216 → informative) from unknown (999 → typo) while registry modelos are unchanged;
28 status/verb + 18 explain tests pass.

## Notes
