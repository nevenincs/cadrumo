---
step_id: S99
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W05.P26.S99 — IvaWalletBalanceReport + iva-wallet balance verb

## Deliverables

- `src/aeat/application/calculations/_iva_wallet_balance.py` (NEW): `IvaWalletBalanceReport` pydantic model (strict/frozen), `build_iva_wallet_balance_report(carry_forward)`, `query_iva_wallet_balance(as_of_year)`.
- `src/aeat/application/calculations/__init__.py`: exports `IvaWalletBalanceReport`, `build_iva_wallet_balance_report`, `query_iva_wallet_balance`.
- `src/aeat/entrypoints/cli/_modelo.py`: `iva_wallet_app` Typer sub-app + `balance` command wired to `app` as `iva-wallet`. Emits tab-delimited metric lines and JSON (`--format json`).
- `src/aeat/locales/{en,es,ca,hu}.yml`: three keys scaffolded and filled — `cli.app.modelo.iva_wallet.{group_help,balance_help,as_of_year_help}`.

## Logic

`next_expiry_year` = `min(source_filing_year + 4)` across lots with `remaining_amount > 0` and `expiry_review_state != EXPIRED_REVIEW_REQUIRED`. Includes ACTIVE (age ≤ 3) and EXPIRY_REVIEW_DUE (age = 4) lots. `None` when no such lots exist.

## Commit

`e9f45806c` — W05.P26.S99: IvaWalletBalanceReport + aeat app modelo iva-wallet balance verb

## Gates

- G2 (typed pydantic): `IvaWalletBalanceReport` strict/frozen, all fields typed.
- G3 (tr()): all operator-facing strings use `tr()` with `default=`.
- G4 (locale): `python -m aeat.locales audit` → `ok` all four files.
- G5 (no shims): no compatibility layers introduced.
