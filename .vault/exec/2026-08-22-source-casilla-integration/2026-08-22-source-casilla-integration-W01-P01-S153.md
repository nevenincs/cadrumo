---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e67e06616732294d48cdc32a706bbdcf7af3c6f9ed6a7f09206269653f3aa94f'
step_id: 'S153'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# make live connectivity authority accept exactly one resolver-matching primary and reject contributor-only, ambiguous, orphaned, drifted, or malformed provenance graphs

## Scope

- `src/cadrumo/application/registry`

## Description

- Match encrypted connectivity proof only against resolver-owned `PRIMARY` rows.
- Refuse contributor-only matches, duplicate primaries, orphan contributors, and identity drift.
- Validate graphs at calculation-resolution, merge, persisted-revision, and live-authority boundaries.

## Outcome

The live authority treats contributors only as support and accepts exactly one truthful primary matching the claimed resolver, source, reference, and fingerprint.

## Notes

Implemented principally in shared-worktree commit `31e504c55b`; the merge-order correction is a follow-up. Selected source-mesh, encrypted-persistence, wallet, and authority coverage passed 85 tests.
