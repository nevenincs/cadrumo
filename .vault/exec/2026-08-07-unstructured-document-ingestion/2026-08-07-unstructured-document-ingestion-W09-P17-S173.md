---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:94d58410a85a2c549982a047078389394454a6935274020fbc74febfe577ee72'
step_id: 'S173'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Migrate the intra-community predicates onto the identification axis, since the fact split landed at the model and producer layers and NOT in the decision table: the criteria carry both identification fields, the producer populates them at all three construction sites, four rows declare consuming the identification fact, and no predicate reads either field even once. Those rows key on a customer tax status that says the customer is registered somewhere and never where, substituting an establishment test for the identification the law requires, so a customer identified in another Member State whose establishment the reader could not settle fails to classify and a legitimate exempt intra-community supply is refused as missing data rather than reported as a defect. Ground the change against LIVA art. 25, which exempts on the acquirer being identified in another Member State, with a worked oracle, since this changes which operations classify and is legal behaviour rather than a refactor

## Scope

- `src/cadrumo/domain/iva`

## Description

## Outcome

## Verification

## Notes
