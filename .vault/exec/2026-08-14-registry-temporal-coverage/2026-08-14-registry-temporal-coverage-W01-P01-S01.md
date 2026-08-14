---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1f4b64200a06bde0c3abaed0d664842d1dcd2c1237d4f7e47d1151d276d2bbf6'
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
to loading. That second proof was additionally run by hand against the committed
corpus outside the working tree, on Modelo 036 revision `2025-02-03-y-siguientes`,
planting the grade in a real administrative fragment: the copy loads ungraded,
the planted copy refuses with the instruction naming `revision.toml`, and the
copy with the plant removed loads ungraded again. Nothing under the source tree
was mutated to obtain it, so no peer sweep could capture the plant and a crashed
run would leave no residue.

The committed corpus loads green at 73 modelos and 97 revisions, none of them
graded, every one reading the fail-closed floor. Those figures are recorded here
as measurement; the shipped test asserts the property instead — that every
revision resolves a reach, declared where declared and the floor where not —
because a revision tally as a pass condition would encode today's corpus and
stop detecting anything the moment the transcription step populates it.

The refusal wording for this branch was corrected in passing. It read "it is
legally load-bearing for the whole revision", which was true of the three legal
scalars that were previously its only members and is not true of a grade; it now
reads "it is a claim about the whole revision", which is true of all four.

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

The broader owned-section refusal the reorder moved behind is itself covered, and
an earlier claim in this campaign's reporting that it shipped untested was wrong.
It carries eighteen tests in the loader topology suite, one of which plants a
section name in the wrong section folder. That test matches on the folder and key
names rather than on the refusal sentence, which is why a search for the sentence
missed it; the search was the defective instrument, not the peer's change. The
reorder leaves that suite green, because the key it plants is a section name and
never a manifest-only field, so the two refusals do not compete for it.

The registry test suite carries substantial redness at the head of this shared
tree that predates this Step, is a separately recorded condition with its own
decision and plan, and belongs to concurrent peer work. The pre-change and
post-change failure sets were therefore captured sequentially and compared as a
delta rather than read as an absolute result: fifteen fixed, two new, and both new
ones traced to peer edits that landed between the two runs. The type checker
reports two pre-existing diagnostics in the loader's fingerprint-collector
binding, untouched here.

While this record was being finalised the bundled corpus stopped loading
altogether, on a malformed administrative fragment filename and then a duplicate
fragment prefix inside a campaign-owned authoring tree being written concurrently.
Three tests that assert the shipped corpus loads go red on it, only one of which
is this Step's; the other two predate it. The corpus measurements above were
therefore taken against the committed tree exported read-only outside the working
copy, which is the honest subject of the claim in any case — an assertion about
the shipped corpus should not be answered by a peer's half-written edit.
