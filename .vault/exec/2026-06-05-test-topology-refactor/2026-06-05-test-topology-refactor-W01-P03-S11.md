---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:13e9b595390c1857b7d02b78b33e6e1e2d1041d1a77be8eed7425c2bb0f0ef65'
step_id: 'S11'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P03.S11`

## Scope

Core and setup-owned naked tests.

## Description

- Moved core package tests into owner-local `tests` folders.
- Moved setup application tests under their owner-local application harness.
- Moved corpus data provenance tests under their `_data/corpus` owner-local harness.

## Outcome

- Core, setup, and corpus-data test files now follow the child `tests` directory topology.

## Notes

- The `_data/corpus` file is not a hexagonal top-level bucket, but the accepted topology rule still places it under a local `tests` child directory.
