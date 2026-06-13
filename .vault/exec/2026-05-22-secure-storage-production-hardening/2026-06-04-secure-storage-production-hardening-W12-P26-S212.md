---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S212'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s212-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S212`

Closed `AFR-110` for the filing runtime schema/profile helpers.

## Description

- Reviewed `src/aeat/application/filing/runtime.py` against the
  `manifest-discovery` classification for manifest-bucket and plain-file
  signals.
- Verified registry TOML access is read-only bundled registry discovery through
  the runtime schema provider and validated registry authority.
- Verified active profile loading delegates to workflow and wizard runtime
  surfaces rather than constructing storage repositories or routes directly.
- Localized filing-runtime `ModeloBuilderError` surfaces through
  `translated_message` keys and structured contexts.
- Kept registry-root failure context path-minimized by exposing the registry
  root name rather than the absolute path.
- Added real-behavior tests for absent modelo lookup, blank modelo selection,
  missing requested modelo definitions, empty registry roots, partial
  filing-year/period selectors, and unsupported registry casilla data types.
- Enrolled locale strings through `python -m aeat.locales`.
- Closed the plan step through the vaultspec CLI and aligned the AFR register
  entry with the recorded closure.

## Outcome

`AFR-110` is closed as `manifest-discovery`. The file remains a registry
discovery and profile-projection composition point, not a secure storage
backend. The convention debt found during the review was closed in the same
step: user-facing runtime builder errors now carry localization keys, and the
empty-registry diagnostic avoids disclosing the absolute registry path.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/application/filing/test_runtime.py`
- `uv run --no-sync ruff check src/aeat/application/filing/runtime.py src/aeat/application/filing/test_runtime.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, `noqa`, `pragma`,
monkeypatch, fake, mock, skip, xfail, or tautological test was introduced.
The canonical locale scaffold also hydrated an already-discovered
`modelo_390_only` locale leaf in the same locale files; that came from the
central locale CLI, not from a manual YAML edit.
