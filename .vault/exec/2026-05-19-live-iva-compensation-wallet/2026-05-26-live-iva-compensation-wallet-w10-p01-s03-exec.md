---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---



# `live-iva-compensation-wallet` `W10.P01.S03`

Completed the first raw user-facing exception-message audit slice and removed
raw positional error messages from the live IVA compensation wallet adapter.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-26-live-iva-compensation-wallet-convention-regrounding-audit.md`

## Description

The live IVA wallet/Sede boundary no longer raises `SedeNavigationError` or
`SedeParseError` with raw positional user-facing strings. Auth-gate failures,
navigation failures, parser shape changes, missing wallet tables, wallet
execute-gate drift, representation-gate refusal, and wallet value parsing
failures now carry `translated_message` keys under the IVA wallet adapter
namespace. Recovery suggestions are restricted to existing CLI command
surfaces instead of prose instructions.

Wallet parse failures that involve captured row values now store only redacted
diagnostic context such as value length, SHA-256 fingerprints, row cell counts,
cause types, and bounded structural page shape metadata. The tests assert that
malformed wallet values do not appear in exception strings or context while the
abstract translation key remains present.

The repository-wide AST inventory still reports many raw exception-message
construction sites outside the wallet adapter. The largest remaining clusters
are calculation registry, outbound adapters, persistence, filing/modelo,
ledger, inbound parsing, domain IVA, live application services, and domain
validation models. These are recorded in the audit as remaining W10.P01 and
W10.P01.S04 work, not as completed cleanup.

Locale catalogue maintenance was run through `uv run python -m aeat.locales
scaffold --sync-locale-parity`; no locale YAML was repaired outside the locale
CLI.

The official plan-step CLI could not close `W10.P01.S03`; it returned `Step
'W10.P01.S03' does not exist in this plan`. The W10 row was closed manually
after reproducing the L4 step-addressing limitation.

## Tests

Passed:

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py -q --disable-warnings`
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py src/aeat/core/errors/test_exception_base_hygiene.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q --disable-warnings`
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/locales/cli.py src/aeat/locales/manager.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py`
- `uv run python -m aeat.locales audit`
