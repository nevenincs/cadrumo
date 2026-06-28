---
step_id: S50
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P16.S50

## Summary

Extracted `TransactionCatalogueRepositoryProtocol` from `domain/transactions/_repository.py` to a new `domain/transactions/_protocols.py`. Moved module-scope adapter imports (`Envelope`, `ClassificationError`, `EnvelopeVersionError`, `SecureObjectRepository`, `SecureObjectWrite`) behind `TYPE_CHECKING` guard with deferred local imports in `load()` and `to_secure_object_write()` method bodies.

## Commit

`de1e11b23` — feat(transactions): extract TransactionCatalogueRepositoryProtocol to _protocols.py (MIGRATE-003 W06.P16.S50)
