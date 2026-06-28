---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P01.S04'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P01.S04`

Closed PERS-2: `SecretRecord` roundtrip coverage now witnesses the
complete record and the JSON index participates in retrieval.

- Modified: `src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Re-verified the audit finding against the current secret-store tests:
the existing roundtrip asserted only value, metadata, and classification.

Added a strict equality test that persists a `SecretRecord` with a
non-default key, value, classification, metadata, created timestamp, and
expiry timestamp through the real `SecretStore`, then asserts
`store.get(record.key) == record`.

Added a JSON-index anti-tautology test that first proves the baseline
record loads, then mutates the persisted `index.json` blob reference for
that digest to a non-existent SHA-256. A subsequent real `store.get`
must raise `BlobNotFoundError`, proving retrieval depends on the
persisted index rather than the test fixture mirroring the input object.

No fakes, mocks, monkeypatches, skipped tests, or copied storage logic
were introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py` passed.

`uv run pytest -q src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py` passed with 19 tests in 1.15s.

`uv run ruff check src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py` passed.

`uv run pytest -q src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py` passed with 9 tests and 1 pre-existing POSIX-only skip in 0.93s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S04` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P01-S04.md src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py` passed.
