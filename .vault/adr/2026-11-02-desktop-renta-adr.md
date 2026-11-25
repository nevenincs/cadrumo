---
tags:
  - '#adr'
  - '#desktop-renta'
date: '2026-11-02'
modified: '2026-11-04'
body_schema: 'body-v2'
body_hash: 'sha256:808f28c3b4e9bcdf3dc0b15c5a767e512605a3acababef5441ceccf9695ac3af'
related:
  - "[[2026-09-07-tuimodelo-form-projection-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-operator-layer-adr]]"
  - "[[2026-10-05-desktop-design-system-adr]]"
  - "[[2026-10-23-desktop-modelo-workspace-adr]]"
  - "[[2026-11-02-operation-refusal-words-adr]]"
  - "[[2026-11-01-export-parity-income-imputation-criterion-adr]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
  - '[[2026-11-02-desktop-renta-reference]]'
---

# `desktop-renta` adr: `Renta workspace: one generated form with served companion reads` | (**status:** `accepted`)

## Problem Statement

The desktop Modelo workspace draws every declaration from the generated `modelo.work.form` read model. For the Modelo 100 that read is about 3.8 MB per language, holds four pages and 87 sections, and 75 of those section headings are dictionary tokens disclosed as `technical`. Descendants and ascendants are flat boxes with no row groups. The household, the imputation criterion, the comparison of individual and joint taxation, the settlement of the result and the borrador comparison have no place in the form at all. A filer cannot navigate or finish a Renta return with the generic workspace alone. A Renta screen must not compute in the window, and it must not grow modelo-specific branches there either. The boundary between what stays generated and what becomes a dedicated element has to be settled before the build.

## Considerations

- The form projection is a generated presentation family seeded from the RentaWeb dictionary, and hand-authored screens are rejected (`2026-09-07-tuimodelo-form-projection-adr`).
- The form read model classifies every box and keeps missing distinct from zero (`2026-09-30-modelo-editor-workbench-adr`, D1 to D8).
- The window renders a closed `modelo.*` family over the held relay and keeps data in memory only (`2026-10-23-desktop-modelo-workspace-adr`).
- The backend serves refusal and finding words, and the window never maps codes (`2026-11-02-operation-refusal-words-adr`).
- The imputation criterion is a dated typed profile fact. Absent means undeclared (`2026-11-01-export-parity-income-imputation-criterion-adr`).
- Earlier-year carries such as 1388 come from the previous filing (`2026-06-02-modelo-multiyear-renta-adr`).
- Discovery, recorded in the plan for this feature: `modelo.project` result version 2 serves tokens only. The Modelo 100 export offer serves no elections. `modelo.work.wizard_context` serves Spanish and raw binding ids in every language. `compare_taxation` reasons are English free text. The calculation refuses without 1388 and 0168, but the form presents them as optional.

## Considered options

- **A Renta-specific hand-built screen.** It would give the best layout, but it duplicates the form, breaks the generated-family ruling and puts tax mapping in the window. Rejected.
- **The generic workspace unchanged.** It keeps one mechanism, but it is unusable: technical headings, no household, no settlement, no unresolved credit routing. Rejected.
- **One generated form plus backend-served companion reads, rendered by payload kind.** It keeps every box in the form and adds typed reads for what is not a box. Chosen.

## Constraints

- Every casilla of Modelo 100 stays in the one generated form, edited through the existing editors and editability. No Renta element writes a box.
- Section navigation, headings and grouping are served by the read model: a served outline with reviewed localized headings, row groups for repeating people and assets, and section attention counts. The window derives none of them.
- Concepts that are not boxes are served as typed companion reads. The window renders each by payload kind, never by modelo number. These concepts are the household, the imputation election, the taxation comparison, settlement elections, the borrador comparison and the projection estimate.
- Each companion read serves its own words in every supported locale. Tokens without words are a backend gap, never a window mapping.
- Withholding boxes 0596, 0597 and 0603 are corrected only in the withholding register. `modelo.project` refuses a caller value for them, so no element offers manual entry, and the read must name the correction surface.
- Unresolved, unknown, advisory and proven-zero stay distinct in every element, including totals that read an unresolved operand.
- This amends the "one mechanism" reading of `2026-09-30-modelo-editor-workbench-adr`. The form remains the sole box editor, and companion reads join it as a second, closed, typed family. It does not reopen the form projection ruling.

## Implementation

We will keep Modelo 100 as one generated form and add served companion reads that the window renders by kind. The read model will serve an outline (groups, reviewed headings, applicability, attention roll-up) and row groups for descendants, ascendants and assets. Profile, wizard and modelo operations will gain the typed reads and writes named in the plan, each admitted through the relay's closed allow-list. The Storybook prototypes under `Prototypes/Renta/` show the element catalogue against served-shaped fixtures and mark every missing read as not served. The grouping in the prototype outline is a proposal for the backend to own, and it may change.

## Rationale

The chosen option is the only one that satisfies both standing rulings: the form stays generated, and the window holds no tax logic. Companion reads keyed by payload kind keep the window modelo-agnostic. The same household or settlement element can serve another declaration later without a branch in the window.

## Consequences

- Benefits: one editor path for boxes, words owned by the backend, and an element catalogue that other declarations can reuse.
- Costs: several new backend reads and relay admissions before the workspace is usable, plus reviewed headings for 75 sections across four locales.
- Reconsider if a companion read would need to write a box, or if the outline cannot be served from the registry without hand-authoring per revision.
