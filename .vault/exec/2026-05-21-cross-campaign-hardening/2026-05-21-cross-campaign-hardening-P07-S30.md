---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P07.S30'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P07.S30`

Closed XDOM-7, XDOM-8, and XDOM-9.

- Modified: `src/aeat/application/ledger/_models.py`
- Modified: `src/aeat/application/ledger/_actions.py`
- Modified: `src/aeat/application/ledger/__init__.py`
- Modified: `src/aeat/application/ledger/test_actions.py`
- Modified: `src/aeat/adapters/outbound/aeat/browser/_site_health.py`
- Modified: `src/aeat/adapters/outbound/aeat/browser/__init__.py`
- Modified: `src/aeat/adapters/outbound/aeat/browser/test_site_health.py`
- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- Modified: `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`
- Verified: `src/aeat/adapters/outbound/aeat/sede/__init__.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

XDOM-7: introduced `LedgerTransactionPayload` as the typed application
projection for ledger transaction payloads and changed
`LedgerReviewRow.transaction` from `dict[str, object] | None` to
`LedgerTransactionPayload | None`. The existing projection helper now
constructs and validates that pydantic model before returning the
CLI/API payload.

XDOM-8: exposed `validate_site_health_url` from the public browser
adapter surface and re-pointed diagnostics to that helper instead of
importing the private `_URL_ADAPTER`.

XDOM-9: verified `IvaCompensationWalletObservation` is exported from
the public `sede` package and re-pointed the wallet reconciliation
application import to that public surface.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/application/diagnostics.py src/aeat/adapters/outbound/aeat/browser/_site_health.py src/aeat/adapters/outbound/aeat/browser/__init__.py src/aeat/adapters/outbound/aeat/browser/test_site_health.py src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/adapters/outbound/aeat/sede/__init__.py` passed.

`uv run pytest -q src/aeat/application/ledger/test_actions.py::test_query_ledger_review_rows_filters_exact_period_and_projects_rows src/aeat/adapters/outbound/aeat/browser/test_site_health.py::test_validate_site_health_url_is_public_browser_surface src/aeat/application/calculations/test_iva_wallet_reconciliation.py::test_wallet_reconciliation_uses_public_sede_observation_export` passed with 3 tests in 2.72s.

`uv run pytest -q src/aeat/adapters/outbound/aeat/browser/test_site_health.py::test_validate_site_health_url_is_public_browser_surface src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py` passed with 14 tests in 1.96s.

`uv run pytest -q src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py::test_query_ledger_review_rows_filters_exact_period_and_projects_rows src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/test_diagnostics.py` passed with 44 tests in 64.79s.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S30` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P07-S30.md src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/application/diagnostics.py src/aeat/adapters/outbound/aeat/browser/_site_health.py src/aeat/adapters/outbound/aeat/browser/__init__.py src/aeat/adapters/outbound/aeat/browser/test_site_health.py src/aeat/application/calculations/_iva_wallet_reconciliation.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/adapters/outbound/aeat/sede/__init__.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings for `_site_health.py`, `test_site_health.py`, and `test_actions.py`.
