---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:a2e3b0858d059adce6bb099cc80133c8a5c1b20cb53413f4de251a229cfcac93'
step_id: 'S04'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Move the ci-full docs build above the tooling-gates step so the terminology gates that resolve to built HTML get their artefact, blocked until the legal-entry defect stops masking the dependency

## Scope

- `.github/workflows/ci-full.yml`

## Description

- Move the docs build above the tooling-gates step in the full lane.

## Outcome

Landed as `db05b4316b` ("fix(ci): build the docs before the tooling gates that also read the
artefact"), one file, 30 insertions and 23 deletions.

The row's premise is an ordering dependency: terminology gates resolve against built HTML, so
running them before the build leaves them reading an artefact that does not exist yet.

## Verification

    git log --format=%H --grep="build the docs before the tooling gates" -1
    git show db05b4316b --numstat
    30      23      .github/workflows/ci-full.yml

Verified by resolved sha, not `git show HEAD`, with the per-file counts read rather than the
file list alone.

This row's evidence is structural, a step order in a workflow file, so there is no test
selection to state. **The ordering has not been observed on a runner**, because the full lane
has not been dispatched since. That exposure belongs to the dispatch row rather than this one,
but it is the honest limit of what this record establishes.

## Notes

The row carries a precondition, that it was blocked until the legal-entry defect stopped
masking the dependency. That defect is `P03.S14`, which landed in the same window, so the
change is unblocked by fact rather than by assumption.
