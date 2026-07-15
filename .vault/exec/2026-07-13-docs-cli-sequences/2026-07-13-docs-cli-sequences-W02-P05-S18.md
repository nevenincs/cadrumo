---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S18'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement the executor-level anti-tautology proof that executes one representative sequence twice and asserts the pre-mask differing paths equal the central mask set exactly

## Scope

- `dev/docs/tests/test_sequence_goldens.py`

## Description

- Prove residual determinism exactly: a representative capture-threaded JSON sequence executed twice in fresh hermetic sandboxes yields pre-mask differing paths pinned to the residual non-deterministic set — EMPTY on today's enrollable surface — so any new residual path, masked or not, is a named regression that must be consciously enrolled.
- Pin the masked-field canary: no hermetic-reachable enrollable envelope surfaces a centrally-masked surrogate key in a fresh sandbox — every `snapshot_id` emitter is live-AEAT (unenrollable), and the one enrollable non-live `run_id` carrier (the diagnostics runs payload) lists per-run rows that are empty in a fresh sandbox, so the key never materialises; the representative sequence deliberately includes that diagnostics read so the canary scans the nearest surface that could emit a masked key. A failure means an enrollable surface started emitting one and the double-run proof must be extended to a sequence that genuinely exercises the flap before the assertion moves.
- Prove the mask bites exactly the declared set through the REAL compare path: a masked-field value flap injected into a real golden/live pair compares clean, while the identical flap under an undeclared key compares red with the key named.

## Outcome

The docs gate cannot silently rot into tautology from either direction: the mask cannot hide a real regression (claim 3b, plus claim 1's exact pin), and a masked-field flap cannot red the gate (claim 3a). The gate composes with the substrate's own anti-tautology proof, which exercises real live-capture envelopes carrying the masked fields.

## Notes

Honest deviation from the literal step text, agreed with the coordinator and adjudicated ACCEPT-AS-STRONGEST-HONEST by the P05 review: the plan asked the double-run pre-mask diff to "equal the central mask set exactly", but no hermetic-reachable enrollable envelope surfaces a masked key in a fresh sandbox — every `snapshot_id` emitter is a live-AEAT read (unenrollable by design, ADR D6), and the one enrollable non-live schema carrying `run_id` (the diagnostics runs payload) has empty per-run rows in a fresh sandbox — so strict equality against a non-empty mask is unreachable from any hermetic sequence. The gate instead pins the residual EXACTLY (empty), scans the diagnostics-runs surface in the representative sequence as the canary's nearest-could-emit coverage, forces a genuinely-flapping proof the day a masked key reaches an enrollable envelope, and proves mask-bite/mask-narrowness through the real compare functions by mutating real envelope documents (the same technique as the store's deleted-field proof).
