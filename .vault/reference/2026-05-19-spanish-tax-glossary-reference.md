---
tags:
  - '#reference'
  - '#spanish-tax-glossary'
date: '2026-05-19'
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
