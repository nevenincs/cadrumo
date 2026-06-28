---
step_id: S51
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P16.S51

## Summary

Extracted `InvoiceCatalogueRepositoryProtocol` from `domain/invoices/_repository.py` to a new `domain/invoices/_protocols.py`. The `InvoiceCatalogueRepository` already used deferred local imports throughout; the Protocol captures the `bucket_id`, `exists`, `load`, `save` surface.

## Commit

`c52787cc5` — feat(invoices): extract InvoiceCatalogueRepositoryProtocol to _protocols.py (MIGRATE-003 W06.P16.S51)
