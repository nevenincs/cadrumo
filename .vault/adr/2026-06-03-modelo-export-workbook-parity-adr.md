---
tags:
  - '#adr'
  - '#modelo-export-workbook-parity'
date: '2026-06-03'
modified: '2026-10-07'
body_hash: 'sha256:5b6784227589377fa9f99755fece77bcf14b784a83b3fedeab064cd46970732e'
related:
  - "[[2026-06-03-modelo-export-evidence-parity-research]]"
  - "[[2026-06-03-modelo-export-evidence-parity-adr]]"
  - '[[2026-06-04-modelo-export-workbook-parity-research]]'
---

# `modelo-export-workbook-parity` adr: `uniform modelo export workbook parity and UX` | (**status:** `accepted`)

## Problem Statement

The modelo workbook export (the calc-sheets plan materialised to Google Sheets,
and the offline xls equivalent) renders the registry casilla grid with live
formulas but lacks a uniform, enforced presentation contract. There is no cell
formatting (no number formats, no section-header styling), the
inputs-to-resultado flow has no explicit labelled start / final anchor, the
offline xls and online Sheets paths do not provably share one builder, and there
is no automated gate asserting the exported structure is a faithful mirror of the
official AEAT modelo / published workbook layout. For a filing artefact the
operator reviews before submitting outside the application, divergence from the
official casilla structure or an unreadable/ambiguous calculation surface is a
critical correctness risk, not a cosmetic one. This ADR defines the uniform
export-workbook UX and the parity gate that enforces it.

## Considerations

- **One builder, two transports.** The official-structure mirror, the live
  formulas, the labels, and the formatting must be defined once (the plan
  builder) and materialised identically to offline xls and online Sheets. The
  transports differ only in how they write cells, never in what the workbook
  says.
- **Saved baselines and explicit scenario boundaries.** Selected-revision review
  baselines contain saved canonical values. Templates or separately labeled
  scenarios may use live spreadsheet formulas. Show where inputs start and the
  result is presented with explicit anchors; external scenario edits are never
  production calculation inputs. Amended under the 2026-10-05 outbound decision.
- **Official-structure fidelity is a gate.** The registry is the authority
  (`CasillaDefinition.number` / `segmento` / `section`, the
  `CalculationCompletenessManifest` derived from the AEAT Diseño de Registros).
  The exported grid's casilla set, numbering, and section ordering must match the
  official layout; a structural divergence is a hard CI failure, not a warning.
- **Readability / UX conventions.** Money casillas carry a money number format;
  sections carry header styling; protected (computed) regions are visually
  distinct from operator-input regions; legal-ref notes remain attached;
  bundled-evidence (sibling ADR) gets its own clearly-labelled surface.
- **Reuse.** Build on the existing `SheetExportPlan` record set (`value_cells`,
  `formula_cells`, `protected_ranges`, `cell_constraints`, `guide`, `metadata`)
  and the existing apply adapter; add formatting + start/final + evidence as new
  plan facets, not a parallel builder.

Amendment 2026-10-05: the live-calculation consideration above applies to templates or separately labeled scenarios. Selected-revision review baselines carry saved values, with the scoped parity rule stated in Implementation. Neither online scenario edits nor review notes are product calculation inputs.

## Constraints

- **openpyxl (offline) + Sheets API (online)** are the two materialisers; both
  already vendored. The plan record set is the shared intermediate; neither
  transport may add structure the plan does not declare.
- **Strict-frozen records, core types, hexagonal layering, relative imports.**
  Formatting facets are typed records on the plan (e.g. number-format / style /
  start-final-anchor cells), not ad-hoc dicts.
- **Parent-feature dependency.** Consumes the evidence-bundling ADR
  (`modelo-export-evidence-parity`) for the Evidencia surface; the parity gate
  and formatting can land independently of it, but the evidence tab requires it.
  The official-layout fixtures depend on the registry completeness manifests
  being present for each covered modelo.
- **Parity oracle.** Faithfulness is asserted against the registry completeness
  manifest (the in-repo authority for the official casilla set) and, where an
  official published-workbook layout is available, a committed layout-fixture;
  never against a hand-authored expectation that could drift from AEAT.

## Implementation

The plan builder gains uniform presentation facets, expressed as typed records on
`SheetExportPlan`: per-cell number formats (money / integer / percentage driven
by `CasillaDefinition.data_type`), section-header style rows derived from
`CasillaDefinition.section`, and explicit **start** (inputs / Entradas opening)
and **final** (resultado / cuota) labelled anchor cells. Both materialisers
consume these: the offline xls writer (openpyxl) and the online Sheets apply
adapter render the same formats, headers, and anchors, so an operator sees an
identical workbook offline and online.

A parity gate validates every covered modelo's generated plan against the
registry authority: the exported casilla set equals the completeness-manifest
required set (numbering + segmento), section ordering follows the registry
declaration order, and the start/final anchors are present and correctly placed.
For selected-revision review exports, computed baseline values are the saved
canonical results, not live formulas. Formula parity applies only to separately
labeled scenarios/template surfaces; scenarios are never ingested into product
calculations. This scoped exception is authorized by the 2026-10-05 outbound
review amendment and does not remove offline XLSX or shared formatting. Divergence fails the gate.
Where an official published-workbook layout fixture exists, an additional
structural-mirror assertion compares the generated grid shape to it.

The Evidencia surface (from the sibling evidence ADR) is rendered as a dedicated
protected tab listing, per casilla, the bundled ledger contributors and manual
fact basis with amounts and legal grounding. Offline and online exports share the
plan, so both carry the evidence surface identically.

### Human workbook transport controls (2026-10-06)

The user's approved registry-workbook-compiler continuation explicitly requires removal of technical internals from human documents while retaining all financial inputs, calculations and references. Within that scope, a human workbook may omit an explicitly authored transport-control placement with a grounded reason. This is a workbook-only presentation exception to the displayed casilla-set rule above: it does not delete the casilla, its value, its export mapping or its ordinary application form projection. Registry placement coverage remains total and the filing export remains unchanged.

Omission is limited to unnumbered working figures classified as transport controls, not computed internal financial intermediates or merely unplaced fields. The shared workbook builder must refuse omission of financial/bound fields, declared calculation/binding/page dependencies, generated sheet-formula references or recorded evidence. Both transports consume the same resulting plan. A source classification without evidence is not authority to infer omissions by field name, numeric position or regular expression. Verification must prove retained financial data and refusal paths, as well as absence of the technical controls from rendered workbook surfaces. Existing unclassified placements retain their previous behavior. This amendment records the user's requested scope and the bounded implementation contract, not complete inventory classification or completed delivery.

### Administrative communication workbooks (2026-10-06)

The approved all-modelo template scope includes registry communications that are not tax filings, such as Modelo 145. Shared workbook metadata preserves these administrative selectors in a separate strict typed frame; it must not substitute a quarterly, annual or ad-hoc filing period. Core filing-period validation remains unchanged. The existing wire coordinate fields and shared materializers are retained. Calendar filing pull must refuse administrative frames, including a forged matching-metadata verdict. This is presentation support, not a new filing capability, legal validity claim, or permission to ingest scenario edits. Tests cover distinct frame admission, coordinate round trips, year binding, unchanged filing refusals and populated form references.

### Fictional historical template previews (2026-10-06)

The approved all-modelo/all-revision template exercise includes enrolled historical revisions outside the runtime filing support envelope. Development-only previews may project an explicitly selected, validated enrolled revision into fictional workbook cells and spreadsheet formulas. They use a distinct strict template source and preview metadata identity, never a RegistrySnapshot manufactured for the purpose or a RegistryRevisionInspection passed into calculation or filing-instance APIs. The development admission factory must verify the exact modelo, revision, source and illustrative frame through canonical authority selection; it must not change the support floor, substitute current declarations for historical ones, or use a raw-loader fallback.

Shared neutral cell-plan assembly and form geometry remain the single compiler used by both workbook materializers. Preview inputs, dates and rows are explicit fictional fixtures; profile reads, filing producers, saved calculation revisions and relation-resolution authority are outside this preview path. Existing spreadsheet formula translation may illustrate the revision's declared expressions, preserving unknown dependencies. Preview metadata uses a separate kind and namespace, carries no publication or snapshot identity, and cannot decode as production export metadata. Human surfaces disclose that the workbook is a fictional example and is not valid for filing, without displaying technical digests.

This bounded template exception does not establish fiscal validity, filing support, legal review, authority adoption, publication eligibility or import authority. Runtime snapshot gates, historical static-inspection restrictions under 2026-08-14-registry-temporal-coverage-adr, and remote-input refusals remain unchanged. Verification must prove ordinary historical snapshot refusal, preview source/revision/frame mismatch refusal, distinct metadata in both transports, absent production data authority, and correct formula/blank/zero behavior. This records the implementation contract within the user's approved exercise, not completed historical preview delivery.

## Rationale

Research finding A established that the calc-sheets plan already mirrors registry
structure and emits live formulas but writes no formatting and has no explicit
start/final or parity gate. Defining presentation as typed plan facets keeps the
single-builder / two-transport invariant the research recommends, so offline and
online cannot drift. Grounding the parity gate in the registry completeness
manifest (the in-repo projection of the AEAT Diseño de Registros) means
"official parity" is checked against the same authority the calculation engine
uses, not a separate hand-maintained spec — eliminating a drift surface.

## Consequences

- **Gain:** uniform, readable, official-faithful workbooks; operators review a
  filing artefact that visually and structurally mirrors the AEAT modelo, with an
  unambiguous input→result flow and live recomputation.
- **Gain:** structural divergence from the official casilla layout is caught in
  CI, not at filing time.
- **Cost:** a formatting + parity layer per covered modelo; the parity gate needs
  the completeness manifest present for each modelo (some may need authoring).
- **Cost:** offline xls formatting via openpyxl and online via the Sheets API are
  two renderers of one plan; a conformance test must assert they agree.
- **Pitfall:** "parity" is only as strong as the registry authority; a modelo
  whose manifest is incomplete yields a weaker gate — the gate must report
  coverage honestly rather than imply full parity.

## Codification candidates

- **Rule slug:** `modelo-export-mirrors-official-structure`.
  **Rule:** Every modelo workbook export (offline xls and online Sheets) must be
  generated from the single shared plan builder, render live formulas with an
  explicit labelled start/final, and pass the registry-grounded parity gate
  (casilla set, numbering, section order) — a structural divergence from the
  official AEAT layout is a hard failure, never a warning.

## Amendment 2026-10-05 - outbound review

The product owner's Session 01 instruction authorizes the scoped wording changes above, governed by 2026-10-05-google-outbound-review-adr. Earlier descriptions of then-current behavior remain historical evidence, not permission to retain retired routes. Other commitments remain in force. This amendment records architecture, not completed implementation or live acceptance.
