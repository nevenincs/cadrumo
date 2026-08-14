---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:2ed7261a86cc58d58d3dfe4fc1ea3774951276782bd9e9e81238404a41bd215a'
step_id: 'S02'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Derive schema-family enrollment from ModeloRevision field markers and project the per-revision coverage manifest with populated, not_applicable and blocked_pending_evidence dispositions, proving a field added without a marker reds the enrollment-completeness check

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`
- `src/cadrumo/domain/calculations/registry/_coverage.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add the `SchemaFamilyMarker` and its `SCHEMA_FAMILY` singleton to the registry
  schema base, deliberately NOT a subclass of the manifest-only marker, and mark
  all 21 of the revision's declared content collections with it.
- Add `collection_shaped_fields`, computing the same set from the annotations
  alone, and `schema_family_enrollment_failures`, which reports both directions
  of disagreement between the declared and the shape-derived set.
- Add the `RegistrySchemaFamilyDisposition` StrEnum to core with its
  `UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS` companion set, and publish both on the
  core facade.
- Add `SchemaFamilyDispositionDeclaration` and a manifest-only, mapping-typed
  `family_dispositions` on the revision, refusing a declaration that names no
  enrolled family and one that contradicts a populated family.
- Project `RevisionCoverageManifest` in the coverage module from one revision
  alone, with `SchemaFamilyCoverageRow` refusing every incoherent
  disposition-versus-count combination and the manifest refusing a dropped or
  duplicated family.
- Restate the coverage module docstring around the three axes it now carries, so
  the family question is not read as the evidence-tier question.
- Add the family coverage test module: enrolment completeness with its planted
  bite proof and anti-tautology pairing, all three dispositions, the row and
  manifest refusals, the declaration surface through the real loader, and a
  corpus-wide projection gate.

## Outcome

An empty schema family is no longer ambiguous. Before this row a revision with no
formulas and a revision whose modelo computes nothing were the same observation -
a zero - and the second reading is the one that lets an unbuilt revision present
as complete. The manifest now reports one row per family for every revision, so
an unbuilt family is a `blocked_pending_evidence` row a reader can count rather
than an absence a reader has to notice.

The enrolment is deliberately two mechanisms rather than one. Marking alone
catches a rename and never an addition, which is the failure the manifest-only
marker was already chosen to avoid; deriving from the annotation alone would
enrol collections nobody meant as families. Requiring the declared set to equal
the shape-derived set makes the enrolment exhaustive AND deliberate, and it is
the shape-derived half that a contributor cannot forget, because appearing in it
is a consequence of the type they wrote rather than a step they took.

The family marker is deliberately not a subclass of the manifest-only marker,
which is the opposite of the choice the governance stamp made. That was right
there because placement is genuinely shared; here the two questions are
unrelated - where a field may be written versus whether its emptiness is a
coverage claim - and the live schema bears it out: the two sets are disjoint, 21
families against 8 manifest-only scalars with no member in common. A hierarchy
would have asserted a relationship that does not exist.

`not_applicable` costs a cited claim rather than an allowlist entry. An allowlist
records that somebody wanted the check quiet; a declaration records what they
claim and what backs it, which is the thing a later reviewer can disagree with.
The registry refuses one that names no family, and refuses one that disclaims a
family the revision has already populated.

Measured across the committed corpus: 97 revisions, 21 families each, 2,037 rows
- 901 populated, 1,136 blocked pending evidence, and zero declared inapplicable,
because nothing declares one yet. No revision is fully resolved. That is the
honest opening worklist this row exists to produce, and it is a derived number
rather than a maintained one.

## Notes

This Step consumed NO entry from the plan's Deletion inventory. It derives and
projects; nothing was deleted and no surface was superseded.

Two of the coverage module's known defects were deliberately left untouched and
not built upon, since they are enrolled on later rows: the single-representative-
year assessment and the by-construction-empty filing-gap surface. The manifest
avoids both by construction rather than by care - it reads one revision, builds
no snapshot, consults no review state and chooses no representative year - which
is also why it reports on all 97 revisions where the tier audit reports on the
empty set of review-eligible ones.

How the new axis relates to the two already there, since all three sound like
completeness: evidence tiers answer what BACKS the content, authority scope
answers which PROJECTION the ledger came from, and family dispositions answer
whether the content is THERE. A populated family with no legal authority and an
empty family with impeccable authority are different findings, and the
vocabularies are checked to share no token.

The disposition enum went to core rather than staying a module-local `Literal`
beside its siblings, which is a small deviation from this row's declared scope.
The architecture rule requires a closed value set to be a StrEnum in core, and
the ladder row will consume it from a different module.

`completeness_manifest` is a singleton rather than a collection and is therefore
outside the enrolled families, as is any required value object. The coverage
question is about an EMPTY collection and neither shape can be empty in that
sense. This is a stated boundary rather than an oversight, and whether the
singleton needs its own disposition is a question for the ladder row.

The enrolment check does not depend on registry load state, so its warm-regime
proof is a demonstration rather than a distinction: with the load settled and
two further warm loads measured at 0.91 of the settling load, the check still
reds on the planted field, clears when the marker is added, and the manifest
still projects. Nothing in it reads a cache.

The projection has no production caller yet - the ladder row and the enforcement
wave are its consumers. Its executor today is the corpus-wide gate, added
deliberately because this module is imported by every registry load and executed
by almost nothing, and anything added here without a caller or a gate inherits
that invisibility.

Re-verified 2026-08-14 against the current working tree: the bundled corpus now
loads cleanly through `load_registry_tree` and the corpus-wide gate test
(`test_every_bundled_revision_projects_a_coherent_manifest`) passes. A note
recorded here earlier claimed the corpus did not currently load because of a
campaign-owned authoring tree with an empty required fragment directory; that
blocker is no longer reproducible and is corrected rather than carried forward
uncritically. The corpus figures above (97 revisions, 2,037 rows, 901 populated,
1,136 blocked pending evidence, 0 declared inapplicable) were independently
re-derived against the live bundled tree for this correction and match the
originally recorded figures exactly.
