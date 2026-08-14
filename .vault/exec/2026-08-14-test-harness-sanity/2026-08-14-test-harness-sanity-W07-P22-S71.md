---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:50e47bdfaa85dd758fbfa1305e93c2fa1486b2f0e1a542af0822d4b3b44a25cd'
step_id: 'S71'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Promote banned-live-import enforcement into the shared root policy helper

## Scope

- `src/cadrumo/tests/_marker_hook.py`

## Description

- Move the banned-live-import targets and AST scanner into the shared collection-policy helper.
- Expose an idempotent live-import policy entry point that composes after marker taxonomy enforcement.
- Preserve the existing violation text, exit status, and one-scan-per-live-module behavior.

## Outcome

The shared marker helper now owns both marker taxonomy and banned live-import policy primitives. The new policy function is ready for the root hook to become the single caller without mutating collected items or executing test modules.

## Notes

Ruff, format checking, diff integrity, and the focused serial marker enforcement tests passed. A broad marker-integrity attempt was not credited because unrelated shared-tree collection failed on missing user-profile exports and temporary-path collisions. Independent review confirmed the extraction is behavior-preserving and linear; S72 must migrate `tryfirst=True`, and S74 must provide the real domain-local subprocess reach proof before the phase closes.
