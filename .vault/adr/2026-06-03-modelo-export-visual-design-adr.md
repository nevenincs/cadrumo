---
tags:
  - '#adr'
  - '#modelo-export-visual-design'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-modelo-export-workbook-parity-adr]]"
  - '[[2026-06-04-modelo-export-visual-design-research]]'
---



# `modelo-export-visual-design` adr: `Modelo export visual design system` | (**status:** `accepted`)

## Problem Statement

The workbook-parity ADR established that every modelo export must mirror the
official AEAT structure from one shared plan builder. The structure landed —
casilla set, numbering, section order, live formulas, labelled start/final — but
the *presentation* did not. A visual baseline (LibreOffice render of the M130
offline xls) showed concept labels clipped to a few characters
(`Rendimien`, `Importe de`), section paths truncated, legal-reference columns
unreadable (`rd-439-20`), no column sizing, no font choice, no colour, no header
freeze, no filter, and no text wrapping. An operator reviewing a filing artefact
before submitting it outside the application could not read it. The official AEAT
paper modelo, by contrast, is a calm, boxed, banded form. This ADR decides the
uniform visual design system the exports apply across both transports.

## Considerations

- **One palette, two transports.** The font and colour decisions live in a single
  shared module both the offline openpyxl materialiser and the online
  Google-Sheets apply adapter import; neither hard-codes a colour or font. This is
  the visual-surface application of the one-builder/two-transport invariant the
  parity ADR established.
- **Typed facets, not per-cell styling.** Presentation is declared as a small set
  of typed plan facets (role-tagged styled ranges, column widths, frozen views,
  basic filters) computed once by the engine, not as thousands of per-cell style
  objects. The facets are compact and deterministic, so two runs produce the same
  design and a conformance test can assert both transports agree.
- **Operator legibility is the goal.** Monospace for column alignment; wrapped
  concept / legal-ref columns so nothing clips; frozen header rows; basic filters
  for navigation; pale-yellow input boxes signalling "fill me in"; grey for
  computed/protected cells; a green accent on the filing result; a slate header
  band. The choices were confirmed with the operator (font: Roboto Mono; theme:
  official-AEAT restrained).
- **Values are untouched.** The design layer adds only formatting; cell values and
  formulas are unchanged, so the pull roundtrip and the registry-grounded parity
  gate are unaffected.

## Constraints

- **Font portability.** A single declared family (Roboto Mono) is applied by both
  transports. It is a native Google-Sheets font (crisp online); the offline xls
  renderer substitutes the nearest installed monospace when Roboto Mono is absent.
  The family is one constant, trivially swappable.
- **openpyxl / Sheets API parity.** Each facet maps cleanly to both backends
  (openpyxl Font / PatternFill / Alignment / freeze_panes / auto_filter / print
  setup, and Sheets repeatCell / updateDimensionProperties /
  updateSheetProperties / setBasicFilter). Colours are stored as `RRGGBB` hex; a
  helper converts to the Sheets 0..1 channel floats and openpyxl consumes the
  `FFRRGGBB` form.
- **Parent stability.** Depends on the accepted workbook-parity and
  evidence-parity ADRs (both shipped). It adds a presentation layer over their
  existing export plan; it does not change the calculation, evidence, or parity
  contracts.

## Implementation

A shared theme module declares the monospace family and a closed style-role
vocabulary (header, section banner, input, computed, result, title, body) each
mapped to a backend-independent role style (fill, font colour, bold, alignment,
wrap). The engine computes four typed facets onto the export plan: role-tagged
styled ranges (the header band, one banner per section change, the input column,
the computed column, the green result accent, wrapped body columns), per-column
widths, per-tab frozen views, and per-tab basic filters. Section labels are
emitted once per section (as a wrapped banner) rather than repeated on every row,
matching the official form. Both transports resolve the same facets through the
same palette: the offline materialiser sets a base monospace font on every
populated cell then overlays role styling, sizes columns, freezes header rows,
installs filters, and applies a landscape fit-to-width print setup with a repeated
header row; the online apply adapter emits a whole-grid base-font request per tab,
a styled-range format request per range, and column-width, frozen-row, and
basic-filter requests. A conformance test asserts both transports emit matching
facets; a styling test asserts the offline workbook renders the palette and font.

## Rationale

Centralising the palette and font in one module is what makes "uniform across all
exports" structural rather than coincidental — the same decision drove the
workbook-parity ADR's single plan builder. Declaring presentation as typed facets
keeps the design deterministic and testable, and keeps the two transports from
drifting. Emitting section labels once as a banner both matches the official form
and eliminates the clipping the per-row repetition caused. The visual baseline was
rendered with LibreOffice and re-rendered after each refinement across M130, M303,
and M100 to confirm the design holds uniformly on every tab.

## Consequences

- **Gain:** an operator-legible, official-faithful filing artefact — banded
  header, boxed inputs, wrapped legal references, frozen headers, filters — that
  prints cleanly and reads identically offline and online.
- **Gain:** the design is one palette plus one facet computation; adding a tab or a
  role is a single-site change both transports inherit.
- **Cost:** the offline materialiser iterates the populated grid to set the base
  font (O(cells)); bounded and acceptable even for the largest modelo (M100, ~9k
  value cells).
- **Cost:** font fidelity depends on the renderer having Roboto Mono; absent it,
  the offline xls substitutes a local monospace (acceptable, still aligned).
- **Pitfall:** a new transport or a new tab that does not read the shared facets
  would drift from the look; the conformance test is the guard.

## Codification candidates

- **Rule slug:** `modelo-export-mirrors-official-structure` (existing).
  The visual design system is the presentation half of that rule's
  one-builder/two-transport mandate: presentation is typed plan facets defined
  once and materialised identically by both transports. No new rule is required;
  this ADR is recorded as the design-system backing decision.
