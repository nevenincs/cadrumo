---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S378'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S378 - Close AFR-276 for config CLI facade

Scope: close `AFR-276` for `src/aeat/entrypoints/cli/_config/__init__.py` with
signals `secure-object, active-profile, manifest-bucket, master-key, plain-file,
remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Re-grounded `_config/__init__.py` after concurrent branch changes materially
  decomposed and documented the config CLI surface.
- Audited profile lifecycle, repair, auth, apoderado, bucket-history, import/export,
  and Google app registration boundaries for direct secure-object, active-profile,
  manifest, master-key, plain-file, and remote-provider ownership.
- Confirmed the config facade delegates profile creation, switch, delete, rename,
  import/export, auth configuration, repair, and remote-provider operations into
  application/domain services rather than constructing raw SQL engines or direct
  secure-storage adapters in command handlers.
- Hardened exception containment by routing broad profile/log/import/status
  containment branches through the centralized logger at debug level before rendering
  operator-safe diagnostics.
- Verified user-facing refusals remain on `tr()` locale keys and existing core
  `AeatError`/CLI boundary errors.
- Closed `W12.P26.S378` through `vaultspec-core vault plan step check` and updated the
  `AFR-276` register status to `closed`.

## Outcome

`AFR-276` is closed. The current config CLI facade is enrolled as a transport facade
over application-owned profile, repair, auth, apoderado, bucket-history, and Google
subtrees. The remaining remote-provider implementation row is `AFR-277` for
`_config/_google.py`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/tests/test_config.py src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/tests/test_repair_bootstrap_exempt.py src/aeat/entrypoints/cli/_config/tests/test_repair_reset_state.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/_config/tests/test_config.py src/aeat/entrypoints/cli/tests/test_repair_bootstrap_exempt.py src/aeat/entrypoints/cli/_config/tests/test_repair_reset_state.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The shared worktree advanced while this row was being audited. The current HEAD already
contains the config-facade decomposition and debug logging hardening; this S378 closure
records the reconciled current state and leaves `AFR-277` open for the Google-specific
remote-provider implementation.
