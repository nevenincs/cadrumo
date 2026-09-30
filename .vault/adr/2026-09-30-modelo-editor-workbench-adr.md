---
tags:
  - '#adr'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:0f2e9e71473dc3cd9985fcf8f2067c29540b1bddfeee7a0114a543dbe8bdcc4c'
related:
  - "[[2026-09-07-tuimodelo-form-projection-adr]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-09-07-tuimodelo-reference]]"
  - '[[2026-09-30-modelo-editor-workbench-form-model-research]]'
  - '[[2026-09-30-modelo-editor-workbench-casilla-row-research]]'
  - '[[2026-09-30-modelo-editor-workbench-edit-interaction-research]]'
  - '[[2026-09-30-modelo-editor-workbench-imports-bindings-research]]'
  - '[[2026-09-30-modelo-editor-workbench-journey-help-research]]'
  - '[[2026-09-30-modelo-editor-workbench-reference]]'
  - '[[2026-09-30-modelo-editor-workbench-operator-layer-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-audit]]'
---

# `modelo-editor-workbench` adr: `Schema-derived modelo editor workbench` | (**status:** `accepted`)

## Problem Statement

Filing a modelo in the TUI means reading developer surfaces. The only edit control is a column
of bare inputs labelled by casilla id; the inputs page groups rows by schema record family and
shows blank labels; values print without locale formatting; results, verification, provenance
and filing are separate pages reached through a table; and a successful calculation dismisses
the workspace. No screen presents one casilla's number, label, value, origin, state and help
together, and there is no interface for importing or overriding source values
(`2026-09-30-modelo-editor-workbench-reference`,
`2026-09-30-modelo-editor-workbench-journey-help-research`).

The operator's requirement is schema-level: every defined modelo must obtain the edit interface
its filer needs programmatically, from the authority, without per-modelo screens. The data to do
so exists but is not shaped for it. Section paths are too fine for some modelos and too coarse
for others, registry order is uncorrelated with the printed form, and nothing declares the
official pages, apartados, rows and columns
(`2026-09-30-modelo-editor-workbench-form-model-research`). The accepted form-projection
decision chose a declared presentation family but left every unreviewed revision
inspection-only, which cannot satisfy "every modelo" on today's review capacity.

This record decides the layout authority, the form read model, the state vocabulary, the
workbench destination and its interaction contract. The persistence prerequisite for trustworthy
editing is decided separately in `2026-09-30-modelo-editor-workbench-operator-layer-adr`.

## Considerations

- A modelo-independent seed ladder over official anchors (export offsets joined to record-design
  text, the modelo 100 dictionary and XSD, design box numbers, numeric casilla numbers) placed
  94.1 per cent of 31,415 hydrated casillas with no per-modelo code; the rest are working figures
  or have no official anchor, each with a reason
  (`2026-09-30-modelo-editor-workbench-form-model-research`, F7).
- Section paths and declaration order are not form structure: 303 has 62 single-casilla leaves,
  390 has a 156-casilla leaf, and snapshot order correlates near zero with the official order for
  303 (`2026-09-30-modelo-editor-workbench-form-model-research`, F1 and F2).
- The official record designs name pages, apartados, rows and columns; runtime splitting of
  translated labels is unsafe because four per cent of labels break the pattern
  (`2026-09-30-modelo-editor-workbench-form-model-research`, F5 and F8).
- The `required` flag is set on 2.4 per cent of casillas; the completeness manifest is the usable
  denominator for "needs your input"
  (`2026-09-30-modelo-editor-workbench-form-model-research`, F10).
- The canonical work review already carries most per-casilla facts, but not `required`, the
  operator-entered flag, localized labels or help
  (`2026-09-30-modelo-editor-workbench-casilla-row-research`, 1.2).
- One widget per casilla mounts in 5.1 s at 1,000 rows and 19.9 s at 3,400; a single virtual list
  mounts in under 0.1 s at every measured size
  (`2026-09-30-modelo-editor-workbench-casilla-row-research`, 2.7).
- Three glyphs the product ships today are missing from the pinned font
  (`2026-09-30-modelo-editor-workbench-casilla-row-research`, 1.5).
- Help exists for about 16 per cent of casillas in substance, yet every casilla carries legal
  references and 389 formulas can be rendered, 241 with a verbatim official quote
  (`2026-09-30-modelo-editor-workbench-journey-help-research`, 1.3).
- The everyday modelos expose no writable bindings, override policy is undeclared for seventeen
  source kinds, and provenance misattributes carries
  (`2026-09-30-modelo-editor-workbench-imports-bindings-research`, 1.2, B5 and B8).
- The accepted workspace decision gives every page its own destination and allows only
  abandon-and-reload on a stale edit (`2026-08-24-tui-modelo-workspace-interface-adr`, D1 and D6).

## Considered options

1. **Keep the page-per-destination workspace and fix its defects.** Rejected: it cannot present a
   casilla's value, origin and help together and keeps five pages between a filer and a result.
2. **Derive layout at runtime from section paths, declaration order or offsets.** Rejected on
   measurement: the section tree is the wrong grain and order is uncorrelated with the form; the
   form-projection decision's rejection of runtime interpretation stands.
3. **Hand-author layouts for the most-filed modelos.** Rejected: it fails "every modelo" and
   creates two mechanisms.
4. **Humanize section tokens as headings.** Rejected: 386 tokens are mangled slugs and 303 mixes
   English tokens into a Spanish taxonomy; humanized text reads as authoritative when it is not.
5. **Generate a declared layout for every revision, reviewed to promote; join it at runtime with
   the canonical review, the current revision and the edit admission into one form read model;
   render it in one workbench per declaration.** Chosen.

## Constraints

- Amends `2026-09-07-tuimodelo-form-projection-adr`: a generated declaration ships and is editable
  with a visible disclosure; review promotes it; inspection-only remains only for a revision whose
  generation fails. Everything else in that decision stands, including declared row groups, the
  unplaced arm, the stability gate and the source discriminator.
- Amends `2026-08-24-tui-modelo-workspace-interface-adr`: D1's read destinations are retired into
  one workbench destination, atomically and without aliases; D6 gains user-confirmed re-basing
  alongside abandon-and-reload. D2, D3, D5, D7 and D8 stand.
- Extends, and does not replace, the canonical work review read model
  (`2026-08-10-casilla-schema-read-model-adr`).
- Editing depends on `2026-09-30-modelo-editor-workbench-operator-layer-adr`; no edit control is
  offered on a path that could still lose an operator value.
- Registry authority flow: the layout is compiled, validated and published with its revision and
  read only through the published authority; it is generator-owned data and never hand-edited in
  place.
- Locale contract: headings, states, actions and help chrome are catalogue keys in all four
  locales; transport tokens and ids never appear on the main surface.

## Implementation

### D1 Layout authority

A per-revision form layout becomes a declared registry family. It names ordered pages with their
official reference and page condition, sections with a heading key and the verbatim official
heading, and blocks: single fields, grids of official rows and columns, repeating row groups over
row-set bindings or repeating records, and groups of binding inputs no casilla owns. Every casilla
has exactly one placement: on the form with its official box number and any alias positions, a
working figure shown under calculation details, or unplaced with a closed reason. Cells may be
design constants, which the edit surface must not offer. Each layout records its seed source,
its review state (generated or reviewed) and the digest of the sources it was generated from. A
validator enrolled in the registry dispatch refuses a layout that omits, duplicates or invents a
casilla, mismatches a grid, or is stale against its revision. A development-time generator with
one seed ladder produces layouts for every revision; its output is the review queue, and a
stability gate reports moved placements between editions.

### D2 Form read model

An application read model builds the editor form from the canonical work review, the declared
layout, the current calculation revision and its operator layer, the edit admission and the
active locale. It carries localized labels and help through the casilla catalogue chain, the
official box number, the presentation kind, an editability classification and an origin state
per field, and counts rolled up to section, page and form. Editability and origin are closed
application enums, so the interface renders and never classifies. The completeness manifest, not
the sparse `required` flag, decides "needs your input". A total source-kind policy table, bound
by test to the calculation precedence ladder, gives every binding source its family, override
policy and destination; an unclassified source shows its policy as undecided. A totality
invariant refuses a form that drops or duplicates any casilla or writable address.

Amendment 2026-09-30, from the convergence phase's read-model work. The completeness manifest
lists the whole calculation closure, including 429 typed Modelo 100 boxes that no filer owes.
Using it made the form demand more than 150 boxes that verification never requires. So
"needs your input" now follows the rule verification applies: a manual casilla the registry
declares required, excluding detail-row templates, which their rows answer for. That rule is
defined once, in `src/cadrumo/application/modelo/required_inputs.py`, and a test proves the form
and a real verification agree. Verification keeps its own additional check of detail-row
templates through their rows. The form also carries, per field, the source family of a bound
value and any named earlier declaration, and, form-wide, the replayed AEAT data, the filing
deadline, the settlement direction and the recorded-filing state. The interface renders these
and does not classify. Authorized under the standing advance authorization the plan records.

### D3 State vocabulary

Every field has one origin state and at most one attention overlay, each a glyph from the pinned
font plus words, with colour as reinforcement only. Origins distinguish not applicable, value
replaces an import, calculated, not calculated yet, could not calculate, for information, needs
your input, imported with its source, not imported yet, optional and empty, default to confirm,
and entered by you. Overlays distinguish a staged change with its previous value and a
verification blocker. Missing is never rendered as zero, a proven zero is never rendered as
missing, and the words for absence are the ones the calculation summary already uses. Values are
formatted per locale by one shared formatter. Glyphs the pinned font lacks are retired
product-wide and a gate keeps every shipped glyph inside the font.

### D4 One workbench per declaration

The workbench is the single Modelo destination. It shows the modelo, period, deadline and the
result in words; a five-step stepper (prepare, fill, calculate, review, file) with one
next-action line and one key to run it; a section navigator with per-section progress; the
casilla list as one virtual list per page with the cursor held by casilla id; a docked help band
that expands to a full help card; and a footer of described keys. Grids render as the official
rows and columns and fall back to stacked records on narrow terminals. Results are rows of the
same list, verification is the review step's issue list with jumps to casillas, provenance is the
help card's origin section, and filing and export are the file step. Operations run in the
existing operation modal and return to the workbench, which refreshes in place. Raw identifiers
live only in a technical drawer.

Amendment 2026-09-30, converging with the UX design specification. An assumed value, one the
calculation holds that nobody is recorded as having entered, keeps the fill step open and
withholds recording the filing until the filer confirms it or enters another value. This follows
no-silent-under-declaration: an unentered value in a filing-bound box is a suspicious zero.

Bulk confirm lists every assumed box with its value and requires an explicit acknowledgement. It
stages ordinary set intents for manual boxes only, through the mandatory review. It never confirms
a bound box, because that would become an override.

A declaration recorded as filed opens read-only, and says that changing it starts a correction.
The step words follow the filer's vocabulary: check, not review, and record filing, not file,
because the workbench submits nothing to the AEAT.

Authorized under the standing advance authorization the plan records.

### D5 Editing interaction

Editing starts on the first staged change. Values are typed through the application parser's
grammar in the operator's locale, inline for simple types and in a detail editor for dates,
IBANs, choices and overrides. Staged changes live in memory, keyed by semantic address, each
showing its previous value; revert, discard, an unsaved-change guard and a mandatory review with
override warnings precede apply. Apply runs through the operation modal, and a diff separates the
operator's changes, recalculated values and values changed by new source data. A stale session
keeps its changes and re-opens its review against the new head with every changed "before" value
marked for the operator to acknowledge.

### D6 Sources hub

A sources view groups every binding the revision declares, including those no casilla names, by
family, with its state, the casillas it feeds, and actions: go to the owning source surface,
enter or override where the policy allows with a reason, restore the source value, and
recalculate keeping the operator's values. A carry override records the source value it
displaced and stays disclosed until filing.

Amendment 2026-09-30, from the plan-close review (`2026-09-30-modelo-editor-workbench-audit`,
sources-hub-reason). The operator layer this workbench persists records neither an override
reason nor the source value an override displaced, and adding either changes the persisted
revision's content identity, a costly decision this record does not make. Until a follow-on
decision settles it, an override is disclosed as replacing its source until restored, the
workbench promises no reason, and the sources view reaches entry, override and restore through
the chosen casilla's editor and recalculation through the workbench, rather than carrying those
actions itself. Authorized under the standing advance authorization the plan records.

### D7 Help and headings

The help card assembles attributed parts: the catalogue explanation labelled as the product's,
official text quoted with its source, the rendered registry formula with box numbers, the legal
basis as citations, constraints in words, the origin, and the casillas it feeds. A help entry that
restates its label counts as absent, and the card says so instead of inventing text. Headings are
per-modelo layout keys plus a small shared column vocabulary, in all four locales; the fallback
order is the operator's locale, Spanish, the official Spanish heading, and finally a technical
name, each disclosed. Section tokens are never humanized.

### D8 Delivery order and acceptance

Delivery follows dependency, with no interim runtime layout: the operator-layer correctness work
and the layout family with its generator proceed in parallel; the form read model consumes the
published layout; the workbench consumes the form read model and retires the old pages in the
same change. A revision whose layout is absent or failed renders the inspection-only arm with its
reason. Acceptance is behavioural: the generator and validator run over every revision of the
real registry, the form builder is exercised against the real compiled registry, and the
workbench through the production composition at 80x24, 120x36 and 160x48 in all four locales and
both themes, with assertions that no transport token, casilla slug or digest reaches the main
surface.

## Rationale

The knockout is coverage with honesty. Only a generated declaration gives every revision a
real form structure (pages, apartados, rows and columns) from official sources while keeping the
structure diffable, validated and published with the revision. Runtime derivation cannot recover
structure the registry does not carry, and hand-authoring cannot reach every modelo. Making the
generated declaration editable is safe because every edit addresses a casilla or binding by id,
never a position, and the box number is always shown, so a grouping mistake can mislead the eye
but cannot misfile a value.

One workbench wins over the page catalogue because a filer's question is always about one
casilla in context: its value, where it came from, whether it is missing, and what to do next.
The measured widget costs make a single virtual list the only architecture that serves modelo 200
without paging as a crutch. Putting classification in the application keeps the TUI a renderer
and lets every future frontend share the same states.

## Consequences

- Every modelo gets an editor from data, and coverage becomes a published number: placed,
  working, unplaced, generated and reviewed.
- The registry gains a large generated family and a review queue; reviewing the most-filed
  modelos first is the path to promoting them.
- The page-per-destination workspace, its route factories and their tests are retired in one
  change; there is no alias to the old destinations.
- Headings start as official Spanish text for most layouts and are visibly disclosed as such until
  catalogue translations land.
- Seventeen source kinds remain read-only in the sources view until their override policy is
  grounded, and date and year casillas remain read-only until the engine has a channel for them.
- Glyph retirement touches surfaces outside the Modelo feature (profile, notices) because the
  pinned font lacks glyphs they already ship.
