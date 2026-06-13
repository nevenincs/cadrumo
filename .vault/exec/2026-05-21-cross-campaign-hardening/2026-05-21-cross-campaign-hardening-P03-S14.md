---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P03.S14'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P03.S14`

Closed XDOM-6: the Cl@ve Móvil diagnostic namespace now has a public
auth-adapter export.

- Modified: `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/__init__.py`
- Modified: `src/aeat/application/auth/_diagnostics.py`
- Modified: `src/aeat/application/auth/test_diagnostics.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added public `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` on the auth adapter
surface and re-pointed auth diagnostics to import it from
`aeat.adapters.outbound.aeat.auth`. The private `_DIAGNOSTIC_NAMESPACE`
remains internal to `_clave_movil.py` for provider-local writes, but
application code no longer imports private adapter internals.

No fakes, mocks, skipped tests, or copied business logic were introduced.
The existing diagnostics test uses its pre-existing `monkeypatch`
fixture for environment isolation.

## Tests

`uv run ruff check src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/__init__.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py` passed.

`uv run pytest -q src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` passed with 29 tests in 4.99s.

`rg -n "from .*auth\\._clave_movil import _DIAGNOSTIC_NAMESPACE" src/aeat/application/auth src/aeat/adapters/outbound/aeat/auth -g "*.py"` found no remaining private diagnostic namespace import.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S14` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P03-S14.md src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/__init__.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py` passed with the existing plan-file CRLF normalization warning.
