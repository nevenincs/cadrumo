---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P04.S15'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P04.S15`

Closed BIND-1: counterpart row resolution no longer treats retired
`source = "invoice"` as a wildcard over every counterpart observation.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_counterpart_bindings.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Changed `resolve_counterpart_binding_row_values` to require exact
`observation.source_kind == binding.source` matching for every
counterpart row cohort. Added a regression proving a retired
`source = "invoice"` row binding only aggregates observations whose
`source_kind` is exactly `"invoice"`, rather than silently consuming
canonical `collectible_invoice` observations.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_counterpart_bindings.py` passed.

`uv run pytest -q src/aeat/domain/calculations/registry/test_counterpart_bindings.py` passed with 19 tests in 16.89s.

`rg -n -F 'source_kind == "invoice" or observation.source_kind == source_kind' src/aeat/domain/calculations/registry/_bindings.py` found no remaining wildcard expression.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S15` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P04-S15.md src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_counterpart_bindings.py` passed with existing CRLF normalization warnings for the plan file and `_bindings.py`.
