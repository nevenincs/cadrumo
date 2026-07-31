---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:a0afe974e467afcd922db5d9b3c0e9787751abba7564992f9c8d32f2036a24d3'
step_id: 'S19'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Record the post-W1-through-W3 per-modelo token count as the ratchet baseline and assert the count may only decrease

## Scope

- `src/aeat/tests/test_generic_module_modelo_carveouts.py`

## Description

- Record the post-W1-W3 distinct-token baseline per module (_projection 14, _calculation_actions 14, _verification_cross_period 6) and assert each module's count may only decrease.

## Outcome

A new carve-out above baseline fails the `<=` ratchet; the baseline only ratchets down. Commit `892faa383`.

## Notes
