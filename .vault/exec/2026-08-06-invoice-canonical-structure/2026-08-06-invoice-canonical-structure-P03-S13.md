---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:cd92a41a1b029b05452578ad941b530740c562b20b99cd9ed12f6c2ea28c8c30'
step_id: 'S13'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Remove the two-store union, the slim loader and the slim observation adapter from the invoice source resolver so exactly one store feeds M347 and M349

## Scope

- `src/cadrumo/application/invoices/_source_resolver.py`

## Description

- Delete the slim-store half of the resolve method: the loader call, its storage-degradation branch, and the observation loop.
- Delete the contiguous slim helper block -- loader, context filter, observation builder, unconverted-foreign check, euro coercion, Modelo 347 observation, date, clave, party tax id and country accessors.
- Delete the slim provenance builder and the slim source-kind accessor.
- Drop the slim repository constructor parameter and the now-unused imports.
- Retype the direction-to-settlement mapping to return the canonical core taxonomy member.

## Outcome

The resolver fell from 888 to 711 lines and the slim store has zero production readers. Exactly one store feeds Modelo 347 and Modelo 349.

The retype closed a duplication the semantic sweep surfaced: the slim direction enum was a byte-identical redeclaration of two members of the canonical binding source-kind enum -- a second home for a closed taxonomy that the single-taxonomy rule requires be singular. The mapping now returns the core member, which is what let the duplicate be deleted in the next Step.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/ -m "unit or integration"
    171 passed in 23.35s

    uv run --no-sync ruff check src/cadrumo/application/invoices/_source_resolver.py
    All checks passed!

## Notes

The two declarable-coverage proofs compared a live slim projection against a live canonical projection, so deleting the slim path would have destroyed the evidence they exist to carry. They were re-pinned to fixture-derived literals instead -- independent of either implementation, with one value grounded in the Modelo 349 clave table rather than read off an implementation.

Both passed first try with no fitting, which is genuine independent confirmation that the canonical path reproduces the retired facts rather than a test bent to match.

Five slim-wired tests were reconciled individually rather than swept. Three were deleted because canonical twins already cover them. Two asserted real capabilities with no canonical equivalent -- the Modelo 347 threshold floor and the consignment-clave refusal -- and were repointed onto canonical records instead.
