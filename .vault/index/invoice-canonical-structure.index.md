---
generated: true
tags:
  - '#index'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:7b294d9a65849c4d90d3a0a4cbce2ac0aa66a57e456f4da7164f45a47ae2a10c'
related:
  - '[[2026-08-06-invoice-canonical-structure-P01-S01]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S02]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S03]]'
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-audit]]'
  - '[[2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research]]'
  - '[[2026-08-06-invoice-canonical-structure-naming-and-capability-reference]]'
  - '[[2026-08-06-invoice-canonical-structure-plan]]'
  - '[[2026-08-06-invoice-canonical-structure-research]]'
---

# `invoice-canonical-structure` feature index

Auto-generated index of all documents tagged with `#invoice-canonical-structure`.

## Documents

### adr

- `2026-08-06-invoice-canonical-structure-adr` - `invoice-canonical-structure` adr: `One canonical invoice aggregate; delete the slim store` | (**status:** `accepted`)

### audit

- `2026-08-06-invoice-canonical-structure-audit` - `invoice-canonical-structure` audit: `Fresh-context honesty review of the campaign`

### exec

- `2026-08-06-invoice-canonical-structure-P01-S01` - Prove declarable coverage, that every declarable fact the slim store contributes today is reachable on the canonical path for both M347 per-party totals and M349 operator rows, asserting fact-level reachability and never output-equality with the double-counting two-store union
- `2026-08-06-invoice-canonical-structure-P01-S02` - Record that canonical M349 party identity is already conserved structurally and do NOT add eu_iva_id to the canonical aggregate, because a non-ES counterparty_country forces counterparty_tax_id to be that country's published NIF-IVA through the central NIF_IVA_FORMATS authority including the GR to EL prefix mapping, so a second identity field would install a second party-identity authority on the one axis where a disagreement mis-declares an intra-community operator, then hand the slim eu_iva_id versus counterparty_nif disagreement to the fold rule in S08 as a record class rather than a missing field
- `2026-08-06-invoice-canonical-structure-P01-S03` - Inventory every production slim-store consumer and record the named canonical replacement for each in the execution record, refusing to proceed to P03 while any consumer has no replacement

### plan

- `2026-08-06-invoice-canonical-structure-plan` - `invoice-canonical-structure` plan

### reference

- `2026-08-06-invoice-canonical-structure-naming-and-capability-reference` - `invoice-canonical-structure` reference: `Canonical verdict, conflation map, capability and custody grounding`

### research

- `2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research` - `invoice-canonical-structure` research: `Source discovery sweep: tangles, gaps and the joint scope`
- `2026-08-06-invoice-canonical-structure-research` - `invoice-canonical-structure` research: `Two invoice aggregates, one operator noun: canonicalisation scope`
