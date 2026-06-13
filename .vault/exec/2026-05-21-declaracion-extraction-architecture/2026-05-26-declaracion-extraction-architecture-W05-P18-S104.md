---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P18.S104'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-architecture-W05-P17-S103]]'
---

# W05.P18.S104 - fixture acquisition classification

Classified the broad `W05.P16.S101` fixture-acquisition blocker into
per-modelo rows so every blocked current declaration-PDF surface has a
specific remaining-work item.

## Evidence Reviewed

- Modelo 180 has reviewed record-design, AEAT procedure/help, and BOE
  form-spec authority, but only export-record extraction and record-design
  workbook parity are locally grounded. It still needs an authorised
  declaration PDF or official printed-form layout before a declaration-PDF
  profile can be implemented.
- Modelo 190 has reviewed 2025 AEAT/BOE authority and a declaration-PDF
  profile, but the available fixture is 2024 while the committed registry
  starts at 2025. It needs either a 2025-or-later fixture or a separately
  sourced 2024 registry revision.
- Modelo 036 has reviewed 2025 AEAT record-design/procedure authority, but
  its declaration-PDF profile is explicitly provisional pending a real
  printed-form PDF.
- Modelo 369 has reviewed AEAT record-design/procedure and BOE form-spec
  authority, but its Esquema Union declaration-PDF profile is explicitly
  provisional pending a real printed-form PDF.
- Modelo 720 has reviewed AEAT record-design/procedure and BOE form-spec
  authority, but no real local declaration PDF fixture exists for round-trip
  coverage.
- Modelo 840 has reviewed AEAT record-design and BOE form-spec authority,
  but its declaration-PDF profile is explicitly provisional pending a real
  printed-form PDF.

## Official Acquisition Refinement

Follow-up official AEAT lookup refined the acquisition paths:

- Modelo 036 paper PDFs are generated through the online validation workflow;
  AEAT help describes them as drafts until office submission, so the backlog
  still requires a generated paper/declaration PDF fixture rather than a
  static record-design source.
- Modelo 369 and Modelo 720 help pages describe successful filings returning
  PDFs containing presentation metadata and the complete declaration copy, so
  those rows still require generated/submitted declaration PDF fixtures.
- Modelo 840 has a verified static AEAT printed-form PDF candidate
  (`mod840e_es_es.pdf`) with printed casilla labels. The remaining work is to
  import that official source into the corpus/source registry and wire a real
  parser round-trip fixture before promoting provisional labels.
- The same Modelo 840 candidate shows that the current provisional profile is
  not merely unverified; its descriptive registry-derived labels must be
  re-grounded to the printed form's casilla labels such as `14 Ejercicio` and
  `15 Declaración de`.

## Plan Updates

Added `W05.P18.S105` through `W05.P18.S110` as per-modelo acquisition rows
and added an acquisition-classification table to the plan. Added
`W05.P18.S111` for Modelo 840 label re-grounding after the official printed
form showed a mismatch with the provisional descriptive labels. `W05.P16.S101`
remains open because no new authorised fixtures/layouts were imported into the
local corpus in this slice.

## Legal Grounding Guard

The plan now records that record-design layouts and BOE form specifications
can ground registry/export surfaces, but they do not by themselves validate
parser `named_label` matches against declaration-PDF text. Promotion of the
provisional profiles remains blocked until fixture-backed parser tests exist.
