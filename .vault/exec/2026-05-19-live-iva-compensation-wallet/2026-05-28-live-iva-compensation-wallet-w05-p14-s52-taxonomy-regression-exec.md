---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S52'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W05.P14.S52`

Added regression assertions proving typed live IVA auth failures are not
collapsed into success, zero-balance, or generic unavailable states.

- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Reviewed: `.vault/audit/2026-05-28-live-iva-compensation-wallet-s52-review.md`

## Description

The combined acquisition report tests now explicitly assert that an operator
missing-prompt Cl@ve timeout leaves auth and both live surfaces failed with
`no_clave_prompt`, never `authenticated` or `unknown`.

The wallet/cartera auth-gate test now asserts a filed-history success does not
turn the wallet 403 into a successful or zero-balance wallet observation:
wallet status remains failed, outcome remains `aeat_403`, and no captured-count
value is synthesized.

## Tests

- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_live_failure_taxonomy.py -q` — passed, 14 tests.
- `uv run ruff check src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_live_failure_taxonomy.py` — passed.
