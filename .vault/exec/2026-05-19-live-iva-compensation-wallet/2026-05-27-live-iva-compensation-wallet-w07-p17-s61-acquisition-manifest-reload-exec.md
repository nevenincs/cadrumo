---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'W07.P17.S61'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W07.P17.S61`

Extended stored remote IVA evidence reload to include acquisition manifests.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`load_iva_remote_state` now returns redacted acquisition-manifest summaries in
the same backend report that already reloads filed-history state, carry-forward
lots, authority decisions, and wallet observations. The manifest row exposes a
hashed acquisition reference, target period, acquisition year range, success
flags, and per-surface outcome text. Raw acquisition object keys stay out of the
reload report.

## Tests

- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.
- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py` passed.
