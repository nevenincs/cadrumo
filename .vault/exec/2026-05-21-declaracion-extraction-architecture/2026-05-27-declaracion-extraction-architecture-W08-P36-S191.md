---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S191'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W08.P36.S191`

PROVISIONAL gate scope survey: all four candidate surfaces audited; gate
extension is unwarranted. `declaracion_pdf` is structurally the only
surface where the silent-failure class applies.

## Surface Inventory

Extraction profiles in `src/aeat/_data/registry/aeat/modelos/` (directories
named `extraction_profiles/`) use only two surfaces:

| Surface | Profile count | Match strategies | Parser |
|---|---|---|---|
| `declaracion_pdf` | 20 | `numeric_casilla`, `named_label` | `parse_declaracion` (PDF text scan) |
| `export_record` | 11 | `numeric_casilla`, `named_label` | `parse_export_payload` (structured XML/binary) |
| `borrador_pdf` | 0 | — | — (no profiles authored) |
| `justificante_pdf` | 0 | — | — (no profiles authored) |
| `official_workbook` | 0 | — | — (no profiles authored) |

## Structural Analysis

**`declaracion_pdf`** — uses `aeat.adapters.inbound.declaracion.parse_declaracion`,
a PDF text extractor that scans printed form text using regex anchors. The
`label_pattern` fields are literal regex strings matched against printed Spanish
text. Silent failure occurs when a `label_pattern` is derived from registry
`label_es` text rather than verified against a printed PDF, because the printed
form may use different wording (e.g. M111: box numbers at line-end, not
line-start). This is exactly the failure class the gate prevents.

**`export_record`** — uses `aeat.domain.calculations.registry.parse_export_payload`,
which operates on AEAT structured payloads: fixed-width binary records (positional
byte offsets from Diseño de Registro specs) or XML dictionary files. Even when
`export_record` profiles carry `label_pattern` fields in `ExtractionTargetDefinition`
(M180, M349 named_label targets), these patterns are used as field labels in the
structured XML dictionary — not as free-text regex anchors against an optical PDF
scan. A mismatch in an `export_record` profile would produce an immediate hard
parse failure on structured data, not a silent extraction miss. No gate extension
needed.

**`borrador_pdf`, `justificante_pdf`, `official_workbook`** — zero profiles
authored. No gate needed; the schema type permits them for future use.

## Determination

The PROVISIONAL gate (`validate_declaracion_pdf_specimen_gate` +
`validate_declaracion_pdf_round_trip_gate`) is **correctly scoped** to
`declaracion_pdf` only. No code changes are required. The existing
`validate_extraction_profile_artefacts` already rejects unknown surface/artefact
combinations as a separate structural gate.

## Existing `export_record` Profile Status

All 11 `export_record` profiles carry neither `provisional_pending_specimen` nor
`corpus_round_trip_verified` — and correctly so. These fields are meaningful only
for the PDF-text-extraction failure class that does not apply to structured-format
parsers grounded against AEAT Diseño de Registro specifications.

**Plan step W08.P36.S191 closed. No code or TOML changes made.**
