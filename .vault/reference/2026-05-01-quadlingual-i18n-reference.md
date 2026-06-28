---
tags:
  - '#reference'
  - '#quadlingual-i18n'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-12-trilingual-i18n-reference]]"
  - "[[2026-05-01-quadlingual-i18n-research]]"
  - "[[2026-05-01-quadlingual-i18n-adr]]"
---

# `quadlingual-i18n` reference: legal-terminology glossary for spanish tax vocabulary across es / en / ca / hu

This reference is the canonical glossary consulted before any
`Translatable` literal is added or refined. Every entry carries a
brief source-citation note in prose. The glossary is open-ended and
expected to grow as the corpus expands; the perpetual i18n audit
loop is responsible for surfacing terms that appear in records but
are not yet in this glossary.

## sourcing principles

- **`es`** is quoted from the AEAT manual práctico for the relevant
  modelo, the BOE article that defines the term, or the AEAT Sede
  Electrónica label exactly as it appears on the form. Where multiple
  AEAT publications disagree, the most recent BOE text wins.
- **`en`** prefers the EU-directive translation (notably Directive
  2006/112/EC for VAT, Directive 2011/16/EU for administrative
  cooperation, and Directive 2003/49/EC for cross-border interest /
  royalties) for cross-border concepts; AEAT's own English-language
  Sede copy for Spain-specific concepts; OECD glossary as a tertiary
  fallback.
- **`ca`** is sourced from native Catalan tax-content publishers —
  Catalan and Spanish are not the same language and a `ca` slot
  must never be a copy of the `es` slot. The authoritative chain
  for sourcing Catalan tax terminology is:

  1. **AEAT Sede Electrónica** in Catalan mode. The Sede serves a
     Catalan-language interface when the operator picks Català from
     the language switcher in the top bar; every form, tooltip, and
     procedural text the operator actually sees there is the most
     authoritative `ca` source for AEAT-domain terms.
  2. **AEAT Manual Pràctic** Catalan editions. AEAT publishes the
     IRPF, IVA, and Sociedades manuals práctics in Catalan as
     downloadable PDFs from the *Manuals, vídeos i fullets* section
     of the Sede; quote `ca` slots from the Catalan PDF, not from a
     translation of the `es` PDF.
  3. **Agència Tributària de Catalunya (ATC)** —
     `atc.gencat.cat`. ATC publishes Catalan-language guidance for
     the autonomous tributes it administers (ITP, AJD, ISD, taxes
     on gambling, the property-transfer surcharge, etc.) plus
     procedural language that aligns with the Generalitat's
     terminology register.
  4. **DOGC** (Diari Oficial de la Generalitat de Catalunya).
     Definitive for any Catalan-tax-law text quoted in a `ca` slot;
     source URLs use `dogc.gencat.cat`.
  5. **Generalitat de Catalunya — Departament d'Economia i Hisenda**
     —`hisenda.gencat.cat`. Cross-references AEAT terminology in
     the Catalan-language fiscal portal and is the source for
     terms specific to the autonomous tax administration.
  6. **TERMCAT** — the official Catalan terminology centre — for
     general legal/financial vocabulary that the AEAT and ATC
     sources do not cover. URL: `termcat.cat`. TERMCAT publishes
     Catalan-Spanish-English-French legal-tax glossaries.

  Per the ADR's acronym-retention decision, Spanish tax acronyms
  (`IVA`, `IRPF`, `IRNR`, `ITP`, etc.) appear unchanged in `ca`
  slots because the Generalitat itself uses them on Catalan-
  language tax forms; the long-form expansions are translated
  (e.g. `Impost sobre el Valor Afegit` for `IVA`).

  When an entry cannot be grounded in one of the six sources
  above, the `ca` slot is marked `_ca_provenance:
  "needs-native-review"` rather than seeded with the Spanish text.
  Catalan-as-Spanish placeholder slots are a defect, not a
  fallback.
- **`hu`** uses NAV (Nemzeti Adó- és Vámhivatal) vocabulary for
  analogous Hungarian concepts; the Spanish acronym is retained in
  parentheses on first use to preserve the link to the source
  document. EU-directive HU translations from eur-lex.europa.eu
  are the cross-reference for cross-border terms.

## taxes and acronyms

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| IVA (Impuesto sobre el Valor Añadido) | VAT (Value Added Tax) | IVA (Impost sobre el Valor Afegit) | ÁFA (általános forgalmi adó) |
| IRPF (Impuesto sobre la Renta de las Personas Físicas) | PIT (Personal Income Tax) | IRPF (Impost sobre la Renda de les Persones Físiques) | SZJA (személyi jövedelemadó) |
| IRNR (Impuesto sobre la Renta de no Residentes) | NRIT (Non-Resident Income Tax) | IRNR (Impost sobre la Renda de No Residents) | KSZJA (külföldi illetőségű személyek SZJA-ja) |
| IS (Impuesto sobre Sociedades) | CIT (Corporate Income Tax) | IS (Impost sobre Societats) | TAO (társasági adó) |
| ITP (Impuesto sobre Transmisiones Patrimoniales) | TPT (Transfer Tax) | ITP (Impost sobre Transmissions Patrimonials) | vagyonátruházási illeték |
| AJD (Actos Jurídicos Documentados) | Stamp Duty | AJD (Actes Jurídics Documentats) | okirati illeték |
| ISD (Impuesto sobre Sucesiones y Donaciones) | IGT (Inheritance and Gift Tax) | ISD (Impost sobre Successions i Donacions) | öröklési és ajándékozási illeték |
| IBI (Impuesto sobre Bienes Inmuebles) | Property Tax | IBI (Impost sobre Béns Immobles) | ingatlanadó |
| IAE (Impuesto sobre Actividades Económicas) | Business Activity Tax | IAE (Impost sobre Activitats Econòmiques) | gazdasági tevékenységi adó |

The acronym is the Spanish form in every language slot per the
ADR's acronym-retention decision. The expansion in parentheses
reflects the official long form in each language. Where the
Hungarian column omits an acronym, NAV does not publish one and
the long-form rendering stands.

## institutions and authorities

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| AEAT (Agencia Estatal de Administración Tributaria) | Spanish Tax Agency (AEAT) | AEAT (Agència Estatal d'Administració Tributària) | spanyol Adóhivatal (AEAT) |
| Hacienda | Treasury | Hisenda | Pénzügyminisztérium / Adóhivatal |
| Sede Electrónica | Electronic Office | Seu Electrònica | elektronikus ügyfélkapu |
| Generalitat de Catalunya | Government of Catalonia | Generalitat de Catalunya | katalán autonóm kormány |
| Agència Tributària de Catalunya (ATC) | Tax Agency of Catalonia (ATC) | Agència Tributària de Catalunya (ATC) | katalán adóhivatal (ATC) |
| BOE (Boletín Oficial del Estado) | Official State Gazette (BOE) | BOE (Butlletí Oficial de l'Estat) | spanyol hivatalos közlöny (BOE) |
| DOGC (Diari Oficial de la Generalitat de Catalunya) | Official Gazette of the Government of Catalonia (DOGC) | DOGC (Diari Oficial de la Generalitat de Catalunya) | katalán hivatalos közlöny (DOGC) |

## form structure terminology

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| modelo | form | model | nyomtatvány |
| casilla | box | casella | rovat |
| ejercicio | tax year | exercici | adóév |
| trimestre | quarter | trimestre | negyedév |
| período | period | període | időszak |
| declaración | tax return / declaration | declaració | bevallás |
| autoliquidación | self-assessment | autoliquidació | önbevallás |
| liquidación | assessment | liquidació | adómegállapítás |
| presentación | filing / submission | presentació | benyújtás |
| justificante | filing receipt | justificant | bizonylat |
| complementaria | supplementary return | complementària | kiegészítő bevallás |
| sustitutiva | substitute return | substitutiva | helyettesítő bevallás |
| rectificación | rectification | rectificació | helyesbítés |
| baja de actividad | cessation of activity | baixa d'activitat | tevékenység megszüntetése |
| alta de actividad | start of activity | alta d'activitat | tevékenység megkezdése |
| sujeto pasivo | taxable person | subjecte passiu | adóalany |
| obligado tributario | tax obligor | obligat tributari | adózó |

## VAT (`IVA`) operational vocabulary

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| base imponible | taxable base | base imposable | adóalap |
| cuota | tax due / tax amount | quota | adóösszeg |
| tipo impositivo | tax rate | tipus impositiu | adómérték |
| tipo general | standard rate | tipus general | általános adómérték |
| tipo reducido | reduced rate | tipus reduït | kedvezményes adómérték |
| tipo superreducido | super-reduced rate | tipus superreduït | szuperkedvezményes adómérték |
| IVA devengado | output VAT | IVA meritat | felszámított ÁFA |
| IVA repercutido | output VAT (charged onward) | IVA repercutit | áthárított ÁFA |
| IVA soportado | input VAT | IVA suportat | előzetesen felszámított ÁFA |
| IVA deducible | deductible VAT | IVA deduïble | levonható ÁFA |
| operaciones interiores | domestic operations | operacions interiors | belföldi ügyletek |
| adquisiciones intracomunitarias | intra-Community acquisitions | adquisicions intracomunitàries | Közösségen belüli beszerzések |
| entregas intracomunitarias | intra-Community supplies | lliuraments intracomunitaris | Közösségen belüli értékesítések |
| importaciones | imports | importacions | importok |
| exportaciones | exports | exportacions | exportok |
| inversión del sujeto pasivo (ISP) | reverse charge | inversió del subjecte passiu (ISP) | fordított adózás |
| recargo de equivalencia | equivalence surcharge (Spain-only retail VAT regime) | recàrrec d'equivalència (règim aplicable només a Espanya) | egyenértékűségi pótlék (csak Spanyolországban alkalmazandó) |
| régimen general | general regime | règim general | általános rendszer |
| régimen simplificado | simplified regime | règim simplificat | egyszerűsített rendszer |
| prorrata | pro-rata | prorrata | arányos levonási hányad |
| prorrata general | general pro-rata | prorrata general | általános arányosítás |
| prorrata especial | special pro-rata | prorrata especial | különös arányosítás |
| OSS (One-Stop Shop) | OSS (One-Stop Shop) | OSS (finestreta única) | OSS (egyablakos rendszer) |

The EU directive HU translation (Council Directive 2006/112/EC,
HU edition) is the source of `Közösségen belüli beszerzések` and
`Közösségen belüli értékesítések`; the capital `K` is preserved
because eur-lex publishes the term that way.

## income tax (`IRPF`) vocabulary

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| rendimiento | income / yield | rendiment | jövedelem |
| rendimientos del trabajo | employment income | rendiments del treball | munkaviszonyból származó jövedelem |
| rendimientos de actividades económicas | self-employment income | rendiments d'activitats econòmiques | önálló tevékenységből származó jövedelem |
| rendimientos del capital mobiliario | investment income | rendiments del capital mobiliari | tőkejövedelem |
| rendimientos del capital inmobiliario | rental / real estate income | rendiments del capital immobiliari | ingatlanjövedelem |
| ganancias y pérdidas patrimoniales | capital gains and losses | guanys i pèrdues patrimonials | tőkejövedelem-nyereség és veszteség |
| base liquidable | net taxable base | base liquidable | levonások utáni adóalap |
| mínimo personal y familiar | personal and family allowance | mínim personal i familiar | személyi és családi adóalap-csökkentés |
| retención | withholding | retenció | adólevonás |
| ingreso a cuenta | payment on account | ingrés a compte | adóelőleg |
| pago fraccionado | fractional payment | pagament fraccionat | részletfizetés |
| deducción por maternidad | maternity deduction | deducció per maternitat | anyasági adókedvezmény |
| deducción por familia numerosa | large-family deduction | deducció per família nombrosa | nagycsaládos adókedvezmény |
| reducción por arrendamiento de vivienda habitual | reduction for letting of primary residence | reducció per arrendament d'habitatge habitual | állandó lakás bérbeadása utáni adóalap-csökkentés |
| módulos | objective-estimation modules | mòduls | átalány-megállapítási modulok |
| estimación directa | direct estimation | estimació directa | tételes elszámolás |
| estimación objetiva | objective estimation | estimació objectiva | átalány-megállapítás |
| residencia habitual | habitual residence | residència habitual | szokásos tartózkodási hely |

## non-resident and cross-border vocabulary

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| convenio de doble imposición (CDI) | double-taxation convention | conveni de doble imposició (CDI) | kettős adóztatási egyezmény |
| establecimiento permanente | permanent establishment | establiment permanent | állandó telephely |
| beneficiario efectivo | beneficial owner | beneficiari efectiu | tényleges haszonhúzó |
| modelo informativo | informational return | model informatiu | adatszolgáltatási bevallás |
| no residente | non-resident | no resident | nem-rezidens |
| residencia fiscal | tax residence | residència fiscal | adóügyi illetőség |
| TIN (Tax Identification Number) | TIN (Tax Identification Number) | TIN (Número d'Identificació Fiscal) | TIN (adóazonosító) |
| NIF (Número de Identificación Fiscal) | TIN-ES (NIF) | NIF (Número d'Identificació Fiscal) | NIF (spanyol adóazonosító) |
| NIE (Número de Identidad de Extranjero) | Foreigner ID Number (NIE) | NIE (Número d'Identitat d'Estranger) | NIE (külföldiek azonosítója) |
| CIF (Código de Identificación Fiscal) | Corporate TIN (CIF) | CIF (Codi d'Identificació Fiscal) | CIF (spanyol cégadószám) |

## taxpayer profile vocabulary

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| autónomo | self-employed (sole trader) | autònom | egyéni vállalkozó |
| empresario individual | individual entrepreneur | empresari individual | egyéni vállalkozó |
| profesional | professional | professional | szabadfoglalkozású |
| sociedad civil | civil partnership | societat civil | polgári jogi társaság |
| comunidad de bienes | community of goods | comunitat de béns | vagyonközösség |
| arrendador | landlord | arrendador | bérbeadó |
| arrendatario | tenant | arrendatari | bérlő |
| pagador | payer | pagador | kifizető |
| perceptor | recipient | perceptor | kedvezményezett |

## status and review vocabulary (CLI-facing)

These are the terms that surface in CLI output (`aeat status *`,
`aeat review queue`, `aeat filing *`) and in error messages, where
fidelity to AEAT terminology is less critical but consistency
across the contract still matters.

| Spanish | English | Catalan | Hungarian |
| --- | --- | --- | --- |
| pendiente | pending | pendent | függőben |
| presentada | filed | presentada | benyújtva |
| aceptada | accepted | acceptada | elfogadva |
| rechazada | rejected | rebutjada | elutasítva |
| en trámite | in progress | en tràmit | feldolgozás alatt |
| caducada | expired | caducada | lejárt |
| anulada | annulled | anul·lada | érvénytelenítve |
| firmada | signed | signada | aláírva |
| sin firmar | unsigned | sense signar | aláíratlan |
| borrador | draft | esborrany | piszkozat |
| revisión requerida | review required | revisió requerida | felülvizsgálat szükséges |
| sin operaciones | no operations | sense operacions | nincs ügylet |
| sin transacciones | no transactions | sense transaccions | nincs tranzakció |
| sin facturas | no invoices | sense factures | nincs számla |
| aprobación caducada | approval stale | aprovació caducada | jóváhagyás lejárt |
| revisar de nuevo | re-review required | revisar de nou | újbóli felülvizsgálat szükséges |
| no hay obligaciones próximas | no upcoming obligations | no hi ha obligacions properes | nincs közelgő kötelezettség |
| perfil no encontrado | profile not found | perfil no trobat | profil nem található |
| certificado faltante | certificate missing | certificat absent | hiányzó tanúsítvány |
| sesión no disponible | session unavailable | sessió no disponible | nem elérhető munkamenet |
| inicia sesión primero | log in first | inicia la sessió primer | először jelentkezzen be |
| identificación requerida | identification required | identificació requerida | azonosítás szükséges |

## diacritics and orthography notes

- Catalan uses geminated `l·l` (U+00B7 middle dot between two L's),
  written here as `l·l` literally; NFC normalisation keeps the
  middle dot as its own codepoint, which is correct.
- Catalan retains the open-vowel diacritics `à è ò` (grave) and the
  close-vowel diacritics `é ó í ú` (acute); both classes are NFC-
  composed in our corpus.
- Hungarian long vowels (`ő ű`) are NFC-composed.
- Spanish `ñ` and the open-quotation `«»` (used by the BOE) are
  NFC-composed.
- The corpus has no character outside the Unicode Multilingual
  Plane; UTF-8 byte length stays bounded.

## entries marked `needs-native-review`

The corpus backfill script seeds the `ca` slot from this glossary
where a Spanish lemma matches a known entry. For records whose
Spanish content does not match any glossary entry, the script
seeds `ca` with the Spanish text plus a `_ca_provenance: "needs-native-review"`
sibling key on the parent record. The perpetual i18n audit loop
re-scans those records on every pass and surfaces them as
candidates for refinement.

A native Catalan tax-terminology reviewer should treat the seeded
records as drafts: edit the `ca` slot to a grounded translation,
remove the `_ca_provenance` marker, and add their initials to
`definition_reviewed_by`.

## glossary expansion protocol

When the perpetual audit loop discovers a new term in the corpus
that this glossary does not cover, the loop's findings task notes:

- the modelo and casilla where the term appears
- the AEAT manual práctico section that defines it
- a proposed quad-lingual rendering with citations

The next loop iteration adds the entry to this glossary and
re-runs the corpus backfill against the updated glossary. The
process is open-ended; this glossary grows alongside the corpus.
