---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S144'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s144-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S144`

Closed `AFR-042` for the local filesystem storage provider.

## Description

- Reviewed `src/aeat/adapters/outbound/storage/_local.py` against the `plain-file` and `remote-provider` scanner signals.
- Added `translated_message` keys and structured contexts to local-provider validation, sidecar, payload I/O, not-found, integrity, corruption, and delete refusals.
- Replaced probe cleanup `contextlib.suppress` with sanitized debug logging so cleanup failures are not silent.
- Added real filesystem tests asserting localized validation, non-object sidecar integrity, and byte-length corruption errors.
- Removed raw local paths and OS exception strings from local provider probe report details.
- Suppressed low-level OS/JSON cause chains on translated local provider boundary errors.
- Updated locale catalogs through `python -m aeat.locales scaffold`, `python -m aeat.locales set`, and `python -m aeat.locales remove`.
- Removed four stale `cli.ledger.link.*` locale keys reported as extras by the canonical locale audit.
- Closed `W12.P26.S144` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-042` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_local.py src/aeat/adapters/outbound/storage/test_factory.py -k "local or factory"`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_local.py src/aeat/adapters/outbound/storage/test_local.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The local provider still uses filesystem paths in structured diagnostic context where path diagnosis is necessary; CLI rendering routes those through the central error/redaction boundary. Probe report details no longer include raw paths.

The cleanup catch in `probe()` is intentionally narrow and logs debug evidence before continuing with the probe result.
