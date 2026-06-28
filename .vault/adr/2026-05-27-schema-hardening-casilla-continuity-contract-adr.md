---
tags:
  - '#adr'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-research]]'
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---



# `schema-hardening` adr: `casilla-continuity-evolution-contract` | (**status:** `accepted`)

## Problem Statement

The registry now has two different cross-revision realities:

- Overlapping revisions can apply to the same filing period. A repeated casilla
  id in overlapping revisions must represent the same legal concept, and drift
  is a load-blocking defect.
- Non-overlapping annual revisions, especially M100, can legally evolve. A
  repeated numeric casilla id can be a stable concept, a label or citation
  evolution, extraction normalisation debt, or a genuine repurposing.

The current schema has no way to distinguish those cases. The overlap-aware
validator is correct, but it cannot safely hard-fail all non-overlapping M100
drift. At the same time, M100 template expansion would need exactly that
continuity knowledge before sharing labels, legal refs, formulas, bindings, or
generated fragments across annual revisions.

The registry therefore needs a generic casilla continuity/evolution contract
before any template authoring compiler is implemented.

## Considerations

The current `CasillaDefinition.id` is a registry reference handle. It is not
enough evidence for year-to-year legal continuity in non-overlapping forms,
because the M100 drift inventory shows repeated ids with mixed causes.

The current `segmento` field solves a different problem: same-number casilla
disambiguation within one revision of a multi-segment modelo. It does not say
whether two annual casillas are the same legal concept.

The current `semantic_role` field is useful continuity evidence but cannot be
the sole continuity key. Roles are optional, shared across modelos, and
sometimes intentionally broad.

The current non-overlap drift inventory is a useful advisory gate. It shows
where decisions are needed, but it intentionally does not encode those
decisions.

External tax-rule systems support the same conclusion. OpenFisca and
PolicyEngine model legal parameters as stable paths with dated value histories.
Tax-Calculator keeps stable policy parameter names with year-indexed values.
The stable concept key is explicit; display text drift is not treated as
identity.

## Constraints

- The contract must be generic across modelos. M100 must not receive
  model-specific schema semantics.
- The loader must continue to compile fragments into complete
  `ModeloRevision` objects before validation. Runtime inheritance and partial
  materialisation remain rejected.
- Physical fragmentation remains the authoring layout for M100. Template
  expansion is not authorised by this ADR.
- Enforcement must be staged. Existing non-overlapping drift is too broad to
  hard-fail globally without authored continuity decisions.
- Every non-trivial continuity/evolution decision must carry source and legal
  grounding.
- Existing overlap-aware hard validation remains mandatory and is not weakened.
- Implementation modules that encode continuity semantics must carry a short
  governing-ADR comment naming this ADR and the specific decision it implements.
  Loader-fragment comments must also name the fragment architecture ADR.

## Implementation

### D1 - Add a generic continuity identity surface

Introduce an additive Spanish-stem continuity identifier for casillas:
`continuidad_id`.

The field is optional during rollout. When present, it declares that the
casilla participates in a cross-revision continuity chain. The identifier is a
stable schema-level concept key, not a display label and not a template name.

The identifier may live directly on `CasillaDefinition`, or in a sibling
revision-level continuity record if implementation research shows that record
form gives better grounding and auditability. The semantics are the same: a
continuity id declares cross-revision concept identity.

### D2 - Add explicit evolution records

Introduce a generic evolution declaration for continuity chains. The declaration
must name the continuity id, the affected revision pair or revision window, the
evolution kind, and grounding.

Initial evolution kinds:

- `unchanged`
- `label_evolved`
- `legal_refs_evolved`
- `label_and_legal_refs_evolved`
- `repurposed`
- `retired`

The exact enum names may be adjusted during implementation to match project
Spanish-stem naming, but the categories are fixed by this ADR.

### D3 - Enforce declared continuity surfaces when a revision opts in

Add a revision-level opt-in flag for non-overlapping continuity validation. The
flag is **surface-scoped strictness**, not a declaration that every repeated
numeric casilla id in the revision pair has been reviewed.

Before opt-in, non-overlap drift remains advisory through the existing
inventory function. After opt-in, the validator must hard-fail drift on every
declared continuity surface:

- If either side of a repeated casilla id declares `continuidad_id`, any drift
  in the validator-owned fields must be covered by an allowed evolution record
  or fail.
- If an evolution record names a continuity id for the revision pair, drift on
  that surface must be checked even when only one side currently carries the
  casilla-level `continuidad_id`.
- A shared continuity id with incompatible `data_type`, `section`, or
  `semantic_role` is a hard error unless an explicit allowed evolution kind
  covers it.
- `repurposed` requires source and legal grounding and prevents template
  sharing across the repurposed boundary.
- `retired` prevents a missing later casilla from being treated as an
  accidental omission in continuity-aware reports.

Unannotated repeated-id drift remains advisory during staged rollout, even if
one of the revisions has opted into surface-scoped strictness. This is
deliberate: the opt-in flag makes authored continuity surfaces irreversible
without pretending the whole repeated-id corpus has been manually reviewed.

Corpus-wide strictness is a later state, not the meaning of this flag. A modelo
can claim corpus-wide continuity coverage only after every repeated-id drift
has either a continuity/evolution decision or a repurposing/retirement
decision. That completeness gate requires separate rollout evidence and must
not be inferred from `continuidad_validation = "strict"` alone.

### D4 - Keep template expansion downstream

Any future M100 template authoring compiler must consume the generic continuity
contract. It must not infer continuity from repeated numeric ids, labels, file
layout, or modelo-specific rules.

Template expansion remains a separate ADR. This ADR only defines the substrate
that would make template expansion defensible.

### D5 - Preserve current overlap validation

The current overlap-aware cross-revision drift validator remains a hard
snapshot-build gate. Overlapping revisions do not need opt-in: repeated casilla
ids in overlapping windows already assert the same legal concept and must not
drift silently.

## Rationale

Explicit continuity metadata is the only defensible middle ground between two
bad options:

- hard-failing all repeated-id annual drift, which would reject valid annual
  legal evolution and repurposing; or
- continuing to rely on repeated numeric ids and labels, which cannot support
  safe template generation or rigorous drift validation.

The accepted fragment architecture already separates authoring layout from
runtime schema. This ADR preserves that boundary. Fragments remain explicit
TOML records; validation sees complete `ModeloRevision` objects; future
template expansion must compile before validation and must be governed by the
same continuity metadata.

The staged opt-in is required because current M100 drift is known to be mixed.
The schema must first let authors record decisions, then enforce those
decisions. Advisory reporting remains useful during migration, including for
unannotated surfaces inside revisions that have already opted into
surface-scoped strictness for a smaller authored subset.

## Consequences

M100 template expansion is blocked until continuity metadata and enforcement
exist. This is intentional: a template compiler without continuity semantics
would turn current ambiguity into generated ambiguity.

The next implementation plan must start with schema and validator support, not
template support. The first data rollout should sample M100 repeated ids into
continuous, evolved, repurposed, and retired buckets, then author continuity
metadata only where evidence supports the decision.

The continuity validator adds another hard snapshot-build gate, but only for
declared continuity surfaces in opted-in revisions. This keeps current corpus
loading stable while making authored continuity hardening irreversible. A
separate corpus-wide completeness gate may later prove that a modelo has no
remaining advisory repeated-id drift, but this ADR does not treat that state as
implemented.

No runtime consumer should need to understand fragment files or template
sources. Snapshot, calculation, export, and application code continue to consume
fully materialized registry objects.
