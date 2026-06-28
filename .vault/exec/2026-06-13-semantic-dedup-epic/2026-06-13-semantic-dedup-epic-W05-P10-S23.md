---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S23'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C3-1 Consume the canonical iva_rate_kind and remove the rebuilt _iva_rate_to_iva_kind dict

## Scope

- `src/aeat/domain/iva/_invoice_classification.py`

## Description

- Re-verified at HEAD: `_iva_rate_to_iva_kind` (lru_cached) rebuilt the
  `IvaRate -> IvaRateKind` map already owned by `invoices._enums.iva_rate_kind`,
  used only at the classify-line call site.
- Deleted the rebuilt dict function; consumed the canonical `iva_rate_kind` via
  the existing lazy `from ..invoices import ...` that breaks the circular
  package-init, adding a type-narrowing guard (canonical returns `Optional`;
  the only keyless rate NOT_SUBJECT is already rejected above the call site).
- Updated the stale module comment and the `_iva_rate_to_domestic_category`
  docstring cross-reference to point at the public accessor.

## Outcome

Committed as `c35e34bd9`, tagged `relocation:iva_rate_kind`. Ruff clean (no
orphaned `IvaRateKind`/`lru_cache`); 261 IVA/invoices classification tests
green. No public shape change. Completes Pass-2 warm-up phase W05.P10.

## Notes

The None-guard branch is unreachable given the NOT_SUBJECT rejection above; it
exists for type-narrowing the `Optional` canonical return into the non-optional
`rate_kind` model field.
