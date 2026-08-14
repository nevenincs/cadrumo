---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:10ac1495e31668915487043a4ef2f65cbb71fd3d4507f4ceff5ccd892cd5c35a'
step_id: 'S74'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Add real subprocess proofs for domain-local banned live imports and clean controls

## Scope

- `src/cadrumo/tests/test_marker_integrity.py`

## Description

- Launch real child pytest processes against temporary domain-local live modules.
- Prove banned imports exit before the default unit selector can deselect live items.
- Prove a clean live control executes and reports one root collection-policy hook owner.

## Outcome

The root live-import policy now has durable out-of-central-subtree regression coverage. The negative control exits with policy status 2 and names the banned import, while the clean control executes two live probes and confirms the child collection-policy traversal was removed.

## Notes

The first assertion incorrectly treated a generic terminal-summary zero-test advisory as policy deselection and was removed; exit status and violation diagnostics are the authoritative negative evidence. The final two focused tests passed in 15.35 seconds, with Ruff, format checking, diff integrity, bounded subprocess timeouts, and independent review all clean. No broad marker suite was claimed.
