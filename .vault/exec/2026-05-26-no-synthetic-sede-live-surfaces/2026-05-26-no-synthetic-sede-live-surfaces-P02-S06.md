---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S06'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P02.S06`

Rewrote outbound Sede live-surface drivers to avoid live synthetic input.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_groi_check.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py`

## Description

The direct GROI and NIF-IVA read guard policies now declare
`synthetic_data_allowed = false`. Existing host pinning, browser-action
allow-lists, authentication flags, and read-only operation checks are unchanged,
so the live drivers continue to preflight the same query flow while refusing
AEAT-hosted synthetic input at policy construction time.

## Tests

`uv run --no-sync pytest -q src\aeat\adapters\outbound\aeat\sede\test_groi_check.py` passed with 20 tests.

`uv run --no-sync pytest -q src\aeat\adapters\outbound\aeat\sede\test_nif_iva_check.py src\aeat\adapters\outbound\aeat\sede\test_renta_web_open.py src\aeat\adapters\outbound\aeat\sede\test_renta_web_open_safety.py src\aeat\adapters\outbound\aeat\sede\test_renta_web_open_capture_replay.py` passed with 31 selected tests and 5 deselected live/opt-in tests.
