---
tags:
  - '#adr'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
related:
  - "[[2026-06-02-modelo-720-prior-year-baseline-adr]]"
  - "[[2026-06-02-modelo-720-prior-year-baseline-research]]"
  - "[[2026-06-02-modelo-721-cripto-data-fidelity-adr]]"
---

# `modelo-720-prior-year-baseline` adr: `M720 class-code taxonomy` | (**status:** `proposed`)

## Problem Statement

The Modelo 720 foreign-asset aggregation path now applies declarability by
regulatory obligation block, but the row projection still depends on a raw
class-code map that is not faithful to the official Modelo 720 record design.
The live code can emit `REAL_ESTATE` as `I`, even though position 102 of the
Modelo 720 type-2 record assigns `I` to participations in instituciones de
inversion colectiva and assigns `B` to bienes inmuebles. It can also expose a
`VIRTUAL_CURRENCY` code for Modelo 720, even though virtual currencies are a
Modelo 721 obligation and no `M` key exists in the Modelo 720 position-102 code
set.

This ADR fixes the taxonomy contract before the code migration. The decision is
narrow: which typed foreign-asset classes may project to a Modelo 720
`clave-tipo-de-bien-o-derecho`, which official code each emits, and how the
Modelo 721 virtual-currency split is represented without adding a new binding
source kind or resolver convention.

## Considerations

- The bundled AEAT Modelo 720 record design defines the position-102 code set as
  exactly `C`, `V`, `I`, `S`, and `B`: cuentas, valores/derechos, IIC
  participations, seguros/rentas, and real estate respectively.
- The same record design defines position 475, `clave-tipo-de-bien-inmueble`, as
  a secondary field that is completed only when position 102 is `B`. It does not
  make `I` a real-estate class.
- RD 1065/2007 keeps the declarability axis at the obligation-block level:
  cuentas under art. 42 bis, valores/derechos/seguros/rentas under art. 42 ter,
  inmuebles under art. 54 bis, and virtual currencies under art. 42 quater.
  That block axis is related to, but not identical with, the record-design
  position-102 class-code axis.
- Modelo 721 is the accepted structural twin for virtual currencies. The
  accepted Modelo 721 ADR grounds the sibling model on RD 1065/2007 art. 42
  quater and Orden HFP/886/2023, and states that 721 has a per-custodian/token
  axis rather than the Modelo 720 asset-class/country axis.
- The current `ForeignAssetClass` shape is close but incomplete for Modelo 720:
  it has account, security, real estate, insurance, and virtual currency, but no
  distinct IIC class. Correcting real estate without adding IIC would preserve a
  silent gap for the official `I` code.

## Considered options

- Keep the current five-class map and only change `REAL_ESTATE` from `I` to `B`.
  Rejected because it fixes the active real-estate miscode but leaves the
  official `I` key unrepresentable.
- Treat `SECURITY` as both `V` and `I` depending on subcategory. Rejected because
  a single typed enum member would no longer determine its official record code;
  row projection would need an implicit secondary convention.
- Add a distinct typed IIC class for Modelo 720, map real estate to `B`, and
  keep virtual currency outside the Modelo 720 projection. Chosen because it
  preserves a total, explicit mapping for every supported Modelo 720 position-102
  key while keeping Modelo 721 ownership of virtual currencies.
- Add a new binding source kind or resolver family for the split. Rejected
  because the Wave 1 freeze forbids new source kinds and resolver conventions;
  the distinction is a typed taxonomy correction, not a new source mechanism.

## Constraints

- The mapping from typed class to Modelo 720 code must be closed over the
  supported Modelo 720 classes and fail closed for unsupported siblings. A
  virtual-currency observation must not silently become a Modelo 720 row.
- No new binding source kind, resolver convention, validator convention, or
  row-source grouping is introduced by this decision. The existing `foreign_asset`
  row source remains the row-binding authority.
- The obligation-block threshold layer is already landed and is the parent
  feature for declarability. It remains stable because this ADR does not change
  threshold grouping; it only corrects the per-row class code emitted after a row
  is deemed declarable.
- The accepted Modelo 721 data-fidelity ADR owns virtual-currency registry
  authoring. Modelo 720 code may carry a shared typed enum member temporarily for
  threshold or ingestion compatibility, but Modelo 720 row projection must refuse
  it until a Modelo 721 projection owns that output.
- Any enum addition must reconcile all consumers in the same migration step:
  obligation-group mapping, tests, row projection, and any user-facing
  documentation comments that describe the class set.

## Implementation

The Modelo 720 class-code taxonomy is:

- `ACCOUNT` emits `C`.
- `SECURITY` emits `V`.
- A new distinct IIC class emits `I`.
- `INSURANCE` emits `S`.
- `REAL_ESTATE` emits `B`.

The new IIC class belongs to the same RD 1065/2007 art. 42 ter obligation block
as securities and insurance for threshold purposes. Real estate remains in the
art. 54 bis block. Virtual currency remains tied to the art. 42 quater / Modelo
721 obligation group and has no Modelo 720 position-102 output.

The row-projection migration should update the central typed class enum and the
Modelo 720 class-code map together. The projection helper must raise a clear
domain error when asked to project `VIRTUAL_CURRENCY` through Modelo 720 rather
than returning a fabricated or sibling-model code. Tests must pin the official
Modelo 720 code set and prove, through the live row-binding path, that real
estate emits `B`, IIC emits `I`, and virtual currency cannot be emitted as a
Modelo 720 row.

## Rationale

The official record-design field is the exporter contract, so the typed taxonomy
must make the official keys first-class. The prior baseline ADR correctly models
the declaration obligation as closed legal blocks, but the position-102 record
design is finer-grained inside art. 42 ter: values/rights, IIC, and
insurance/rents have separate row codes even though they share the same
obligation-block threshold. Collapsing that distinction into `SECURITY` would
move the ambiguity into projection code and recreate the silent-miscode risk.

The virtual-currency split follows the accepted Modelo 721 ADR. Virtual currency
shares the foreign-assets conceptual family and threshold shape, but it does not
share Modelo 720's row-code axis. Keeping it out of Modelo 720 projection is the
smallest correction that prevents under-specified exports while preserving the
existing Modelo 721 path for the sibling registry.

## Consequences

- Modelo 720 row projection can become a closed official-code mapping instead of
  a loose enum-to-character table.
- Real-estate rows stop being vulnerable to the `I`/`B` inversion, and IIC rows
  gain a real typed home.
- Virtual-currency observations fail closed in Modelo 720 until the Modelo 721
  registry/projection path owns them.
- The next migration step must touch shared taxonomy consumers carefully. A
  partial enum update would break totality tests or, worse, leave a supported
  class without a legal obligation group.
- This decision does not close the row-carrier mesh gap. It only establishes the
  official class-code contract that the later carrier and enrollment work must
  preserve.
