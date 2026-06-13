---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P10.S43'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
---

# `cross-campaign-hardening` `P10.S43`

Ran the final verification gate set for the closed hardening rows.

- Verified: locale parity
- Verified: CLI suite
- Verified: registry suite
- Verified: touched application / outbound suites

## Description

Executed the planned final gates after P09 closed. Two test regressions
surfaced during the first pass and were repaired:

- `test_export.py` still built a synthetic binding with the retired
  `source = "ledger"` kind; updated it to `ledger_transaction`, matching
  the P07.S32 source-contract removal.
- `test_referential_integrity.py` still called the informative-class
  invariant through `RegistryValidator`; updated the test to call the
  extracted `validate_informative_class_invariant` helper directly.

The profile-census CLI refusal assertion was also made robust to both
Typer-rendered output and exception text, preserving the same user-facing
message expectation.

## Tests

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run ruff check src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_export.py src/aeat/entrypoints/cli/test_profile_census_verbs.py` passed.

`uv run pytest src/aeat/entrypoints/cli -q` passed with 605 tests in 287.89s, with 8 `ofxparse` deprecation warnings.

`uv run pytest src/aeat/domain/calculations/registry -q` passed with 1819 tests in 786.99s.

`uv run pytest src/aeat/application/modelo -q` passed with 155 tests in 116.34s.

`uv run pytest src/aeat/application/user_profile -q` passed with 86 tests in 11.18s.

`uv run pytest src/aeat/application/filing -q` passed with 220 tests in 195.78s.

`uv run pytest src/aeat/adapters/outbound/aeat/sede -q` passed with 175 selected tests and 22 deselected in 47.45s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S43` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P10-S43.md src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_export.py src/aeat/domain/calculations/registry/test_schema_hygiene.py src/aeat/entrypoints/cli/test_profile_census_verbs.py src/aeat/_data/registry/aeat/modelos/100/revisions/2020/bindings/0001-renta-2020-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2021/bindings/0001-renta-2021-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-renta-2022-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2023/bindings/0001-renta-2023-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0001-renta-2024-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/0001-renta-2025-modelo-100-estimacion-directa-es-normal.toml` passed; Git repeated the pre-existing CRLF notices for the plan and `test_profile_census_verbs.py`.

## Residual Baseline

`uv run ruff check src/aeat .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P09-S42.md` was attempted as an extra repository-wide lint pass and failed on 115 pre-existing repository-wide findings outside the scoped S43 repair surface. The scoped lint gate above is green.
