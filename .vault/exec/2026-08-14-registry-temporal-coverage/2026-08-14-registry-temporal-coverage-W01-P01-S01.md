---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1a1a380393267b097b2ae250a0aed46ce77709f5a91897e88e9152a4f9b0b5e8'
step_id: 'S01'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Add the RegistryAuthorityGrade enum to core and an optional manifest-only authority_grade on ModeloRevision with a fail-closed ungraded default, hydrated at the loader boundary and refused in any fragment, proving a fragment-declared grade reds registry load while the untouched corpus loads green

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/domain/calculations/registry/_schema.py`
- `src/cadrumo/domain/calculations/registry/_loader.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add the `RegistryAuthorityGrade` StrEnum to core in a new `_authority_grade.py`
  module carrying `applicability`, `calculation` and `filing`, alongside the
  `UNDECLARED_REGISTRY_AUTHORITY_GRADE` companion naming the fail-closed floor an
  undeclared grade reads as, and publish both on the core facade.
- Add the `RegistryAuthorityGradeField` coercion alias to the registry schema base,
  mirroring the existing `RevisionReviewStatusField` hop, so registry TOML stays
  free-form and the token hydrates into the typed member before strict validation.
- Declare an optional `authority_grade` on `ModeloRevision`, marked manifest-only
  through the existing field marker so it enrols itself in the derived placement
  set without any second list being edited, and deliberately NOT marked as part of
  the governance stamp vocabulary.
- Add the `is_graded` and `effective_authority_grade` readers so the fail-closed
  reading of absence is one decision rather than an `or` at each consumer, and so an
  ungraded revision stays distinguishable from one declared at the same floor.
- Reorder the loader's two fragment refusals so the manifest-only refusal runs
  before the broader owned-section refusal, restoring reachability of the
  marker-derived placement gate.
- Add a dedicated test module driving the real directory loader over real on-disk
  TOML for hydration, the fail-closed floor, the declared-versus-undeclared
  distinction, the placement refusal with its differential control, a planted-grade
  bite proof on a copy of a real shipped revision, the vocabulary separation from
  the governance stamp, and a bundled-corpus property.
- Extend the existing manifest-only placement gate's derived-set fixtures with the
  new field, which the parametrized refusal picks up automatically.

## Outcome

The grade axis is typed and declarable, and absence is safe. A revision declaring
`authority_grade` in its own `revision.toml` hydrates the enum member; an unknown
token refuses at registry load naming the vocabulary; an undeclared grade reads as
the lowest rung, so an ungraded corpus confers scheduling reach and nothing more.
The field is optional by design rather than by convenience: a required
manifest-only field could not have landed without one atomic edit across every
bundled manifest, including two authoring trees another in-flight campaign owns,
and defaulting the field to the floor instead of leaving it optional would have
made every revision read as explicitly graded the day the field shipped.

Placement is enforced by the same marker mechanism the governance scalars use, so
the enrolment is the marker rather than a hand-kept list — the shape that catches
an addition, not only a rename. The grade carries the placement guarantee without
joining the stamp vocabulary, which keeps an authority claim from being read or
emitted as declared review provenance by the conformance stamp writer.

That mechanism was found shadowed at the head of the shared tree: a broader
refusal added earlier the same day rejected every foreign key in a section
fragment before the manifest-only refusal could run, since no fragment folder is
named after a manifest-only field. The specific refusal had become unreachable and
its shipped gate was red. Restoring the ordering fixes both, and loses nothing:
every key the broader refusal used to catch is still caught by it.

Two proofs back the placement claim. A synthetic fragment carrying the grade
refuses while the identical text in the manifest loads, which separates placement
from content. Because a proof over synthetic input cannot catch a refusal that
never reaches real shapes, a copy of a real bundled fragmented modelo is also
planted with the grade in a real section fragment, observed refusing, and restored
to loading. The untouched bundled corpus loads green with every revision resolving
a reach — asserted as a property over whatever the corpus holds rather than
against a revision tally, which would encode today's corpus and detect nothing
tomorrow.

## Notes

This Step consumed NO entry from the plan's Deletion inventory. It is purely
additive: nothing was deleted, no surface was superseded, and no replacement was
landed that would leave an old implementation behind.

No grade was promoted anywhere, no filing year was declared supported, and no
review attestation was written. No bundled manifest declares a grade after this
Step; every shipped revision is ungraded and reads the fail-closed floor.

Neither campaign-owned authoring tree was touched.

The loader ordering repair is outside the additive shape of the Step. It was taken
because the Step's own verification criterion is that the marker mechanism refuses
a fragment-declared grade, and shipping a marker whose refusal cannot execute
would have landed a gate that reports clean because nothing reaches it. It was
reported to the campaign lead as a finding in the same message as this record.

The registry test suite carries substantial redness at the head of this shared
tree that predates this Step and belongs to concurrent peer work; the pre-change
and post-change failure sets were captured sequentially and compared rather than
read as an absolute result. The type checker reports two pre-existing diagnostics
in the loader's fingerprint-collector binding, untouched here.
