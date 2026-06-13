---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P07.S32'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P07.S32`

Closed BIND-3/BIND-4/BIND-5.

- Verified: `src/aeat/application/modelo/test_profile_binding.py`
- Modified: `src/aeat/domain/calculations/registry/test_selector_shape.py`
- Verified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Verified BIND-3 coverage for profile-sourced numeric bindings: the
Modelo 100 snapshot is extended in-test with a controlled
`source="profile"` decimal binding consumed by a formula, and the
resolver asserts the profile fact lands in `binding_values`, not
`enum_binding_values`.

Closed the BIND-4 stale-test gap by replacing the obsolete
free-form-source expectation with schema-level rejection coverage for
the retired `ledger`, `rental`, `vat`, and `category` source names.

BIND-5 is dispositioned in the plan row to the GEN-6 / coordinator task
that owns the estimacion-directa profile-auto-resolution decision, so no
duplicate registry behavior was introduced here.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/modelo/test_profile_binding.py src/aeat/domain/calculations/registry/test_selector_shape.py` passed.

`uv run pytest src/aeat/application/modelo/test_profile_binding.py -q` passed with 10 tests in 44.33s.

`uv run pytest src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/application/modelo/test_profile_binding.py -q` passed with 71 tests in 43.97s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S32` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P07-S32.md src/aeat/application/modelo/test_profile_binding.py src/aeat/domain/calculations/registry/test_selector_shape.py` passed.
