---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S86'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-live-iva-auth-read-acquisition-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
  - '[[2026-05-26-aeat-sede-constants-centralization-adr]]'
---

# Live Own-Name Representation Dispatcher Fix

Scope: `src/aeat/adapters/outbound/aeat/sede`, `src/aeat/application/live`, `.vault/exec`.

## Description

- Reproduced a live read-only wallet/cartera failure after authenticated session reuse.
- Classified the failure as a real guard regression: AEAT returned the centralized own-name `DialogoRepresentacion` dispatcher with `propio` selected, while the wallet driver only allowed a direct wallet form boundary.
- Narrowed the representation guard to accept only the existing direct wallet boundary or the centrally configured own-name dispatcher boundary.
- Kept representative mode fail-closed when the representative radio is selected.
- Added a second fail-closed guard for non-empty text-like represented-taxpayer fields before any representation submit click.
- Added non-private regression coverage for the live-observed dispatcher shape and the forbidden representative-selection shape.
- Re-ran read-only live capture for a 2026-only slice and a full 2022-2026 slice.
- Re-ran a 2026-only read-only capture after the represented-text guard was added.
- Reloaded profile-local evidence through secure storage and reported only aggregate counts and status labels.

## Outcome

Focused gates passed:

- `.venv\Scripts\python.exe -m ruff check src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- `.venv\Scripts\python.exe -m pytest -q src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py::test_own_name_representation_guard_accepts_dialogo_dispatcher_shape src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py::test_own_name_representation_guard_rejects_representative_selection src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py::test_own_name_representation_guard_rejects_prefilled_represented_taxpayer_text src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py::test_iva_wallet_read_guard_allows_own_name_representation_gate src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py::test_iva_wallet_read_guard_allows_wallet_execute_read_query`

Live read-only evidence:

- The 2026-only capture reused the persisted Cl@ve session, succeeded for filed-history, and succeeded for wallet/cartera.
- The 2022-2026 capture reused the persisted Cl@ve session, succeeded for filed-history, succeeded for wallet/cartera, and captured 12 Modelo 303 calculation observations.
- The post-review 2026-only capture still succeeded for filed-history and wallet/cartera with the stricter represented-text refusal in place.
- No fresh phone prompt was expected or observed for these successful retries because the persisted session remained valid.

Profile-local reload evidence, without contacting AEAT and without printing private values:

- 12 IVA compensation history rows.
- 8 carry-forward lots.
- 2 wallet authority decisions.
- 9 stored wallet observations.
- 20 stored acquisition manifests.
- The stored target authority decisions for 2026 1T and 2026 2T select `aeat_wallet`, carry `wallet_only` divergence, and are not blocked or stale.

## Notes

No AEAT filing, payment, confirmation, amendment, represented-taxpayer selection, or tax-return submission path was attempted. The only AEAT form actions exercised were the authenticated own-name dispatcher continuation and the guarded wallet read query.

The failed pre-fix live attempt is a real failure, not noise: wallet/cartera returned `dom_drift` because the guard rejected AEAT's own-name dispatcher. The fix is intentionally narrow and remains blocked for representative mode.

A bare Python reload attempt without the CLI root callback first failed for lack of an active bucket session, then later resolved a bucket id with no manifest. The CLI profile status remained healthy and the CLI live capture succeeded. This is tracked as a backend bootstrap ergonomics/routing follow-up, not as evidence that live wallet storage failed.
