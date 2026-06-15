---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S42'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C4 Extract a shared ledger catalogue load/save helper for the evidence and business-invoice modules

## Scope

- `src/aeat/application/ledger/_evidence.py`

## Description

- Re-read the C4 candidate (`application/ledger/_evidence` and
  `_business_operation_invoice` `_repository`/`_load`/`_save` helper triplet)
  under the substitutability pre-filter.

## Outcome

**Constraint-divergent / thin-idiom — NOT actioned.** The `_repository` helpers
already delegate to the canonical `secure_object_repository_for_bucket` (no
duplication there); the `_save` builders construct different document types with
a divergent `source_kind` axis (business-invoice) the evidence variant lacks;
and the only genuinely-shared fragment is the one-line load unwrap
`list(document.records) if document is not None else []` — an F4-class trivial
idiom whose extraction (a 2-line generic over 2 sites) provides negligible value.
Its natural home would have been the C3 single-catalogue base, which is itself
excluded as constraint-divergent (see S41).

## Notes

Folds into the S41 finding. No code change; the disciplined pre-filter verdict
is "no clean, non-leaky extraction exists."
