---
generated: true
tags:
  - '#index'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b41d5a3519aa6ec87eb6119797bf02fba75bc842b046962c983163681b1f855c'
related:
  - '[[2026-08-06-invoice-canonical-structure-P01-S01]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S02]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S03]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S08]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S09]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S10]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S28]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S29]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S30]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S31]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S34]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S35]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S36]]'
  - '[[2026-08-06-invoice-canonical-structure-P01-S37]]'
  - '[[2026-08-06-invoice-canonical-structure-P02-S07]]'
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
- `2026-08-06-invoice-canonical-structure-P01-S08` - Decide and implement the fold rule per unmigratable-record class, covering the empty counterparty_name, the null country_code, the totals that do not reconcile, the absent line concept and the bare Decimal iva_rate against the closed IvaRate enum, stating per class whether the fold synthesises, refuses or quarantines and never silently coercing a value the source record did not hold
- `2026-08-06-invoice-canonical-structure-P01-S09` - Remove the COLLECTIBLE_INVOICE default from InvoiceObservation.source_kind and make the direction axis required, after confirming every production construction site already passes it explicitly
- `2026-08-06-invoice-canonical-structure-P01-S10` - Carry created_at and updated_at onto the canonical aggregate or record their loss as a deliberate decision in the execution record, so no slim field disappears unremarked
- `2026-08-06-invoice-canonical-structure-P01-S28` - Produce the three-lane capability inventory covering income, business operations and purchase evidence, listing for BOTH stores every field, validator, CLI verb, downstream binding and persistence or custody behaviour, each with its named canonical replacement and the test that proves it, and scoping the field comparison to a per-axis diff of DEFAULTS AND NULLABILITY rather than field presence, because an axis that routes a filing can be permissive on the canonical side and strict on the slim side, which converts a loud failure into a quiet wrong answer and is invisible to a field-list inventory, treating any entry with no named replacement as a blocker on the fold rather than a waiver
- `2026-08-06-invoice-canonical-structure-P01-S29` - Strengthen the custody-carry proof for the canonical catalogue from a non-empty assertion to a strict save-export-import-load equality roundtrip with every defaultable field populated non-default, plus the anti-tautology proof that a mutated exported payload surfaces refusal or inequality
- `2026-08-06-invoice-canonical-structure-P01-S30` - Add the parameters that make the canonical writer reach parity with what the canonical model already claims to represent, namely invoice-class, series, rectifies-invoice-number and recargo-amount, which no production path can set today so every canonically written invoice is ORDINARIA with no series and no recargo by construction and rectificativas are unrepresentable
- `2026-08-06-invoice-canonical-structure-P01-S35` - Close the bucket-attribution asymmetry before the fold, making a persisted canonical Invoice carry a bucket_id by requiring it at the construction boundary rather than defaulting to None, and correcting the InvoiceCatalogueRepository ownership-guard docstring which today asserts as its stated justification that most invoices carry no bucket at all, a premise the production writers refute because every canonical construction path passes a resolved bucket_id
- `2026-08-06-invoice-canonical-structure-P01-S36` - Remove the ES counterparty-country default from both canonical entry verbs so an omitted country refuses or derives rather than silently stamping a domestic country on a foreign invoice, preserving the slim verb's derive-or-raise behaviour across the fold because country is the routing key for both informativas
- `2026-08-06-invoice-canonical-structure-P01-S37` - Give the canonical invoice write paths the bucket lifecycle events the slim store emits, because the canonical creation, mutation and deletion paths emit no bucket event of any kind while the slim services emit six dedicated event types and return their ids in the operator mutation result, so repointing the bare verbs would drop the invoice audit trail and the bucket-event-ids field together, and deleting the slim store would orphan six enum members that then need consumer reconciliation
- `2026-08-06-invoice-canonical-structure-P02-S07` - Stop synthesising exactly one line at BOTH synthesis sites, the canonical builder and the live bulk importer, accepting a supplied line set and proving a two-line invoice at different rates persists and aggregates per line with no persisted-schema change
- `2026-08-06-invoice-canonical-structure-P01-S31` - Write the capability-parity proof, a bucket exercising every capability of both stores run through the canonical path asserting identical M347, M349, M303 and M390 outputs and an identical export-import roundtrip, and if that proof cannot be written record that the fold is not ready and what is missing
- `2026-08-06-invoice-canonical-structure-P01-S34` - Re-decide the M349 treatment of an absent iva_category now that its stated justification is stale, the enum having gained intra-community service members in 7502ee65ed while the resolver docstring still says services map to no member, and either correct the reasoning while keeping the behaviour or change the behaviour, never leaving a filing-path guard resting on a false premise

### plan

- `2026-08-06-invoice-canonical-structure-plan` - `invoice-canonical-structure` plan

### reference

- `2026-08-06-invoice-canonical-structure-naming-and-capability-reference` - `invoice-canonical-structure` reference: `Canonical verdict, conflation map, capability and custody grounding`

### research

- `2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research` - `invoice-canonical-structure` research: `Source discovery sweep: tangles, gaps and the joint scope`
- `2026-08-06-invoice-canonical-structure-research` - `invoice-canonical-structure` research: `Two invoice aggregates, one operator noun: canonicalisation scope`
