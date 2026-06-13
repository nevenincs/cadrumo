---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P07.S28'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P07.S28`

Closed PERS-8 and PERS-9.

- Modified: `src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py`
- Modified: `src/aeat/adapters/persistence/storage/envelope/_envelope.py`
- Modified: `src/aeat/adapters/persistence/storage/envelope/test_envelope.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

PERS-8: added an on-disk bucket-manifest test that reads the emitted
`manifest.toml` text and asserts `created_at` and `last_unlocked_at`
are written as TOML offset datetime literals with ISO offset form.

PERS-9: made `EncryptionMetadata.associated_data_b64` a required
field. `EncryptionMetadata.from_blob(..., associated_data=b"")` and
explicit `associated_data_b64=""` still represent zero-length AAD, but
missing AAD metadata is now rejected as malformed/legacy metadata rather
than silently collapsed to empty AAD.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/envelope/_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py` passed.

`uv run pytest -q src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py` passed with 23 tests in 0.84s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S28` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P07-S28.md src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py src/aeat/adapters/persistence/storage/envelope/_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings for the plan and locale files.
