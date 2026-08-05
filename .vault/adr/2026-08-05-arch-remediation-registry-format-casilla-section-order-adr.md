---
tags:
  - '#adr'
  - '#arch-remediation-registry-format'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c411b815cf2f27fca5d2dbfa0a06476b639bd93bde846f84930008124efe2fbe'
related:
  - "[[2026-08-05-arch-remediation-registry-format-casilla-fragment-content-naming-audit]]"
  - "[[2026-07-02-arch-remediation-registry-format-adr]]"
  - "[[2026-06-03-modelo-export-workbook-parity-adr]]"
---

# `arch-remediation-registry-format` adr: `casilla section order is an ungated presentational concern; the export rule states only the enforced parity set` | (**status:** `accepted`)

## Problem Statement

The export rule `modelo-export-mirrors-official-structure` states that the
registry-grounded workbook parity gate asserts three things: the casilla set
against the completeness manifest, numbering plus segmento, and
registry-declaration section order. The audit
`2026-08-05-arch-remediation-registry-format-casilla-fragment-content-naming-audit`
measured the third claim false twice over (findings
export-rule-claims-unenforced-section-order and section-order-not-held): no
gate reads casilla `section` at all, and the corpus does not hold section
contiguity in declaration order either — Modelo 303 declares 19 contiguous
runs across 10 sections, Modelo 200 declares 1,010 runs across 638, both
measured before the fragment rename. Adding the advertised assertion today
would therefore red immediately. The gap cannot be closed mechanically; a
decision is needed on whether section order becomes enforced (on the workbook
or on the corpus) or the rule's claim is corrected. This record is that
decision.

## Considerations

- The claim's origin is narrower than its current reading. The parity-gate
  spec in `2026-06-03-modelo-export-workbook-parity-adr` says "section
  ordering follows the registry declaration order" — a property the layout
  planner `plan_layout` satisfies by construction, because it iterates
  `revision.casillas` in declaration order. The rule compressed this into
  "registry-declaration section order" inside the gate's assertion list,
  which reads as a contiguity or official-layout guarantee neither the spec
  nor any gate ever made.
- AEAT's own official orderings disagree with each other, so section
  contiguity is not a property of the official structure. Walking the loaded
  Modelo 303 `2023-y-siguientes` snapshot in declaration order shows the
  numbered casillas ascending the official key with sections following the
  official form flow (devengado, deducible, simplificado, resultado), and the
  interleaving arising from exactly two sources: unnumbered internal
  calculation casillas appended after the numbered set, and AEAT's own
  late-added boxes — casillas `150`, `156`, `165` (the reduced-tier and
  recargo additions) carry high official numbers while belonging to the
  devengado and recargo sections declared at the start of the form. The
  official record design is number-keyed and not section-contiguous; the
  official paper form is visually section-grouped with non-monotone numbers.
  One declaration order cannot satisfy both, and the corpus tracks the record
  key (the audit measured only 18 adjacent descents against the official
  record-design key for Modelo 303).
- The sequence that legally matters is already enforced, as data. The
  fichero-BOE lane asserts emitted record order against the export layout's
  explicit integer `order` field per record
  (`_assert_record_order_fidelity`), which is the official Diseño de
  Registros sequence. That is a different concept from casilla `section` and
  is not in question here.
- The workbook is a working surface, not a facsimile. It splits casillas
  across the Entradas and Cálculos tabs by computedness, so it structurally
  never mirrored the official page sequence; `section` is consumed only as an
  orientation aid — a bold banner rendered whenever the section path changes
  (`_section_headers`). Non-contiguity costs repeated banners, nothing else.
- Everything deciding what the taxpayer declares is casilla-id-keyed and
  order-invariant, pinned by `test_casilla_order_invariance.py` (finding
  order-consumer-inventory of the same audit).
- The stale-workbook guard binds sheets to the snapshot digest, which the
  layout algorithm does not feed. A planner-side re-sort (option A below)
  changes every cell address while `registry_sha` stays identical, so that
  digest alone would not invalidate a previously exported workbook. The
  binding does carry a second axis that covers this: the pull also matches
  `CALC_SHEETS_ENGINE_VERSION`, so a re-sort shipped with an engine-version
  bump refuses stale sheets correctly. The residual risk is therefore a
  discipline requirement rather than an open hazard — a planner-side
  ordering change MUST bump the engine version, because the digest will not
  catch it — and this consideration is weaker than first recorded. It is
  not among the reasons option A is rejected below; the knockout is the
  official-key incompatibility.
- Declaration order is now an artifact of lexicographic content-derived
  fragment stems. Enforcing a semantic order through declaration order would
  require putting ordering back into filenames, which the audit's
  recommendations explicitly reject after retiring the drifting merge
  ordinal.
- The project's standing discipline is that a documented guarantee is either
  enforced or not claimed.

## Considered options

- **Option A: the workbook groups by section.** The layout planner sorts by
  section instead of following declaration order. Rejected: it breaks the one
  official-order property the workbook does track (ascending the official
  record key), moves the export further from the official numbering flow,
  and buys only fewer repeated banners. It would additionally oblige an
  engine-version bump so previously exported sheets are refused on pull,
  which is existing discipline rather than a blocker.
- **Option B: section contiguity becomes a corpus authoring invariant.**
  Rejected: the property is not achievable jointly with the official record
  key, because AEAT's own numbering interleaves sections; a corpus-wide
  reorder migration in this shared worktree carries the exact risk class the
  audit just documented (a runner that silently applied 103 of 12,663
  moves), and the ongoing constraint would have to be smuggled back into
  fragment filenames, reversing the content-derived naming decision.
- **Option C (chosen): correct the rule to state what is genuinely gated.**
  Casilla section order becomes an explicitly ungated presentational
  concern; the rule stops advertising a guarantee nothing enforces. Any
  future need for a specific presentation sequence must be declared as
  explicit data, the way the fichero-BOE record `order` field already is.

## Constraints

- The rule text is corrected at its `.vaultspec/rules/` source and propagated
  with the sync verb, never by editing the generated copies — per the
  vaultspec centralisation rule, which permits correcting an existing rule
  while new-rule authoring stays retired.
- `2026-06-03-modelo-export-workbook-parity-adr` remains accepted; this
  record narrows only the section-ordering clause of its parity-gate
  description. Its casilla-set, numbering, segmento, live-formula, anchor,
  and completeness decisions are untouched.
- No production code, gate, or corpus change is authorised by this record.
  The parity gate stays as it is; the corpus stays as it is.
- If the order-invariance gate is ever relaxed, the presentation-only status
  of declaration order — and with it this record's premise — must be
  reconsidered together with the content-derived naming convention, as the
  audit already notes.

## Implementation

One surface changes: the `modelo-export-mirrors-official-structure` rule.
Its parity-gate sentence is rewritten to enumerate the genuinely enforced
set — casilla set equals the completeness-manifest required set, numbering
plus segmento, a live formula on every renderable computed casilla, number
formats, start and final anchors, and, on the fichero-BOE lane, record order
against the explicit `order` field. A short paragraph is added stating that
casilla `section` is a semantic tag rendered as orientation banners in
declaration order, that section contiguity is deliberately not gated and not
held by the corpus, and that a future need for a specific casilla
presentation sequence must land as explicit data on the casilla or its
export layout rather than through fragment filenames or an authoring
convention. Optionally, a one-line note in the workbook parity gate's
docstring records that section order is deliberately unasserted, so a future
reader does not re-add the claim from the rule's history.

## Rationale

Both enforcement options fail a knockout: they would manufacture a property
the official structure itself does not have. Section contiguity and the
official record key are incompatible orderings for AEAT's real forms, so
enforcing contiguity — on the workbook or on the corpus — would move exports
away from the official sequence that is already enforced as data, at
migration cost and data-integrity risk, to protect a surface whose only
section consumer is a banner. Meanwhile every declaration-bearing projection
is id-keyed and gated order-invariant. The honest, cheap, and
structure-faithful correction is to the claim: the rule advertises exactly
what the gates enforce, and the door to a declared presentation order stays
open through explicit data, consistent with the audit's recommendation
against re-encoding order in filenames.

## Consequences

- The rule stops overstating; a reader consulting it now gets the true
  enforced set, closing the compound failure the audit flagged (claimed as
  gated, absent from the data).
- Workbook section banners keep repeating where sections interleave. This is
  accepted as faithful to the official record key rather than treated as a
  defect; the cost is cosmetic.
- No corpus migration, no export change, no gate reds, no new authoring
  constraint; the content-derived naming decision stands undisturbed.
- The workbook-parity ADR's gate description is narrowed on one clause by
  this record; readers of that ADR must read its section-ordering sentence
  subject to this one.
- If AEAT ever publishes a modelo whose official record design is
  section-keyed rather than number-keyed, the presentation-sequence door
  this record leaves open (explicit order data) is the sanctioned mechanism,
  and this decision does not need to be revisited to use it.
