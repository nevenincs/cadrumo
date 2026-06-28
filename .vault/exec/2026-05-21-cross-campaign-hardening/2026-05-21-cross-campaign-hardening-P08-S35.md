---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P08.S35'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P08.S35`

Closed XDOM-11/XDOM-12.

- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/application/modelo/_profile_binding.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/modelo/test_declaration_period_binding.py`
- Verified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Exported `RegistrySnapshotRef` from the public registry package and
re-pointed filing to that public surface. Also exported the registry
runtime helpers that Modelo already consumes, then re-pointed Modelo's
imports away from private registry submodules.

Added non-303 declaration-period resolver coverage using real Modelo
111 and Modelo 100 snapshots extended in-test with controlled
informational `filing_year` / `filing_period` casillas. The monthly 111
case proves `"03"` resolves to `3`; the annual 100 case proves `"0A"`
resolves to `0`.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/__init__.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_profile_binding.py src/aeat/application/filing/__init__.py src/aeat/application/modelo/test_declaration_period_binding.py` passed.

`uv run pytest src/aeat/application/modelo/test_declaration_period_binding.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py -q` passed with 13 tests in 40.40s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S35` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P08-S35.md src/aeat/domain/calculations/registry/__init__.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_profile_binding.py src/aeat/application/filing/__init__.py src/aeat/application/modelo/test_declaration_period_binding.py` passed.
