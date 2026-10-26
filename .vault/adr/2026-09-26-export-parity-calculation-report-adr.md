---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:7a06d883c2a45821bbae21607d943d24d5915eb4c9ba56733f8dde16d5bc48c2'
related:
  - "[[2026-09-26-export-parity-audit]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
  - "[[2026-06-03-modelo-export-workbook-parity-adr]]"
  - "[[2026-06-03-modelo-export-visual-design-adr]]"
  - '[[2026-09-26-export-parity-calculation-summary-pdf-adr]]'
---

# `export-parity` adr: `calculation report destinations for CSV and PDF` | (**status:** `accepted`)

## Problem Statement

A verified or filed modelo calculation can leave the product only as its filing file or as an online workbook; there is no CSV and no PDF of the calculation (`2026-09-26-export-parity-audit`). The accepted destinations decision fixes the contract every destination follows but names no artefact family for either format, so building them requires deciding what each contains and how it is produced. The operator asked on 2026-09-26 for CSV and PDF exports of modelo calculations and chose a calculation-report PDF built from the same plan as the workbook over an overlay of the official paper form.

## Considerations

- Destinations differ in where bytes go and in their wrapper, never in how a declaration is computed (`2026-09-07-tuimodelo-export-destinations-adr`).
- The workbook carries live formulas from one plan builder (`2026-06-03-modelo-export-workbook-parity-adr`); a CSV or PDF has no formula engine and must carry the revision's computed values.
- Absent, zero and not-applicable values must stay distinct in every artefact.
- The runtime already ships PDF readers but no PDF writer; reportlab is a pinned development dependency.
- A local report is not official filing evidence and must say so.

## Considered options

- **Overlay values on the official modelo form.** Rejected by the operator: AEAT publishes no positional source for most forms, so every modelo and year would need hand-authored coordinates.
- **Render CSV and PDF from the workbook plan.** Rejected: the plan holds formulas and blank operator cells, not computed values.
- **One calculation-report builder serialised twice.** Chosen.

## Constraints

- One application builder produces the report; the CSV and PDF serialisers add no content of their own.
- Row order follows the registry's section order and casilla numbering; a value's absence is carried explicitly, never as zero.
- The PDF writer is an optional extra reported through the destination's capability gate; an installation without it states the destination is unavailable.
- Every artefact states that it is a local calculation, not official AEAT evidence, and names the software-identity grade when the filing file would carry one.

## Implementation

An application builder turns one verified or filed calculation revision and its pinned registry snapshot into a typed calculation report: header facts (modelo, year, period, revision id and state, authority generation, export timestamp), then one row per casilla the revision carries, with section path, casilla number and id, label, value state (value, absent, not applicable), typed value, input kind, legal references and source provenance. The CSV destination serialises the rows through the existing tabular serializer with fixed columns. The PDF destination renders the same report as a PDF/A-3a, PDF/UA-1 document embedding the report and CSV with a signed integrity statement, as decided in `2026-09-26-export-parity-calculation-summary-pdf-adr` (amendment accepted 2026-09-27). Both are enrolled in the typed destination contract with the filing file and the workbook, refuse to overwrite an existing file, and are reachable from the CLI and the TUI through the same application service.

## Rationale

A single report builder keeps CSV and PDF consistent with each other by construction, and the revision's computed values are the only content both formats can carry faithfully. Keeping the PDF writer optional follows the existing capability-gated integrations and leaves the base install unchanged.

## Consequences

- Operators get machine-readable (CSV) and printable (PDF) records of a calculation for review and archiving; neither is presentable at AEAT.
- Adding reportlab to an extra adds a runtime dependency path and its notice entry.
- The report builder becomes the single place where a calculation's printable shape is decided; later formats reuse it.
