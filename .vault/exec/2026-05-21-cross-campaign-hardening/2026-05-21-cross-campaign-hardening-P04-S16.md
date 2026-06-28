---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P04.S16'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P04.S16`

Closed BIND-2: snapshot-build selector validation now rejects retired
bare `source = "invoice"` bindings.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_selector_shape.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added an early fail-closed branch in `validate_binding_selector_shape`
for `binding.source == "invoice"`, returning a diagnostic that points
registry authors to canonical invoice-shaped sources:
`collectible_invoice`, `payable_invoice`, or
`purchase_invoice_evidence`.

Updated selector-shape coverage so a canonical `collectible_invoice`
binding remains accepted, while a bare `invoice` binding is rejected
before selector-shape validation.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_invoice_bindings.py` passed.

`uv run pytest -q src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_invoice_bindings.py` passed with 40 tests in 19.00s.

`uv run pytest -q src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed with 41 tests in 20.17s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S16` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P04-S16.md src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_selector_shape.py` passed with the existing plan-file CRLF normalization warning.
