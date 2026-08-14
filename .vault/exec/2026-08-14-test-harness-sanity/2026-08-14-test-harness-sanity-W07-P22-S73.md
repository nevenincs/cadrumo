---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e5989914eeceaa759c1b6a5b9a9a45bb36e2959d5054430fa23e1799f8aafebb'
step_id: 'S73'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Remove duplicate marker traversal and live-policy ownership from the child conftest

## Scope

- `src/cadrumo/tests/conftest.py`

## Description

- Delete the policy-only child conftest after root ownership landed.
- Remove the duplicate marker traversal and banned-import scanner implementation.
- Reconcile code, README, and synthetic-path prose to the root/shared policy owner.

## Outcome

Collection policy now executes from one repository-root hook. The central test subtree no longer performs a second marker walk or live-import scan, while live opt-in remains owned by `tests.live_gate` and all active ownership prose names the root/shared surface.

## Notes

Focused marker collection reported 32 items, serial enforcement passed two cases, and a domain-local live module collected successfully. The updated skip-policy control, Ruff, stale-owner scan, and diff integrity passed. The full marker-integrity module remained red on unrelated current marker debt, so it was not credited. Independent review confirmed the deleted child had no fixture or opt-in responsibility and the separate S86 fixture-placement rationale remains untouched.
