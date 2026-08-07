---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f471b98707ddd1580b5e7d704f03d81d670894f475208977cef39f2ab3309192'
step_id: 'S81'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Assert the invoice-level identity holds exactly on a parsed multi-rate document with grand total equal to base plus IVA plus recargo and retencion outside it, red if per-line rounding is allowed to accumulate into the invoice-level total

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Assert the invoice-level identity on the parsed multi-rate document: grand total equals base plus IVA exactly.
- Assert the per-line parts reconstitute the invoice-level figures, so the identity is a real check rather than three constants agreeing.

## Outcome

Base 150,00, cuota 26,00, total 176,00 on the bundled two-rate fixture, with the two lines summing exactly to the invoice-level base and cuota.

Asserted at the invoice level rather than per line because per-line rounding is where drift accumulates: two lines each rounded half a cent the same way put a full cent on the total, and a document whose parts are individually plausible stops reconciling against the paper.

Retencion sits outside this identity by construction -- it is withheld from the payment, not deducted from the invoice -- so the identity is base plus cuota plus recargo. This fixture carries neither a recargo nor a retencion, which is stated in the test rather than left for a reader to infer from the numbers.

## Verification

Red before the confirm-boundary fix, on the lost cuota rather than on rounding:

    AssertionError: assert Decimal('0') == Decimal('26.00')
    2 failed in 4.36s

Green after:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_confirm_multi_rate.py -m "unit or integration" -n 0
    2 passed in 8.05s

## Notes

The reconstitution assertion is the anti-tautology half. Without it the identity test compares three expected constants that were all read off the same fixture, and would stay green against an implementation that rebuilt the lines from the totals instead of carrying them through -- which is precisely the collapse S70 exists to catch.
