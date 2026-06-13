---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-01'
modified: '2026-06-01'
step_id: 'S676'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W27.P61.S676`

Corrected 5 stale line numbers in `_KNOWN_VIOLATING_LINES` after W26 comment insertions shifted `def` linenos by +1.

- Modified: `src/aeat/test_any_param_rationale_inventory.py`

## Description

The ratchet stored 171/367 for `_envelope.py` and 310/319 for `_borrador_100.py` and 400 for `_censo.py`. Actual `def` lines after W26 are 170/366, 311/320, 401 respectively. Updated all five entries to match reality.

## Tests

`test_any_param_rationale_inventory` — 1 passed. Ratchet green.
