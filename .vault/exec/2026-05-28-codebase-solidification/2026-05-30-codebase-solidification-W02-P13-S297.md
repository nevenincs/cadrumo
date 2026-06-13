---
step_id: S297
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-iota6
commit: ae373e0f4
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P13.S297

Migrated wait-state literals to `_WAIT_DOMCONTENTLOADED` / `_WAIT_NETWORKIDLE` constants:
- `_iva_compensation_wallet.py`: 6 sites (3 domcontentloaded, 3 networkidle)
- `_groi_check.py`: 2 sites (networkidle)
- `_nif_iva_check.py`: 3 sites (networkidle)
- `_walker.py`: 6 wait_until sites + 1 wait_for_load_state site
- `_declarations.py` and `_censo_live.py`: already committed by parallel agent in prior commit 22904f4b5

Total: 16 sites migrated across 7 files (5 in this commit, 2 in prior).
