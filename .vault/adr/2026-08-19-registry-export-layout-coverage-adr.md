---
tags:
  - '#adr'
  - '#registry-export-layout-coverage'
date: '2026-08-19'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:fab686dd8f530fcb02f07b4d71007b1ef3e8a93749c80b8747aa39549faea232'
related:
  - "[[2026-08-19-registry-export-layout-coverage-research]]"
---

# `registry-export-layout-coverage` adr: `Modelos with no AEAT positional design cannot claim the filing rung` | (**status:** `proposed`)

## Problem Statement

Modelos **136** (gravamen especial sobre premios de loterías, autoliquidación) and **721**
(monedas virtuales situadas en el extranjero, informativa anual) both declare
`authority_grade = "filing"`. The filing rung asserts a revision can back a filing draft
**and its export**.

`.vault/research/2026-08-19-registry-export-layout-coverage-research.md` established, against
AEAT's own record-design index rather than against our bundled corpus, that these are the only
two modelos in the registry for which **AEAT publishes no positional record design at all**.
AEAT publishes designs for 118 modelos; 136 and 721 are not among them. For 721 the only
layout artefact is its approving BOE orden's anexo — a printable form, not a positional design
a fixed-width writer can be authored from.

So their filing claim is not merely unbuilt. It is **unbackable in principle**: no amount of
authoring can produce an export for a format AEAT does not define. `_validate_export_exemption.py`
already encodes the consequence — it excuses these two from the "declares no export layout"
refusal precisely because "for a modelo AEAT publishes no design for that is not a task, it is
an impossibility". The grade was never reconciled with that exemption.

This matters beyond tidiness. A `filing`-grade revision is admitted to filing surfaces; the
runtime `_check_snapshot_filing_capability` then refuses any filing-grade snapshot lacking an
export layout. The two claims guarantee a refusal at the point of use, which is the worst place
to discover it — the operator has already done the work.

## Considerations

- The filing rung promises both a filing draft and export, but the runtime already refuses filing-grade snapshots without an export layout.
- AEAT's record-design index establishes that models 136 and 721 have no positional record design; 721's BOE annex is a printable form and does not supply byte positions or widths.
- The survey does not establish whether another AEAT file route exists, so the open follow-up bounds the claim.

## Decision

**A revision MUST NOT declare the `filing` rung when AEAT publishes no positional record design
for its modelo.** Such a revision declares `applicability`, and resolves its `export_layouts`
family as not-applicable with the reason grounded in the absence of an AEAT design.

Concretely: 136/2026 and 721/2023-y-siguientes move `filing` -> `applicability`, each carrying a
family disposition stating that AEAT publishes no positional design for the modelo and citing
the record-design index survey.

The predicate is already computed and already load-bearing:
`modelo_publishes_a_record_design(modelo, source_refs)`. This decision makes the grade agree
with it instead of contradicting it.

## Considered options

- **Leave `filing` and author nothing.** Rejected. The registry then asserts a filing capability
  that cannot exist, and the assertion is only discovered when a snapshot is requested. It also
  keeps two permanent entries on the export-layout backlog that no work can ever close, which
  makes the backlog lie about how much is left.

- **Leave `filing` and author a layout from the BOE orden's anexo.** Rejected, and this is the
  option to name explicitly because it is the tempting one. The anexo is a printed form: it fixes
  what a human writes in which box, not byte offsets, widths, padding or field order. Authoring a
  fixed-width layout from it means inventing the positional facts AEAT never published. That
  produces a file that renders, digests and validates while being wrong in a way no gate can
  catch — the same defect class this campaign removed from three fabricated corpus sources.

- **Introduce a fourth rung for "files, but not by fichero".** Rejected for now as premature.
  Nothing today consumes such a distinction, and `applicability` plus an explicit
  export-family disposition already records both facts — that the modelo is real and due, and
  that no positional design exists. Revisit if a web-form submission surface is ever built.

- **Demote silently without an ADR.** Rejected. The grade validator states that the rung is the
  reach a revision is INTENDED to support and warns "DO NOT pick the rung by looking at which
  families this revision currently has". A demotion driven by present content is exactly what it
  forbids; a demotion driven by an external, permanent fact about what AEAT publishes is a
  different thing, and the difference has to be written down or the next reader cannot tell them
  apart.

## Constraints

- Do not invent positional offsets, lengths, field order, or padding from a printed BOE form.
- The decision is limited to absence in the surveyed AEAT record-design index; another submission route would require reconsideration.
- Keep the filing grade tied to export capability rather than present implementation completeness.

## Implementation

If adopted, move 136/2026 and 721/2023-y-siguientes from filing to applicability. Give each an export_layouts not-applicable disposition that cites the record-design survey. Retain the existing modelo_publishes_a_record_design predicate as the basis for the grade check.

## Rationale

A filing-grade claim for a format AEAT does not define cannot be fulfilled through the sanctioned positional exporter. Keeping that grade guarantees a late refusal and leaves impossible backlog items open. Applicability preserves the fact that the modelos exist and are due, while the explicit disposition records why no positional export can be authored.

## Consequences

- 136 and 721 leave the export-layout backlog permanently and correctly. The remaining backlog
  becomes an honest count of work that can actually be done.
- Both lose admission to filing surfaces. That is a real capability loss on paper only: the
  runtime already refuses them, so nothing that works today stops working.
- The registry gains a stated, citable reason for two revisions that would otherwise read as
  unfinished forever.
- **If AEAT later publishes a positional design for either modelo, the decision reverses**: the
  design is acquired, the export layout authored, and the rung promoted. The disposition reason
  names the survey date so a future reader knows what was true when, and what to re-check.

## Open follow-up

Whether either modelo is submissible by any file route outside the record-design index (a
distinct AEAT surface) was not established. The survey covered the published index only. If such
a route exists this decision is wrong for that modelo and should be revisited — recorded here so
the limitation travels with the decision rather than being rediscovered.
