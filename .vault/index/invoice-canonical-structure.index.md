---
generated: true
tags:
  - '#index'
  - '#invoice-canonical-structure'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:14fd47418d0689ca1715b9aadf247c289d5ba2de859be58edc962c3bd4f03d34'
related:
  - '[[2026-08-06-invoice-canonical-structure-adr]]'
  - '[[2026-08-06-invoice-canonical-structure-audit]]'
  - '[[2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research]]'
  - '[[2026-08-06-invoice-canonical-structure-naming-and-capability-reference]]'
  - '[[2026-08-06-invoice-canonical-structure-plan]]'
  - '[[2026-08-06-invoice-canonical-structure-research]]'
  - '[[2026-08-07-invoice-canonical-structure-close-honesty-review-audit]]'
  - '[[2026-08-07-invoice-canonical-structure-decision-coverage-map-audit]]'
  - '[[2026-08-07-invoice-canonical-structure-fragmentation-sweep-audit]]'
  - '[[2026-08-07-invoice-canonical-structure-iva-treatment-axis-adr]]'
  - '[[2026-08-07-invoice-canonical-structure-iva-treatment-axis-research]]'
---

# `invoice-canonical-structure` feature index

Auto-generated index of all documents tagged with `#invoice-canonical-structure`.

## Documents

### adr

- `2026-08-06-invoice-canonical-structure-adr` - `invoice-canonical-structure` adr: `One canonical invoice aggregate; delete the slim store` | (**status:** `accepted`)
- `2026-08-07-invoice-canonical-structure-iva-treatment-axis-adr` - `invoice-canonical-structure` adr: `Where the IVA treatment axis lives on a multi-operation factura` | (**status:** `proposed`)

### audit

- `2026-08-06-invoice-canonical-structure-audit` - `invoice-canonical-structure` audit: `Fresh-context honesty review of the campaign`
- `2026-08-07-invoice-canonical-structure-close-honesty-review-audit` - `invoice-canonical-structure` audit: `Close honesty review: what a fresh inheritor finds behind the 38/38`
- `2026-08-07-invoice-canonical-structure-decision-coverage-map-audit` - `invoice-canonical-structure` audit: `Decision-to-Step coverage: all 21 ADR decisions checked against the tree`
- `2026-08-07-invoice-canonical-structure-fragmentation-sweep-audit` - `invoice-canonical-structure` audit: `Fragmentation sweep of the invoice and identifier surfaces`

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
- `2026-08-06-invoice-canonical-structure-P01-S32` - Enrol the invoice decomposition contract as a capability-inventory row with both production consumers and the modelos each serves, the renta sales-evidence gate running the full grounded check and the M349 gate narrowed to the two self-contradiction defects, and record which record classes each would exclude after the fold
- `2026-08-06-invoice-canonical-structure-P01-S33` - Prove decomposition parity, that an ex-slim record and a natively rich record carrying identical economic facts decompose to identical components and land on the same partition side, and decide per unmigratable class whether it decomposes correctly, refuses loudly or is flagged defective
- `2026-08-06-invoice-canonical-structure-P01-S34` - Re-decide the M349 treatment of an absent iva_category now that its stated justification is stale, the enum having gained intra-community service members in 7502ee65ed while the resolver docstring still says services map to no member, and either correct the reasoning while keeping the behaviour or change the behaviour, never leaving a filing-path guard resting on a false premise
- `2026-08-06-invoice-canonical-structure-P02-S04` - Prove the already-landed retention-rate and retention-amount writer options persist through the real encrypted namespace with a strict save-load-equality roundtrip plus an anti-tautology proof, the CLI and builder code having landed in ef0438561d and only the roundtrip gate remaining
- `2026-08-06-invoice-canonical-structure-P02-S05` - Add explicit recargo, iva-category, invoice-class and series options to the canonical writer and both entry verbs so every regime is expressible without inferring one from operation-type, holding the peer totals identity grand_total equals base_total plus iva_total plus recargo_amount with retencion outside it
- `2026-08-06-invoice-canonical-structure-P02-S06` - Accept operation-date on every entry verb including the guided one, so a guided entry can reach a declared devengo rank rather than only the proxy rank
- `2026-08-06-invoice-canonical-structure-P02-S26` - Widen the confirm-boundary override set from the extraction draft's field set to the writer's, adding retencion, recargo, invoice-class, series, rectifies-invoice-number, iva-category, operation-date and the missing iva-amount, so an operator confirming a rectificativa or a retencion-bearing invoice from evidence need not abandon the evidence path
- `2026-08-06-invoice-canonical-structure-P02-S27` - Make the recargo figure reachable at the confirm boundary and on the persisted invoice once the llm-package-split lane lands its draft-side recargo slot at W02.P04.S79, so the printed-total discrepancy that lane's reader already detects has somewhere to resolve to, this Step owning only the confirm side and never the draft model
- `2026-08-06-invoice-canonical-structure-P03-S11` - Repoint the five bare invoice verbs add, view, list, update and remove at the canonical aggregate and retire the catalogue sub-noun, keeping the operator noun and the kind issued-or-received flag exactly as the superseded ADR established them
- `2026-08-06-invoice-canonical-structure-P03-S12` - Record the lane-partition decision explicitly, whether the slim store's per-source-kind document partition is reproduced on the canonical home or consciously dropped in favour of the existing per-consumer gates, naming those gates and what each still guarantees
- `2026-08-06-invoice-canonical-structure-P03-S13` - Remove the two-store union, the slim loader and the slim observation adapter from the invoice source resolver so exactly one store feeds M347 and M349
- `2026-08-06-invoice-canonical-structure-P03-S14` - Delete the slim model, both services, the repository, the storage namespace and the BusinessOperationInvoiceDirection enum in one atomic explicit-path commit carrying every consumer, fixture and __all__ update, with no alias, bridge or re-export left behind
- `2026-08-06-invoice-canonical-structure-P03-S15` - Delete the slim CLI payload schemas and retire the blessing test that creates one invoice in both stores and asserts only that the ids differ, keeping the surviving link tests in that module
- `2026-08-06-invoice-canonical-structure-P03-S16` - Remove every locale leaf orphaned by the deletion through the locales CLI so all four catalogues stay in parity, then run the locale and apidocs drift gates
- `2026-08-06-invoice-canonical-structure-P03-S38` - Build the canonical invoice update operation before the bare verbs are repointed, because the canonical surface has create, view, list and remove but NO update, so repointing the five bare verbs would silently drop the operator's only way to correct a persisted invoice and deleting the slim store would remove the sole update surface with nothing named to replace it
- `2026-08-06-invoice-canonical-structure-P04-S17` - Delete the dead second Invoice writer and its tests outright rather than routing it, because the live bulk importer already routes canonically and routing would create a third import surface
- `2026-08-06-invoice-canonical-structure-P04-S18` - Rename InvoiceLine.category_id to state what it is, first confirming whether the preflight site using category_id with the spending-taxonomy meaning shares a serialised key with it or is unrelated, and sweeping data consumers as well as callers
- `2026-08-06-invoice-canonical-structure-P04-S19` - Add the plausibility gate at the confirm boundary refusing a document confirmed as ISSUED that was not plausibly issued by this taxpayer, mirroring the hard gate that already refuses an ISSUED invoice as purchase evidence
- `2026-08-06-invoice-canonical-structure-P04-S20` - Retire InvoiceKindOption and type the CLI kind option directly on InvoiceKind, in one atomic explicit-path commit across all thirteen sites
- `2026-08-06-invoice-canonical-structure-P04-S21` - Record that InvoiceKind STAYS in the iva domain and do NOT relocate it, because the enum is a shared direction axis both domains consume, domain/iva imports it at module level in two files while domain/iva references domain/invoices only under TYPE_CHECKING guards, so moving it would convert a clean one-way static dependency into a hard module-level cycle that two new deferred imports would then have to paper over
- `2026-08-06-invoice-canonical-structure-P05-S22` - Answer whether an invoice-only bucket can reach a filed M390 through the screen gap, tracing the M390 binding set to its value sources and settling whether both sides of the 390-to-303 reconciliation blocking rule derive from the same ledger, and encode the answer as a test rather than as prose
- `2026-08-06-invoice-canonical-structure-P05-S23` - Extend the invoice-versus-ledger screen past its ES-only counterparty filter so intracomunitaria, import and export invoices are screened, proving a non-ES invoice diverging from the ledger is now caught where it passes silently today
- `2026-08-06-invoice-canonical-structure-P05-S24` - Extend the screen past its four-cuota screened binding set to cover recargo de equivalencia, proving a recargo figure diverging from the ledger is caught
- `2026-08-06-invoice-canonical-structure-P05-S25` - Add an M390-scoped equivalent of the invoice-versus-ledger screen, because the 390-to-303 blocking rule compares two ledger-derived sides and cannot detect consistent under-population, proving a bucket whose invoices exceed its ledger is caught on the annual path

### plan

- `2026-08-06-invoice-canonical-structure-plan` - `invoice-canonical-structure` plan

### reference

- `2026-08-06-invoice-canonical-structure-naming-and-capability-reference` - `invoice-canonical-structure` reference: `Canonical verdict, conflation map, capability and custody grounding`

### research

- `2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research` - `invoice-canonical-structure` research: `Source discovery sweep: tangles, gaps and the joint scope`
- `2026-08-06-invoice-canonical-structure-research` - `invoice-canonical-structure` research: `Two invoice aggregates, one operator noun: canonicalisation scope`
- `2026-08-07-invoice-canonical-structure-iva-treatment-axis-research` - `invoice-canonical-structure` research: `Measured consumer set of the invoice IVA category, and the prorrata denominator trace`
