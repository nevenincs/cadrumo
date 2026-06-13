---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S142'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s142-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S142`

Closed `AFR-040` for the outbound storage provider factory.

## Description

- Reviewed `src/aeat/adapters/outbound/storage/_factory.py` against the `active-profile` and `remote-provider` scanner signals.
- Removed eager concrete backend imports from the factory module so importing the public storage surface no longer imports the local or Google Drive provider implementations.
- Preserved the factory as the single public construction API while moving concrete provider imports into the selected provider branch.
- Routed provider-kind and Google Drive setup refusals through `translated_message` keys and structured contexts.
- Added real active-profile coverage proving the local provider factory uses the isolated runtime profile bucket root.
- Added import-boundary coverage proving concrete provider modules are not imported at factory module top level.
- Added localized refusal coverage for blank provider kind, unknown provider kind, missing Google Drive root folder id, missing Google OAuth client, and missing Google OAuth token.
- Updated locale catalogs through `python -m aeat.locales scaffold` and `python -m aeat.locales set`.
- Resolved the reviewer medium test-completeness finding by adding real secure-session-store coverage for the Drive missing-client and missing-token branches.
- Closed `W12.P26.S142` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-040` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_factory.py src/aeat/adapters/outbound/storage/test_foundation.py -k "factory or public_surface"`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_factory.py src/aeat/adapters/outbound/storage/test_factory.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `rg -n "Settings\(|PROJECT_ROOT|os\.environ|print\(|typer\.echo|# noqa|pragma|type: ignore|except Exception|except BaseException|monkeypatch|_Fake|_Stub|skip\(|xfail" src/aeat/adapters/outbound/storage/_factory.py src/aeat/adapters/outbound/storage/test_factory.py`

## Notes

The source scan intentionally returned no matches for direct settings construction, project-root constants, direct environment access, print/echo output, suppression pragmas, broad exception catches, monkeypatching, test fakes/stubs, skips, or xfails in the S142 slice.

The locale scaffold initially refused direct `set` because the new keys were not yet discovered. The factory now passes literal `translated_message` keys so the canonical locale scanner can discover and audit the surface.

The `google_auth_import_failed` branch remains an environment-failure branch; it is localized and typed, but not forced in tests with monkeypatching or dependency shadowing.
