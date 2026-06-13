---
tags:
  - '#reference'
  - '#spanish-tax-glossary'
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# spanish-tax-glossary reference

Authoritative glossary of Spanish tax-system terms for the AEAT codebase
reconciliation campaign (master tracker tag: code-duplication-sweep). The
project lead has declared Spanish stems authoritative for tax-system
nomenclature; this reference documents each canonical stem, the English
forms currently mixed into the codebase, the primary BOE or AEAT source,
the precise semantic scope, and the migration decision.

Each entry cites a primary legal source. Citations were verified against
boe.es consolidated texts and AEAT Sede Electronica manuals on
2026-05-19. Entries marked UNVERIFIED require user sign-off because no
authoritative URL could be reached during verification.

## Decision summary

Spanish stems win for: IVA, IRPF, modelo, declaracion, autoliquidacion,
justificante, borrador, renta, fincas, expediente, censo, CCAA.

English exceptions retained: NIF, CIF, IBAN, SWIFT (international
identifiers fixed in BOE / ISO standards), Decimal, datetime (Python
primitives), Snapshot, Repository (generic infrastructure terms used
strictly inside adapter and persistence packages).

## Glossary entries

### IVA (Impuesto sobre el Valor Anadido)

- Canonical Spanish form: iva.
- English equivalents currently in codebase: vat, value_added_tax,
  value-added tax.
- Primary source: Ley 37/1992, de 28 de diciembre, del Impuesto sobre el
  Valor Anadido (BOE num. 312, 29 de diciembre de 1992;
  BOE-A-1992-28740). Verified.
- Semantic scope: Spanish consumption tax on supplies of goods and
  services, intra-EU acquisitions, and imports, including the special
  regimes (recargo de equivalencia, simplificado, REAGP, REBU, criterio
  de caja, SII). Covers domestic IVA filed via Modelos 303, 322, 349,
  390. Does NOT cover IGIC (Canarias), IPSI (Ceuta/Melilla), or
  non-Spanish VAT systems.
- Decision: Spanish wins. iva is the BOE statutory name; VAT is an
  inaccurate English back-translation that loses the distinction from
  IGIC/IPSI.

### IRPF (Impuesto sobre la Renta de las Personas Fisicas)

- Canonical Spanish form: irpf.
- English equivalents currently in codebase: income_tax,
  personal_income_tax, pit.
- Primary source: Ley 35/2006, de 28 de noviembre, del Impuesto sobre la
  Renta de las Personas Fisicas y de modificacion parcial de las leyes
  de los Impuestos sobre Sociedades, sobre la Renta de no Residentes y
  sobre el Patrimonio (BOE num. 285, 29 de noviembre de 2006;
  BOE-A-2006-20764). Verified.
- Semantic scope: Spanish personal income tax on natural persons
  resident in Spanish territory, covering rendimientos del trabajo, del
  capital mobiliario / inmobiliario, de actividades economicas,
  ganancias y perdidas patrimoniales, and imputaciones de renta. Filed
  on Modelo 100 (annual) and supported by Modelos 111, 115, 130, 131,
  180, 190. Does NOT cover IRNR (non-residents, regulated separately)
  or Impuesto sobre Sociedades (corporate, Ley 27/2014).
- Decision: Spanish wins. Generic income_tax collides with IRNR and
  IS; only irpf carries the residency-plus-natural-person scope.

### modelo

- Canonical Spanish form: modelo (always followed by the official
  three-digit number, e.g. modelo_100, modelo_303, modelo_720).
- English equivalents currently in codebase: form, filing, tax_form,
  return_form.
- Primary source: AEAT publishes each modelo via Orden Ministerial in
  the BOE (e.g. Orden HFP/227/2017 for Modelo 303; Orden HAC for the
  annual Modelo 100 campana). AEAT Sede Electronica catalogues every
  modelo under the Todas las gestiones / Modelos y formularios
  taxonomy.
- Semantic scope: Numbered standardised filing form prescribed by AEAT
  for a specific tax obligation and period. The number is the unique
  identifier; Modelo 303 and Modelo 100 are not interchangeable with
  the generic English form. Does NOT refer to ad-hoc reports, internal
  worksheets, or census documents (those are declaracion censal, see
  censo).
- Decision: Spanish wins. The number is part of the legal name; the
  English word form loses the AEAT-numbered identity and conflicts
  with HTML/UI form.

### declaracion

- Canonical Spanish form: declaracion.
- English equivalents currently in codebase: declaration, return,
  filing.
- Primary source: Ley 58/2003, de 17 de diciembre, General Tributaria,
  Articulo 119 (Declaracion tributaria; BOE-A-2003-23186). Verified.
- Verified verbatim title: "Articulo 119. Declaracion tributaria."
  Verified verbatim opening: "Se considerara declaracion tributaria
  todo documento presentado ante la Administracion tributaria donde se
  reconozca o manifieste la realizacion de cualquier hecho relevante
  para la aplicacion de los tributos." (boe.es consolidated text,
  cross-checked via supercontable.com mirror, 2026-05-19.)
- Semantic scope: Any document by which the taxpayer recognises or
  manifests the realisation of any hecho relevante for the application
  of a tribute. A declaracion may be informativa (no liquidation, e.g.
  Modelo 720) or operative (precedes administrative liquidation).
  Distinct from autoliquidacion (see below) which both declares and
  self-liquidates. Does NOT mean the same as filing generically; a
  filing may be an autoliquidacion, a declaracion informativa, or a
  declaracion censal.
- Decision: Spanish wins. English return is overloaded with
  refund/repayment semantics; declaration loses the legal precision of
  LGT Articulo 119 vs. Articulo 120.

### autoliquidacion

- Canonical Spanish form: autoliquidacion.
- English equivalents currently in codebase: self_assessment,
  self_liquidation.
- Primary source: Ley 58/2003 General Tributaria, Articulo 120
  (Autoliquidaciones; BOE-A-2003-23186). Verified.
- Verified verbatim title: "Articulo 120. Autoliquidaciones."
  Verified verbatim opening: "La autoliquidacion es el acto por el
  cual el obligado tributario, en los casos previstos en las normas
  reguladoras de cada tributo, determina por si mismo la deuda
  tributaria que le corresponde." (boe.es consolidated text,
  cross-checked via noticias.juridicas.com mirror, 2026-05-19.)
- Semantic scope: A declaracion in which the obligado tributario, in
  addition to communicating the data necessary for the liquidation,
  also performs the operations of calificacion and quantification
  necessary to determine and pay the resulting tax debt (or, where
  applicable, the refund or compensation owed). Modelos 100, 303, 130,
  131, 200, 111, 115 are autoliquidaciones. Modelo 720 is NOT (it is a
  declaracion informativa).
- Decision: Spanish wins. English self-assessment is the closest match
  but conflates with UK HMRC procedure (different scope and
  semantics); autoliquidacion carries the LGT Articulo 120 contract.

### justificante

- Canonical Spanish form: justificante (full term in code:
  justificante_de_presentacion).
- English equivalents currently in codebase: receipt, proof,
  confirmation, submission_receipt.
- Primary source: AEAT Sede Electronica generates the justificante de
  presentacion as the official electronic receipt of a successful
  submission, bearing the CSV (Codigo Seguro de Verificacion).
  Underlying framework: Ley 39/2015 LPAC Articulo 27 on validez y
  eficacia de las copias realizadas por las Administraciones Publicas
  (BOE-A-2015-10565), supplemented by Real Decreto 203/2021 on
  actuacion administrativa por medios electronicos. Verified.
- Verified verbatim title: "Articulo 27. Validez y eficacia de las
  copias realizadas por las Administraciones Publicas." (Ley 39/2015
  LPAC, BOE-A-2015-10565, boe.es consolidated text, 2026-05-19.)
  Correction: prior draft cited Ley 40/2015 LRJSP (BOE-A-2015-10566);
  Articulo 27 belongs to Ley 39/2015 LPAC (BOE-A-2015-10565). The
  article governs authentic-copy validity (the legal substrate for
  CSV-bearing justificantes); the direct CSV regime is articulated in
  Ley 39/2015 Articulo 27.3 (authentic electronic copies) together
  with Real Decreto 203/2021.
- Semantic scope: The PDF artifact emitted by Sede Electronica
  immediately after an electronic presentation, containing the CSV,
  presentation timestamp, and identifying data of the modelo. It is
  the AEAT-side legal acknowledgement of receipt of an autoliquidacion
  or declaracion. CRITICAL: it is NOT an invoice (factura) and NOT a
  commercial receipt (recibo). A factura is a commercial document
  governed by Real Decreto 1619/2012 (reglamento de facturacion); a
  justificante is an administrative attestation of submission. They
  are NOT synonyms.
- Decision: Spanish wins. English receipt is ambiguously commercial
  and conflates with factura/recibo. The codebase must distinguish
  three artifacts: factura (commercial invoice), recibo (commercial
  receipt), justificante (AEAT submission attestation).

### borrador

- Canonical Spanish form: borrador.
- English equivalents currently in codebase: draft, snapshot, prefill.
- Primary source: Ley 35/2006 del IRPF, Articulo 98 (Borrador de
  declaracion; BOE-A-2006-20764). Verified.
- Verified verbatim title: "Articulo 98. Borrador de declaracion."
  Verified verbatim opening: "La Administracion tributaria podra
  poner a disposicion de los contribuyentes, a efectos meramente
  informativos, un borrador de declaracion..." (boe.es consolidated
  text, cross-checked via supercontable.com mirror, 2026-05-19.) The
  article explicitly authorises the AEAT to provide the borrador.
- Semantic scope: The pre-prepared IRPF draft declaration that AEAT
  makes available to taxpayers via Renta Web during the Renta campana.
  The borrador contains the AEAT view of the taxpayer renta data and
  may be confirmed, modified, or replaced before presentation. Tied
  specifically to IRPF (Modelo 100) and to the Sede Electronica
  Servicio de tramitacion del borrador / declaracion. Does NOT mean a
  generic local draft, an unsaved working copy, or an export snapshot.
- Decision: Spanish wins. English draft misses the AEAT origin and
  Renta-Web scope; snapshot is reserved for the generic infra term.

### renta

- Canonical Spanish form: renta.
- English equivalents currently in codebase: income, rental.
- Primary source: Ley 35/2006 del IRPF, Titulo I, Capitulo I (concepto
  y ambito de aplicacion). Verified.
- Semantic scope: The IRPF tax base aggregating rendimientos del
  trabajo, del capital, de actividades economicas, ganancias y
  perdidas patrimoniales, and imputaciones. Also used as shorthand for
  la declaracion de la Renta (Modelo 100 / Renta Web campana). Does
  NOT mean English rental (alquiler). A finca alquilada produces
  rendimientos del capital inmobiliario, not renta in the rental
  sense.
- Decision: Spanish wins. Critical disambiguation: codebase symbols
  involving rental properties must use alquiler or
  capital_inmobiliario; symbols involving IRPF income base use renta.
  Never let English rental collapse into renta.

### fincas

- Canonical Spanish form: finca (singular) / fincas (plural).
- English equivalents currently in codebase: real_estate, properties,
  rental_property.
- Primary source: Decreto de 8 de febrero de 1946 por el que se aprueba
  la nueva redaccion oficial de la Ley Hipotecaria, Titulo II
  (Inscripcion de fincas; BOE-A-1946-2453). Cadastral counterpart:
  Real Decreto Legislativo 1/2004 del Catastro Inmobiliario
  (BOE-A-2004-4163). Verified.
- Semantic scope: A registrable real-estate unit identified in the
  Registro de la Propiedad with a unique number, and/or in the
  Catastro with a referencia catastral. In AEAT context, fincas are
  the unit of account for Modelo 100 rendimientos del capital
  inmobiliario, Modelo 210 IRNR rentas inmobiliarias, IBI references,
  and Modelo 347 arrendamientos. Does NOT mean rental property
  specifically; a finca may be a residence, a rustic plot, a parking
  space, etc.
- Decision: Spanish wins. English real_estate is broader and loses the
  registral-unit identity. The codebase aligns on finca as the unit,
  with alquiler as the optional rental status of the finca.

### expediente

- Canonical Spanish form: expediente.
- English equivalents currently in codebase: case_file, case, record.
- Primary source: Ley 39/2015, de 1 de octubre, del Procedimiento
  Administrativo Comun de las Administraciones Publicas, Articulo 70
  (Expediente administrativo; BOE-A-2015-10565). Verified.
- Semantic scope: The ordered electronic set of documents,
  actuaciones, reports, and resolutions that constitute the precedent
  and basis for an administrative resolution. In AEAT context: the
  procedural file for a comprobacion, requerimiento, sancion, or
  devolucion. Has electronic format with foliated index. Auxiliary
  notes and internal drafts are explicitly excluded by Articulo 70.3.
  Does NOT mean a generic database row, an internal ticket, or a UI
  case view.
- Decision: Spanish wins. The Articulo 70 contract (electronic,
  indexed, exclusion of internal drafts) is lost in English case_file.

### censo

- Canonical Spanish form: censo (full term:
  censo_de_obligados_tributarios; censal forms: declaracion_censal).
- English equivalents currently in codebase: census, registry,
  taxpayer_registry.
- Primary source: Real Decreto 1065/2007, de 27 de julio, por el que
  se aprueba el Reglamento General de las actuaciones y los
  procedimientos de gestion e inspeccion tributaria, Titulo II
  Capitulo I (censo de obligados tributarios; BOE-A-2007-15984).
  Verified. Declaracion censal filed via Modelos 036 / 037.
- Semantic scope: The AEAT census of obligados tributarios, recording
  identity, fiscal domicile, activities, regimes (IVA, IRPF,
  retenciones), and representation. Does NOT mean the domain registry
  subpackage (which is rule taxonomy), and does NOT mean Registro
  Mercantil or Registro de la Propiedad.
- Decision: Spanish wins. English census is acceptable but ambiguous
  with statistical census; censo plus declaracion_censal keeps the
  Modelo 036/037 tie explicit and avoids the registry symbol clash
  with the domain rule registry.

### CCAA (Comunidades Autonomas)

- Canonical Spanish form: ccaa / comunidad_autonoma.
- English equivalents currently in codebase: already standardised as
  CCAA; no English variant in active use.
- Primary source: Constitucion Espanola de 1978, Titulo VIII (BOE num.
  311, 29 de diciembre de 1978; BOE-A-1978-31229); financial framework
  in LOFCA (Ley Organica 8/1980, BOE-A-1980-21166).
- Semantic scope: The 17 autonomous communities plus Ceuta and Melilla
  (ciudades autonomas) holding ceded or shared competence over
  portions of IRPF (escala autonomica), Impuesto sobre el Patrimonio,
  ISD, ITP, and others. Drives the quadlingual locale set (es / ca /
  gl / eu) and the IRPF autonomica scale.
- Decision: Spanish wins (already in place).

## Legitimate English exceptions

These English terms remain authoritative in the codebase regardless of
the Spanish-stems-win default:

- NIF, CIF, NIE -- fiscal identifiers defined by Real Decreto 1065/2007
  and Ley 58/2003; the acronyms themselves are language-neutral and
  BOE-stable.
- IBAN -- ISO 13616. SWIFT / BIC -- ISO 9362. International banking
  identifiers.
- Decimal, datetime, bool -- Python standard-library primitives. Never
  translate.
- Snapshot, Repository -- generic persistence-layer infrastructure
  terms; permitted strictly inside adapters/ and persistence packages.
  NOT permitted in domain or application packages where they would
  shadow borrador or censo respectively.

## Cross-reference notes

- factura, recibo, justificante are three distinct artifacts. Never
  collapse them into a single receipt symbol.
- renta (IRPF base) and alquiler (rental income source) are distinct.
  A property generating alquiler contributes rendimientos del capital
  inmobiliario to the renta total.
- censo (AEAT taxpayer census) and registry (codebase calculation /
  rule registry) are distinct. The English word registry is reserved
  for the rule taxonomy; the AEAT taxpayer census is censo.
- declaracion and autoliquidacion are not synonyms: LGT Articulo 119
  vs. Articulo 120. Every modelo must be tagged with its correct LGT
  category.

## Verification status

Verified against BOE consolidated texts (boe.es): Ley 37/1992 IVA;
Ley 35/2006 IRPF (including Articulo 98 verbatim title and opening on
borrador de declaracion); Ley 58/2003 LGT (including Articulo 119
verbatim title "Declaracion tributaria" and Articulo 120 verbatim
title "Autoliquidaciones", both with verbatim opening paragraphs);
Ley 39/2015 LPAC Articulo 27 (Validez y eficacia de las copias
realizadas por las Administraciones Publicas; BOE-A-2015-10565) and
Articulo 70; Real Decreto 1065/2007; Ley Hipotecaria Decreto 1946.
Verified against AEAT Sede Electronica documentation: justificante de
presentacion workflow; borrador / Renta Web tramitacion; modelo
nomenclature catalogue.

Verification round 2 (2026-05-19) confirmed the four citations
previously flagged for sign-off:

- LGT Articulo 119 "Declaracion tributaria" verbatim title and
  opening sentence captured.
- LGT Articulo 120 "Autoliquidaciones" verbatim title and opening
  sentence captured.
- IRPF Articulo 98 "Borrador de declaracion" verbatim title and
  opening sentence captured.
- LPAC Articulo 27 "Validez y eficacia de las copias realizadas por
  las Administraciones Publicas" verbatim title captured. Citation
  corrected from Ley 40/2015 LRJSP (BOE-A-2015-10566) to Ley 39/2015
  LPAC (BOE-A-2015-10565); Articulo 27 in Ley 40/2015 LRJSP is a
  different article (Sistema de informacion administrativa) and is
  not the CSV / authentic-copy basis.

No UNVERIFIED items remain.

## IVA Cluster Statutory Sanity Check (2026-05-19)

Sanity check of the IVA reversal cluster's canonical identifiers
against verified BOE citations. Read-only advisory; no code edits
performed.

### IvaInvoiceClassification - confirmed correct

Hybrid `Iva` + English `InvoiceClassification` suffix matches the ADR
English-infra carve-out. Ley 37/1992 uses `factura` and
`clasificacion` separately but has no statutory compound name for
the classifier-result type; coining `ClasificacionFactura` would be
a false-statutory neologism. No amendment.

- Statutory anchors: Ley 37/1992 IVA Articulo 4 (hecho imponible);
  Articulos 8 / 11 (entregas de bienes / prestaciones de servicios).
  BOE-A-1992-28740.

### IvaResidency - suggested amendment (rename, not values)

The 5 values (ES_MAINLAND, ES_CANARIAS, ES_CEUTA_MELILLA, EU_MEMBER,
THIRD_COUNTRY) cover the canonical IVA segmentation, but the type
name `IvaResidency` is statutorily imprecise. Ley 37/1992 does not
frame these as "residency". The ES_* trio reflects the territorio
de aplicacion del impuesto (TAI) carve-out, and the EU vs.
third-country split reflects lugar de realizacion rules; counterparty
residency (Articulo 84 reverse-charge triggers) is related but
distinct.

Suggested amendment: rename to `IvaTerritorialScope` (preferred) or
`IvaTaiSegmentation`. Values stay the same.

- Statutory anchors: Ley 37/1992 IVA Articulo 3.Dos (ambito espacial /
  TAI; Canarias, Ceuta y Melilla excluidas); Articulos 68-72 (lugar
  de realizacion del hecho imponible); Articulos 25-26
  (entregas / adquisiciones intracomunitarias). BOE-A-1992-28740.

### IvaFlowDirection - suggested amendment (third value)

`REPERCUTIDO` and `SOPORTADO` are the canonical statutory terms
(Articulo 88 repercusion del impuesto; Articulo 92 cuotas tributarias
soportadas). `AUTOREPERCUTIDO` is a colloquial gloss; the BOE / AEAT
canonical phrase for the self-charge / reverse-charge case is
`inversion del sujeto pasivo`, and AEAT Modelo 303 labels the
relevant casillas verbatim with this phrase.

Suggested amendment: rename the third enum value from
`AUTOREPERCUTIDO` to `INVERSION_SUJETO_PASIVO` (alias `ISP`
acceptable).

- Statutory anchors: Ley 37/1992 IVA Articulo 84.Uno.2 (inversion
  del sujeto pasivo); Articulo 88 (repercusion); Articulo 92 (cuotas
  soportadas). BOE-A-1992-28740.

### InvoiceKind ("issued" / "received") - confirmed correct, with SII boundary note

Lowercase English values are acceptable per the ADR English-infra
allowance and align with registry TOML selectors. Note for awareness
only: Real Decreto 1619/2012 (reglamento de facturacion) and the SII
regime use `factura expedida` and `factura recibida`, and the AEAT
SII libros registro are named `Libro registro de facturas expedidas`
and `Libro registro de facturas recibidas`. If an SII or
libro-registro adapter is added, the Spanish stems `expedida` /
`recibida` should appear at that boundary even while the internal
enum keeps `issued` / `received`.

- Statutory anchors: Real Decreto 1619/2012 (reglamento por el que
  se regulan las obligaciones de facturacion; BOE-A-2012-14696);
  Real Decreto 596/2016 (modificacion del Reglamento del IVA,
  instaurando el SII; BOE-A-2016-11575).

### Summary

| Identifier               | Verdict             | Action                                            |
| :----------------------- | :------------------ | :------------------------------------------------ |
| IvaInvoiceClassification | Confirmed correct   | None                                              |
| IvaResidency             | Suggested amendment | Rename -> IvaTerritorialScope                     |
| IvaFlowDirection         | Suggested amendment | Rename AUTOREPERCUTIDO -> INVERSION_SUJETO_PASIVO |
| InvoiceKind              | Confirmed correct   | Document SII-boundary Spanish-stem expectation    |

## Verification addendum (2026-05-19): SII / facturacion boundary anchors

Verbatim verification of the two advisory-cited anchors introduced in
the IVA Cluster Statutory Sanity Check section. Both verified against
boe.es consolidated texts on 2026-05-19. Promoted from advisory to
verified.

### Real Decreto 1619/2012 (reglamento de facturacion)

- Identifier: BOE-A-2012-14696. Verified.
- Verbatim official title: "Real Decreto 1619/2012, de 30 de
  noviembre, por el que se aprueba el Reglamento por el que se
  regulan las obligaciones de facturacion."
- Articulo 2 verbatim title: "Obligacion de expedir factura."
- Articulo 2 verbatim opening: "Los empresarios o profesionales estan
  obligados a expedir factura y copia de esta por las entregas de
  bienes y prestaciones de servicios que realicen en el desarrollo
  de su actividad..."
- Articulo 1 establishes the dual obligation verbatim: "Los
  empresarios o profesionales estan obligados a expedir y entregar,
  en su caso, factura u otros justificantes por las operaciones que
  realicen en el desarrollo de su actividad empresarial o profesional,
  asi como a conservar copia o matriz de aquellos. Igualmente, estan
  obligados a conservar las facturas u otros justificantes recibidos
  de otros empresarios o profesionales..."
- Boundary terms locked: `factura expedida` (issued / outbound) vs.
  `factura recibida` (received / inbound). These are the canonical
  Spanish stems for the InvoiceKind enum's SII / libro-registro
  boundary presentation.

### Real Decreto 596/2016 (SII)

- Identifier: BOE-A-2016-11575. Verified.
- Verbatim official title: "Real Decreto 596/2016, de 2 de diciembre,
  para la modernizacion, mejora e impulso del uso de medios
  electronicos en la gestion del Impuesto sobre el Valor Anadido."
- Modifies the Reglamento del IVA (RD 1624/1992) to instaurate the
  Suministro Inmediato de Informacion (SII).
- Articulo 63.3 verbatim opening: "En el libro registro de facturas
  expedidas se inscribiran, una por una, las facturas expedidas..."
- Articulo 64.4 verbatim opening: "En el libro registro de facturas
  recibidas se anotaran, una por una, las facturas recibidas..."
- Canonical libro-registro names locked: `Libro registro de facturas
  expedidas` and `Libro registro de facturas recibidas`. These are
  the verbatim Spanish names that an SII / libro-registro adapter
  must surface at the boundary, while the internal InvoiceKind enum
  retains `issued` / `received`.

## Modelo Cluster Statutory Sanity Check (2026-05-19)

Forward-looking sanity check of the W04 Modelo cluster (P08-P13)
ADR-proposed renames against verified BOE citations. Read-only
advisory; no code edits performed. Intended to inform coder
dispatches before the renames land.

### FilingDraft -> ModeloDraft - suggested amendment

ADR Section 1 declares `borrador` authoritative for the AEAT-prepared
Modelo 100 draft per Ley 35/2006 IRPF Articulo 98. The proposed
`ModeloDraft` is a generic "draft of a modelo" — a local in-progress
work-product the user assembles, not the AEAT-served pre-filled
borrador. These are two distinct artefacts and the codebase must
not collapse them.

Recommendation:
- Keep `ModeloDraft` for the generic local-draft entity (user
  assembles, validates, exports). This is structurally correct.
- Add an explicit ADR carve-out that `ModeloDraft` is NOT the
  AEAT-served borrador. Borrador stems remain reserved for entities
  where the data origin is AEAT Renta Web (Modelo 100 / borrador
  100 ingestion path). Document the semantic test: who supplies the
  draft contents (taxpayer-side -> ModeloDraft; AEAT-side ->
  Borrador*).
- Confirm there is no Modelo 100-borrador entity hiding under any
  `FilingDraft*` symbol that should migrate to `Borrador100*`
  instead of `ModeloDraft*`.

Statutory anchors: Ley 35/2006 IRPF Articulo 98 (Borrador de
declaracion); BOE-A-2006-20764. Already verbatim-verified.

### FilingRecord -> ModeloRecord - confirmed correct (consolidation pending)

`Record` is a generic infrastructure suffix retained in English per
ADR Section 4 (Record / Repository / Snapshot exceptions). Composing
`Modelo` + `Record` is the canonical pattern (cf. ModeloRepository,
BorradorSnapshot). No statutory imprecision.

Footnote 1 in the ADR ledger correctly flags the open consolidation
question between the domain pydantic record (`FilingRecord`) and the
persistence SQL row (already named `ModeloRecord` in
`src/aeat/adapters/persistence/storage/sql/records.py`). Statutory
basis does not pick one shape over the other; project lead
adjudication required on:
- collapse to one type (single ModeloRecord crossing the boundary), or
- domain pydantic `ModeloRecord` + persistence row `ModeloRow`
  (matching the `ModeloRow` already present in `_orm.py`).

The naming itself is statutorily defensible either way.

### FilingObligation -> ModeloObligation - suggested amendment

LGT Articulo 17 (BOE-A-2003-23186, verbatim verified 2026-05-19)
defines `la relacion juridico-tributaria` as "el conjunto de
obligaciones y deberes, derechos y potestades originados por la
aplicacion de los tributos". The statutory term is `obligacion
tributaria` (or `obligacion formal` for non-pecuniary duties per
Art. 29). `Modelo + Obligation` is a structural mismatch: the
modelo is the form that satisfies the obligation, not the obligation
itself.

Two refinement options worth considering before the rename lands:

1. Preferred: rename to `ModeloDeadline` or `ModeloFilingDeadline`
   if the entity captures the deadline / enrollment view of a
   modelo (the surrounding file path is
   `src/aeat/domain/deadlines/_models.py`, which supports this
   reading — these look like deadline / enrollment records, not
   abstract LGT obligations).
2. Alternative: keep ModeloObligation if the entity genuinely
   models the per-modelo slice of the broader LGT obligation, but
   add an inline comment anchoring it to LGT Articulo 17 and
   Articulo 29 (obligaciones tributarias formales).

Statutory anchors: Ley 58/2003 LGT Articulo 17 (relacion
juridico-tributaria; verbatim verified 2026-05-19); Articulo 29
(obligaciones tributarias formales). BOE-A-2003-23186.

### FilingAmendment -> ModeloAmendment - suggested amendment

LGT Articulo 122 (BOE-A-2003-23186, verbatim verified 2026-05-19)
verbatim title: "Declaraciones, autoliquidaciones y comunicaciones
complementarias o sustitutivas." First sentence opens: "Las
declaraciones, autoliquidaciones y comunicaciones de datos
complementarias o sustitutivas se presentaran..." The statute names
two distinct amendment kinds:

- `complementaria` — additional / supplementary filing that adds to
  the original.
- `sustitutiva` — substitute filing that replaces the original in
  full.

`ModeloAmendment` flattens this binary distinction. The statutorily
precise stems are `complementaria` and `sustitutiva` — these are
verbatim BOE terms taxpayers and AEAT both use.

Recommendation:
- Preferred: replace `ModeloAmendment` with two concrete types or a
  discriminated union: `ModeloComplementaria` and `ModeloSustitutiva`
  (or a `ModeloAmendment` umbrella whose `kind` discriminator is
  `complementaria | sustitutiva`).
- Acceptable fallback: keep `ModeloAmendment` as the umbrella type
  but ensure the `kind` field uses the verbatim statutory values
  `"complementaria"` / `"sustitutiva"` (not English `"supplementary"`
  / `"substitute"`).

`ModeloAmendmentError` follows the same logic — naming the error
class is structurally OK because errors live in the English-infra
exceptions list.

Statutory anchors: Ley 58/2003 LGT Articulo 122 (declaraciones,
autoliquidaciones y comunicaciones complementarias o sustitutivas).
BOE-A-2003-23186.

### SubmittedFiling -> SubmittedModelo - suggested amendment

`Submitted` is an English past-participle. The AEAT canonical
status verb is `presentar` / `presentado`. The justificante de
presentacion (verified 2026-05-19, Ley 39/2015 LPAC Articulo 27
anchor in this glossary) uses `presentacion` verbatim, and the AEAT
Sede Electronica surface labels submission state as `Presentada`
across Modelos 100 / 303 / 130 / 720 / 036 status pages.

Recommendation:
- Preferred: rename to `ModeloPresentado` (Spanish past-participle
  matching AEAT status nomenclature) or `PresentedModelo` if the
  English-prefix pattern is preferred for grammatical reasons.
- Acceptable: keep `SubmittedModelo` if `Submitted` is treated as a
  generic English-infra status adjective, but the ADR's
  Spanish-stems-win posture argues for `Presentado`.

Note: a parallel state machine likely needs `Borrador` (draft) ->
`EnRevision` / `Aprobado` (approved) -> `Presentado` (submitted) ->
`Aceptado` / `Rechazado` (accepted / rejected by AEAT). If the
codebase already has English state names elsewhere, harmonise as
part of the state-machine review rather than only this one symbol.

Statutory anchors: Ley 39/2015 LPAC Articulo 27 (validez y eficacia
de las copias / justificante de presentacion; verbatim verified).
AEAT Sede Electronica Modelo-status nomenclature
(`Borrador` / `Pendiente de presentar` / `Presentada` /
`Aceptada` / `Rechazada`).

### Summary

| ADR Proposal      | Verdict             | Action                                                                                  |
| :---------------- | :------------------ | :-------------------------------------------------------------------------------------- |
| ModeloDraft       | Suggested amendment | Keep, but add ADR carve-out separating from Borrador (AEAT-supplied Modelo 100 draft)   |
| ModeloRecord      | Confirmed correct   | None (pending project-lead consolidation decision per Footnote 1)                       |
| ModeloObligation  | Suggested amendment | Rename to ModeloDeadline (if deadline/enrollment scope) or anchor to LGT Art. 17/29     |
| ModeloAmendment   | Suggested amendment | Split into ModeloComplementaria / ModeloSustitutiva (LGT Art. 122 verbatim terms)       |
| SubmittedModelo   | Suggested amendment | Rename to ModeloPresentado (AEAT Sede `Presentada` status verbatim)                     |


## Fincas Cluster Statutory Sanity Check (2026-05-19)

Forward-looking sanity check of the W05.P15 Fincas cluster
ADR-proposed renames against verified BOE citations. Read-only
advisory; no code edits performed.

### Package rename: domain/rental/ -> domain/fincas/ - confirmed correct

The Renta-vs-Rental adjudication in ADR Section 5 is statutorily
sound. fincas is the BOE-stable unit of account across the AEAT
surfaces this package feeds.

Statutory anchors: Decreto de 8 de febrero de 1946 Ley Hipotecaria
(BOE-A-1946-2453); RDLeg 1/2004 Catastro Inmobiliario.


### RentalFinca -> Finca - confirmed correct

The bare Finca is the canonical statutory term per Ley Hipotecaria
Titulo II for registrable parcels in the Registro de la Propiedad,
and per the Catastro Inmobiliario for cadastral units. AEAT uses
Inmueble (broader: real-estate property) and Finca (narrower:
registrable parcel) in different contexts:

- Finca is the registral / cadastral unit. Statutorily anchored.
- Inmueble is used in Ley 35/2006 IRPF (e.g. Articulo 85 Imputacion
  de rentas inmobiliarias, title verbatim verified 2026-05-19) for
  the broader real-estate concept feeding imputed rentas.

The package choice Finca is correct because the unit of account
for the domain is the registrable parcel. If any future entity
captures the IRPF imputed-renta view at the inmueble (broader)
level, that entity may legitimately use the Inmueble stem instead.
The two stems are not synonyms.

Statutory anchors: Ley Hipotecaria Decreto 1946 Titulo II
(BOE-A-1946-2453); RDLeg 1/2004 Catastro Inmobiliario
(BOE-A-2004-4163); Ley 35/2006 IRPF Articulo 85 (title verbatim
verified 2026-05-19; first-sentence verbatim verification deferred
to a direct BOE-PDF read).

### RentalContract -> Arrendamiento - confirmed correct

Arrendamiento is the canonical statutory term for the lease
contract under both the urban regime (LAU) and the rural regime
(LAR):

- Ley 29/1994 LAU (BOE-A-1994-26003) verbatim title: Ley 29/1994,
  de 24 de noviembre, de Arrendamientos Urbanos. Articulo 1
  verbatim title: Ambito de aplicacion. Verbatim opening: La
  presente ley establece el regimen juridico aplicable a los
  arrendamientos de fincas urbanas que se destinen a vivienda o
  a usos distintos del de vivienda.
- Ley 49/2003 LAR (BOE-A-2003-21616) verbatim title: Ley 49/2003,
  de 26 de noviembre, de Arrendamientos Rusticos. Articulo 1
  verbatim title: Arrendamiento rustico. Verbatim opening: Se
  consideraran arrendamientos rusticos aquellos contratos mediante
  los cuales se ceden temporalmente una o varias fincas, o parte
  de ellas, para su aprovechamiento agricola, ganadero o forestal
  a cambio de un precio o renta.

The bare Arrendamiento is correct as the umbrella domain stem.
Rural-vs-urban context is a property of the specific arrendamiento
instance, not a separate type. If the domain needs to
discriminate, add a field regimen with values urbano or rustico
on Arrendamiento (verbatim values from LAU and LAR titles),
following the discriminator pattern recommended for
ModeloComplementaria / ModeloSustitutiva.

Note: arrendamiento covers both LAU/LAR lease contracts and the
broader Codigo Civil contrato de arrendamiento. AEAT Modelo 347
uses arrendamientos as the operations category.

Statutory anchors: Ley 29/1994 LAU (BOE-A-1994-26003; verbatim
verified 2026-05-19); Ley 49/2003 LAR (BOE-A-2003-21616; verbatim
verified 2026-05-19); RDLeg 1/2004 Catastro for the cadastral
side; Codigo Civil Articulos 1542-1582 for the general
arrendamiento regime.


### Income / Expense / Amortization Spanishness - suggested amendment

The PM call to retain English Income / Expense / Amortization as
generic accounting infra is defensible if the entities are
strictly generic. They are not. Ley 35/2006 IRPF uses three
specific verbatim Spanish stems that map directly onto these
entities:

- Rendimiento per Ley 35/2006 IRPF, specifically rendimientos del
  capital inmobiliario (Capitulo III, Articulos 22-24 - the
  Modelo 100 income category the domain feeds). NOT generic
  accounting income; it is the IRPF-base income category whose
  determination is regulated verbatim.
- Gasto deducible per Ley 35/2006 IRPF Articulo 23 (gastos
  deducibles del rendimiento del capital inmobiliario). NOT
  generic expense; statutorily enumerated list of allowable
  deductions.
- Amortizacion per Ley 35/2006 IRPF Articulo 23.1.b and the
  Reglamento IRPF (RD 439/2007) Articulo 14: amortizacion del
  inmueble + amortizacion de bienes muebles cedidos con el
  inmueble. NOT generic accounting amortization; the percentage
  bases and asset-class split are statutory.

Final advisory (revised from prior advisory): Spanish stems
recommended for this trio in the IRPF-fed paths:

- FincaIncomeRecord -> FincaRendimientoRecord (or
  RendimientoCapitalInmobiliarioRecord if the file feeds Modelo
  100 directly; the verbose form is more precise but longer).
- FincaExpense -> FincaGasto (or GastoDeducible if the Articulo
  23 enumeration is what is being modelled).
- FincaAmortizationLedger -> FincaAmortizacionLedger. Ledger is
  in the English-infra carve-out so the hybrid stem composes
  cleanly (cf. JustificanteFetchError, BorradorSnapshot).

Caveat for project lead adjudication: if the codebase has a clean
boundary between IRPF-specific records (Spanish) and a separate
generic accounting layer (English-OK), apply Spanish stems only
at the IRPF boundary. The ADR Section 4 English-infra carve-out
exists to avoid stem-stuttering on generic infrastructure
entities; Income / Expense / Amortization in the IRPF domain are
NOT generic.

Statutory anchors: Ley 35/2006 IRPF Articulos 22-24 (rendimientos
del capital inmobiliario y gastos deducibles); Articulo 23.1.b
(amortizacion); RD 439/2007 Reglamento IRPF Articulo 14
(amortizacion del capital inmobiliario). BOE-A-2006-20764.

### Imputacion (_imputacion_parameters.py sibling) - confirmed statutorily defined

Imputacion is verbatim statutory in Ley 35/2006 IRPF. The relevant
regime for the fincas domain is:

- Imputacion de rentas inmobiliarias per Articulo 85 (title
  verbatim verified 2026-05-19: Imputacion de rentas
  inmobiliarias). Applies to inmuebles urbanos no afectos a
  actividades economicas, no arrendados, no constitutivos de
  vivienda habitual; assigns a calculated renta to the
  propietario.

The bare Imputacion stem is correct and statutorily anchored. If
the entity name needs more precision,
ImputacionRentasInmobiliarias is the verbatim Articulo 85 phrase.

Statutory anchors: Ley 35/2006 IRPF Articulo 85 (Imputacion de
rentas inmobiliarias; title verbatim verified 2026-05-19).
BOE-A-2006-20764.


### Summary

| ADR Proposal                                        | Verdict             | Action                                                                     |
| :-------------------------------------------------- | :------------------ | :------------------------------------------------------------------------- |
| domain/rental/ -> fincas/                           | Confirmed correct   | None                                                                       |
| RentalFinca -> Finca                                | Confirmed correct   | Disambiguate Inmueble vs Finca for any IRPF-imputed-renta type             |
| RentalContract -> Arrendamiento                     | Confirmed correct   | Add regimen field (urbano / rustico) if discrimination needed              |
| RentalIncomeRecord -> FincaIncomeRecord             | Suggested amendment | Rename to FincaRendimientoRecord (IRPF Art. 22-24 anchor)                  |
| RentalExpense -> FincaExpense                       | Suggested amendment | Rename to FincaGasto (IRPF Art. 23 gastos deducibles)                      |
| RentalAmortizationLedger -> FincaAmortizationLedger | Suggested amendment | Rename to FincaAmortizacionLedger (IRPF Art. 23.1.b + RD 439/2007 Art. 14) |
| Imputacion (sibling module)                         | Confirmed correct   | None (IRPF Art. 85 verbatim title verified)                                |

### New verified citations added (2026-05-19)

- Ley 29/1994 LAU (BOE-A-1994-26003) - title + Articulo 1 verbatim.
- Ley 49/2003 LAR (BOE-A-2003-21616) - title + Articulo 1 verbatim.
- Ley 35/2006 IRPF Articulo 85 (BOE-A-2006-20764) - title verbatim;
  first-sentence verbatim verification deferred (WebFetch result
  paraphrased; direct BOE-PDF read required for verbatim opening).

Cumulative verified-citation count: 16 + 2 fully-verified (LAU,
LAR) + 1 partial (IRPF Art. 85 title only) = 18 fully verified,
1 partial.


## IRPF Art. 85 verbatim verification confirmation (2026-05-19)

Followup to the Fincas cluster sanity check section. The previously
partial citation for Ley 35/2006 IRPF Articulo 85 (Imputacion de
rentas inmobiliarias) is now fully verbatim-verified via direct
read of the BOE consolidated PDF (BOE-A-2006-20764-consolidado.pdf,
TITULO X, Capitulo I, Seccion 1, page 73).

- TITULO X verbatim header: "Regimenes especiales."
- Seccion 1.a verbatim header: "Imputacion de rentas inmobiliarias."
- Articulo 85 verbatim title: "Imputacion de rentas inmobiliarias."
- Articulo 85.1 verbatim opening (first paragraph, in full): "En el
  supuesto de los bienes inmuebles urbanos, calificados como tales
  en el articulo 7 del texto refundido de la Ley del Catastro
  Inmobiliario, aprobado por el Real Decreto Legislativo 1/2004,
  de 5 de marzo, asi como en el caso de los inmuebles rusticos con
  construcciones que no resulten indispensables para el desarrollo
  de explotaciones agricolas, ganaderas o forestales, no afectos
  en ambos casos a actividades economicas, ni generadores de
  rendimientos del capital, excluida la vivienda habitual y el
  suelo no edificado, tendra la consideracion de renta imputada la
  cantidad que resulte de aplicar el 2 por ciento al valor
  catastral, determinandose proporcionalmente al numero de dias
  que corresponda en cada periodo impositivo."

This confirms the structural anchor used in the Fincas cluster
sanity check for ImputacionRentasInmobiliarias and the
Finca-vs-Inmueble disambiguation note. The article explicitly
covers both bienes inmuebles urbanos and inmuebles rusticos
(con-construcciones, no-afectos), excluding vivienda habitual and
suelo no edificado.

Status update: the previously-flagged partial citation is promoted
to fully verbatim-verified. Cumulative verified-citation count
moves from 18 fully + 1 partial to 19 fully verified.
