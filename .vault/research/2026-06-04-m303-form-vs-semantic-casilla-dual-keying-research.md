---
tags:
  - '#research'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-04'
modified: '2026-08-10'
body_hash: 'sha256:a83fa9130bdefc9e0978efa15b9154aa94e0418ccd21d1123e92a84f93a8c01f'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - '[[2026-08-07-official-form-coverage-audit]]'
  - '[[2026-08-10-casilla-schema-research]]'
  - '[[2026-07-10-modelo-303-regimen-simplificado-research]]'
---
# `m303-form-vs-semantic-casilla-dual-keying` research: `M303 semantic homes and fixed-slot projection grounding`

The S44 question is whether every Modelo 303 official field can be assigned to one existing or necessary semantic owner before the five record-design epochs are mapped. The evidence supports one projection architecture over several deliberately distinct canonical grains: calculation values, repeated filing rows, stable profile facts, filing-instance elections, presenter identity, and secure account values. It does not support a second official-box classifier, a second IVA aggregation path, or export-header dictionaries as semantic authorities. The ADR must settle the ownership and refusal rules; this research records the evidence and option trade-offs.

## Findings

### The official record is a projection target, not a semantic store

The accepted dual-key ADR already establishes semantic casilla identity as the calculation key and numbered official casillas as downstream projection endpoints. The official-form coverage audit expands the missing surface to annual-summary, five-row prorrata, and two-sector differentiated-deduction blocks, including the fact that the prorrata gap is row-shaped rather than a missing scalar. The accepted casilla-schema canonical-derivations ADR separately owns only the three-state question of whether a casilla is officially addressed; its `classify_official_boxes` result does not choose a producer or populate a value. These scopes compose if the fixed-width semantic map references canonical producers and never becomes another producer registry.

Alternative: make each parser field or export header key its own authoritative value. Rejected by the evidence because `_compose_export_headers` currently derives profile and filing facts into a mutable string dictionary, including `presenter_nif` from the taxpayer NIF, while the record design also contains casilla, draft, computed, constant, and account fields (`src/cadrumo/application/modelo/_export.py:705-800`). That dictionary is a transport assembly surface, not a typed persistence or calculation boundary.

### Existing legal-computation grains must not be collapsed into official rows

The IVA substrate already distinguishes whole-entity and sector calculations. `ProrrataInputs`, `ProrrataSector`, and `ProrrataResult` own legal prorrata inputs and results; the cross-period prorrata register persists year/sector state; transaction rows carry `prorrata_reference` and `prorrata_sector_id` into sector-aware aggregation (`src/cadrumo/domain/iva/_prorrata.py:107-205`, `src/cadrumo/domain/prorrata_register/__init__.py:100-220`, `src/cadrumo/domain/transactions/_models.py:633-682`). The official five-activity block is not the same grain as either the global percentage or differentiated sectors. A fivefold copy of the global scalar would fabricate activity detail; a second sector deduction sum for export would duplicate the calculation path.

The viable shape is a typed filing-row substrate for official activity identity and row-specific facts, with exact fixed-slot projection, while existing global and sector computations remain the only owners of their calculated totals. Where an official row consumes an existing computation, it references that result and carries provenance; it does not recompute it. Applicability with a missing row or referenced result must refuse export.

### Simplified-regime activity and module data need one collection, not numbered scalar slots

The live simplified-regime formula path consumes one IAE epigraph and three module-quantity casilla ids, and explicitly treats its table as partial advisory support (`src/cadrumo/domain/calculations/registry/_formula_runtime.py:1112-1235`). The proposed simplificado ADR correctly rejects a second resolver and retains manual box 48 until annual-Orden coverage is complete, but it leaves that decision in a sibling proposed record and describes the inputs as scalar support casillas. The official source contains repeated activity/module fields, so completing it by adding more numbered scalars would redeclare one capability per slot.

The evidence favors absorbing the one-formula/shared-Orden constraint into the governing dual-key ADR and replacing the scalar input shape with typed activity rows containing typed module quantities. The formula runtime remains the calculation owner; fixed source slots are transport projections of the collection. The existing proposed ADR can then be superseded without losing its one-mechanism constraint.

### Profile, elections, presenter, and accounts have different lifetimes and security boundaries

`TaxpayerProfile` and `ModeloIVAProfile` own stable taxpayer and IVA enrolment facts; refund and charge accounts are distinct typed profile values (`src/cadrumo/domain/deadlines/_models.py:425-590`). `PaymentElection`, `RefundElection`, and `PriorDomiciliationElection` are typed filing-instance choices in core and are resolved by the filing workflow, not profile defaults (`src/cadrumo/core/_payment_election.py:1-40`, `src/cadrumo/core/_refund_election.py:1-55`, `src/cadrumo/core/_prior_domiciliation_election.py:1-35`). The current export composer selects charge or refund account from the resolved disposition but also falls back from presenter identity to taxpayer identity (`src/cadrumo/application/modelo/_export.py:580-800`).

The lifetimes rule out one generic header bag. Stable profile facts must be projected from the persisted typed profile; elections and amendment evidence from the immutable filing instance; presenter identity from its own filing-instance model; and account bytes from secure storage only after disposition selection. Missing applicable values refuse rather than defaulting, aliasing presenter to taxpayer, or storing plaintext in registry/casilla rows.

### Applicability is the boundary between an honest blank and under-declaration

The official-form audit records that the annual-summary block is required only for the exonerated population and that making the flag settable before the block exists would create a live wrong-file path. The generator plan applies the same requirement to prorrata, differentiated sectors, simplified regime, amendment, payment, and account populations. Therefore blank is valid only after a typed applicability decision says the field or row is not applicable. An applicable population with an absent producer, incomplete required row, unresolved secure value, or unsupported parser field must refuse the whole export; reserve and constant fields remain parser-owned literals.

## Sources

- `2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr`
- `2026-07-01-modelo-303-regimen-simplificado-adr`
- `2026-08-07-official-form-coverage-audit`
- `2026-08-10-casilla-schema-canonical-derivations-adr`
- `2026-08-10-casilla-schema-research`
- `src/cadrumo/application/modelo/_export.py:580-800`
- `src/cadrumo/domain/deadlines/_models.py:425-590`
- `src/cadrumo/domain/iva/_prorrata.py:107-205`
- `src/cadrumo/domain/prorrata_register/__init__.py:100-220`
- `src/cadrumo/domain/transactions/_models.py:633-682`
- `src/cadrumo/domain/calculations/registry/_formula_runtime.py:1112-1235`
- `src/cadrumo/core/_payment_election.py:1-40`
- `src/cadrumo/core/_refund_election.py:1-55`
- `src/cadrumo/core/_prior_domiciliation_election.py:1-35`
