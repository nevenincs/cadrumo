---
step_id: S92
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S92 step record

## Step

Implement Clause 5 asserting no `domain.<a>` module imports from `domain.<b>._enums` for `a != b`, with anti-tautology proof.

## Status

DONE

## Implementation

Fixed all 4 clause-5 sibling-domain _enums violations:

- `src/aeat/domain/iva/_invoice_classification.py:56` — changed from
  `from ..invoices._enums import IvaRate` to `from ..invoices import IvaRate`.
- `src/aeat/domain/iva/test_invoice_classification.py:13` — same fix.
- `src/aeat/domain/iva/test_legal_basis_binding.py:37` — changed to
  `from aeat.domain.invoices import iva_rate_percentage` (required adding
  `iva_rate_percentage` to `domain/invoices/__init__.py` public surface).
- `src/aeat/domain/iva/test_legal_basis_binding.py:243` — removed inline
  import of private `_IVA_RATE_TO_VAT_KIND`; rewrote test to use public
  `lookup_rate` and `iva_rate_percentage` helpers instead.

`iva_rate_percentage` exported through `domain/invoices/__init__.py`.

Zero-violation assertion `test_no_sibling_domain_enum_imports` added to
diagnostics test in S95 commit (covers clauses 5-8 together).

## Action class

MOVE (import path correction — no symbol relocation required)

## Commits

- `d49fdf3b9` — exec(core-authority): W11.P28.S92 clause-5 sibling-domain _enums fix

## Files touched

- `src/aeat/domain/iva/_invoice_classification.py`
- `src/aeat/domain/iva/test_invoice_classification.py`
- `src/aeat/domain/iva/test_legal_basis_binding.py`
- `src/aeat/domain/invoices/__init__.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py` (clause-5 zero-violation test added in S95)
