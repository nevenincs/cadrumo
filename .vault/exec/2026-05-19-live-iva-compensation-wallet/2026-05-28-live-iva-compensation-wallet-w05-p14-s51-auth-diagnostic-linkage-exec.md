---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S51'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W05.P14.S51`

Persisted redacted live-auth diagnostic linkage through the profile-local live
IVA acquisition storage path.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Reviewed: `.vault/audit/2026-05-28-live-iva-compensation-wallet-s51-review.md`

## Description

`LiveIvaAuthOutcome` now carries an optional `diagnostic_ref` derived from an
auth exception's `diagnostic_id` context using the existing redacted evidence
reference format. The raw diagnostic identifier remains in the encrypted auth
diagnostics namespace; the live IVA acquisition report, persisted acquisition
manifest, and reloaded remote-state summary expose only the hashed reference.

This links failed live IVA acquisition attempts to persisted auth diagnostics
when a profile runtime is available without placing Cl@ve page content,
operator-private object keys, or raw identifiers into IVA calculation evidence.

## Tests

- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py -q` — passed, 8 tests.
- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py` — passed.
