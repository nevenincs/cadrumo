---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:10ae2c8ee286015ec244a3d5b5c5960a969d5db68be33cdb2d0bb6a94910ff1d'
step_id: 'S146'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the non-negative canonical-decimal predicate once and route both CLI money validators through it, then add the assertion to the three payloads that stringified a bounded amount without re-asserting the bound

## Scope

- `src/cadrumo/core/decimal/`
- `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_payloads.py`
- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `src/cadrumo/entrypoints/cli/_app_live_iva_wallet_payloads.py`
- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`

## Changes

- `M` `src/cadrumo/core/decimal/_grammar.py`
- `M` `src/cadrumo/core/decimal/__init__.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_iva_wallet_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `verify:` predicate probed at 1234.56 / 0 / -1 / "" / NaN / abc / 1e3
- `verify:` M210 payload accepts rate 0.24 and 1, refuses rate 5, gross -5, rate abc
- `verify:` inventory refuses cogs -1; wallet history refuses a negative balance
- `verify:` `pytest core/decimal + payload gate + ledger contract -n 0 -m ""` -> 101 pass, 1 peer failure

## Notes

Second pass over the measured queue, and the measurement had to be corrected
first. Comparing constraint METADATA between a CLI payload and the record it
projects reported 400 disagreements, and the money ones were all false: every
flagged field is a `str` on the wire, so a `Ge(ge=Decimal(0))` bound cannot
apply to it. A stringified decimal cannot carry a Decimal constraint, and a scan
that reads metadata alone will say so 400 times.

Narrowing each CLI model to its single best inner match removed a second noise
class -- unrelated records pairing on a shared `snapshot_id` and `source_url`.

The real question turned out to be different and better: when a payload
stringifies a bounded amount, does it RE-ASSERT the bound in string form? Some
did and some did not, which is the same concept answered two ways.

Two answers, and two implementations of the answer. `_modelo_iva_wallet_payloads`
and `_ledger_payloads` each carried a non-negative-canonical-decimal validator,
and the second docstring already said it was the "same shape" as the first. Now
one predicate in `core.decimal`, with each caller keeping its own refusal --
the difference between them is real and worth preserving: an export column spells
an absent optional as "" and must accept it, a balance is always present and an
empty one is malformed.

Three payloads asserted nothing at all, so a negative balance, a negative cost
of goods sold or a negative gross income could reach the wire from a record whose
Decimal field forbids it. `_app_live_iva_wallet_payloads` and
`_ledger_business_payloads` had no validators in the module whatsoever.

`applicable_rate` needed the other bound, not this one. The M210 record bounds it
`ge=0, le=1` -- a share of one -- so asserting only non-negativity would have let
a rate of `5` onto the wire. Five hundred per cent reads as a plausible
percentage typed into a share field, so the upper bound is the half that catches
the real mistake. It routes through `is_unit_proportion`, the existing authority.

Two peer relocations interrupted verification mid-probe, both in the storage
namespace registry: first a module absent while its lazy map still named it, then
a duplicate namespace key. Both cleared on retry, so neither was stranded state
and neither was acted on.
