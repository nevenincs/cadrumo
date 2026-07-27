---
tags:
  - '#audit'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
  - "[[2026-07-27-conformance-cli-adr]]"
---

# `conformance-cli` audit: `governance stamp and classification coherence`

## Scope

Mandatory code review of two landed work packages, verified at HEAD `0b3d198022`.
Package A is Phase P01, the declared per-revision governance stamp: the review-status
enum in `src/cadrumo/core/_revision_review.py`, the governance scalars and coherence
validator in `registry/_schema.py` and `_schema_base.py`, the placement refusal in
`registry/_loader.py`, the compiled-cache key enrolment in `registry/_compiled_cache.py`,
and `registry/tests/test_governance_stamp.py` (commits `8b0194f88e`, `b3986f43de`,
`f1a1bacaed`, `ee6c524baf`, `5ec1f98f1a`, `01c4569996`). Package B is Steps S09 and S11,
`registry/_classification_coherence.py` and its test module (commits `bbc05fcdef`,
`1758aa9671`, `70e13633b3`, `c996b4e309`, `2fc5ceb0d2`).

Verification actually run by the reviewer, not inferred: six adversarial placement probes
against the real directory loader, ten token and coercion probes, three in-process
production mutations of Package A with counts compared against the exec records, four
detection-power mutations of Package B, a parsed sweep of all 15,945 bundled section
fragments, an instrumented unpickler walk of the compiled registry payload, the live
classification census, the full registry suite at 3064 passed, `ruff check` on all eight
files, the apidocs stub-drift check, and the core-struct docstring gate.

The two high findings of the first review round were re-checked and hold: the fichero-BOE
required set now has an independent registry-grounded oracle, and the dev-path literal
detector fires on the root-anchored join form.

Verdict: PASS. No critical or high findings. The stamp survived genuine adversarial
effort. The residual findings are a pre-existing cache-enrolment gap the campaign
touched, one hole in the signoff claim, and low-severity drift hazards.

## Findings

### whitespace-reviewer-satisfies-the-signoff-claim | medium | A revision can declare operator signoff with a reviewer field containing only spaces

CONFIRMED, reproduced against the real loader. `reviewed_by` is constrained with
`min_length=1`, and that counts whitespace, so a revision declaring `operator_reviewed`
with a three-space reviewer loads clean and reports as operator-signed-off. A tab is
equally accepted, as is a whitespace-only `engineered_by`. The validator's own docstring
states its purpose as refusing an unfalsifiable claim so that a claimed review always
names its reviewer; a blank reviewer names nobody, so the claim is exactly as
unfalsifiable as the one the validator exists to refuse.

Failure scenario: a stamping-campaign agent scripts the write and emits an
empty-but-present reviewer, a trivially plausible template bug or a deliberate shortcut.
The revision leaves the pending-review backlog, the conformance report renders it green,
and nothing reds, because the bundled-tree invariant asserts only that the field is not
null. The house precedent for the fix already exists in the same package, where citation
required-text entries are rejected on an empty strip.

### embedded-core-type-enrolment-not-general | medium | The cache fix closed one instance of a class of bug, and ten sibling types remain unhashed

CONFIRMED, reproduced by empirical unpickling. The claim behind the cache enrolment
commit is exactly true: the key hashes registry-package sources plus a hand-listed
embedded-core-symbol tuple, the new review-status enum was in neither, and enrolling it
brings its defining file into the key. That half is right and is correctly written as a
public-facade pair.

The mechanism is not general. An instrumented unpickler walk over the real compiled
payload enumerated every first-party class the stream reconstructs from outside the
registry package. The four already-enrolled entries all appear, which validates the probe
as a positive control. Ten more appear that are not hashed, including the core modelo
enum, the export field-kind enum, and eight IVA-domain enums. The core modelo enum is
indistinguishable in kind from the one this campaign enrolled.

The guard test is one-directional: it asserts every listed symbol resolves to a real file,
never that every embedded type is listed. So the module's own stated policy, to extend the
tuple when a new core type becomes embedded, is enforced by author memory alone, which is
precisely how the review-status enum was missed for two Steps.

Failure scenario: an author changes the shape of an embedded pydantic model outside the
registry package, adding a field with a default. No registry-package file changes, so the
key stands still and a pre-change pickle is served whose objects lack the field, and
downstream reads the default instead of the authored value. For the ten unenrolled types
the practical risk is lower because all ten are string enums, where a changed value fails
loudly at unpickle rather than silently, but that is equally true of the enum this
campaign enrolled, so its own entry and the ten it left out sit in the same risk class.

### degraded-mode-label-rides-the-container-not-the-row | low | The record and the code state different rules about where the unvalidated label lives

The ADR rules that a degraded read stamps every emitted row as unvalidated, and names an
unlabelled degraded read as the thing that must never be mistaken for authority. In the
classification fold the validated flag is declared once on the audit container; the row
and finding models carry no such field, and the bundled entry point is permanently
unvalidated, so today every bundled read is degraded.

Failure scenario, prospective and cheap to prevent: a renderer or JSON payload serialises
the findings property into a row list, or a later composer merges these findings with
findings from a validated source. At that point the rows are indistinguishable and the
label is gone. Either carry the flag onto the row and finding models, or amend the ADR to
the container-level design, but decide it rather than leaving record and code divergent.

### placement-set-does-not-auto-enroll-a-new-governance-field | low | The anti-rot test catches a rename but not an addition

The governance field set is a hand-written frozenset of four strings and is the sole input
to the loader's placement refusal. The existing test asserts the model's field names are a
superset of the frozenset, which genuinely catches a rename. It cannot catch an addition: a
fifth governance scalar added to the model but not to the frozenset is silently
fragment-placeable, which is the exact laundering vector the placement refusal closed for
the first four. Since governance-ness is not derivable from the annotation, mark the fields
at their declaration and derive the frozenset from the marker, so enrolment becomes a
property of the declaration rather than a second list.

### finding-detail-bound-duplicated-and-the-clamp-untested | low | The clamp is proven load-bearing, but nothing shipped exercises it and its bound is a copied literal

The clamp claim holds under direct verification. Neutering the sampler alone against a
modelo with 200 bound casillas still builds, producing a detail at the bound ending in an
ellipsis; neutering the clamp as well raises. So the clamp is load-bearing, not decorative,
exactly as its exec record says. The overflow was real: the live tree's Modelo 100 row
carries 1,150 invariant blockers, and joining them would have overflowed the bound by two
orders of magnitude.

Two residual hazards. The maximum-length constant is a hand-copied literal of the field
constraint it mirrors, and nothing binds them, so lowering the field bound leaves the clamp
permissive. And no shipped test reaches the clamp: the many-blockers test exercises the
sampler, whose forty blockers produce a detail well inside the bound, so the truncation
branch has zero coverage.

### refusal-tests-key-on-error-prose | low | Two placement assertions match on a substring generic enough to pass on a different refusal

A placement test matches on the manifest filename, which several unrelated loader refusals
also mention, including the missing-manifest error and the inline-section refusal. The test
is safe today because its fixture cannot reach those paths, but the discriminator is the
message rather than the mechanism. The paired differential test matches the full sentence
and is sound; strengthening the parametrized one to the same phrase costs nothing.

### compiled-cache-read-bypasses-the-stamp-validator | low | Unpickling does not re-run the coherence validator, so the cache is an unvalidated re-entry point

CONFIRMED, and it materially affected the reviewer's own measurements. A pickle round trip
restores an incoherent stamp without raising, because pydantic pickles the instance
dictionary and does not revalidate. During the first default-flip mutation run only two
tests failed instead of the recorded three, precisely because the bundled-tree test was
served a pre-mutation pickle; with a fresh cache directory it failed as recorded.

This is not a practical laundering vector, because writing the cache pickle already implies
arbitrary code execution on read, a far larger pre-existing trust boundary, and the real
source edit that would flip the default also re-keys the loader fingerprint. It is recorded
because it means the fail-closed guarantee is enforced at compile time only, and any future
consumer reasoning that a loaded snapshot cannot carry an incoherent stamp is relying on
the cache key rather than on the validator.

### future-dated-review | low | The review date has no upper bound

A revision declaring operator signoff dated in the year 3999 loads clean. The revision model
already carries a window validator for its validity dates, so date coherence is an
established concern here. A signoff dated in the future is not a signoff. Low because it is
inert until something reports on stamp dates.

## Recommendations

Reject blank reviewer and engineer values with a strip-based field validator, following the
citation precedent already in the same package, and tighten the bundled-tree invariant from
not-null to non-blank. A stamp that claims operator signoff while naming nobody defeats the
one guarantee the validator advertises. Bound the review date so a signoff cannot be dated
in the future. Tracked as Step S33.

Bind the two duplicated constants to their declarations: derive the governance field set
from a marker on the field declarations so a fifth scalar enrols itself into the placement
refusal, and derive the detail bound from the field it mirrors, adding the one missing case
whose single blocker exceeds it so the truncation branch is proven. Tracked as Steps S34
and S36.

Make the embedded-core-type enrolment derivable rather than remembered: walk the compiled
models' annotations for first-party types defined outside the registry package and either
hash the derived set or assert it is a subset of the hand list. Ten types including the core
modelo enum are unenrolled today; the enrolment this campaign added is correct but closes
one instance of an open class. Tracked as Step S35.

Rule the degraded-mode labelling granularity rather than leaving record and code divergent,
either carrying the validated flag onto the row and finding models as the ADR text says or
amending the ADR to the container-level design. This belongs in the ADR amendment already
tracked as Step S32, alongside the boundary-wording correction the previous round raised.

Open a Step for the residual fragment-placement gap the narrow scope leaves: legal
references, the applicability order, and the validity end date are legally load-bearing and
can still be declared in any of 15,945 fragment files, which is the same readability hazard
the governance refusal closed. That is not this campaign's debt, but it is now the only
remaining instance of a pattern this campaign proved worth closing.

## Verifications that came back clean

The placement refusal is real, complete, and correctly scoped. Six adversarial probes: a
stamp in a section fragment is refused; a stamp in a new fragment subdirectory the loader
walks is refused; a second manifest planted deeper in the tree is refused, being treated as
a section fragment; a stamp at modelo-manifest level is refused by the forbid-extra config;
a stamp in a locale file is inert and leaves the revision pending, which is the fail-closed
direction; and the manifest home still accepts byte-identical text. Every merge path funnels
through one fragment-field merge function, so there is no bypass.

The narrow scope is justified against the real tree. A parse of all 15,945 bundled section
fragments found exactly one non-section scalar anywhere, a period selector in a Modelo 303
fragment, and zero governance keys anywhere. The executor's claim is exact, and the S03
record's honest correction of its own first pattern-matched sweep, which falsely reported
thousands of hits from nested casilla keys, is why the number is right.

Vocabulary closure holds. Refused: empty token, integer token, uppercase token, unknown
token, misspelled key, empty reviewer, empty engineer, a string-typed date, and both
incoherence directions in both layouts. The coercion hop correctly mirrors an existing
precedent rather than inventing a pattern.

All three mutation claims in the P01 records reproduce exactly: flipping the default gives
three failures, neutering the placement gate five, short-circuiting the coherence validator
six. The validator mutation required rebuilding the parent definition as well, because the
parent's core schema embeds a snapshot of the child's.

Package B's numbers are exact: 73 modelos, 90 revisions, all pending review, zero engineers
named; 11 informative by calculation class, 17 by tax domain, intersection 2, 24 diverging,
split 9 and 15 as recorded; none of the 24 carries a blocker, so the no-divergence-is-forced
claim is true; all five tracked axes unused. The fold reports and never canonicalizes or
raises. Its tests hold behaviour rather than the census: the live-tree assertions are
if-and-only-if invariants with independently recomputed denominators, so a registry edit
reconciling an axis pair passes rather than reds. Four detection mutations all kill real
assertions.

Project rules hold in both packages: no untyped mappings at any boundary, closed sets as
core string enums with derived companion sets, cross-package imports through public facades,
no mocks or skips, real loader over real on-disk TOML, and the new fields
optional-with-fail-closed-default from birth with no migration branch.

Record honesty: no overclaims found. Every sampled claim reproduced. Three records go
further than required and volunteer things that weaken their own Step: S03 states plainly
that three of its four Step-row obligations were already satisfied before any edit, and
records that its first leakage sweep was wrong and why a pattern match cannot answer that
question; S04 records a line-ending near-miss where a content-level diff read clean while
the working tree carried a fully rewritten file, caught only by comparing raw bytes against
the committed object. The discovery waiver is named in every record rather than omitted.

No peer feature index was damaged. No campaign commit touched any index other than this
feature's own. The indexes modified in the working tree carry zero deletions that are not a
date stamp; every other change is an addition.
