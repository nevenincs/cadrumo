---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---



# `schema-hardening` research: `casilla-continuity-contract`

Researched the generic substrate needed before any M100 template-expansion ADR.
The immediate question is whether non-overlapping annual revisions can safely
share repeated casilla ids without a schema concept that distinguishes legal
continuity from annual repurposing.

## Findings

The current hard validator is intentionally overlap-aware. It treats a repeated
casilla id across overlapping revision windows as one stable legal concept and
hard-fails drift in `label`, `section`, `data_type`, `semantic_role`, and
`legal_refs`. It deliberately does not hard-fail non-overlapping annual drift,
because M100 shows that repeated numeric ids can be a mix of continuous
concepts, legitimate annual label evolution, citation retrofit debt, extraction
normalisation debt, and real repurposing.

The existing schema already has several adjacent concepts but none is a
continuity contract:

- `CasillaDefinition.id` is the within-registry reference handle, not a
  cross-year identity declaration for non-overlapping forms.
- `CasillaDefinition.segmento` disambiguates same-number casillas within one
  revision. It solves same-revision identity collisions, not year-to-year
  continuity.
- `semantic_role` captures business meaning but is intentionally optional and
  shared across modelos. It is useful evidence for continuity, but cannot be
  the continuity key by itself.
- `ConstructDefinition` groups revision members inside one revision. It can
  provide a natural place to group related casillas, but today it has no
  cross-revision identity semantics.
- `summarize_non_overlapping_cross_revision_casilla_drift` is the correct
  advisory inventory, but it cannot decide which annual differences are legal
  evolution and which are defects.

External tax-rule systems point toward explicit stable identities with dated
values rather than implicit continuity from display labels. OpenFisca and
PolicyEngine parameter trees use stable paths and value histories indexed by
effective date. Tax-Calculator keeps policy parameter names stable and varies
values by year/indexing metadata. Those systems model time variation under a
stable concept key; they do not infer concept identity from annual label text.

## Design Pressure

M100 template expansion is unsafe without a continuity contract. A template
would need to know that two annual casillas are the same concept before it can
share labels, legal refs, formulas, bindings, or generated fragments. The
current repeated numeric id is not sufficient evidence because some ids are
repurposed across years.

The contract should be generic and cross-modelo. M100 must not receive special
template semantics, and the loader must continue to compile explicit fragments
into complete `ModeloRevision` objects before validation. Any future compiler
feature should consume the same generic continuity metadata that validators use.

## Candidate Contract

A future ADR should evaluate an additive schema surface with these pieces:

- A stable Spanish-stem continuity identifier on casillas or a sibling
  revision-level continuity record, such as `continuidad_id`.
- An explicit evolution classification for non-identical repeated concepts,
  such as `unchanged`, `label_evolved`, `legal_refs_evolved`, `repurposed`, or
  `retired`.
- Source and legal grounding on every non-trivial evolution classification.
- A validator that hard-fails contradictory declarations: same continuity id
  with incompatible data type or semantic role unless an allowed evolution is
  declared; repeated numeric id with drift and no continuity/evolution decision
  once a modelo opts into continuity enforcement.
- An advisory inventory mode that remains available for modelos not yet opted
  into the hard contract.

## Recommendation

Do not implement M100 template expansion next. The next architectural slice
should be an ADR for a generic casilla continuity/evolution contract, preceded
by a concrete M100 inventory that samples repeated ids into three buckets:
continuous, annual label/legal evolution, and repurposed.

Until that ADR exists, the safe state is explicit fragmented TOML plus the
current overlap-only hard validator and non-overlap advisory inventory.
