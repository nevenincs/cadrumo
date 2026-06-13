---
step_id: S299
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

# codebase-solidification W02.P13.S299

Extracted named constants in `_renta_web_open.py`:
- `_VISIBLE_PROBE_TIMEOUT_MS: int = 2_000` — fast-path visible probe for casilla input fast-path
- `_ELEMENT_WAIT_TIMEOUT_MS: int = 10_000` — standard element wait/click budget

Migrated:
- `:283` `wait_for(state="visible", timeout=10_000)` → `_ELEMENT_WAIT_TIMEOUT_MS`
- `:291` `timeout_ms=10_000` in `_click_expected` → `_ELEMENT_WAIT_TIMEOUT_MS`
- `:341` `wait_for(state="visible", timeout=2_000)` → `_VISIBLE_PROBE_TIMEOUT_MS`
