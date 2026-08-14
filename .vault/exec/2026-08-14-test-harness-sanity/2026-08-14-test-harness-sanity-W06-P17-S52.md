---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1b8c0b2968fc1b9fc8a1ef0a12ff893947910a01bed064fe0cf59d6f719c2768'
step_id: 'S52'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Prove the harness recipe selects every declared member and fails when membership collapses

## Scope

- `dev/ci/tests/test_ci_workflow.py`

## Description

- Pin the exact harness members, individual collection preflights, and combined outer-serial command.
- Assert that CI exposes a standalone blocking harness verdict and keeps it out of routine jobs.
- Execute the live rendered preflight against real populated and empty pytest modules to prove exit-5 discrimination.

## Outcome

The harness lane now has structural and behavioral regression coverage. A populated-plus-empty aggregate demonstrates the formerly hidden green case, while the real per-member preflight rejects the empty member with pytest exit 5.

## Notes

The first implementation only mirrored recipe text and was rejected during independent review. The corrected test resolves the installed `just`, renders the live recipe, and invokes real `uv` and pytest subprocesses against test-owned modules without mocks, patches, skips, or simulated behavior. Ruff, format checking, diff integrity, and the focused integration suite passed with 37 tests.
