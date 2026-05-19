---
tags:
  - '#adr'
  - '#code-duplication-sweep'
date: '2026-05-19'
related:
  - "[[2026-05-19-code-duplication-sweep-research]]"
  - "[[2026-05-19-spanish-tax-glossary-reference]]"
  - "[[2026-05-19-code-duplication-sweep-adr]]"
---

<!-- LINK RULES: wiki-links only in related field above. -->

# spanish-stem-terminology-authority adr: Spanish Stem Terminology Authority for Tax-Domain Identifiers | (**status:** accepted)

## Problem Statement

The code-duplication-sweep campaign audit catalogued large-scale English/Spanish terminology drift across the codebase:

- 189 identifier candidates flagged across src/aeat/** for stem drift (filing/modelo, declaration/declaracion, census/censo, borrador/draft/snapshot, vat/iva, renta/rental, etc.).
- 251 exception class definitions audited; 3 class-name collisions (StorageError, StorageValidationError, WorkUnitNotFoundError, plus the NoActiveBucketError family), one parent-class divergence on WorkUnitNotFoundError, and 2 dead exceptions.
- 23 numbered duplication findings in the deeper structural sweep, plus 13 adapter-layer ENG/ESP drift candidates concentrated in the outbound Sede artefacts (Declaration*, FiledDeclaration*) and the SQL ORM Rental*Row cluster.
- Public-API and persistence-layer surfaces are split between Spanish stems in some packages (domain/renta, domain/justificante, domain/modelos) and pure English in others (domain/vat, domain/rental, outbound Declaration*).

The prior code-duplication-sweep ADR proposed consolidating Value-Added Tax under English in domain/vat, with VatClassification absorbing IvaInvoiceClassification. The project lead has since declared Spanish stems authoritative for tax-system terms, reversing that direction and requiring a fresh decision document.

## Considerations

- The accepted Spanish-tax-glossary reference document cites the primary BOE or AEAT source for every canonical stem.
- Hexagonal boundaries must hold. Adapter renames ripple to wire formats; persistence renames carry schema-migration cost; domain renames stay in-process.
- The 189-row raw inventory contains known stem-stuttering proposals that must not be executed verbatim (e.g. BorradorBorrador, RentaRenta, FincasFinca).
- Zero-mock and roundtrip-discipline gates require that every rename flows through to real-adapter persistence tests; no rename is cosmetic.
- The campaign master tracker remains the code-duplication-sweep feature; this ADR is filed under that feature tag.

## Constraints

- Adapter-layer renames touching the outbound Sede contract must preserve wire-format compatibility with AEAT responses; identifier renames affect Python symbols only, never serialised payloads controlled by AEAT.
- Persistence renames where the identifier is encoded in column names, table names, or envelope schema headers require a strict roundtrip-test gate before and after the rename.
- Public CLI JSON contract field names are not in scope for this ADR.
- The Spanish-stem rule applies only to tax-domain identifiers as catalogued in the glossary reference. Infrastructure suffixes and international identifiers remain English.


## Implementation

### 1. Decision

Spanish stems are authoritative for tax-domain identifiers. The canonical stems, each grounded in the cited primary source, are:

- iva per Ley 37/1992 IVA (BOE-A-1992-28740). Supersedes vat, value_added_tax.
- irpf per Ley 35/2006 IRPF (BOE-A-2006-20764). Supersedes income_tax, personal_income_tax, pit.
- modelo per AEAT Sede Electronica nomenclature and the per-modelo Ordenes Ministeriales (e.g. Orden HFP/227/2017 for Modelo 303). Supersedes form, tax_form, return_form. Always followed by the three-digit modelo number.
- declaracion per Ley 58/2003 LGT Articulo 119 (BOE-A-2003-23186). Supersedes declaration, return when used in the LGT-119 sense.
- autoliquidacion per Ley 58/2003 LGT Articulo 120. Supersedes self_assessment, self_liquidation.
- justificante per AEAT Sede Electronica (CSV / justificante de presentacion workflow); regulatory framework Ley 40/2015 Articulo 27. Supersedes receipt, proof, confirmation when the artifact is the AEAT submission attestation. Does not absorb factura (commercial invoice, RD 1619/2012) or recibo (commercial receipt).
- borrador per Ley 35/2006 IRPF Articulo 98 (AEAT Renta Web draft). Supersedes draft, prefill when the entity is the AEAT-prepared Modelo 100 draft.
- renta per Ley 35/2006 IRPF (Titulo I, Capitulo I). Supersedes income in the IRPF base sense. Never collapses with English rental.
- fincas (singular finca) per Ley Hipotecaria (Decreto 1946, BOE-A-1946-2453) and RDLeg 1/2004 del Catastro Inmobiliario. Supersedes real_estate, properties when the unit is a registrable real-estate parcel.
- expediente per Ley 39/2015 LPAC Articulo 70 (BOE-A-2015-10565). Supersedes case_file, case when the artifact is the AEAT administrative expediente.
- censo per RD 1065/2007 RGAGI Titulo II Capitulo I (BOE-A-2007-15984). Supersedes census, taxpayer_registry. declaracion_censal for Modelos 036 / 037.
- ccaa / comunidad_autonoma per Constitucion Espanola Titulo VIII; financial framework LOFCA (Ley Organica 8/1980). Already standardised.

### 2. English exceptions (retained)

The following remain in English regardless of the Spanish-stem default and are explicitly composable with Spanish stems as suffixes:

- International identifiers fixed in BOE or ISO standards: NIF, CIF, NIE, IBAN (ISO 13616), SWIFT / BIC (ISO 9362).
- Python standard-library primitives: Decimal, datetime, bool, str, int. Never translated.
- Generic infrastructure suffixes used in adapter and persistence layers. These compose with Spanish stems; they do not replace them: Snapshot, Repository, Record, Row, Service, Factory, Validator, Observation, Protocol, Error, Selector, Catalogue, Store, Adapter, Driver, Oracle, Result, Payload, Ref, Spec, Kind, Status.
- Examples of valid composition: ModeloRepository, DeclaracionObservation, Borrador100Snapshot, JustificanteFetchError, FincaRow, CensoSyncService.

These suffixes remain English because they encode generic infrastructure roles, not tax semantics, and translating them would produce stem-stuttering or over-translation (FilaModelo, RegistroModelo, OracleVerificador).

### 3. Stem-stuttering rule

No rename may produce stem-stuttering. If the canonical stem already appears in the identifier, do not re-add it during the rename. The following raw-inventory proposals are explicitly invalid and must be filtered out by any executing agent:

- BorradorSnapshotNotFoundError to BorradorBorradorNotFoundError.
- Borrador100Snapshot to Borrador100Borrador.
- RentaIncomeType to RentaRentaType.
- RentalFinca to FincasFinca (also blocked on Renta vs Rental adjudication; Fincas is plural and incorrect as a singular class prefix in any case).
- Any Snapshot to Borrador rename where the entity is a generic state-capture (ProfileSnapshot, RegistrySnapshot, AeatGateEnvSnapshot, etc.).

The rule generalises: a single canonical stem appears at most once per identifier, and the surrounding tokens are infrastructure suffixes from the English-exceptions list.

