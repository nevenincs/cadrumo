---
tags:
  - '#research'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:df102f4db394bd067c580076aeee1ab4181bf9d53835d082a26598da42987489'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---

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
rectifications downstream (the former source file,

### Existing IVA axes do not encode the official deduction families

`IvaCategory`, rate, flow, and `InputClassification` are orthogonal authorities,
but none distinguishes current from investment goods. Existing registry selectors
cannot close the seven official pairs (the former source file,

### Existing transaction and invoice evidence can ground a stronger classification

Transactions retain invoice identity, IVA classification, sector identity, and
typed evidence provenance. Invoices retain linked transactions and rectification
evidence, but these identities are not propagated to the frozen observation

### Bienes-inversion regularisation lacks reciprocal asset linkage

`BienInversionIvaRecord` owns acquisition and regularisation facts but has no
authoritative acquisition-ledger or sector link. The casilla-43 resolver emits an
aggregate value rather than per-asset contributions, so allocating it backward
would invent authority (`src/cadrumo/domain/bienes_inversion/__init__.py:141`,
`src/cadrumo/domain/bienes_inversion/__init__.py:499`,

### The secure schema has no existing migration route

The bienes-inversion payload and namespace are version 1, while the upgrader
registry is empty. A cutover needs an atomic migration and refusal where evidence
cannot prove new classifications and links (`src/cadrumo/domain/bienes_inversion/__init__.py:79`,
`src/cadrumo/adapters/persistence/profile/bienes_inversion.py:112`,

### Replacement is safer than parallel or detached classification

Keeping `IvaLedgerInputKind` creates two owners and still cannot identify every
family. A detached envelope duplicates frozen-observation authority. Replacing it
with one closed deduction-family taxonomy, immutable provenance, and reciprocal
asset links is the only option that can support S49 without scalars or a second
store. The ADR must settle enum, linkage, adjustment, migration, and refusal.

## Sources

- `src/cadrumo/domain/bienes_inversion/__init__.py:79`
- `src/cadrumo/domain/bienes_inversion/__init__.py:141`
- `src/cadrumo/domain/bienes_inversion/__init__.py:499`

- `src/cadrumo/adapters/persistence/profile/bienes_inversion.py:112`
