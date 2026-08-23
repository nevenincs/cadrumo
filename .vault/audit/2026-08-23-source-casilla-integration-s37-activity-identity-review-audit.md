---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:1469a6c5e717288263a94df4f24767951a848033ebc2842740169628b0da7601'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
---
# `source-casilla-integration` audit: `S37 activity identity remediation`

## Scope

Reviewed the reopened typed inventory selector contract against the accepted 2025 inventory mapping and the canonical inventory-ledger activity identity. The review excluded the concurrent S38 registry enrollment changes.

## Findings

### s37-activity-identity | resolved | Selector carries the exact inventory-ledger activity coordinate

The selector now requires the same strict non-empty `actividad_id` identity carried by `InventoryLedger`. Otherwise identical projections for different activities remain distinct, and serialization roundtrips retain the exact activity identity. Missing, empty, integer, and null identities refuse at validation.

The correction preserves the closed 2025 Modelo 100 operation vocabulary and exact destinations: complete acquisition cost to 0181, positive closing-minus-opening to 0177, and positive opening-minus-closing to 0182. Stale 0155, generic signed variation, unsupported grain, and source-readiness claims remain unrepresentable.

Formal review found no Critical, High, Medium, or Low issues. Twenty-four focused tests, Ruff, and `ty` passed.

## Recommendations

Proceed to S38 enrollment using this selector as the single inventory family contract. Do not duplicate or weaken the activity identity in registry dispatch or later resolution.
