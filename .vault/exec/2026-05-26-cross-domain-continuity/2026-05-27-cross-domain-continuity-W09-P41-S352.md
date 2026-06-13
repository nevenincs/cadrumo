---
step_id: S352
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# S352: M303 iva-wallet seed verb

## Outcome

Implemented `aeat app modelo iva-wallet seed` CLI verb and `seed_iva_compensation_period` application function. First-time M303 operators can now bootstrap the carry-forward balance before local filing history exists.

## Commit

`c5a41d7c2` — S352: M303 iva-wallet seed verb — bootstrap carry-forward balance for first-time users

## Changes

- `src/aeat/application/calculations/_iva_compensation_history.py`: Added `IvaCompensationSeedConflictError`, `seed_iva_compensation_period`. Seeds an `IvaCompensationPeriodState(status='seeded')` that flows through `_observation_from_iva_compensation_history` → binding prefill for `modelo-303-compensacion-pendiente-anteriores`.
- `src/aeat/entrypoints/cli/_modelo.py`: New `iva-wallet seed` command with `--filing-year`, `--period`, `--amount`, `--confirm`. Requires `--confirm`, refuses without active profile NIF, refuses duplicate periods via `IvaCompensationSeedConflictError`.
- `src/aeat/application/modelo/_actions.py`: Improved `ModeloAggregationBindingError` message for compensation binding override path — hints at the seed verb.
- `src/aeat/locales/{en,es,ca,hu}.yml`: 10 new CLI locale keys scaffolded (`seed_help`, `seed_filing_year_help`, `seed_period_help`, `seed_amount_help`, `seed_confirm_help`, `seed_confirm_required`, `seed_invalid_amount`, `seed_negative_amount`, `seed_no_nif`, `seed_conflict`).
- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`: 6 regression tests — persist + round-trip, anti-tautology amount proof, duplicate refusal, CLI happy path, CLI no-confirm refusal, CLI duplicate refusal.

## Investigation: --binding override rejection source

The rejection comes from `_actions.py:1730` (`_reject_caller_overrides_of_source_bindings`) in the engine — not a missing CLI registration. The error message was improved to suggest `aeat app modelo iva-wallet seed` when `compensacion-pendiente-anteriores` is among the rejected bindings.

## Gates

- 13/13 tests pass (all pre-existing + 6 new)
- ruff: 0 errors
- pyright: 0 errors on modified files
- locale audit: ok (en/es/ca/hu)
