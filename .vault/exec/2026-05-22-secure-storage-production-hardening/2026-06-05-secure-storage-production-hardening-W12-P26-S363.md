---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S363'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S363 - Close AFR-261 for submission preflight

Scope: close `AFR-261` for `src/aeat/domain/submission/_preflight.py` with signals
`plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_preflight.py` for direct remote-provider calls, secure-storage access,
  active-profile resolution, settings/environment access, and filesystem IO.
- Confirmed the module performs no physical storage or remote calls itself. It invokes
  injected `DeadlineWindowChecker` and `AuthProviderProbe` protocols and surfaces
  refusal results as typed `SubmissionPreflightError` instances.
- Confirmed refusal paths use localized `errors.refused.submission_preflight_*` keys
  with structured context, and provider-description failures are logged with
  `exc_info=True` before being chained.
- Confirmed current preflight relocation/locale work is present in HEAD
  (`64b3d79ef`) and the focused preflight tests pass.
- Closed `W12.P26.S363` through `vaultspec-core vault plan step check` and updated
  the `AFR-261` register status to `closed`.

## Outcome

`AFR-261` is closed. `_preflight.py` is a pure policy gate around injected protocols;
it is not a remote mirror writer, plaintext side-store owner, or secure-storage
repository owner.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/submission/_preflight.py src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/tests/test_engine.py -k "preflight"`

## Notes

The plan's `plain-file, remote-provider` signals are retained as scanner provenance.
The closeout disposition is that this file is policy-only; the remote/provider
behaviour is delegated to injected protocol implementations outside this module.
