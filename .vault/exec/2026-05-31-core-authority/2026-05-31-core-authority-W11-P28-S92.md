---
step_id: S92
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S92 step record

## Step

Implement Clause 5 asserting no `domain.<a>` module imports from `domain.<b>._enums` for `a != b`, with anti-tautology proof.

## Status

BLOCKED

## Implementation

Added `find_sibling_domain_enum_imports()` to `src/aeat/diagnostics/_identity_placement.py`.
The detector walks every module under `domain/`, resolves relative and absolute imports,
and flags any `from domain.<b>._enums import ...` where `<b>` differs from the consumer's
subpackage and both are named (non-underscore-prefixed) subpackages.

Anti-tautology proof `test_sibling_domain_enum_detector_flags_synthetic_violation` added to
`src/aeat/diagnostics/test_identity_primitive_placement.py`. Proof passes.

## Blocked reason

The current tree has 4 violations (3 in test files + 1 production):

- `src/aeat/domain/iva/_invoice_classification.py:56` — imports `IvaRate` from
  `domain.invoices._enums`. Owning wave: W04 (enum centralisation / MERGE-013).
- `src/aeat/domain/iva/test_invoice_classification.py:13` — test import of `IvaRate` from
  `domain.invoices._enums`.
- `src/aeat/domain/iva/test_legal_basis_binding.py:37,243` — two test imports from
  `domain.invoices._enums`.

The zero-violation assertion `test_no_sibling_domain_enum_imports` is NOT added to the
test file until W04 closes the production violation.

## Commit

`8a08cac3f` — diagnostics(W11.P28): extend enforcement test to 10 clauses per Rule 11

## Files touched

- `src/aeat/diagnostics/_identity_placement.py` (detector added)
- `src/aeat/diagnostics/test_identity_primitive_placement.py` (proof added)
