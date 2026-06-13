---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P08.S34'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P08.S34`

Closed PERS-10/PERS-11.

- Modified: `src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Verified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added explicit manifest TOML roundtrip witnesses for the under-covered
Argon2id KDF fields: `time_cost`, `parallelism`, and `output_length`.
The strict manifest equality check was already present; these assertions
make each parameter visible in the test failure surface.

Added `SecureObjectNamespaceIntegrity` validation coverage proving the
diagnostic model rejects an empty namespace and negative readable or
unreadable counts at construction time.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed.

`uv run pytest src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q` passed with 17 tests in 2.30s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S34` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P08-S34.md src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed.
