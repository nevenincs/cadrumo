---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ea529ce07ce4ad987d5db12cc50a4c544b439a9248e8daf16f64527c67703d48'
related:
  - "[[2026-08-26-tui-architecture-m184-socio-clave-subclave-research]]"
  - "[[2026-07-09-m184-socio-attribution-handoff-adr]]"
---

# `tui-architecture` adr: `modelo 184 socio row shape: repeat per member, clave and subclave` | (**status:** `proposed`)

## Problem Statement

The modelo 184 socio export record was found truncating a multi-member attribution to a
single member (the original S289 finding). Fixing that by adding per-row bindings to the
existing one-row-per-member domain row cannot work: `2026-08-26-tui-architecture-m184-socio-clave-subclave-research`
establishes that the record's real repetition axis is `(member, clave, subclave)`, not
member alone, with roughly twenty fields whose applicability and meaning depend on which
clave and subclave the row declares. The row shape itself has to change before any
export wiring or profile input surface can be built correctly. This ADR decides that
shape and what it does to the accepted S288 edit contract, which was built against the
one-row-per-member assumption.

This record does not overlap `2026-07-09-m184-socio-attribution-handoff-adr`. That
accepted decision governs how the entity's already-computed attributed base reaches a
member's own, separate M100 filing (a cross-bucket transport question); this record
governs how the entity's own M184 socio record represents its income lines in the first
place (a row-shape question). The handoff ADR's `Modelo184MemberRow` usage is read-only
downstream of whatever shape this record settles on; neither decision requires the other
to change.

## Considerations

- The record's own diseño states the repetition rule directly (research, "socio record
  repeats per (member, clave, subclave)"); this is not inferred from field naming.
- An existing detail-row family already solved an equivalent problem: the 349 operador
  row's identity already includes its clave axis, and survived S285's per-kind
  membership refusal and S288's natural-key edit contract unchanged (research, "M349
  already models an equivalent axis correctly").
- A row's field set alone is not evidence of a repetition axis: the 347 contraparte row
  carries a clave field despite its record never repeating on it (research, "M347
  contraparte row already carries a clave field without the record repeating on it").
  The test is what each modelo's own diseño states, not what fields a row happens to
  carry.
- Several fields are legally conditional on the clave/subclave pair (research, "remaining
  fields are conditional on clave and subclave"), so a shape that cannot express "this
  field only applies when clave = C" invites either fabricated values or silent omission.
- `provisiones-gastos-dificil-justificacion` is a computed formula reading a fact from a
  DIFFERENT record (the entity's own tipo-2 régimen), not an operator-declared value
  (research, same section; legal basis Reglamento IRPF art. 30 regla 2ª, verified).
- The clave-E eligibility test (member must be an IS or IRNR-con-establecimiento
  taxpayer) has no existing representation anywhere in this tree (research, field
  inventory).
- Whole-set replacement by natural key and absence-as-deletion (S288) are the accepted,
  general mechanism every detail-row kind uses; a new row shape must fit that mechanism,
  not fork a second one.

## Considered options

1. **Add clave/subclave as fields on `Modelo184MemberRow`, keep the row per (member,
   clave, subclave) pair.** Mirrors the 349 precedent directly: one row instance per
   income line, addressed by the widened tuple. Pro: reuses an already-proven shape and
   the existing whole-set-replacement mechanism without new machinery. Con: an operator
   declaring one member's total picture now declares N rows for that member instead of
   one, which is more entry surface per member than before.
2. **Keep one row per member, add a nested tuple of income-line sub-objects.** Pro: keeps
   "one row = one member" intuitive at the top level. Con: introduces a second addressing
   axis inside a single row that the natural-key/whole-set-replacement/detail_rows
   contract (a flat tuple of rows) does not model at all; every consumer that walks
   `detail_rows` as a flat sequence (the calc mesh, the export renderer, the S288 edit
   surface) would need a second, nested iteration layer that does not exist anywhere else
   in this tree. Rejected: invents a new pattern where a working one already exists.
3. **Leave `Modelo184MemberRow` as one row per member and store the clave-conditional
   detail as an unstructured blob or free-form mapping.** Rejected outright: violates the
   project's typed-boundary mandate and the grounding rule that a regulated value must be
   validated against its own selector model, not schemaless data.

## Constraints

- The decision is scoped to the row shape and its edit-contract ripple; it does not
  design the operator-facing profile input surface for declaring clave/subclave-scoped
  income lines (research, "not investigated"), which is separate downstream work.
- The clave-E eligibility test and the provisiones-gastos cross-record dependency are
  real, grounded facts this ADR must dispose of explicitly (accept as in-scope work, or
  record as a further, separately-tracked gap) rather than leave implicit.
- No live BOE cross-check was performed; the bundled consolidated corpus was treated as
  authoritative per the standing bundled-corpus-first grounding rule, with all four cited
  articles read in full rather than excerpted (research, "Legal citation cross-check,
  resolved").

## Implementation

`Modelo184MemberRow` gains `clave` and `subclave` fields (following the row's own
existing validation pattern for its current fields), and its identity becomes the tuple
`(nif, clave, subclave)` rather than `nif` alone — the same shape 349's `operador` row
already uses. The clave-conditional fields (inmueble sub-block under clave C; the
rendimiento-neto sub-fields under clave D's subclaves 03/04; the clave-C and clave-D
reduccion fields, grounded on LIRPF arts. 23.2/23.3 and 32.1 respectively, both verified)
become fields on the same row, each populated only when its governing clave/subclave
applies; a row declaring a value for a field its clave does not license is a validation
refusal at the row's own boundary, the same shape the row's current share-percentage
bound check already uses.

**The clave-A reducción field is explicitly BLOCKED, not merely flagged.** Its governing
provision is unresolved: the diseño cites LIRPF art. 24.2, which does not exist as such
(art. 24 is an unrelated related-party rule) — see the research document's citation
cross-check. Art. 26.2 is a candidate by cross-reference match, but was identified from a
single consolidated bundled file rather than a per-article authoritative source, and
adopting the nearest plausible article is exactly what the grounding rule forbids for a
value whose specific binding provision is not correctly identified. **The clave-A
reducción field on `Modelo184MemberRow` MUST NOT be implemented, and no export or
resolver wiring may target it, until a dedicated follow-up research pass identifies and
verifies its governing provision.** Every other clave-conditional field in this ADR's
scope has a verified citation and may proceed; this one field alone is gated on that
separate research pass.

`provisiones-gastos-dificil-justificacion` is NOT collected as row input. It is computed
from the entity's own régimen fact (read from the sibling tipo-2 entidad record) and the
member's share percentage, per the Reglamento IRPF art. 30 regla 2ª formula, at the same
layer the registry formula engine already computes other cross-casilla values — not
inside the row model and not as a profile-collected fact.

The clave-E eligibility test (member is an IS or IRNR-con-establecimiento taxpayer) is
recorded here as an EXPLICIT GAP, not silently absorbed into this ADR's scope: this tree
has no existing representation of a member's own contribuyente classification, and
building one is a further, separately-scoped Step. Until it exists, a clave-E row is
accepted at face value without that eligibility check — a known, stated limitation, not
an invented default.

The S288 edit contract requires no contract change, only a configuration change: the
compound-natural-key mechanism `_DETAIL_ROW_NATURAL_KEY_FIELDS` already generalizes to,
and today already carries, a multi-field tuple for the `operador` row kind
(`("nif_comunitario", "clave_operacion")`). Widening the `miembro` row kind's entry from
`("nif",)` to `("nif", "clave", "subclave")` exercises that existing mechanism rather
than extending it — no new code path, no new validation shape, nothing S288 did not
already have to handle for a different row kind. Whole-set replacement,
absence-as-deletion, the ADD/UPDATE/DELETE intent kinds and MOVE_ROW's retirement all
apply unchanged under the wider key; nothing else in the edit contract depends on a row
kind's specific field set. This materially lowers the risk of the row-shape redesign:
the riskiest-looking consequence (does the edit contract need to change?) resolves to "no
— configure the existing mechanism differently."

## Rationale

Option 1 wins because the shape it proposes is not new: it is the pattern the 349
operador row already carries, already proven against S285's per-kind membership refusal
and S288's natural-key edit contract without modification. Option 2 would require
building a second detail-row addressing pattern (nested per-row sub-objects) parallel to
the flat-tuple pattern every other consumer already assumes, for no benefit the flat
shape does not already provide once the natural key widens. Option 3 fails the project's
typed-boundary and grounding mandates outright.

## Consequences

- Every detail-row consumer that pattern-matches on `Modelo184MemberRow`'s field set
  (the S285 per-kind membership check, the S288 edit surface, the resolver) needs the two
  new fields threaded through, and the natural-key widening lands in the same change as
  the row-shape change to avoid a window where the two disagree.
- The operator-facing input surface for declaring clave/subclave-scoped income lines is
  NOT designed here and remains a real, separately-scoped gap: an operator today has no
  way to declare more than the four fields S289 already found wired (nif, name, share,
  base_imponible_assigned), and this ADR does not close that gap by itself — it only
  makes the row shape capable of representing the answer once that input surface exists.
- The clave-E eligibility test is a stated, tracked gap rather than a silent default,
  consistent with the no-silent-under-declaration standing rule.
- `repeat = "binding_rows"` on the socio export record still cannot ship until every
  clave/subclave-conditional field that carries a money value has a real per-row source
  reaching the export boundary — this ADR enables that state without shipping it itself.
- The clave-A reducción field is explicitly excluded from what "every field has a
  verified grounding" covers here: it is blocked pending its own follow-up research pass,
  and the row shape must accommodate a member declaring clave A / subclave 02 without
  that one field being populated until the block lifts.
