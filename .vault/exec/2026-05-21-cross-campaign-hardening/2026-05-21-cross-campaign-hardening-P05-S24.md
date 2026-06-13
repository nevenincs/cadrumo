---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P05.S24'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P05.S24`

Closed EXIM-3: the asset-ledger anti-tautology suite includes a
delete-field proof for `cost_basis`.

- Verified: `src/aeat/adapters/persistence/profile/test_assets_roundtrip.py`

## Description

The requested proof exists as
`test_assets_ledger_missing_cost_basis_surfaces_at_load`. It persists a
real encrypted assets ledger, edits the decrypted secure-object payload
through the SQL storage row, deletes `cost_basis`, and asserts
`AssetsLedgerRepository.load()` raises `pydantic.ValidationError`.

No duplicate test was added. The sibling mutation proof for a wrong
`cost_basis` value remains in the same file, so the suite covers both
mutate-field and delete-field anti-tautology paths.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/profile/assets.py` passed.

`uv run pytest -q src/aeat/adapters/persistence/profile/test_assets_roundtrip.py` passed with 3 tests in 1.30s.

`uv run pytest -q src/aeat/adapters/persistence/profile/test_assets.py` passed with 3 tests in 1.24s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S24` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P05-S24.md src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/profile/assets.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings for locale files.
