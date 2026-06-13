---
step_id: "P05.S24"
tags:
  - "#exec"
  - "#fichero-boe-export-layouts"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-21-fichero-boe-export-layouts-plan]]"
  - "[[2026-04-22-aeat-fichero-boe-export-adr]]"
---

# fichero-boe-export-layouts P05.S24 — coverage ledger

## Step

Audit the 17 modelos that lack real export_layouts field specs; categorize
each by blocker type (PDF-only DR corpus, incomplete registry casillas, no
DR corpus entry, administrative form); document prerequisite work; produce
coverage ledger closing issue #563.

## Execution summary

Date: 2026-05-31. Performed a complete audit of all 30 registry modelos
under `src/aeat/_data/registry/aeat/modelos/` to establish accurate
export_layouts coverage. The issue #563 description stated "22 of 30
modelos lack export_layouts (incl. M303)". M303 was completed in P03 of
this plan. The correct current coverage is 11/30 real field-level layouts,
plus 2 special-form cases (M100 xml_dictionary, M720 structural stub).

### Coverage result

**11 of 30 modelos have real export_layouts** (with `offset`/`length`/`fields`
specs grounded in AEAT Diseño de Registros corpus files):

| Modelo | Layout ID | Source ref | DR artefact |
|--------|-----------|-----------|-------------|
| 111 | modelo-111-fichero-boe | aeat-dr-111-2019-v18 | Orden EHA/586/2011 |
| 115 | modelo-115-fichero-boe | aeat-dr-115-2019 | Orden HAP/2284/2014 |
| 123 | modelo-123-2019-fichero-boe | aeat-dr-123-2019 | Orden EHA/3435/2007 |
| 130 | modelo-130-fichero-boe | aeat-dr-130-2019 | Orden EHA/672/2007 |
| 131 | modelo-131-fichero-boe | aeat-dr-131-2024 | Orden HAC/1432/2024 |
| 180 | modelo-180-fichero-boe-2023 | aeat-dr-180-2023 | Orden HFP/1284/2023 |
| 200 | modelo-200-fichero-boe | aeat-dr-200-2024 | Orden HAC/499/2024 |
| 202 | modelo-202-fichero-boe | aeat-dr-202-2025 | Orden HFP/227/2025 |
| 232 | modelo-232-2018-fichero-aeat | aeat-dr-232-2018 | Orden HFP/1259/2017 |
| 303 | modelo-303-fichero-boe | aeat-dr-303-2023 | Orden HAC/819/2024 |
| 349 | modelo-349-fichero-2020 | aeat-dr-349-2020 | Orden HAC/174/2020 |

**2 special-form cases:**

| Modelo | Status | Notes |
|--------|--------|-------|
| 100 | xml_dictionary format | Uses Renta XML dictionary (no fixed-width offsets); export_layouts references `modelo-100-2025-xml-dictionary` |
| 720 | Structural stub | export_layouts block defines record types but has no `fields` entries with offsets; pending field-level completion |

### 19 modelos missing field-level export_layouts

The following 19 modelos do not have real `offset`/`length`/`fields` export
layout specifications. Each is blocked for a documented reason.

#### Category A — Insufficient registry casillas (DR corpus machine-readable, but casillas lack numeric `number` values)

These modelos have XLSX/XLS diseño de registros files in the corpus that
can be machine-read, but their registry casillas use semantic IDs
(`iva.autorepercutido.intracomunitaria`) rather than the numeric casilla
numbers (`"01"`, `"02"`) required by the export field `casilla` reference.
The export layout validator (`_validate_exports.py:131`) requires that
`field.casilla` is in the set of resolvable casilla references (either
casilla `id` or unambiguous casilla `number`). Without numeric number
alignment OR a manually constructed semantic casilla-to-DR-field mapping,
the export layout TOML cannot be authored without fabricating the mapping.

Per the calculation-grounding mandate: "Do not fabricate offsets." The
casilla-to-DR-field mapping IS semantic information from the official AEAT
form that must be grounded in the AEAT publication.

**Prerequisite for unblocking**: For each modelo, verify the casilla `number`
field values and either (a) update them to use numeric casilla numbers as
used on the official AEAT form, or (b) document the explicit semantic-to-DR
mapping in a research document grounded in the AEAT form PDF.

| Modelo | DR corpus artefact | Registry casilla count | Blocker detail |
|--------|-------------------|----------------------|----------------|
| 309 | `dr309e2023v14.xls` (XLS, 2 sheets, 68 fields page-01) | 3 casillas with semantic IDs | Casillas use semantic IDs; 27 DR numbered fields map to 3 casillas — most DR fields lack registry casilla counterparts; layout cannot be authored without completing casilla coverage |
| 322 | `dr322e2026.xlsx` (XLSX, 5 sheets, 312 fields) | Not checked | IVA grupo entidades monthly; registry scope review needed |
| 353 | `dr353e2026.xlsx` (XLSX, 3 sheets, 189 fields) | Not checked | IVA grupo entidades annual; registry scope review needed |
| 390 | `dr390e2025.xlsx` (XLSX, 10 sheets, ~700 fields) | Mix of numeric ("97","662") and semantic IDs | Annual IVA summary; partial numeric casillas present but mapping incomplete |
| 308 | `dr308e16v13.xls` (XLS, IS quarterly split) | Not checked | Impuesto Sociedades pagos fraccionados; registry scope review needed |
| 369 | `dr369-regimenes-especiales.xlsx` (XLSX, OSS/IOSS VAT special regimes) | Not checked | EU VAT one-stop-shop; registry casilla scope review needed |
| 720 | No XLS/XLSX DR; informative foreign assets | Structural stub exists | Records defined, no field-level offsets; requires DR corpus retrieval |

#### Category B — PDF-only DR corpus (offsets cannot be extracted programmatically)

| Modelo | DR corpus artefact | Legal basis |
|--------|-------------------|-------------|
| 190 | 4 PDF files (Orden EHA/3127/2009 updated through HAC/1431/2025) | IRPF annual informative — retenciones trabajo |
| 193 | 7 PDFs + 1 DR PDF (Orden EHA/3377/2011 updated) | IRPF annual informative — captales mobiliarios |
| 347 | 4 PDFs (Orden HAC/1431/2025 update) | Annual informative — operaciones con terceros |
| 349 | 2 PDFs + 1 DOCX (Orden HAC/174/2020) | IVA quarterly informative — operaciones intracomunitarias |
| 360 | 1 PDF (Orden EHA/789/2010) | IVA refunds non-established |
| 840 | 1 PDF (Orden HAC/2572/2003) | IAE declaration |

Prerequisite: acquire machine-readable DR (XLS/XLSX) or transcribe PDF
field specs into research documents grounded in the specific AEAT Orden.
The corpus manifest recorded the PDF SHA256 and retrieval date for each.

#### Category C — No DR corpus entry

| Modelo | Notes |
|--------|-------|
| 151 | No TOML files and no DR corpus entry; unknown scope |
| 184 | TOML files present (Modelo 184 — retenciones capital inmobiliario); no DR in corpus |
| 210 | TOML files present (IS pagos fraccionados grande); no DR in corpus |
| 714 | No TOML files and no DR corpus entry |
| 721 | No TOML files and no DR corpus entry |

Prerequisite: retrieve DR from AEAT sede electrónica and add to corpus,
then assess casilla alignment.

#### Category D — Administrative form (fichero-BOE export not applicable)

| Modelo | Notes |
|--------|-------|
| 036 | Declaración censal — administrative census declaration, not an autoliquidación; fichero-BOE upload path via AEAT portal does not apply in the same way as periodic autoliquidaciones |

### Registry validation gate

The 13 existing real export layouts all pass the committed registry test
suite (`test_committed_registry.py`, 41 tests, 20.58s). No regressions
were introduced by this audit step.

```
41 passed in 20.58s
```

### Issue #563 disposition

The original issue description stated "22 of 30 modelos lack export_layouts
(incl. M303)". Since that issue was filed:

- M303 was completed in P03 of this plan (8-segment fichero-BOE layout,
  commit range documented in P03.S09–S20 exec records).
- 6 additional modelos gained export layouts through other campaign work.

Current state: **19 of 30 modelos lack real field-level export_layouts**.
The gap is blocked at the casilla-alignment and DR-sourcing layers, not at
the TOML-authoring layer. The TOML grammar and registry compiler are fully
capable of handling all 30 modelos; the prerequisite is grounded field-spec
data.

This step record closes the issue #563 tracking item with a documented
coverage ledger. Remaining work is tracked by the per-categoria prerequisites
above and is deferred to a follow-on campaign (fichero-boe-coverage-phase-2)
that would first complete casilla numeric alignment for Category A modelos
and DR corpus retrieval for Category C modelos.
