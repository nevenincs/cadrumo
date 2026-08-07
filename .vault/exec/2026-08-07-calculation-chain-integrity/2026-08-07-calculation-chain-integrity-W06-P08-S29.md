---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bb0fe89410baa51435ca62b0adcc2328f3e2688025a7906f177ea1d27a1078ae'
step_id: 'S29'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S29

## Outcome

Done and verified at HEAD. Both accessors sit on the `domain.iva` public facade, so no cross-package consumer dots into the private module.

## Verification

`domain/iva/__init__.py` imports `domestic_categories_by_rate_kind` and `rate_kind_for_domestic_category` (lines 61-62) and lists both in `__all__` (lines 269, 286).

The application-layer consumer reaches them correctly: `application/aggregation/_iva_ledger.py:76` imports from the package, never from `_classification`. The only importer of the private module is its sibling inside the same package (`domain/iva/_invoice_classification.py:52`), which is intra-package and therefore fine.

## Why the promotion had to precede the consumption

The Step's ordering, promote before any application-layer consumer reads it, is `service-imports-via-top-level-reexports` applied in advance rather than repaired afterwards. A consumer landing first would have had to dot into `_classification`, and that reads to every later consumer as permission to do the same. Both halves landed together, so the precedent never existed.

The mapping is exposed as a read-only view rather than the mutable dict, so a consumer cannot mutate the shared taxonomy through the accessor.
