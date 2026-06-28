---
name: 2026-04-13-modelo-inventory-research
description: Authoritative AEAT modelo inventory + applicability matrix + gap analysis for Spanish autónomos and SL entities
type: research
tags:
  - "#research"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-12-casilla-db-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-04-12-normatives-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# modelo-inventory research: authoritative AEAT modelo catalogue

Research to seed the feature/108 modelo inventory. Target user profile:
`autonomo_ed_solo` (Spanish autÃ³nomo, estimaciÃ³n directa simplificada, no
employees, no rental, no intracomunitario, no bienes en el extranjero).
The catalogue must be extensible to the other seven profiles tracked by
`aeat.domain.deadlines.AutonomoProfile`, and must leave a narrow door for SL
entities without polluting the autÃ³nomo core.

## 1. executive summary

The `aeat` project today ships filing builders for only three modelos
(130, 303, 390) but the north-star goal of automated end-to-end filing
for a Spanish autÃ³nomo requires a closed, typed catalogue of every
modelo the user may plausibly owe. This research catalogues the minimum
set requested in the brief plus the adjacent modelos surfaced by the
on-disk normatives corpus (100, 111, 115, 123, 130, 131, 180, 190, 232,
303, 347, 349, 369, 390, 720, 036, 037, 200, 202, 840) and produces a
profile-applicability matrix and a gap analysis the ADR phase can bind
to. The catalogue is local state only (Track A): it does not move money,
it teaches the rest of the system which modelos exist, who owes them,
when they are due, and which corpus citations back them up.

## 2. methodology

Sources consulted on 2026-04-13 from the worktree:

- `corpus/normatives/ley-35-2006.json` â€” IRPF ley
- `corpus/normatives/ley-37-1992.json` â€” IVA ley
- `corpus/normatives/ley-58-2003.json` â€” LGT
- `corpus/normatives/rd-439-2007.json` â€” RIRPF
- `corpus/normatives/rd-1624-1992.json` â€” RIVA
- `corpus/normatives/rd-1065-2007.json` â€” RGAT
- `corpus/normatives/orden-hac-242-2025.json` â€” Orden anual IRPF 2024
- `corpus/manuals/iva/2025/manifest.json` â€” Manual prÃ¡ctico IVA 2025 (PDF
  manifest; source_pdf_url recorded, no extracted text on disk)
- `corpus/manuals/renta/2025/parte1/manifest.json`,
  `corpus/manuals/renta/2025/parte2-deducciones-autonomicas/manifest.json`
- `corpus/casillas/modelo_303/2025Q4.json`,
  `corpus/casillas/modelo_130/2025Q4.json`,
  `corpus/casillas/modelo_390/2025.json`
- `src/aeat/application/filing/_builders/` â€” existing builder surface (130, 303, 390)
- `src/aeat/domain/modelos/__init__.py` â€” confirmed stub (empty `__all__`)
- `src/aeat/domain/deadlines/_models.py` â€” `AutonomoProfile`, `IVARegime`
- `src/aeat/domain/casillas/` â€” catalogue loader surface
- Project knowledge of AEAT public Sede ElectrÃ³nica form URLs (hint only)

**Citation discipline.** The on-disk normatives corpus stores Spanish
`summary` fields per article rather than the literal BOE article body.
In this document every `quoted_text_es` is the `summary.es` extracted
verbatim from the corresponding `corpus/normatives/*.json` record and is
flagged as such â€” it is a project-curated Spanish abstract, not the BOE
literal article text. Where a modelo is not directly named in the on-disk
corpus the citation falls back to the closest statutory umbrella (Ley
37/1992 art 164 for IVA formal duties, Ley 35/2006 art 99 for IRPF pagos
a cuenta, RD 1065/2007 art 30 for informativas, Ley 58/2003 art 29 for
LGT formal duties) and the gap is flagged explicitly under the affected
modelo and in section 8. The Manual prÃ¡ctico IVA/Renta 2025 is present
only as PDF manifests; no manual text is quoted.

## 3. d1 â€” modelo inventory

Every modelo below carries: official code + trilingual name, category,
cadence, legal basis (citations), applicability, thresholds,
relationships, deadline rule description, submission channel hint,
casilla count and gotchas. Citations point at concrete
`corpus/normatives/*.json` articles by `{file_id}#{articulo}`;
`quoted_text_es` is the Spanish `summary.es` from that record unless
otherwise noted.

### 3.1 modelo 100 â€” declaraciÃ³n anual del IRPF

- **Trilingual name.** es: `DeclaraciÃ³n del Impuesto sobre la Renta de
  las Personas FÃ­sicas`; en: `Annual personal income tax return`; hu:
  `Ã‰ves szemÃ©lyi jÃ¶vedelemadÃ³-bevallÃ¡s (IRPF)`.
- **Category.** `irpf`.
- **Cadence.** `annual` (ejercicio n, presentada en n+1 entre abril y
  junio).
- **Legal basis.**
  - `ley-35-2006#27`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a27`,
    `quoted_text_es` (summary): "Define quÃ© se considera rendimiento de
    una actividad econÃ³mica frente a los rendimientos del trabajo y del
    capital, y fija el criterio de ordenaciÃ³n por cuenta propia de los
    medios de producciÃ³n y de los recursos humanos."
  - `orden-hac-242-2025#primero`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2025-5049#primero`,
    `quoted_text_es` (summary): "Aprueba los modelos de declaraciÃ³n del
    IRPF (Modelo 100) y del Impuesto sobre el Patrimonio (Modelo 714)
    correspondientes al ejercicio 2024, cuyo contenido figura en los
    anexos I y II de la propia orden."
- **Applicability.** Mandatory for natural persons whose income exceeds
  the umbrales de Ley 35/2006 art 96; always mandatory for autÃ³nomos
  with rendimientos de actividades econÃ³micas regardless of the general
  umbrales (Manual prÃ¡ctico Renta 2025 â€” corpus gap, PDF only).
- **Thresholds.** Employment-income thresholds (22 000 EUR / 15 876 EUR)
  are not material for the autÃ³nomo-solo profile because the
  activity-income rule overrides.
- **Relationships.** `receives_from = {130, 131}`;
  `related_modelos = {714}`.
- **Deadline.** Calendar window, typically 2 April â€“ 30 June n+1; draft
  available from early April; payment-split option end of June.
- **Channel hint.** `https://sede.agenciatributaria.gob.es/Sede/renta.html`.
- **Casillas.** Very large (~500+); historically unstable year-to-year.
  No catalogue entries yet.
- **Gotchas.** Deducciones autonÃ³micas are per-CCAA (corpus has
  `renta/2025/parte2-deducciones-autonomicas` manifest). The borrador
  flow is distinct from the raw form and has its own submission endpoint.

### 3.2 modelo 130 â€” pago fraccionado IRPF (estimaciÃ³n directa)

- **Trilingual name.** es: `Pago fraccionado IRPF. EstimaciÃ³n directa`;
  en: `IRPF fractional payment â€” direct estimation`; hu: `IRPF
  rÃ©szletfizetÃ©s â€” kÃ¶zvetlen becslÃ©s`.
- **Category.** `irpf`. **Cadence.** `quarterly`.
- **Legal basis.**
  - `rd-439-2007#110`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a110`,
    `quoted_text_es` (summary): "Fija el cÃ¡lculo del pago fraccionado
    trimestral de los contribuyentes que desarrollan actividades
    econÃ³micas: estimaciÃ³n directa (20% del rendimiento neto) y
    estimaciÃ³n objetiva (tipos en funciÃ³n de magnitudes del mÃ³dulo)."
  - `ley-35-2006#99`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a99`,
    `quoted_text_es` (summary): "Establece la obligaciÃ³n general de
    practicar retenciones, ingresos a cuenta y pagos fraccionados como
    pagos a cuenta del IRPF."
- **Applicability.** Mandatory for autÃ³nomos en estimaciÃ³n directa cuyo
  rendimiento no estÃ© sujeto a retenciÃ³n en al menos el 70% (regla RD
  439/2007 art 110.3.b).
- **Thresholds.** 70% retenciÃ³n excludes some profesionales. No monetary
  floor; always due even with zero/negative result.
- **Relationships.** `caps_into = {100}`; mutually exclusive with 131.
- **Deadline.** Q1â€“Q3: 1â€“20 abril / julio / octubre; Q4: 1â€“30 enero n+1.
  DD cutoff 5 days before close.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/irpf/modelo-130.html`.
- **Casillas.** ~19 casillas, stable. Catalogue stub
  (`corpus/casillas/modelo_130/2025Q4.json`, 4 seeded).
- **Gotchas.** Negative acumulado-to-date carries forward within the
  year; cannot go below zero on the period result.

### 3.3 modelo 131 â€” pago fraccionado IRPF (estimaciÃ³n objetiva)

- **Trilingual name.** es: `Pago fraccionado IRPF. EstimaciÃ³n objetiva`;
  en: `IRPF fractional payment â€” objective estimation (mÃ³dulos)`; hu:
  `IRPF rÃ©szletfizetÃ©s â€” objektÃ­v becslÃ©s (modulok)`.
- **Category.** `irpf`. **Cadence.** `quarterly`.
- **Legal basis.**
  - `rd-439-2007#110`, retrieved 2026-04-13, same passage as 3.2.
  - `ley-35-2006#31`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a31`,
    `quoted_text_es` (summary): "Regula el rÃ©gimen de estimaciÃ³n
    objetiva (mÃ³dulos), las magnitudes excluyentes y la renuncia al
    rÃ©gimen."
- **Applicability.** Mandatory for autÃ³nomos en estimaciÃ³n objetiva.
  **Out of scope for autonomo_ed_solo** â€” ED and EO are mutually
  exclusive.
- **Thresholds.** Ley 35/2006 art 31: 250 000 EUR gross, 125 000 EUR
  B2B invoicing, 250 000 EUR compras.
- **Relationships.** `caps_into = {100}`; mutually exclusive with 130.
- **Deadline.** Same calendar as 130.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/irpf/modelo-131.html`.
- **Casillas.** ~15 casillas; stable. No catalogue entry yet.
- **Gotchas.** `autonomo_eo` profile only.

### 3.4 modelo 303 â€” autoliquidaciÃ³n IVA

- **Trilingual name.** es: `AutoliquidaciÃ³n del IVA`; en: `Periodic VAT
  self-assessment`; hu: `IdÅ‘szakos IVA-Ã¶nbevallÃ¡s`.
- **Category.** `iva`. **Cadence.** `quarterly` (monthly REDEME / large
  taxpayers out of scope).
- **Legal basis.**
  - `ley-37-1992#164`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a164`,
    `quoted_text_es` (summary): "Enumera las obligaciones formales del
    sujeto pasivo del IVA: facturaciÃ³n, libros registro, declaraciones-
    liquidaciones periÃ³dicas y declaraciÃ³n-resumen anual."
  - `rd-1624-1992#71`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925#a71`,
    `quoted_text_es` (summary): "Regula la declaraciÃ³n-liquidaciÃ³n
    periÃ³dica del IVA, fija los plazos de presentaciÃ³n (trimestrales o
    mensuales segÃºn el rÃ©gimen) y remite a los modelos oficiales
    aprobados por Orden Ministerial."
- **Applicability.** Mandatory for any sujeto pasivo del IVA not in
  recargo de equivalencia or exento. Gated by `aeat.domain.deadlines.IVARegime`:
  GENERAL/SIMPLIFICADO filed; RECARGO_EQUIVALENCIA/EXENTO not.
- **Thresholds.** None; filed even with zero activity.
- **Relationships.** `caps_into = {390}`; interacts with 349 when
  intracomunitario; 369 is its OSS counterpart.
- **Deadline.** Q1â€“Q3: 1â€“20 abril / julio / octubre; Q4: 1â€“30 enero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/iva/modelo-303.html`.
- **Casillas.** ~88 casillas (rÃ©gimen general). Catalogue stub
  (`corpus/casillas/modelo_303/2025Q4.json`, 4 seeded).
- **Gotchas.** Pro-rata (art 104 LIVA) mutates several casillas; SII
  subjects have a different window.

### 3.5 modelo 390 â€” declaraciÃ³n-resumen anual IVA

- **Trilingual name.** es: `DeclaraciÃ³n-resumen anual del IVA`; en: `VAT
  annual summary return`; hu: `Ã‰ves IVA Ã¶sszesÃ­tÅ‘ bevallÃ¡s`.
- **Category.** `iva`. **Cadence.** `annual` (1â€“30 enero n+1).
- **Legal basis.**
  - `ley-37-1992#164`, retrieved 2026-04-13, same passage as 3.4 â€” art
    164 explicitly lists the "declaraciÃ³n-resumen anual".
  - `rd-1624-1992#71`, retrieved 2026-04-13, same passage as 3.4.
- **Applicability.** Mandatory for rÃ©gimen general filers not enrolled
  in SII (SII exempts from 390).
- **Relationships.** `receives_from = {303}`.
- **Deadline.** 1â€“30 enero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/iva/modelo-390.html`.
- **Casillas.** ~180 casillas. Catalogue stub
  (`corpus/casillas/modelo_390/2025.json`, 3 seeded).
- **Gotchas.** SII exoneration; recargo-de-equivalencia filers file
  308/309 instead.

### 3.6 modelo 349 â€” recapitulativa operaciones intracomunitarias

- **Trilingual name.** es: `DeclaraciÃ³n recapitulativa de operaciones
  intracomunitarias`; en: `Recapitulative statement of intra-EU
  operations`; hu: `EU-n belÃ¼li Ã¼gyletek Ã¶sszesÃ­tÅ‘ nyilatkozata`.
- **Category.** `informativa`. **Cadence.** Monthly if rolling
  quarterly operations cap breached, otherwise `quarterly`.
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30`,
    `quoted_text_es` (summary): "Desarrolla las obligaciones de
    presentaciÃ³n de declaraciones informativas por parte de los
    obligados tributarios, fijando el contenido mÃ­nimo, la forma y los
    plazos de presentaciÃ³n reglamentarios que sirven de base a los
    modelos anuales (347, 349, etc)."
  - `ley-37-1992#164` â€” formal duty umbrella (same passage as 3.4).
- **Applicability.** Mandatory when the autÃ³nomo performs entregas or
  adquisiciones intracomunitarias. Maps to
  `AutonomoProfile.does_intracomunitario`.
- **Thresholds.** 50 000 EUR rolling quarterly threshold flips cadence
  (art 81.3 RIVA â€” not on disk; flagged).
- **Relationships.** `related_modelos = {303}`.
- **Deadline.** Monthly: 1â€“20 of month n+1 (Dec: 1â€“30 enero).
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/iva/modelo-349.html`.
- **Casillas.** ~10 header + repeating operator block. Not in catalogue.
- **Gotchas.** ROI census precondition via M036.

### 3.7 modelo 369 â€” IVA OSS / IOSS

- **Trilingual name.** es: `AutoliquidaciÃ³n del IVA â€” rÃ©gimen de
  ventanilla Ãºnica (OSS/IOSS)`; en: `OSS/IOSS VAT self-assessment`; hu:
  `OSS/IOSS IVA Ã¶nbevallÃ¡s`.
- **Category.** `iva`. **Cadence.** `quarterly` (UniÃ³n y exterior) /
  `monthly` (ImportaciÃ³n).
- **Legal basis.**
  - `ley-37-1992#164` (umbrella). Ley 37/1992 TÃ­tulo IX Cap. XI
    (rÃ©gimen OSS) NOT on disk â€” flagged.
  - `rd-1624-1992#71` (umbrella).
- **Applicability.** Optional opt-in for B2C cross-border EU distance
  sales and certain digital services.
- **Thresholds.** 10 000 EUR annual EU B2C threshold.
- **Relationships.** `replaces = {303}` for operations in scope.
- **Deadline.** End-of-month following end of period.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/iva/modelo-369.html`.
- **Casillas.** Dozens, per-country repeating blocks.
- **Gotchas.** OSS requires separate census filing (M035). Deferral
  candidate.

### 3.8 modelo 111 â€” retenciones IRPF (trabajo y actividades)

- **Trilingual name.** es: `Retenciones e ingresos a cuenta del IRPF.
  Rendimientos del trabajo y de actividades econÃ³micas`; en: `IRPF
  withholdings on employment and professional fees`; hu: `IRPF forrÃ¡sadÃ³
  (munkabÃ©rek Ã©s szabadfoglalkozÃ¡sÃº dÃ­jak)`.
- **Category.** `retenciones`. **Cadence.** `quarterly`.
- **Legal basis.**
  - `rd-439-2007#80`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a80`,
    `quoted_text_es` (summary): "Fija los tipos aplicables al cÃ¡lculo de
    retenciones e ingresos a cuenta sobre rendimientos del trabajo y
    establece las reglas de cÃ¡lculo de la base de retenciÃ³n y del tipo
    de retenciÃ³n."
  - `rd-439-2007#95`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a95`,
    `quoted_text_es` (summary): "Establece los tipos fijos de retenciÃ³n
    aplicables a los rendimientos de actividades profesionales,
    agrÃ­colas, ganaderas y forestales, y a las actividades en estimaciÃ³n
    objetiva."
  - `rd-439-2007#109`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a109`,
    `quoted_text_es` (summary): "Desarrolla las obligaciones formales de
    los retenedores y obligados a ingresar a cuenta, incluyendo el
    modelo, el plazo de presentaciÃ³n y la comunicaciÃ³n de datos a la
    AdministraciÃ³n tributaria."
- **Applicability.** Mandatory when the autÃ³nomo pays salaries or
  practitioner fees under retenciÃ³n. Maps to
  `AutonomoProfile.has_employees` OR `pays_professionals_with_retencion`
  (latter not on profile â€” see Â§8).
- **Thresholds.** None; filed even with zero.
- **Relationships.** `caps_into = {190}`.
- **Deadline.** Q1â€“Q3: 1â€“20 abril/julio/octubre; Q4: 1â€“20 enero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/retencion-trabajo-personal/modelo-111.html`.
- **Casillas.** ~15 casillas. Not in catalogue.
- **Gotchas.** Zero-activity periods still require presentation;
  suspension needs M036 mod.

### 3.9 modelo 115 â€” retenciones arrendamientos urbanos

- **Trilingual name.** es: `Retenciones e ingresos a cuenta. Rentas o
  rendimientos procedentes del arrendamiento o subarrendamiento de
  inmuebles urbanos`; en: `Withholdings on urban property rentals`; hu:
  `VÃ¡rosi ingatlanbÃ©rlet forrÃ¡sadÃ³ja`.
- **Category.** `retenciones`. **Cadence.** `quarterly`.
- **Legal basis.**
  - `ley-35-2006#99`, retrieved 2026-04-13, same passage as 3.2.
  - `rd-439-2007#109`, retrieved 2026-04-13, same passage as 3.8. Gap:
    specific art 100 RD 439/2007 not on disk.
- **Applicability.** Mandatory when the autÃ³nomo rents the local de
  negocio from a lessor subject to retenciÃ³n. Maps to
  `AutonomoProfile.pays_rent_with_retencion`.
- **Thresholds.** Exempt for arrendamiento de viviendas (LAU) and
  practical-practice cutoffs.
- **Relationships.** `caps_into = {180}`.
- **Deadline.** Q1â€“Q3: 1â€“20 abril/julio/octubre; Q4: 1â€“20 enero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/retencion-arrendamientos/modelo-115.html`.
- **Casillas.** ~5 casillas. Not in catalogue.
- **Gotchas.** Lessor NIF feeds the contacts store dependency.

### 3.10 modelo 123 â€” retenciones capital mobiliario

- **Trilingual name.** es: `Retenciones e ingresos a cuenta. Determinados
  rendimientos del capital mobiliario`; en: `Withholdings on certain
  movable-capital income`; hu: `Egyes tÅ‘kejÃ¶vedelmek forrÃ¡sadÃ³ja`.
- **Category.** `retenciones`. **Cadence.** `quarterly`.
- **Legal basis.**
  - `ley-35-2006#99`, retrieved 2026-04-13, same passage as 3.2.
  - `rd-439-2007#109`, retrieved 2026-04-13, same passage as 3.8. Gap:
    RIRPF arts 74â€“76 not on disk.
- **Applicability.** Mandatory for sociedades paying dividends /
  interest. **Out of scope for autonomo_ed_solo**; applies to SL.
- **Relationships.** `caps_into = {193}`.
- **Deadline.** Same as 111/115.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/retencion-capital/modelo-123.html`.
- **Casillas.** ~7 casillas.
- **Gotchas.** SL-only in practice.

### 3.11 modelo 180 â€” resumen anual retenciones arrendamientos

- **Trilingual name.** es: `Resumen anual. Retenciones e ingresos a
  cuenta sobre rendimientos del arrendamiento de inmuebles urbanos`;
  en: `Annual summary â€” urban rental withholdings`; hu: `Ã‰ves Ã¶sszesÃ­tÅ‘ â€”
  vÃ¡rosi ingatlanbÃ©rlet forrÃ¡sadÃ³ja`.
- **Category.** `informativa`. **Cadence.** `annual` (enero n+1).
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13, same passage as 3.6.
  - `rd-439-2007#109`, retrieved 2026-04-13, same passage as 3.8.
- **Applicability.** Mandatory when M115 was filed during the year.
- **Relationships.** `receives_from = {115}`.
- **Deadline.** 1â€“31 enero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/retencion-arrendamientos/modelo-180.html`.
- **Casillas.** ~10 header + N per-lessor rows.
- **Gotchas.** Must reconcile with four M115 sums.

### 3.12 modelo 190 â€” resumen anual retenciones trabajo y actividades

- **Trilingual name.** es: `Resumen anual. Retenciones e ingresos a
  cuenta sobre rendimientos del trabajo y de actividades econÃ³micas`;
  en: `Annual summary â€” employment and professional withholdings`; hu:
  `Ã‰ves Ã¶sszesÃ­tÅ‘ â€” munka- Ã©s szabadfoglalkozÃ¡sÃº forrÃ¡sadÃ³`.
- **Category.** `informativa`. **Cadence.** `annual` (enero n+1).
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13, same passage as 3.6.
  - `ley-35-2006#99`, retrieved 2026-04-13, same passage as 3.2.
- **Applicability.** Mandatory when M111 was filed during the year.
- **Relationships.** `receives_from = {111}`.
- **Deadline.** 1â€“31 enero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/retencion-trabajo-personal/modelo-190.html`.
- **Casillas.** ~20 header + N per-perceptor rows; keyed by subclave.
- **Gotchas.** Subclave taxonomy is the state machine.

### 3.13 modelo 347 â€” declaraciÃ³n anual de operaciones con terceros

- **Trilingual name.** es: `DeclaraciÃ³n anual de operaciones con
  terceras personas`; en: `Annual information return â€” third-party
  transactions`; hu: `Ã‰ves adatszolgÃ¡ltatÃ¡s harmadik felekkel folytatott
  Ã¼gyletekrÅ‘l`.
- **Category.** `informativa`. **Cadence.** `annual` (febrero n+1).
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13, same passage as 3.6.
  - `ley-58-2003#29`, retrieved 2026-04-13,
    `https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29`,
    `quoted_text_es` (summary): "Enumera las obligaciones tributarias
    formales, incluida la presentaciÃ³n de declaraciones,
    autoliquidaciones y comunicaciones, la llevanza de libros y
    registros y la expediciÃ³n y conservaciÃ³n de facturas."
- **Applicability.** Mandatory for taxpayers with third-party operations
  exceeding 3 005,06 EUR with the same counterparty. SII subjects
  exempt.
- **Thresholds.** 3 005,06 EUR per counterparty (IVA included).
- **Deadline.** 1â€“28/29 febrero n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/otros-impuestos-tasas/modelo-347.html`.
- **Casillas.** ~5 header + N per-counterparty rows.
- **Gotchas.** Heavy exclusion rules; SII exemption central for SL.

### 3.14 modelo 720 â€” bienes y derechos en el extranjero

- **Trilingual name.** es: `DeclaraciÃ³n informativa sobre bienes y
  derechos situados en el extranjero`; en: `Information return on
  assets and rights held abroad`; hu: `AdatszolgÃ¡ltatÃ¡s kÃ¼lfÃ¶ldÃ¶n lÃ©vÅ‘
  vagyonrÃ³l`.
- **Category.** `informativa`. **Cadence.** `annual` (marzo n+1).
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13, same passage as 3.6.
  - RGAT arts 42 bis / 42 ter / 54 bis NOT on disk â€” flagged.
- **Applicability.** Mandatory when holding bienes en el extranjero
  above 50 000 EUR in any of the three asset classes. Maps to
  `AutonomoProfile.bienes_extranjero_above_threshold`.
- **Thresholds.** 50 000 EUR per asset class; subsequent years only if
  value grows by 20 000 EUR.
- **Deadline.** 1 enero â€“ 31 marzo n+1.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/otros-impuestos-tasas/modelo-720.html`.
- **Casillas.** Three bloques, ~15 casillas each repeating.
- **Gotchas.** Post-CJEU C-788/19 sanctions struck down but informative
  duty stands.

### 3.15 modelo 232 â€” operaciones vinculadas y paraÃ­sos fiscales

- **Trilingual name.** es: `DeclaraciÃ³n informativa de operaciones
  vinculadas y de operaciones y situaciones relacionadas con paÃ­ses o
  territorios calificados como paraÃ­sos fiscales`; en: `Information
  return â€” related-party and tax-haven transactions`; hu: `Kapcsolt
  felekkel Ã©s adÃ³paradicsomokkal folytatott Ã¼gyletek
  adatszolgÃ¡ltatÃ¡sa`.
- **Category.** `informativa` (Sociedades-adjacent). **Cadence.**
  `annual` (mes 11 del cierre).
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13, same passage as 3.6.
- **Applicability.** **SL-only.**
- **Thresholds.** 250 000 EUR related-party threshold.
- **Relationships.** `related_modelos = {200}`.
- **Deadline.** Mes 11 desde fin del periodo impositivo.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/impuestos-sociedades/modelo-232.html`.
- **Casillas.** Per-operation repeating blocks.
- **Gotchas.** SL-only; deferral candidate.

### 3.16 modelo 036 â€” declaraciÃ³n censal completa

- **Trilingual name.** es: `DeclaraciÃ³n censal de alta, modificaciÃ³n y
  baja en el Censo de Empresarios, Profesionales y Retenedores`; en:
  `Full census filing â€” registration, modification and deregistration`;
  hu: `VÃ¡llalkozÃ³i adÃ³nyilvÃ¡ntartÃ¡si bevallÃ¡s (teljes)`.
- **Category.** `censal`. **Cadence.** `ad_hoc`.
- **Legal basis.**
  - `rd-1065-2007#30`, retrieved 2026-04-13, same passage as 3.6.
  - `ley-58-2003#29`, retrieved 2026-04-13, same passage as 3.13.
- **Applicability.** Mandatory at alta, modification of epÃ­grafes IAE,
  domicile, rÃ©gimen IVA, rÃ©gimen IRPF, ROI, baja.
- **Relationships.** Gate for 349 (ROI), 303 rÃ©gimen switching, 111/115.
- **Deadline.** Event-driven.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml`.
- **Casillas.** ~100 boxes across pÃ¡ginas 1â€“7.
- **Gotchas.** Full form; autÃ³nomo simple normally uses 037.

### 3.17 modelo 037 â€” declaraciÃ³n censal simplificada

- **Trilingual name.** es: `DeclaraciÃ³n censal simplificada`; en:
  `Simplified census filing`; hu: `EgyszerÅ±sÃ­tett adÃ³nyilvÃ¡ntartÃ¡si
  bevallÃ¡s`.
- **Category.** `censal`. **Cadence.** `ad_hoc`.
- **Legal basis.** Same as 3.16.
- **Applicability.** AutÃ³nomos personas fÃ­sicas que encajan en el
  subconjunto. Default for autonomo_ed_solo.
- **Relationships.** 037 strictly subset of 036; ROI forces 036.
- **Deadline.** Event-driven.
- **Channel hint.** Same as 036.
- **Casillas.** ~40 boxes.
- **Gotchas.** Upgrade path to 036 on rÃ©gimen change.

### 3.18 modelo 200 â€” impuesto sobre sociedades

- **Trilingual name.** es: `DeclaraciÃ³n del Impuesto sobre Sociedades`;
  en: `Corporate income tax return`; hu: `TÃ¡rsasÃ¡gi adÃ³bevallÃ¡s`.
- **Category.** `sociedades`. **Cadence.** `annual` (mes 7 del cierre).
- **Legal basis.**
  - `ley-58-2003#29`, retrieved 2026-04-13, same passage as 3.13. Ley
    27/2014 IS NOT on disk â€” flagged.
- **Applicability.** **SL-only.**
- **Relationships.** `receives_from = {202}`.
- **Deadline.** 1â€“25 julio for aÃ±o natural.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/impuestos-sociedades/modelo-200.html`.
- **Casillas.** Very large (~600+); unstable year-to-year.
- **Gotchas.** SL-only; catalogue stub candidate.

### 3.19 modelo 202 â€” pago fraccionado IS

- **Trilingual name.** es: `Pago fraccionado del Impuesto sobre
  Sociedades`; en: `Corporate income tax fractional payment`; hu:
  `TÃ¡rsasÃ¡gi adÃ³ rÃ©szletfizetÃ©s`.
- **Category.** `sociedades`. **Cadence.** Three periods (abril,
  octubre, diciembre).
- **Legal basis.** Same umbrella as 3.18.
- **Applicability.** SL-only; INCN/result gated.
- **Thresholds.** 6M EUR INCN drives rÃ©gimen de cÃ¡lculo.
- **Relationships.** `caps_into = {200}`.
- **Deadline.** 1â€“20 abril / octubre / diciembre.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/impuestos-sociedades/modelo-202.html`.
- **Casillas.** ~40 casillas.
- **Gotchas.** SL-only; deferral candidate.

### 3.20 modelo 840 â€” impuesto sobre actividades econÃ³micas (IAE)

- **Trilingual name.** es: `DeclaraciÃ³n del Impuesto sobre Actividades
  EconÃ³micas`; en: `Economic Activities Tax census declaration`; hu:
  `GazdasÃ¡gi tevÃ©kenysÃ©gek adÃ³ja (IAE) nyilvÃ¡ntartÃ¡si bevallÃ¡s`.
- **Category.** `otros`. **Cadence.** `ad_hoc`.
- **Legal basis.**
  - `ley-58-2003#29`, retrieved 2026-04-13, same passage as 3.13. RDLeg
    2/2004 TRLHL arts 78â€“91 NOT on disk â€” flagged.
- **Applicability.** Exento para personas fÃ­sicas y para personas
  jurÃ­dicas con INCN < 1M EUR. **autonomo_ed_solo is exempt.**
- **Thresholds.** 1 000 000 EUR INCN.
- **Deadline.** Event-driven.
- **Channel hint.**
  `https://sede.agenciatributaria.gob.es/Sede/tributos-locales/modelo-840.html`.
- **Casillas.** ~20 casillas.
- **Gotchas.** Default-exempt for every autÃ³nomo profile.

## 4. d2 â€” profile applicability matrix

Profiles: `A1 = autonomo_ed_solo`, `A2 = autonomo_ed_con_empleados`,
`A3 = autonomo_ed_con_profesionales`, `A4 = autonomo_ed_con_alquiler`,
`A5 = autonomo_ed_ue`, `A6 = autonomo_ed_bienes_extranjero`,
`A7 = autonomo_eo`, `S1 = sl`. Cells: `M` = must_file, `y` = may_file,
`x` = exempt, `-` = n_a.

| modelo | A1 | A2 | A3 | A4 | A5 | A6 | A7 | S1 | note |
|-------:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:-----|
| 100    | M  | M  | M  | M  | M  | M  | M  | -  | f1 |
| 130    | M  | M  | M  | M  | M  | M  | -  | -  | f2 |
| 131    | -  | -  | -  | -  | -  | -  | M  | -  | f3 |
| 303    | M  | M  | M  | M  | M  | M  | M  | M  | f4 |
| 390    | M  | M  | M  | M  | M  | M  | M  | M  | f5 |
| 349    | -  | -  | -  | -  | M  | -  | -  | y  | f6 |
| 369    | y  | y  | y  | y  | y  | y  | y  | y  | f7 |
| 111    | -  | M  | M  | -  | -  | -  | y  | M  | f8 |
| 115    | -  | -  | -  | M  | -  | -  | -  | M  | f9 |
| 123    | -  | -  | -  | -  | -  | -  | -  | y  | f10 |
| 180    | -  | -  | -  | M  | -  | -  | -  | M  | f11 |
| 190    | -  | M  | M  | -  | -  | -  | y  | M  | f12 |
| 347    | y  | y  | y  | y  | y  | y  | y  | y  | f13 |
| 720    | -  | -  | -  | -  | -  | M  | -  | y  | f14 |
| 232    | -  | -  | -  | -  | -  | -  | -  | y  | f15 |
| 036    | y  | y  | y  | y  | M  | y  | y  | M  | f16 |
| 037    | M  | y  | y  | y  | -  | y  | M  | -  | f17 |
| 200    | -  | -  | -  | -  | -  | -  | -  | M  | f18 |
| 202    | -  | -  | -  | -  | -  | -  | -  | y  | f19 |
| 840    | x  | x  | x  | x  | x  | x  | x  | y  | f20 |

Footnotes:

- **f1.** AutÃ³nomos always must_file M100 regardless of umbrales.
- **f2.** M130 must_file for any ED autÃ³nomo unless 70% retenciÃ³n rule
  excludes them per activity.
- **f3.** Only `autonomo_eo` owes M131; 130/131 mutually exclusive.
- **f4.** Gated by `IVARegime`: GENERAL/SIMPLIFICADO must_file;
  RECARGO_EQUIVALENCIA/EXENTO exempt.
- **f5.** Same regime gating as f4; SII filers exempt.
- **f6.** Triggered by `does_intracomunitario=True`.
- **f7.** OSS opt-in; never mandatory absent the opt.
- **f8.** Triggered by `has_employees` OR paying profesionales with
  retenciÃ³n.
- **f9.** Triggered by `pays_rent_with_retencion`.
- **f10.** SL-only in practice.
- **f11.** Must_file iff M115 filed in the year.
- **f12.** Must_file iff M111 filed in the year.
- **f13.** 3 005,06 EUR per-counterparty; SII exempt. Default may_file;
  flips to must_file once totals cross threshold.
- **f14.** Triggered by `bienes_extranjero_above_threshold`.
- **f15.** SL-only, operaciones vinculadas thresholds.
- **f16.** 036 mandatory for A5 (ROI) and S1; other autÃ³nomos default
  037.
- **f17.** 037 default; A5 pushed to 036 by ROI.
- **f18.** SL-only.
- **f19.** SL-only; INCN/result gated.
- **f20.** IAE exempt for personas fÃ­sicas and INCN <1M; may_file for
  SL above 1M INCN.

## 5. d3 â€” gap analysis vs current codebase

### 5.1 already on main (builders)

Confirmed by `src/aeat/application/filing/_builders/`:

- `modelo_130.py` + `_modelo_130_schema.py` â€” IRPF pago fraccionado.
- `modelo_303.py` + `_modelo_303_schema.py` â€” IVA autoliquidaciÃ³n.
- `modelo_390.py` + `_modelo_390_schema.py` â€” IVA resumen anual.

No other builder, no other schema, no generator glue.

### 5.2 casilla catalogue coverage

Confirmed by `corpus/casillas/`:

- `modelo_130/2025Q4.json` â€” 4 casillas seeded (stub).
- `modelo_303/2025Q4.json` â€” 4 casillas seeded (stub).
- `modelo_390/2025.json` â€” 3 casillas seeded (stub).

Every other modelo has zero catalogue coverage.

### 5.3 enum / registry references

`src/aeat/domain/modelos/__init__.py` is a **stub** with empty `__all__`. No
`ModeloCode` enum, no registry, no metadata. The deadline engine at
`src/aeat/domain/deadlines/_models.py` references modelos as free-form `str`
(`FilingObligation.modelo: str`) and must migrate once #108 lands. The
`AutonomoProfile` carries four boolean triggers (`has_employees`,
`pays_rent_with_retencion`, `does_intracomunitario`,
`bienes_extranjero_above_threshold`) that map directly onto the rules
in Â§3. A fifth boolean `pays_professionals_with_retencion` is implied
by 111/190 and flagged in Â§8.

### 5.4 absent modelos â€” effort estimates

`S = 1â€“2 days`, `M = 3â€“5 days`, `L = 1â€“2 weeks`, `XL = 2â€“4 weeks` per
modelo, counting builder + submitter + casilla catalogue + tests.

| modelo | builder | submitter | casillas | tests | overall |
|-------:|:-------:|:---------:|:--------:|:-----:|:-------:|
| 100    | XL      | L         | XL       | L     | **XL**  |
| 131    | M       | S         | M        | S     | **M**   |
| 349    | M       | M         | M        | M     | **M**   |
| 369    | L       | L         | L        | M     | **L**   |
| 111    | M       | S         | M        | S     | **M**   |
| 115    | S       | S         | S        | S     | **S**   |
| 123    | S       | S         | S        | S     | **S**   |
| 180    | M       | S         | M        | S     | **M**   |
| 190    | L       | M         | L        | M     | **L**   |
| 347    | L       | M         | L        | M     | **L**   |
| 720    | M       | M         | M        | M     | **M**   |
| 232    | M       | M         | M        | S     | **M**   |
| 036    | L       | L         | L        | M     | **L**   |
| 037    | M       | M         | M        | S     | **M**   |
| 200    | XL      | L         | XL       | L     | **XL**  |
| 202    | M       | M         | M        | S     | **M**   |
| 840    | S       | S         | S        | S     | **S**   |

## 6. d5 â€” follow-up implementation issue sketches

All Track A. Priority tiers: P0 = user owes in 2026; P1 = near-future
autÃ³nomo; P2 = SL / deferrable.

### 6.1 modelo 111

- **Title.** `feat(filing): modelo 111 builder + submitter`
- **Path.** `src/aeat/application/filing/_builders/modelo_111.py`,
  `src/aeat/domain/casillas/catalogues/modelo_111/`
- **Scope.** Builder + JSON schema + casilla catalogue + unit tests +
  CLI wire-up.
- **Deps.** `has_employees` OR new `pays_professionals_with_retencion`;
  `aeat.contacts` perceptor store (not yet built â€” blocker).
- **Track / effort / priority.** A / **M** / **P1**.

### 6.2 modelo 190

- **Title.** `feat(filing): modelo 190 annual summary builder`
- **Path.** `src/aeat/application/filing/_builders/modelo_190.py`
- **Scope.** Builder + subclave enum + casilla catalogue + reconciliation
  against four M111 + tests.
- **Deps.** Blocked by 111.
- **Track / effort / priority.** A / **L** / **P1**.

### 6.3 modelo 115

- **Title.** `feat(filing): modelo 115 builder`
- **Path.** `src/aeat/application/filing/_builders/modelo_115.py`
- **Scope.** Builder + 5 casillas + tests.
- **Deps.** `pays_rent_with_retencion`; lessor NIF contacts store.
- **Track / effort / priority.** A / **S** / **P1**.

### 6.4 modelo 180

- **Title.** `feat(filing): modelo 180 annual summary builder`
- **Path.** `src/aeat/application/filing/_builders/modelo_180.py`
- **Scope.** Builder + per-lessor rows + reconciliation vs M115.
- **Deps.** Blocked by 115.
- **Track / effort / priority.** A / **M** / **P1**.

### 6.5 modelo 349

- **Title.** `feat(filing): modelo 349 recapitulativa builder`
- **Path.** `src/aeat/application/filing/_builders/modelo_349.py`
- **Scope.** Builder + cadence flip + ROI gate + tests.
- **Deps.** `does_intracomunitario` + M036 ROI precondition.
- **Track / effort / priority.** A / **M** / **P2**.

### 6.6 modelo 347

- **Title.** `feat(filing): modelo 347 annual third-party return`
- **Path.** `src/aeat/application/filing/_builders/modelo_347.py`
- **Scope.** Builder + counterparty threshold + SII exemption + per-
  counterparty row generation from TDP T1â€“T6.
- **Deps.** Track B TDP counterparty totaliser.
- **Track / effort / priority.** A / **L** / **P1**.

### 6.7 modelo 100

- **Title.** `feat(filing): modelo 100 draft builder`
- **Path.** `src/aeat/application/filing/_builders/modelo_100.py`
- **Scope.** Builder + ~500 casillas + reconciliation against four
  M130 + M190 perceptor rows + CCAA deductions catalogue + Renta Web
  borrador interop.
- **Deps.** Blocked by 130 (present), 190 (absent), CCAA catalogue
  (absent), Manual prÃ¡ctico Renta text extraction (absent).
- **Track / effort / priority.** A / **XL** / **P0**.

### 6.8 modelo 131

- **Title.** `feat(filing): modelo 131 builder`
- **Path.** `src/aeat/application/filing/_builders/modelo_131.py`
- **Scope.** Builder + module-regime casillas + tests.
- **Deps.** `autonomo_eo` profile branch.
- **Track / effort / priority.** A / **M** / **P2**.

### 6.9 modelo 720

- **Title.** `feat(filing): modelo 720 informativa`
- **Path.** `src/aeat/application/filing/_builders/modelo_720.py`
- **Scope.** Builder + three bloques + 50 000 EUR gate + tests.
- **Deps.** `bienes_extranjero_above_threshold`.
- **Track / effort / priority.** A / **M** / **P2**.

### 6.10 modelo 036 / 037

- **Title.** `feat(filing): modelo 036/037 censal builders`
- **Path.** `src/aeat/application/filing/_builders/modelo_036.py`,
  `src/aeat/application/filing/_builders/modelo_037.py`
- **Scope.** Shared schema (037 = subset of 036) + event-driven cadence
  + tests.
- **Deps.** Event-driven branch in deadline engine (not modelled).
- **Track / effort / priority.** A / **L** / **P1**.

### 6.11 modelo 123

- **Title.** `feat(filing): modelo 123 builder (SL-scope)`
- **Track / effort / priority.** A / **S** / **P2**.

### 6.12 modelo 200 / 202

- **Title.** `feat(filing): modelo 200/202 (SL track)`
- **Scope.** Catalogue entries only in v1; builder deferred.
- **Track / effort / priority.** A / **XL** / **P2**.

### 6.13 modelo 232

- **Title.** `feat(filing): modelo 232 (SL track)`
- **Track / effort / priority.** A / **M** / **P2**.

### 6.14 modelo 369

- **Title.** `feat(filing): modelo 369 OSS builder`
- **Track / effort / priority.** A / **L** / **P2**.

### 6.15 modelo 840

- **Title.** `feat(filing): modelo 840 IAE (stub)`
- **Scope.** Catalogue entry only; default-exempt for autÃ³nomos.
- **Track / effort / priority.** A / **S** / **P2**.

## 7. downstream code shape (informative)

The execution phase â€” after the ADR fixes decisions â€” will materialise a
pydantic v2 shape under `src/aeat/domain/modelos/`. Candidate types:

- `ModeloCode(StrEnum)` â€” closed enum of codes (`M_100`, `M_130`,
  `M_131`, `M_303`, `M_390`, `M_349`, `M_369`, `M_111`, `M_115`,
  `M_123`, `M_180`, `M_190`, `M_347`, `M_720`, `M_232`, `M_036`,
  `M_037`, `M_200`, `M_202`, `M_840`). The `M_` prefix avoids
  leading-digit identifier issues.
- `ModeloCategory(StrEnum)` â€” `IRPF | IVA | RETENCIONES | INFORMATIVA |
  CENSAL | SOCIEDADES | PATRIMONIO | OTROS`.
- `ModeloCadence(StrEnum)` â€” `MONTHLY | QUARTERLY | ANNUAL | AD_HOC`.
- `TaxpayerProfile(StrEnum)` â€” the eight profile codes from Â§4.
- `LegalCitationSource(StrEnum)` â€” `NORMATIVE | MANUAL_IVA |
  MANUAL_RENTA | BOE_ORDEN`.
- `LegalCitation(BaseModel, frozen=True, strict=True, extra='forbid')`
  â€” `source: LegalCitationSource`, `ref_id: str` (e.g.
  `ley-37-1992#164`), `url: str | None`, `retrieval_date: date`,
  `quoted_text_es: str` (min len 1), `notes: str = ""`.
- `ModeloApplicability(BaseModel, frozen=True)` â€” per-profile
  `must_file | may_file | exempt | n_a` plus a free-form trigger keyed
  to Â§4 footnotes.
- `ModeloMetadata(BaseModel, frozen=True)` â€” `code: ModeloCode`,
  `name: Translatable`, `category: ModeloCategory`,
  `cadence: ModeloCadence`, `legal_basis: tuple[LegalCitation, ...]`,
  `applicability: Mapping[TaxpayerProfile, ModeloApplicability]`,
  `caps_into: tuple[ModeloCode, ...]`,
  `related: tuple[ModeloCode, ...]`, `channel_hint: str | None`,
  `casilla_count_estimate: int | None`, `gotchas: tuple[str, ...]`.
- `MODELO_REGISTRY: Mapping[ModeloCode, ModeloMetadata]` â€” frozen
  mapping validated at import time: every code has at least one
  citation, every citation carries non-empty `quoted_text_es`,
  `caps_into` references only known codes, registry covers every value
  of `ModeloCode`.

`Translatable` reuses the project's `aeat.core.i18n.Translatable` (es / en /
hu).

## 8. open questions for the adr

- **SL scope.** Does v1 include SL rows for 123, 200, 202, 232 with
  `must_file`, or should SL be stubbed with `n_a` placeholders? The
  north-star is autÃ³nomo, so SL-only modelos cost maintenance.
- **Deferral set.** Confirm 232, 369, 720, 840, 200, 202 are catalogue-
  only / no builder in v1. 720 is the borderline case.
- **Casilla cross-reference strictness.** Must `ModeloMetadata` require
  the casilla catalogue to exist before registration? Current stubs
  only cover 130/303/390.
- **Portal URL hints.** Freeze `channel_hint` shape now or defer until
  the submitter work for #7 lands? Risk of URL drift.
- **Profile boolean.** `pays_professionals_with_retencion` is implied
  by 111/190 but absent from `aeat.domain.deadlines.AutonomoProfile`. Add a
  new flag or overload `has_employees` (semantically wrong)?
- **Citation provenance.** The on-disk corpus stores `summary.es`, not
  the BOE literal body. Is the ADR OK treating `summary.es` as
  `quoted_text_es` (marked as a curated summary), or must a separate
  pipeline extract literal BOE XML before the catalogue can cite it?
- **Manual prÃ¡ctico extraction.** Manuals are PDF-manifest only. Block
  on extraction for modelos where ley/reglamento is thin (e.g. 369 OSS)?
- **Deadline-engine integration.** Does the registry own the
  `DeadlineRule` for each modelo, or does `aeat.domain.deadlines` keep
  ownership and the registry only reference rules by key?
- **037 vs 036 default.** For `autonomo_ed_solo`, mark 037 as
  `must_file` at alta or `may_file` (the user may have historically
  filed 036)?
- **IVA regime as dimension.** The matrix collapses `IVARegime` into
  profile defaults. Should the registry expose applicability as
  `(TaxpayerProfile, IVARegime)` rather than `TaxpayerProfile` alone?
