---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P01.S03'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P01.S03`

Closed PERS-1: `SecureObjectRecord` roundtrip coverage now witnesses
all boundary fields and rejects a database-side metadata mutation.

- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Re-verified the audit finding against the current test module: the
existing encrypted persistence test asserted only payload equality.

Added a real repository roundtrip test that saves a secure object with
non-default namespace, object key, classification, schema version,
timestamp, and payload, then asserts equality against a full
`SecureObjectRecord` built from the persisted lookup digest and the
expected metadata.

Added an anti-tautology mutation test that updates the persisted
`schema_version` column directly in SQLite after a successful baseline
load. The real repository must then raise `EnvelopeVersionError` when
loaded with the original supported-version contract.

No fakes, mocks, monkeypatches, skips, or copied storage logic were
introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed.

`uv run pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed with 10 tests in 2.38s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S03` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P01-S03.md src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed.
