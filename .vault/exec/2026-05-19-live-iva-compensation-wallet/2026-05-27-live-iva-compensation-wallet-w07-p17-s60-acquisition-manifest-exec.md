---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'W07.P17.S60'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W07.P17.S60`

Persisted redacted live IVA remote-state acquisition manifests through the active
profile secure-object backend.

- Modified: `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

Added a centralized storage namespace for live IVA remote-state acquisition
manifests and wired the combined read-only acquisition path to persist a
profile-local encrypted manifest after each capture attempt. The manifest
repository now requires the active-profile secure-object runtime route by
default, so sessionless/root fallback storage cannot silently receive live
remote-state manifests. The manifest stores only redacted operational facts:
target period, year range, surface-level success/failure status, typed failure
mode, capture counts, reloaded filed-history count, and hashed wallet-decision
reference. It does not persist raw AEAT page text, exception messages, raw
taxpayer identifiers, local output paths, or cleartext wallet decision keys.

The acquisition report now carries the persisted manifest id when produced by
the live orchestration, and application helpers can persist, load, and list
manifests from the active profile route for later reconciliation and diagnostics.
The object key uses the full SHA-256 digest declared by the storage namespace
grammar.

## Tests

- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.
- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py` passed.
