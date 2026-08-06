---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:d53aa1787426abe8ac572dd8dad907e9cba0680108455b497d4e5c806806b896'
step_id: 'S25'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Sweep for tests relying on the English CLI env override for help text, it is inert against the cached Click tree so any such test asserts against whatever language the tree was built in

## Scope

- `src/cadrumo/entrypoints/cli/tests`

## Description

- Sweep the CLI tests for reliance on the English environment override for help text.

## Outcome

Landed as `56ab637c42` ("docs(tests): record that a language env is inert for the in-process
CLI runner"), one file, 27 insertions and no deletions.

The sweep's finding is that the override is inert against the cached command tree: help
strings are rendered when the tree is built, so an environment variable set afterwards cannot
change them, and any test relying on it asserts against whatever language the tree was built
in. The landed change records that where the next author will meet it.

## Verification

    git log --format=%H --grep="a language env is inert for the in-process CLI runner" -1
    git show 56ab637c42 --numstat
    27      0       (one CLI test module)

Insertions only, no deletions: the commit adds an explanation and removes no assertion.

## Notes

**This row closes on a sweep whose result was "no test to repair", and that deserves stating
rather than leaving implied by a documentation-only commit.** The row asks for a sweep; the
sweep found the mechanism inert and documented it. Had a test been found relying on the
override, the row would have required a repair and the commit would not have been
documentation only.

A reader auditing this row later should read the absence of a code change as the sweep's
finding, not as the sweep having been skipped.
