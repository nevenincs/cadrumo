---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S56'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-02-live-iva-compensation-consultation-research]]'
---

# `live-iva-compensation-wallet` `W06.P15.S56` wallet live success

## Scope

Read-only AEAT IVA wallet/cartera verification, multi-year filed-history cross-check, and profile-local reload verification.

## Description

- Verified the implemented wallet parser/driver and central settings/constants with focused local gates.
- Removed a live-looking wallet amount from the wallet test surface before committing further work.
- Fixed a blocking committed `pyproject.toml` duplicate-key parse issue by merging the per-file ignore entries for the deterministic sampler test.
- Exercised the live read-only `aeat app live iva-wallet capture-remote-state` command against the active Cl@ve Móvil profile.
- Fixed filed-history fail-fast behavior so a per-declaration capture failure is accumulated and later periods can still be attempted.

## Outcome

Focused gates passed:

- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py pyproject.toml src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/core/config.py src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py`
- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/core/test_external_constants.py`

Live read-only evidence:

- A narrow 2026-only remote-state capture reused the persisted Cl@ve session and succeeded for both filed-history and wallet/cartera. Filed-history returned zero rows for that year slice.
- A first 2022-2026 full-span retry proved wallet/cartera success but filed-history failed on one 2024 declaration. A 2024-only retry then reproduced a declaration-observation timeout.
- After the filed-history loop fix, a 2024-only live retry succeeded with four Modelo 303 calculation observations and wallet/cartera success.
- The full 2022-2026 live retry then succeeded with 12 Modelo 303 calculation observations and wallet/cartera success.

Profile-local reload verification, without contacting AEAT and without printing private amounts, reported:

- 12 IVA compensation history rows.
- 8 carry-forward lots.
- 7 stored wallet observations.
- 17 acquisition manifests.
- Latest manifest range 2022-2026, target 2026/1T.
- Latest filed-history surface succeeded with 12 captured/calculation observations.
- Latest wallet/cartera surface succeeded with one wallet row.
- Latest authority decision is present, selected authority is `aeat_wallet`, divergence is `wallet_only`, and `blocked` is false.

## Notes

No AEAT write, filing, payment, confirmation, amendment, represented-taxpayer submission, or tax-return filing path was attempted. The only AEAT form action exercised was the guarded wallet read-query action. Exact live taxpayer identifiers and monetary amounts are deliberately omitted from this record.

The remaining open work is no longer "wallet cannot be read" for the observed live surface. It is now broader hardening: keeping the live test path open, expanding non-private regression coverage for exact-match/higher/lower/stale/local-incomplete divergence states, and verifying downstream Modelo 303 readiness/export behavior against the persisted wallet authority decision.
