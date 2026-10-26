---
tags:
  - '#audit'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:56ef153e543e911f11f8c6395bbf3eba3efa450016b07983cac7d653f05f0a75'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `m303-form-vs-semantic-casilla-dual-keying` audit: `S69 rectificativa motive ADR independent review`

## Scope

Independent architecture review of the accepted dual-keying ADR's 2026-08-14 rectificativa-motive amendment against the current calculation-revision, WorkUnit, filing-instance evidence, amendment service, revision-identity, producer-snapshot, and producer-key contracts. The review asks whether the required and prohibited motive states can be enforced without duplicating modelo, period, and registry-revision axes or allowing invalid persisted revisions to survive authoritative load. Production implementation and semantic-map authoring are outside scope.

## Findings

### s69-rectificativa-motive-context | critical | The isolated calculation revision lacks the axes required by the ADR invariant

`CalculationRevision` retains only `work_unit_id`; the parent `WorkUnit` owns modelo, period, and registry revision. The encrypted calculation catalogue currently deserializes independently of the WorkUnit catalogue. An optional motive added only to `CalculationRevision` therefore cannot prove at construction or reload that its parent is Modelo 303 or that the selected revision and period admit the 2024-late amendment region. Field-local validation must either duplicate those axes or accept a context-free revision shape that can be invalid for its referenced WorkUnit.

### s69-rectificativa-motive-coordinate | high | Existing filing evidence can close the epoch coordinate only after an aggregate cross-check

The mandatory M303 filing-instance evidence already retains period plus the simplified calculation result's registry revision, record-design source, source digest, and record-design epoch. Those facts avoid another persisted context stamp, but they do not independently prove equality with the parent WorkUnit. The authoritative boundary must join and compare both owners before returning a revision.

### s69-rectificativa-motive-export-authority | high | Command-supplied amendment evidence can currently diverge from persisted revision authority

The current export path receives `AmendmentEvidence` from the export command and compares only its amendment kind with the revision. Free-text motive and original AEAT receipt can therefore vary while the persisted revision remains unchanged. Adding the typed motive to the revision without deleting or exactly reconciling that command path would create two value authorities.

### s69-rectificativa-motive-identity | high | Current revision identity excludes amendment classification

The sole calculation-revision identity builder includes filing-instance evidence but excludes amendment kind and amended filing-record identity. The amendment service derives the new id before constructing amendment metadata. Adding only the new motive would make motive alternatives diverge, but would leave amendment kind and amended target mutable metadata over the same content address.

### s69-rectificativa-motive-future-epoch | medium | An open later-than rule would admit unreviewed record designs

`record_design_epoch` is an open string. The phrase "2024-late or later" cannot safely become a lexical comparison, year shortcut, or future-default rule, and conflicts with the amendment's separate requirement that later epochs inherit only after exact source review.

### s69-rectificativa-motive-projection | medium | Producer-key closure depends on the upstream authority repair

The current producer vocabulary contains only the general rectificativa marker, complementaria marker, and original receipt. Two separate motive keys and their opposite-boolean truth table are structurally compatible with the exhaustive resolver, but only after the persisted motive and applicability context are authoritative.

### s69-rectificativa-motive-target-authority | high | The amended filing target was not part of the authoritative aggregate join

The amendment identity can content-address an `amends_filing_record_id`, but the earlier aggregate rule joined only the calculation revision, WorkUnit, and M303 filing-instance evidence. `ModeloRecord` separately owns the target's WorkUnit, Modelo, filing period, AEAT-accepted state, and `ExternalEvidence`; that evidence carries only a `reference_id`, while the original receipt number is the resolved `Justificante.presentation_id`. Without resolving and cross-checking that chain, an arbitrary, nonexistent, or cross-context target could remain internally self-consistent and export could not derive the receipt from one authoritative source.

## Recommendations

- Amend the ADR before implementation to choose one context-bound aggregate validation boundary. Resolve the referenced WorkUnit during canonical construction and encrypted load, and refuse motive-bearing revisions when that context is unavailable. Do not copy WorkUnit axes onto the revision.
- Reuse the exact period, registry revision, record-design source, digest, and epoch already retained by M303 filing-instance evidence, and require equality with the parent WorkUnit and selected registry snapshot.
- Define a closed source-bound applicability set for the reviewed 2024-late, 2025, and 2026 amendment regions. Require another reviewed amendment for any future epoch.
- Put amendment kind, amended filing-record identity, and typed M303 motive in one nullable revision-identity payload. Resolve it before id derivation; keep free-text explanation outside identity.
- Construct export amendment evidence from persisted revision and filing authorities. Remove motive and receipt as command overrides, or refuse unless every supplied field equals persisted evidence exactly.
- Resolve `amends_filing_record_id` through the authoritative `ModeloRecord` catalogue during aggregate construction and encrypted load. Require exact target id, WorkUnit, Modelo, filing period, registry-context, AEAT-accepted state, and matching `ExternalEvidence.reference_id` to persisted `Justificante` metadata; derive the original receipt only from its non-null `presentation_id`. Refuse arbitrary, nonexistent, duplicated, cross-context, unresolvable, mismatched, or receipt-less targets before snapshot construction or export.
- Add two distinct producer keys and resolve only `(true, false)`, `(false, true)`, or the inapplicable `(None, None)` state. Prove authoritative reload refusal, aggregate mismatch refusal, identity divergence, the full applicability truth table, snapshot exhaustiveness, command substitution refusal, and exact emitted wire alternatives before S69 map authoring.
