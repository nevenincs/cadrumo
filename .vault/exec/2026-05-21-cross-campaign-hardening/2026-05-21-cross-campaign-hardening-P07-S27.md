---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P07.S27'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P07.S27`

Closed CALC-4, CALC-5, and CALC-6.

- Modified: `src/aeat/domain/calculations/registry/_formula_runtime.py`
- Verified: `src/aeat/domain/calculations/registry/_bindings.py`
- Verified: `src/aeat/domain/calculations/registry/test_formula_runtime.py`
- Verified: `src/aeat/domain/calculations/registry/test_selector_shape.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

CALC-4: added a defence-in-depth note at `_initial_values` documenting
that Decimal-only validation is intentionally centralised at the
public `calculate_registry_snapshot` entry point via
`_reject_non_decimal`, before `_initial_values` handles registry
identity checks.

CALC-5: verified the typed per-source selector registry is already in
place in `_bindings.py`, with snapshot-time validation via
`validate_binding_selector_shape` and coverage in
`test_selector_shape.py`.

CALC-6: verified the formerly tautological annual-summary formula test
has already been replaced with structural assertions: binding ids are
present, `perceptores` is count-based, and aggregate outputs are
Decimal-valued without re-summing the same synthetic inputs in the test.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_registry_schema.py` passed.

`uv run pytest -q src/aeat/domain/calculations/registry/test_formula_runtime.py` passed with 15 tests in 25.81s.

`uv run pytest -q src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_registry_schema.py::test_validator_rejects_invoice_binding_without_typed_selector src/aeat/domain/calculations/registry/test_registry_schema.py::test_validator_rejects_invoice_binding_aggregation_mismatch` passed with 25 tests in 22.22s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S27` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P07-S27.md src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings for the plan and locale files.
