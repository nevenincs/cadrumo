---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:333b457459b782787ceb79ce8c2076e0fa42051feb5470801559f0658ce12a29'
step_id: 'S19'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Reconcile the rich-invoice IvaRate enum against the registry rate table, closing the missing members rather than leaving a rate the registry knows and the record cannot express

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Measure the registry's Spanish numeric IVA rate coverage directly from `rates.toml` (bypassing the enum) and confirm the served window starts 2024-01-01, carrying exactly `general/21`, `reduced/10`, `super_reduced/4`, `zero/0`.
- Confirm `IvaRate`'s numeric slots (`RATE_0`, `RATE_4`, `RATE_10`, `RATE_21`) already equal that set; no enum member is missing and no unresolvable member exists, so no enum change ships.
- Add a parity gate under the invoices domain test folder asserting `numeric_iva_rate_percentages()` equals the registry's numeric ES rate set for the served window, and a companion assertion over rate kinds.
- Add a mutation-proof test demonstrating the equality comparison discriminates: perturbing either the registry-side or enum-side set by one member flips agreement to disagreement, so the gate is not vacuously true.
- Pin the `RATE_5` absence as an explicit invariant test tied to the registry carrying no matching rate for the served window.

## Outcome

Registry-vs-enum agreement confirmed both independently (raw TOML parse) and through the loaded `IvaRateRecord` table: both declare `{0, 4, 10, 21}` for Spain across the served window (2024-01-01 onward, continuous through the open-ended 2025 window). No enum member was added or removed. Landed `src/cadrumo/domain/invoices/tests/test_rate_parity.py` with four tests: numeric-percentage parity, numeric-kind parity, the RATE_5-absence invariant, and the mutation-discrimination proof. Full invoices test folder plus the IVA rate-table tests (138 tests) pass.

## Notes

No production code changed; the Step's gap premise (a missing 5% enum member) was disproven at HEAD before implementation began, so the deliverable narrowed to the parity gate the ADR's corrected ruling calls for. Two files were left untouched though touched by peer work in the same working tree during discovery (`src/cadrumo/domain/iva/_components.py`, `src/cadrumo/domain/invoices/_decomposition.py`) — out of this Step's scope and not committed here.
