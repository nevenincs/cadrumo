---
tags:
  - '#reference'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:5b14fb594a7e625ec239deabf1335273dd7c5bb5ae476cba8045b4dfa9956fa7'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
---

# `modelo-editor-workbench` reference: `Modelo editor workbench grounding`

Grounds the editor workbench decision in the live tree as measured on 2026-09-30:
what the operator sees today, what the application layer already knows about each
casilla, how an edit reaches persistence, and what the registry declares that a
generated form can group and order by. Figures are from a census of the authored
casilla declarations under `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/casillas/`
(authored rows, before delta hydration) and from reading the cited modules.

## Summary

### What the operator sees today

- The only edit surface is a column of bare text inputs on the overview page, one per
  writable casilla or manual-input binding, with the casilla id as placeholder and no
  label, value, help, type, or state (`src/cadrumo/entrypoints/tui/modelo/view/overview.py:181`).
  The apply handler reads each input as a raw string and submits every non-empty one
  (`src/cadrumo/entrypoints/tui/modelo/view/overview.py:355`).
- The inputs page is a read-only data table grouped by schema record family
  (casillas, bindings, formulas, relations, parameters) rather than by the modelo's
  sections, with a four-column row of address, label, value and input kind
  (`src/cadrumo/entrypoints/tui/modelo/view/inputs.py:124`).
- The workspace projection never carries the canonical work review: both admissions
  declare the work-review facet `UNMEASURED` with no review
  (`src/cadrumo/application/modelo/workspace.py:189`,
  `src/cadrumo/application/modelo/workspace.py:1592`). Values reach the TUI only through
  the materialization facet of a graded snapshot.

### What the application layer already knows per casilla

- `ModeloWorkReviewCasilla` (`src/cadrumo/application/modelo/work_review.py:107`) carries
  number, official reference, section path, label, data type, constraints, declared
  input kind, concrete bindings with source kind and a resolved flag, formula origin,
  realised value kind, value, absent-by-design, operator-override anomaly, official
  export state, legal and source references, and verification blockers. The review
  label is resolved in Spanish only (`src/cadrumo/application/modelo/_work_review_assembly.py:375`).
- The realised value classifier distinguishes computed, literal, inherited and empty,
  and emits `OPERATOR_OVERRIDE` only when a persisted bound value disagrees with the
  persisted observation (`src/cadrumo/application/modelo/_work_review_assembly.py:259`).
  It cannot tell an operator-entered manual value from a materialised default; the
  current revision's `input_values_by_casilla_id` can.
- Help text is already resolvable per locale through the same catalogue identity as
  the label (`src/cadrumo/domain/calculations/registry/schema_surfaces.py:439`), and the
  English catalogue alone holds 5,102 help entries against 16,394 labels.
- `required` is declared on the casilla definition and is not carried by the review.

### How an edit reaches persistence

- Admission projects the permitted surface: every manual casilla is a writable scalar
  with set and clear intents; every manual-input binding is a writable override; all
  else is read-only with a reason (`src/cadrumo/application/modelo/edit_admission.py:134`).
  The baseline lives five minutes (`src/cadrumo/application/modelo/edit_admission.py:57`)
  but the installed workbench admits it once while composing the declaration door
  (`src/cadrumo/entrypoints/tui/launcher.py:1035`), so an editor held open longer is
  refused as stale at submit.
- The executor re-supplies the current revision's detail rows
  (`src/cadrumo/application/modelo/_edit_execution.py:191`) but builds scalar inputs
  and binding values only from the submitted intents
  (`src/cadrumo/application/modelo/_edit_execution.py:102`). Calculation is memoryless
  over those inputs (`src/cadrumo/application/modelo/calculation_actions.py:1431`), so a
  second edit silently drops every manual value and binding override the first edit
  wrote. The accepted edit contract states that intent absence means unchanged
  (`2026-08-24-modelo-edit-contract-adr`, D4); the executor does not honour it.
- Binding override removal is refused as not yet wired
  (`src/cadrumo/application/modelo/_edit_execution.py:251`).
- No typed value parser exists: the parse request and parsed-value records are
  declared (`src/cadrumo/application/modelo/edit_models.py:504`) but nothing produces
  them. Numeric data types are coerced with `Decimal(str(value))` at execution and
  everything else is passed through as text (`src/cadrumo/application/modelo/_edit_execution.py:102`).
  Finite European decimal coercion (`src/cadrumo/core/decimal/coercion.py`) and IBAN
  checking (`src/cadrumo/core/iban.py`) already exist in core.

### What the registry declares for grouping and ordering

- 58 modelos, 13,046 authored casilla rows. Every row declares a `section` path; depths
  are 1 to 5 (1,054 distinct two-segment paths, 247 three-segment, 148 one-segment).
  1,311 distinct section tokens overall; the nineteen most-used consumer and withholding
  modelos use 180 of them. No section token has a catalogue entry today.
- Input kinds: 12,066 manual, 369 computed, 289 bound, 261 informational, 61
  projection-only. Data types: 19 in use, led by money (9,149), text (1,901), ratio
  (523), boolean (286), decimal (286), nif (267). 283 rows are marked required.
- Export fields carry a one-based offset and an optional casilla id within records that
  carry an order (`src/cadrumo/domain/calculations/registry/schema_exports.py:491`,
  `src/cadrumo/domain/calculations/registry/schema_exports.py:858`), and
  `derive_export_layouts_from_bindings` resolves binding-derived fields
  (`src/cadrumo/domain/calculations/registry/export.py:91`). The prior campaign measured
  that offsets place about a third of the corpus and nothing for modelo 100
  (`2026-09-07-tuimodelo-reference`); casilla numbers are present on every row.

### Reusable presentation language

- The profile manager already establishes the product's field-editing language: section
  folds titled with a done or pending glyph and counts, a docked what/why/where help
  panel, a typed field-edit modal, search and a required-only filter
  (`src/cadrumo/entrypoints/tui/profile/overview.py:155`,
  `src/cadrumo/entrypoints/tui/profile/overview.py:173`), backed by the `flows.profile`
  catalogue keys.
- Theme tokens, the disclosure group, notice band and data table live in
  `src/cadrumo/entrypoints/tui/components/theme.py` and
  `src/cadrumo/entrypoints/tui/components/widgets.py`.
