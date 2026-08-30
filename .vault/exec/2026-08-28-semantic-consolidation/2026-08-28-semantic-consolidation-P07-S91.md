---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:63ca41c20111023bedef853f54264e0172a7008630526ad2e5a3850e5712cf6e'
step_id: 'S91'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the censo, attachments, categories, invoices and buckets facades, dissolving the invoices-iva import cycle the invoices namespace made spellable

## Scope

- `src/cadrumo/domain/`

## Changes

- `M` `src/cadrumo/domain/censo/__init__.py`
- `M` `src/cadrumo/domain/attachments/__init__.py`
- `M` `src/cadrumo/domain/categories/__init__.py`
- `M` `src/cadrumo/domain/invoices/__init__.py`
- `M` `src/cadrumo/domain/buckets/__init__.py`
- `M` `src/cadrumo/domain/iva/tests/test_invoice_classification.py`
- `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `verify:` `pytest src/cadrumo/domain/{censo,attachments,categories,invoices,buckets} src/cadrumo/application/invoices src/cadrumo/domain/iva/tests -n 0 -m ""` -> `pass`

## Notes

The invoices namespace re-exported three names belonging to domain/iva while
iva imported back into invoices for IvaRate. The cycle is dissolved, not moved:
iva reaches invoices.enums directly and its own tests stop importing its own
functions back through the invoices facade.
