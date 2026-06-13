---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P05.S18'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P05.S18`

Closed CALC-3: snapshot referential-integrity validation now asserts
that every `input_kind="bound"` casilla has a binding definition.

- Modified: `src/aeat/domain/calculations/registry/_validate_references.py`
- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Moved the missing-bound-input guard into the snapshot integrity layer by
adding a dedicated bound-casilla binding coverage check to
`_check_all_id_references`. Bound casillas with no binding now fail
snapshot construction before formula-runtime input resolution can see
them.

Added a regression that constructs a valid minimal revision, applies a
corrupted bound casilla through the model-copy path, and asserts
snapshot construction raises `RegistryValidationError` with the bound
casilla binding diagnostic.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_references.py src/aeat/domain/calculations/registry/test_referential_integrity.py` passed.

`uv run pytest -q src/aeat/domain/calculations/registry/test_referential_integrity.py::test_dangling_casilla_binding_reference src/aeat/domain/calculations/registry/test_referential_integrity.py::test_bound_casilla_without_binding_definition_fails_snapshot_integrity` passed with 2 tests in 0.19s.

`uv run pytest -q src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed with 41 tests in 22.15s.

`uv run pytest -q src/aeat/domain/calculations/registry/test_referential_integrity.py` was also run after the fix; 48 tests passed and `test_config_repair_report_includes_registry_integrity_check` failed on unrelated local state: `var/storage/buckets/36732be3-652a-4400-92b8-dcaf39e1e0a0` has a bucket manifest missing required lifecycle status.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S18` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P05-S18.md src/aeat/domain/calculations/registry/_validate_references.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only the existing CRLF normalization warning for the plan file.
