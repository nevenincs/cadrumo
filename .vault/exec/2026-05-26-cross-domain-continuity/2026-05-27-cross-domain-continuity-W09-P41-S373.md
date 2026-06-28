---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: S373
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W09.P41.S373`

M303 wallet-seed error guidance regression: route obsolete `--mode modelo` hint through `tr()` to iva-wallet seed verb; two fresh-profile raise sites updated; 4-locale parity; regression + anti-tautology CLI tests.

- Modified: `src/aeat/core/errors/registry/_domain.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Modified: `src/aeat/application/modelo/test_iva_wallet_engine_integration.py`
- Modified: `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`

## Description

Two `ModeloIvaWalletReconciliationBlocked` raise sites emitted bare positional strings, bypassing the i18n path. Pedro's fresh-profile M303 path hit one of these and received no actionable guidance — only the stale `default_suggestion="aeat app ledger preflight --mode modelo"` from the `ModeloAggregationBindingError` registry entry, which references a `--mode` flag that was never valid.

Changes:

- `_domain.py`: `ModeloAggregationBindingError.default_suggestion` changed from `"aeat app ledger preflight --mode modelo"` to `"aeat app ledger preflight"` (removes invalid flag). `ModeloIvaWalletReconciliationBlocked.default_suggestion` updated to the full seed command as a registry-level fallback.

- `_actions.py` (two sites): both fresh-profile raises (`decision is None AND caller value present` at line 1135; `persisted is None` at line 1202) now use `translated_message="application.modelo.errors.iva_wallet_not_seeded"` plus `suggestion="aeat app modelo iva-wallet seed --filing-year YEAR --period PERIOD --amount 0 --confirm"` so the i18n path fires and the seed verb surfaces as a `-> Run` hint.

- All four locale files: new key `application.modelo.errors.iva_wallet_not_seeded` with translations in en/es/ca/hu, naming the exact seed verb and explaining the zero-opening-balance first-filing purpose.

## Tests

- `test_iva_wallet_engine_integration.py::test_unpersisted_wallet_decision_cannot_feed_modelo_303_engine`: updated `match=` to assert `translated_message` attribute and `suggestion` contains `iva-wallet seed`. All 7 engine integration tests pass.

- `test_iva_wallet_inspector.py::test_m303_fresh_profile_binding_override_surfaces_seed_verb_not_mode_flag`: regression test — fresh profile + compensation binding override → error output contains `iva-wallet seed`, does NOT contain `--mode`.

- `test_iva_wallet_inspector.py::test_m303_fresh_profile_calculate_without_binding_override_does_not_raise_wallet_error`: anti-tautology — fresh profile calculate without binding override does not trigger wallet-seed error. All 15 inspector tests pass.

Locale audit: `python -m aeat.locales audit` shows 2 pre-existing missing keys unrelated to this change; 0 new gaps introduced.
