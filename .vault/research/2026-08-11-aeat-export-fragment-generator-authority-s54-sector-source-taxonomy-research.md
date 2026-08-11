---
tags:
  - '#research'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a5392cbcfb3d33bc148e019997e779eddd7b2008ed771f5f65ef74351d31477c'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `aeat-export-fragment-generator-authority` research: `S54 differentiated-sector source taxonomy`

Casillas 700 through 735 cannot be projected from current canonical state: the
candidate-to-observation path discards adjustment identity, no closed axis
distinguishes current from investment deductions, and bienes-inversion lacks
reciprocal ledger and sector links. The evidence favors a new-only typed
classification and provenance cutover over retaining or inferring the old shape.

## Findings

### The frozen observation loses a live classification axis

`IvaLedgerCandidate` carries `IvaLedgerInputKind`, including signed adjustment
semantics, but `validate_iva_ledger_observation` constructs an
`IvaLedgerObservation` without it. The frozen contract cannot select
rectifications downstream (`src/cadrumo/application/aggregation/_iva_ledger.py:322`,
`src/cadrumo/application/aggregation/_iva_ledger.py:336`,
`src/cadrumo/application/aggregation/_iva_ledger.py:496`,
`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:365`).

### Existing IVA axes do not encode the official deduction families

`IvaCategory`, rate, flow, and `InputClassification` are orthogonal authorities,
but none distinguishes current from investment goods. Existing registry selectors
cannot close the seven official pairs (`src/cadrumo/domain/iva/_schema.py:38`,
`src/cadrumo/domain/iva/_flow.py:95`, `src/cadrumo/domain/iva/_prorrata.py:147`,
`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:756`).

### Existing transaction and invoice evidence can ground a stronger classification

Transactions retain invoice identity, IVA classification, sector identity, and
typed evidence provenance. Invoices retain linked transactions and rectification
evidence, but these identities are not propagated to the frozen observation
(`src/cadrumo/domain/transactions/_models.py:610`,
`src/cadrumo/domain/transactions/_models.py:835`,
`src/cadrumo/domain/transactions/_models.py:845`,
`src/cadrumo/domain/transactions/_models.py:848`,
`src/cadrumo/domain/invoices/_models.py:452`,
`src/cadrumo/domain/invoices/_models.py:508`,
`src/cadrumo/domain/invoices/_models.py:518`).

### Bienes-inversion regularisation lacks reciprocal asset linkage

`BienInversionIvaRecord` owns acquisition and regularisation facts but has no
authoritative acquisition-ledger or sector link. The casilla-43 resolver emits an
aggregate value rather than per-asset contributions, so allocating it backward
would invent authority (`src/cadrumo/domain/bienes_inversion/__init__.py:141`,
`src/cadrumo/domain/bienes_inversion/__init__.py:499`,
`src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py:281`,
`src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py:398`).

### The secure schema has no existing migration route

The bienes-inversion payload and namespace are version 1, while the upgrader
registry is empty. A cutover needs an atomic migration and refusal where evidence
cannot prove new classifications and links (`src/cadrumo/domain/bienes_inversion/__init__.py:79`,
`src/cadrumo/adapters/persistence/profile/bienes_inversion.py:112`,
`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:331`,
`src/cadrumo/adapters/persistence/storage/_schema_lineage.py:74`).

### Replacement is safer than parallel or detached classification

Keeping `IvaLedgerInputKind` creates two owners and still cannot identify every
family. A detached envelope duplicates frozen-observation authority. Replacing it
with one closed deduction-family taxonomy, immutable provenance, and reciprocal
asset links is the only option that can support S49 without scalars or a second
store. The ADR must settle enum, linkage, adjustment, migration, and refusal.

## Sources

- `src/cadrumo/application/aggregation/_iva_ledger.py:322`
- `src/cadrumo/application/aggregation/_iva_ledger.py:336`
- `src/cadrumo/application/aggregation/_iva_ledger.py:496`
- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:365`
- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:756`
- `src/cadrumo/domain/iva/_schema.py:38`
- `src/cadrumo/domain/iva/_flow.py:95`
- `src/cadrumo/domain/iva/_prorrata.py:147`
- `src/cadrumo/domain/transactions/_models.py:610`
- `src/cadrumo/domain/transactions/_models.py:835`
- `src/cadrumo/domain/transactions/_models.py:845`
- `src/cadrumo/domain/transactions/_models.py:848`
- `src/cadrumo/domain/invoices/_models.py:452`
- `src/cadrumo/domain/invoices/_models.py:508`
- `src/cadrumo/domain/invoices/_models.py:518`
- `src/cadrumo/domain/bienes_inversion/__init__.py:79`
- `src/cadrumo/domain/bienes_inversion/__init__.py:141`
- `src/cadrumo/domain/bienes_inversion/__init__.py:499`
- `src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py:281`
- `src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py:398`
- `src/cadrumo/adapters/persistence/profile/bienes_inversion.py:112`
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py:331`
- `src/cadrumo/adapters/persistence/storage/_schema_lineage.py:74`
