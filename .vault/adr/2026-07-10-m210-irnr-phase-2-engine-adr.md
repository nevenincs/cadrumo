---
tags:
  - "#adr"
  - "#m210-irnr-phase-2-engine"
date: '2026-07-10'
related:
  - "[[2026-07-10-m210-irnr-phase-2-engine-research]]"
supersedes:
  - '2026-07-09-m210-irnr-phase-2-engine-adr'
modified: '2026-07-17'
---
# `m210-irnr-phase-2-engine` adr: `M210 grouped-rentas and source-scope ingestion` | (**status:** `accepted`)

## Problem Statement

The original Phase 2 plan assumed that two outstanding M210 behaviours could
be added to its scalar, manual-input calculation engine: grouped-renta
legality (S06) and source-jurisdiction exclusion from the IRNR base
(S10--S12). Reconciliation showed that neither input has the facts needed for
that work. A scalar casilla cannot establish the code, payer, rate and
property/right identity of its component rentas; the ledger has no M210
income-code classification from which it can derive a lawful base observation.

This decision supplies those missing, distinct contracts. It is limited to
M210's grouping evidence and its transaction-ledger source projection. It does
not introduce a second calculation service, infer IRNR classifications from
generic IRPF categories, or alter the registry-owned M210 formula.

## Considerations

- Consolidated Orden EHA/3316/2010 requires grouped rentas to have the same
  tipo code, payer, rate and, where applicable, bien/derecho; only code 35
  permits multiple payers, and components may not offset each other.
- Consolidated TRLIRNR Article 13 is the generic Spanish-source authority.
  Articles 24 and 25 govern the base and rate consequences. Article 25.1 is
  not a substitute for Article 13 as the scope authority.
- `ModeloDetailRow` and `CalculationRevision.detail_rows` are the existing
  strict, persisted declaration-row channel. Existing verification predicates
  consume scalar values and must receive a declared row set explicitly rather
  than reconstructing it from casillas.
- The current transaction `irpf_category` taxonomy cannot identify the full
  official M210 income-code set. A classifier must require an explicit M210
  classification and retain its source transaction evidence.
- The accepted calculation taxonomy makes a registry-bound ledger projection
  the sole writer of a bound value. Filtering a manually entered computed base
  after calculation, or merging manual and ledger values, would create a
  parallel write path and lose provenance.

## Considered options

- **Keep scalar manual inputs and add a predicate.** Rejected: the predicate
  would have no component rows or statutory grouping keys to evaluate.
- **Reuse M353 `per_grupo_member` or a generic row fan-in.** Rejected: it
  aggregates filed observations across declarations and does not model
  intra-filing renta legality.
- **Copy Modelo 151's classifier and infer a code from `irpf_category`.**
  Rejected: the generic categories cannot distinguish M210's official codes
  and its annual-only base/window rules do not apply.
- **Persist M210 renta rows and project explicitly M210-classified Spanish
  source transactions through one registry ledger binding.** Accepted.

## Constraints

The M210 code axis, strict detail-row persistence, source-binding taxonomy,
and source-jurisdiction field are established, accepted parent surfaces.
Their contracts are stable enough to extend. The current M210 revision remains
manual-input based, so no source binding may be added until its selector,
target fact and source authority are declared together.

The bundled corpus presently gives a concrete Article 13.1.h property example,
but the implementation must bundle or cite the consolidated Article 13
generic rule before it marks generic source classification legally grounded.
This is a delivery gate, not permission to use Article 25.1 as a shortcut.
The full official M210 code list is registry data; the classifier must validate
against that declared list and may not silently enrol a smaller inferred subset.

## Implementation

### Grouped-renta declaration contract

Add a frozen `Modelo210AgrupacionRentaRow` to the existing detail-row union and
persist it with the calculation revision. Each row carries a stable row/source
identifier, one registry-declared official M210 tipo-de-renta code, a
non-negative component amount, the applicable rate, payer identity, and the
applicable bien/derecho identity. Code 35 records its multiple-payer exception
as an explicit payer mode; it is never encoded as a missing payer. The row
validator rejects blank identities, negative components, and invalid exception
combinations.

The selected official code is a durable M210 input/provenance field on the
calculation revision. It remains separate from the existing conceptual
`TipoRentaIrnr` text value used by formula and treaty-rate resolution: codes
such as `01` and `03` may share that rate concept but are not legally
interchangeable for aggregation or grouping.

When the operator elects M210 agrupacion/`0A`, the application boundary accepts
only the annual lease/sublease codes `01` or `35` in this M210 row set and
passes it explicitly to one registry-authorable row-set verification operator.
That operator verifies a non-empty set, a single tipo code and rate, one
identified bien/derecho, a single payer unless every component uses the
explicit code-35 exception, and no offsetting amount. It produces ordinary
typed verification findings. The rows prove declaration legality and
provenance only: the established registry formula remains the single arithmetic
path for manual M210 casillas.

### Ledger source-ingestion contract

Add a typed, persisted `M210IncomeClassification` on a transaction rather than
overloading `irpf_category`. It declares the official M210 tipo code, the
non-negative gross-income amount supplied to the M210 gross-income fact, payer
identity or code-35 payer mode, applicable rate, and bien/derecho identity when
applicable. Its code must exist in the revision's declared M210 code axis. It
is explicit operator/classifier evidence; no generic category, bank narrative,
or rate is treated as an implicit M210 code.

Add `ledger_irnr_income_aggregation` as a typed binding source and resolver.
For the selected M210 code and filing window it converts only explicitly
classified, incoming, Spanish-source (`ES`) transactions into typed
observations and provenance for the registry-owned gross-income target. The
binding owns that target when selected; caller-supplied scalar values are
rejected rather than merged. Manual grouped rows remain a legality/provenance
channel, while ledger mode derives the same statutory row facts from the
classification; the calculation boundary makes the modes mutually exclusive
for one target revision.

Every non-`ES` classification, including an unresolved jurisdiction, is
excluded before amount aggregation and becomes a typed M210 issue carrying the
transaction id and original jurisdiction (`None` remains distinguishable from
a foreign code). A Spanish-source transaction that lacks a complete explicit
M210 classification is also an issue, never a default admission. The resolver
turns issues into normal calculate-time diagnostics and retains only admitted
transaction ids in casilla provenance. A new localized issue surface is
authorised after these machine-readable reasons are settled.

## Rationale

The research document establishes that current M210 inputs are scalar and
manual, while the official grouping rule is relational across renta components.
The reference blueprint identifies the accepted strict row persistence seam
and the M151 classifier/resolver topology, while also documenting why neither
the M353 grouping path nor the M151 annual selector is reusable. This decision
uses the established seams without weakening their boundaries: a typed row set
for declaration legality and a separate typed ledger projection for source
scope and base provenance.

## Consequences

M210 can now prove grouping legality, retain source evidence, and exclude
foreign or unresolved-source income without silently changing the calculation.
The result supports all registry-declared M210 codes through explicit evidence
rather than a fragile inferred mapping.

The cost is a schema and migration surface for transaction classification, a
new source-binding family, and real behaviour tests through secure persistence.
Implementation must not broaden grouped rows into an alternate sum path, bind
the computed base casilla, use a free-text payer exception, or treat missing
jurisdiction/classification as Spanish-source admission. The follow-on plan
must close S06 and S10--S12 with those contracts before it localizes the issue
and closes cross-domain task #62.
