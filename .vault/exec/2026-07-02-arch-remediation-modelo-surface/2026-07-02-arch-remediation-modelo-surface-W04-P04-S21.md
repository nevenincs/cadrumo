---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:dda02a5132b0718ba9b21e1cbbc25eb4549ed1f69f54a9009f73ecb384135d62'
step_id: 'S21'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Confirm the ratchet gate passes at the recorded baseline and fails on an injected per-modelo branch probe

## Scope

- `src/aeat/tests/test_generic_module_modelo_carveouts.py`

## Description

- Confirm the gate passes at the recorded baseline and detects an injected `Modelo.M999` / `_M999_*` probe (anti-tautology) while ignoring `_MAX_`/non-Modelo lookalikes.

## Outcome

5 tests pass: 3 per-module ratchets + the injection probe + the lookalike guard. Commit `892faa383`.

## Notes
