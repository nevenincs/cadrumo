---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:b8f9b894584fc49de62a50c4ab01b4c203a4e802a00dcdeaea358dbdc8b4a9f2'
step_id: 'S295'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Closed as unnecessary, a peer fix bridged the payload-name filter by importing the wizard result classes into a walked module, so enrolment is filename-filtered still and the divergence ended when that bridge landed

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

Determine whether the wizard result schemas need enrolling in the manifest
population walk before the identity fix can land.

## Outcome

SATISFIED as unnecessary, after two wrong explanations were corrected.

The schemas are declared in a module the population walk never reaches: the
walk imports `*payload*`-named modules under two declared payload packages, and
that module is under neither. Enrolment is filename-filtered, and the finding
was correct when filed.

What made the step unnecessary is a peer fix at `92b0dfd10b`, landed thirteen
hours after the finding and a descendant of the HEAD it was measured at, which
bridges the filter by importing the two result classes into a module the walk
already visits. That fix's own comment states the mechanism and marks the
imports load-bearing.

Measured after it: a `git archive` tree with no untracked files reports 295
schemas, both profile schemas present, zero import failures, identical to the
working tree.

Two explanations were asserted here before that one and both were wrong - that
enrolment was never filename-filtered, and that the untracked-module commit was
the repair. Both were fabricated from present state without checking history,
which `git log -S` answers in one command. The verification phase caught it by
testing the claim rather than agreeing with it.

## Notes
