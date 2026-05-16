---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/research/ location)
# Feature tag (replace modelo-036-census-sync with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#research'
  - '#modelo-036-census-sync'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-16'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-plan]]")
related: []
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `modelo-036-census-sync` research: AEAT G313/G322 surface, per-field legal grounding, stale-cascade contract

Modelo 036 (Declaracion Censal de Alta, Modificacion y Baja en el Censo de Empresarios, Profesionales y Retenedores) is treated in this codebase as a live-synced census data store, not a filing lifecycle artefact. The alta / modificacion / baja periods in `036.toml` are event-trigger kinds that mark what changed and when; they are not filing states. This research documents the AEAT surface contracts, per-field legal grounding, the cross-validation map from census fields to downstream calculations, the stale-cascade contract, and the confirmed suppression of Modelo 037.

## Findings

### Section 1 -- AEAT G313 / G322 surface contract

**G313 -- Mis Datos Censales (consultation)**

G313 (`/Sede/procedimientoini/G313.shtml`) is the AEAT Sede Electronica procedure for Certificados tributarios -- Situacion Censal. It exposes the taxpayer current census status as a read-only certified document. The legal basis is Articles 70-76 of Real Decreto 1065/2007 (RGAT), which regulate tax certificates and their expedicion. The G313 page describes the certificate as showing Situacion Censal -- the set of census data currently registered for the NIF, including economic activities declared, fiscal address, applicable tax regimes, and census dates.

Authentication accepted by G313 is limited to strong electronic credentials: certificado electronico reconocido (FNMT or equivalent), DNIe, Cl@ve Permanente, and Cl@ve PIN. Cl@ve Movil is **not** accepted for G313 certificate procedures (it is accepted for simpler self-service procedures, but certificate expedicion requires stronger identity assurance). This is the binding design constraint for the `aeat config profile census refresh` adapter: it must present a valid certificate or Cl@ve Permanente credential; PIN-only flows are insufficient for the consultation certificate endpoint.

The G313 read-only surface is the sole target for the census sync adapter in this wave. The HTML result page returns a structured certificate with named sections corresponding to the Modelo 036 page structure (Pagina 1 -- identificacion, Pagina 2 -- IRPF, Pagina 3 -- IVA, etc.). The adapter must parse these sections to reconstruct the census snapshot.

Source: https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml

**G322 -- Modelo 036 declaration (submission)**

G322 (`/Sede/procedimientoini/G322.shtml`) is the submission procedure for Modelo 036. It accepts alta (registration), modificacion (modification), and baja (deregistration) declarations. Unlike G313, G322 additionally accepts Cl@ve Movil, in line with the general pattern that declaration submission has a broader authentication surface than certificate expedicion. G322 supports fully electronic (telematica) submission, PDF generation for paper presentation, and the Censos WEB service for individual taxpayers.

**G322 is permanently out of scope for this wave.** Live writes against AEAT census are prohibited under `aeat-safety-legal-gates.md`. No CLI verb in the `aeat config profile census` tree will call G322 without a future explicit ADR reversing the live-write prohibition.

Source: https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml

**Sync verb tree**

The four verbs that operate against G313 data are:

- `aeat config profile census refresh` -- pulls a fresh G313 snapshot from AEAT and stores it content-addressed (ACTIVE, superseding the previous snapshot to SUPERSEDED)
- `aeat config profile census show` -- displays the current ACTIVE snapshot
- `aeat config profile census compare` -- diffs the ACTIVE snapshot against the local profile config
- `aeat config profile census apply` -- applies the ACTIVE snapshot to the local profile, cross-validating dependents and stamping CENSUS_STALE where needed

The snapshot lifecycle mirrors Borrador100: each snapshot is content-addressed; a new pull marks the previous snapshot SUPERSEDED and creates a new ACTIVE record.

---

### Section 2 -- Per-field legal grounding inventory

**`census.activity_start_date` (fecha de alta)**

Legal basis: RGAT Art. 9 (Real Decreto 1065/2007, BOE-A-2007-15984). Art. 9 requires any person who must be included in the Census of Businesspeople, Professionals and Withholders to file a registration declaration (declaracion de alta) before beginning the activity. The date of alta registered in Modelo 036 is the date from which tax obligations in the census are computed. RIRPF Art. 75 references the activity-start date for determining when withholding obligations commence.

Source: https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984

**`census.activity_end_date` (fecha de baja)**

Legal basis: RGAT Art. 11 (Real Decreto 1065/2007, BOE-A-2007-15984). Art. 11 requires a declaracion de baja when the taxpayer ceases all business or professional activities, or stops paying income subject to withholding. The baja date closes the census period and is the reference point for pro-rating annual obligations in the year of cessation.

Source: https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984

**`census.establecimiento_type` (own / rented / free-use premises)**

Legal basis: LIRPF Arts. 28 and 30 (Ley 35/2006, BOE-A-2006-20764). Art. 28 establishes that net income from economic activities in direct estimation is computed following Impuesto sobre Sociedades rules as adapted by Art. 30. Art. 30 limits deductibility to expenses effectively incurred and directly related to the activity. Premises tenure type determines which expense line is deductible: rental payments for rented premises; amortisation for owned premises; neither for free-use premises. The field feeds the expense-category selector in the calculation engine and is declared on Modelo 036 per Orden EHA/1274/2007 (BOE-A-2007-9508).

Source: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (LIRPF Arts. 28 and 30)

**`census.elected_withholding_pct` (1% / 7% / 15%)**

Legal basis: LIRPF Art. 101.5 (Ley 35/2006, BOE-A-2006-20764) and RIRPF Art. 95.1-95.2 (Real Decreto 439/2007, BOE-A-2007-6820, as amended by Real Decreto 31/2023, BOE-A-2023-2023).

- **15% -- standard professional retention.** LIRPF Art. 101.5 sets the general withholding rate for income from professional activities at the percentage established by regulation. RIRPF Art. 95.1 sets this at 15% of the gross amount. This is the default for all professionals not in a reduced-rate category.

- **7% -- reduced rate for nuevos profesionales.** RIRPF Art. 95.1 (as amended by Real Decreto 31/2023) establishes a 7% rate applicable during the tax period of activity initiation and the two following periods, provided the taxpayer had not carried out any professional activity in the year prior to the activity start date. The taxpayer must notify each payer in writing; the payer must retain the signed communication. The 7% also applies to certain listed IAE groups (851, 852, 853, 861, 862, 864, 869 of Section 2 and groupings 01, 02, 03, 05 of Section 3) and to performing-arts / audiovisual / musical activities.

- **1% -- activities in objective estimation (modulos) and transport.** RIRPF Art. 95.2 sets a 1% retention for income from activities included in the objective estimation method as listed in the annual Orden ministerial. The annual enabling Orden for 2026 is Orden HAC/1425/2025 (BOE-A-2025-25272).

The `elected_withholding_pct` field stores which rate the taxpayer has communicated on their 036 census declaration. The calculation engine uses this value as the override for the default 15% in all pago a cuenta models (Modelo 130, 131, 115).

Sources: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (LIRPF Art. 101.5); https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820 (RIRPF Art. 95); https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-2023 (RD 31/2023); https://www.boe.es/buscar/act.php?id=BOE-A-2025-25272 (Orden HAC/1425/2025)

**`contact.fiscal_address_cadastral_reference`**

Legal basis: Real Decreto Legislativo 1/2004, de 5 de marzo (BOE-A-2004-4163, Texto Refundido de la Ley del Catastro Inmobiliario). The referencia catastral is the mandatory official identifier for real estate: an alphanumeric code that uniquely positions the property on the cadastral cartography. The Modelo 036 instructions issued by Orden EHA/1274/2007 (BOE-A-2007-9508) require the cadastral reference of the fiscal address premises to be declared. The precise article of RDLeg 1/2004 mandating inclusion of the cadastral reference in census-tax declarations is [UNCONFIRMED -- the article governing the declaration obligation requires direct reading of the current consolidated BOE text; available sources confirm the mandatory-identifier status of the referencia catastral but do not quote the exact article number for its inclusion in census declarations].

Source: https://www.boe.es/buscar/act.php?id=BOE-A-2004-4163; https://www.boe.es/buscar/act.php?id=BOE-A-2007-9508

**`contact.fiscal_address_is_habitual_vivienda` (flag)**

Legal basis: LIRPF Art. 68.1.3 (Ley 35/2006, BOE-A-2006-20764) as in force on 31 December 2012, preserved under Disposicion Transitoria Decimoctava (introduced by Ley 16/2012) for taxpayers who already held rights entitling them to the deduccion por inversion en vivienda habitual. Art. 68.1.3 defined vivienda habitual as the building constituting the taxpayer residence for a continuous period of at least three years, with exceptions for death or forced relocation (marriage, separation, job transfer, first employment, job change). From 1 January 2013, Art. 68.1 was suppressed for new acquisitions but the concept of vivienda habitual remains legally operative for the afectacion parcial expense deductibility computation under LIRPF Art. 30 rule 5. The flag drives the eligibility check for HOME_OFFICE deductions and transitional-regime vivienda habitual deducciones.

Source: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (LIRPF Art. 68.1.3 and DT 18)

**`vivienda_office.total_m2` + `vivienda_office.office_m2` and the `business_ratio`**

Legal basis: LIRPF Art. 30.2 rule 5 (Ley 35/2006, BOE-A-2006-20764), introduced by Ley 6/2017 de Reformas Urgentes del Trabajo Autonomo (effective 1 January 2018). This rule provides that when a taxpayer partially dedicates their habitual residence to an economic activity, utility and supply expenses (suministros: water, gas, electricity, telephone, internet) are deductible at the percentage resulting from applying **30% to the ratio of business square metres to total dwelling square metres**, unless the taxpayer proves a higher or lower percentage applies.

The business_ratio for suministros is therefore: `(office_m2 / total_m2) * 0.30`.

The 30% is not a cap on how much of the dwelling may be designated as business use -- it is a statutory multiplier applied to the surface ratio for the suministros deduction category only. Ownership costs (amortisation, IBI, building fees) remain deductible in simple proportion `office_m2 / total_m2` without the 30% multiplier, per RIRPF Art. 22 and LIRPF Art. 29. The AEAT 2022 IRPF Practical Guide (Chapter 6) confirms there is no statutory percentage ceiling on the proportion of a dwelling that may be designated as business-affected; affectation is limited to the portion actually used for the activity capable of separate, independent use (RIRPF Art. 22).

Consequently, the HOME_OFFICE calculation category applies the 30% multiplier to the surface ratio for suministros line items and the raw surface ratio for ownership-cost line items. There is no statutory 30% ceiling on the overall `office_m2 / total_m2` ratio itself.

Sources: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (LIRPF Art. 30.2 rule 5); https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820 (RIRPF Art. 22); https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2022/c06-rendimientos-actividades-economicas-cuestiones-generales/elementos-patrimoniales-afectos-actividad-economica/criterios-afectacion-bienes-derechos-ejercicio.html

**`iva.roi_enrolled` (Registro de Operadores Intracomunitarios / VIES)**

Legal basis: LIVA Art. 25 (Ley 37/1992, BOE-A-1992-28740), which defines the exemption for intra-community deliveries and requires the acquirer to be identified by a VAT number assigned by another member state. RIVA Art. 3 (Real Decreto 1624/1992, BOE-A-1992-29636) and RGAT census provisions (Real Decreto 1065/2007, BOE-A-2007-15984) govern the census declaration of ROI enrollment. Inclusion in the ROI results in assignment of an intra-community VAT identification number (NIF-IVA, prefix ES) and entry into the VIES (VAT Information Exchange System) EU-wide cross-check database. The flag gates the obligation to file Modelo 349 (Declaracion Recapitulativa de Operaciones Intracomunitarias) and triggers the GROI live validation step.

Source: https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740 (LIVA Art. 25); https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984 (RGAT census provisions)

**`iva.oss_enrolled` (One Stop Shop / Ventanilla Unica)**

Legal basis: LIVA Art. 163 unvicies (Ley 37/1992, BOE-A-1992-28740, Chapter XI of Title IX), inserted by transposition of the EU e-commerce VAT package (Directive 2021/514, DAC7). Art. 163 unvicies establishes the special OSS regime for: (a) EU-established service providers supplying services to non-taxable persons in other member states; (b) intra-community distance sales of goods; (c) certain domestic deliveries through electronic interfaces. Under OSS, the operator registers in a single member state and declares and pays VAT on covered transactions across all member states via a single quarterly return (Modelo 369 in Spain). The flag indicates the taxpayer has enrolled in OSS through AEAT as member state of identification.

Source: https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740 (LIVA Art. 163 unvicies et seq.)

**`iva.regime` (IVA regime enum)**

Legal basis: LIVA Title IX (Ley 37/1992, BOE-A-1992-28740):

- `GENERAL` -- the residual regime for operations not covered by any special regime. Art. 120 LIVA lists the special regimes that derogate from it; the general regime is the default for all other operators.
- `SIMPLIFICADO` -- Arts. 122-123 LIVA. Applies to natural persons and certain entities in objective estimation (modulos) for IRPF, for activities listed in the annual Orden ministerial. The volume threshold is fixed at EUR 250,000 for 2016-2026 by successive prorrogas, most recently Orden HAC/1425/2025 (BOE-A-2025-25272).
- `AGRICULTURA_GANADERIA_PESCA` (REAGP) -- Art. 124 LIVA. Applies to agricultural, livestock, and fishing activities. Operators under REAGP receive a flat compensation percentage from buyers and do not file periodic IVA returns.
- `RECARGO_EQUIVALENCIA` -- Arts. 148-163 LIVA. Applies compulsorily to minoristas who do not transform the goods. They pay a surcharge alongside the IVA type on purchases; they do not file periodic IVA returns, so Modelo 303 is not required for this regime.
- `OSS` -- Art. 163 unvicies LIVA (see iva.oss_enrolled above).
- `IOSS` -- [UNCONFIRMED: the exact LIVA article number for Import OSS should be verified against the current consolidated BOE text of Ley 37/1992, as the e-commerce package uses latin ordinal article numbering and authoritative article numbers for IOSS differ between secondary sources.]

Source: https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740

**`irpf.uses_objective_estimation` (estimacion objetiva / modulos)**

Legal basis: LIRPF Art. 31 (Ley 35/2006, BOE-A-2006-20764). Art. 31 establishes the rules for the objective estimation method: scope (activities listed by Orden ministerial), exclusion thresholds (volume of operations, number of employees, purchase amounts), and the requirement to opt in or out by January of each year. The annual implementing Orden for 2026 is Orden HAC/1425/2025 (BOE-A-2025-25272), which approves the signs, indices, and modules applicable to activities in its Annexes I, II, and III. The exclusion threshold for the set of non-agricultural activities is EUR 150,000 in net turnover. The flag determines which IRPF calculation method the engine uses (Modelo 130 for directa vs Modelo 131 for objetiva) and whether the 1% withholding rate (RIRPF Art. 95.2) applies.

Sources: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (LIRPF Art. 31); https://www.boe.es/buscar/act.php?id=BOE-A-2025-25272 (Orden HAC/1425/2025)

---

### Section 3 -- Cross-validation: census fields that gate calculations

| Census field | Downstream calculation gated |
|---|---|
| `vivienda_office.office_m2` / `total_m2` | HOME_OFFICE suministros deduction. Any change to either m2 field invalidates all open HOME_OFFICE expense calculations. |
| `census.elected_withholding_pct` | Overrides the default 15% retention in Modelo 130, Modelo 131, and Modelo 115. A change from 15% to 7% at the start of year 2 changes all quarterly retention line items. |
| `census.activity_start_date` | Determines whether the 7% nuevos profesionales rate is still valid. Gates the eligibility check in `validate_withholding_rate`. |
| `iva.roi_enrolled` | Gates the Modelo 349 obligation check. Also gates the GROI live cross-validation step. |
| `iva.oss_enrolled` | Gates Modelo 369 obligation. If false, the OSS Modelo 369 builder raises a precondition error. |
| `iva.regime` | Determines which IVA modelo family is obligatory per the regime rules in Section 2. |
| `irpf.uses_objective_estimation` | Determines whether Modelo 130 (directa) or Modelo 131 (objetiva) is used for quarterly IRPF payments. A mid-year change requires revision of all year-to-date quarterly calculations. |
| `census.establecimiento_type` | Feeds the expense-category selector: OWN enables amortisation; RENTED enables rental deduction; FREE_USE disables both. |
| `contact.fiscal_address_cadastral_reference` | Used in IBI cross-reference and Modelo 347 address field. A change invalidates any pre-built Modelo 347 draft. |
| `contact.fiscal_address_is_habitual_vivienda` | If flips to false, HOME_OFFICE deduction category becomes unavailable and all related calculations become stale. |

---

### Section 4 -- Stale-cascade contract

When `aeat config profile census apply` applies a new snapshot, it cross-validates each changed field against the dependency map above and stamps `CENSUS_STALE` on any downstream object that consumed the changed field. The six services that refuse work on a stale-flagged unit are:

**`calculate`** reads: `elected_withholding_pct`, `uses_objective_estimation`, `iva.regime`, `office_m2` / `total_m2`, `activity_start_date` (for rate eligibility). Refuses if any of these fields changed since the calculation snapshot was produced. The refusal surfaces as a `CensusStaleError` with a diff of which fields changed.

**`verify`** reads: all fields consumed by `calculate`, plus `roi_enrolled` (for 349 cross-check) and `oss_enrolled` (for 369 cross-check). Refuses if the census snapshot linked to the filing record is SUPERSEDED.

**`file`** reads: fiscal address (for form header), all regime flags (for form selection). Refuses if the profile active census snapshot differs from the snapshot stamped on the verified draft.

**`build_draft`** reads: all fields that determine form selection (regime, `oss_enrolled`, `roi_enrolled`), plus withholding rate and m2 ratio for line-item population. Refuses if the profile active census snapshot is SUPERSEDED relative to the draft stamp.

**`approve_draft`** reads: the census snapshot linked to the draft at build time. Refuses if that snapshot is SUPERSEDED.

**`export_draft`** reads: the census snapshot linked to the approved draft. Refuses if that snapshot is SUPERSEDED (the export would embed stale data in the submission XML/PDF).

The pattern in all six cases: the service reads the census snapshot ID stamped on the object when it was last computed and compares it against the currently ACTIVE snapshot. If they differ and the changed fields overlap with the service dependency set, the service raises `CensusStaleError` and requires the caller to re-run the upstream step (recalculate / re-verify / etc.) or explicitly acknowledge the staleness via `--force-stale` (audit-logged; never silently suppressed).

---

### Section 5 -- Modelo 037 suppression confirmation

Modelo 037 (Declaracion Censal Simplificada) is definitively suppressed by **Orden HAC/1526/2024, de 11 de diciembre**, published as **BOE-A-2025-410** in BOE num. 8 of 9 January 2025.

The Orden amends Orden EHA/1274/2007 (de 26 de abril, BOE-A-2007-9508) by suppressing Articles 14, 15, and 16 of that order together with its Annex II -- the articles and annex that constituted Modelo 037. The stated reason is that the generalised electronic submission of census models and the technological development of the Asesor Censal and activity-search tools since 2007 allow the simplification that 037 offered to be delivered through 036 itself.

**Entry into force:** Disposicion final unica of Orden HAC/1526/2024 states the order enters into force on **2025-02-03** and applies for the first time to models 030 and 036 presented from that date. From 2025-02-03, all taxpayers who formerly used 037 must use 036 for all census declarations regardless of prior eligibility for the simplified form.

**Codebase status:** Modelo 037 is inert in this codebase. It carries historical metadata (alta/baja/modificacion dates filed on 037 before suppression remain in the data model for audit trail purposes) but has no live CLI surface, no active adapter, no submission path, and no live AEAT endpoint. The `aeat config profile census` verb tree operates exclusively through 036 / G313. No new CLI verbs will be added for 037. This is consistent with the permanent live-write prohibition and the regulatory fact that 037 no longer exists as a valid submission vehicle from 2025-02-03.

Source: https://www.boe.es/buscar/doc.php?id=BOE-A-2025-410 (Orden HAC/1526/2024, BOE-A-2025-410, 9 January 2025)
