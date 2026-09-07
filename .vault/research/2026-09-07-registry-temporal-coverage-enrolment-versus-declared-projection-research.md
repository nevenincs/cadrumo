---
tags:
  - '#research'
  - '#registry-temporal-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b800d5f37e49d896262308e48941199f1f328b0044e9765917e3c406a6766d3d'
related: []
---

# `registry-temporal-coverage` research: `registry temporal coverage`

## Question

Is `m390-2022` failing alone a fact about that revision, or an artefact of what a
gate happens to enrol? And if the latter, how widely does the pattern hold?

## Measured answer

Three counts over the same tree, taken the same day:

    declared revisions in the registry            128 across 58 modelos
    projected by registry_conformance             128 across 58 modelos   100%
    enrolled by _GENERATED_TREES                   29 across 14 modelos    23%

`m390-2022` is not special. Five modelo 390 revisions exist (2021-2025), NONE has
a published export tree, and exactly one is enrolled. The gate iterates one row,
so one row reds. The number that looked like a fact about 2022 was a fact about
the enrolment list.

## Shape of the defect

A gate whose subject is a hand-written list of `(modelo, revision)` pairs answers
a different question from the one its name implies. It reports on what someone
remembered to enrol, not on the registry's temporal coverage. Three consequences,
all present today:

* **A single red reads as revision-specific.** It took an operator challenge -
  "this fact does not exist, how could only one revision fail" - to expose that
  the singularity came from the list, not the data.
* **Silence is indistinguishable from absence.** 44 of 58 modelos have zero
  enrolled revisions. Their export trees are unasserted and the suite is green
  about them.
* **New revisions are unprotected by default.** Adding `390/2026` extends
  declared coverage without extending any gate. Nothing fails to say so.

Partial enrolment is the most dangerous shape, because the modelo appears
covered: 390 (1 of 5), 184 (2 of 6), 322 (3 of 4), 200 (1 of 2), 185 (1 of 2).

## Why this is a conformance gap, not a missing capability

The corrective standard already exists in this repository and is documented in
its own words. `src/cadrumo/tests/registry_conformance.py` composes "exactly one
RevisionConformanceRow per modelo revision in the loaded tree", and says why a
per-modelo scalar cannot stand for a range:

    Absence is not zero. ... an axis that was not measured is None here, never a
    fabricated zero or a fabricated default.

Measured, it emits 128 rows over 58 modelos - exactly the declared coverage. Both
idioms therefore coexist in the same subsystem: some gates enumerate declared
revisions (applicability, authority, the conformance composer, continuity
analysis), others carry literal revision lists (the generated-export-tree gate
and its neighbours).

The hand-enrolled idiom silently under-declares what is checked, which is the
condition `no-silent-under-declaration` forbids elsewhere in this codebase:
missing, unsupported and proven-absent are distinct states and must not collapse
into a green suite.

## What a correct gate looks like

The registry is structurally uniform per revision: a schema check that holds for
`390/2022` has no principled reason to skip `390/2023`. So the enrolment list
should be DERIVED from the declared tree, with any exclusion carried as an
explicit, reasoned per-item pin rather than as an omission - the same shape the
export-tree gate already uses for `_SOURCE_DEFECTS` and `_CHECK_MODE_PENDING`,
where a defect is pinned to a source sha and goes dormant when the source is
reissued.

An omission says nothing. A pin says why, and fails when its reason expires.

## Prior art — this is NOT a new problem class

Semantic discovery over the vault found the class already decided and planned.

**Governing decision.** `2026-08-28-registry-narrow-mechanism-widening-adr`
(accepted): *"A narrow registry mechanism widens only by an explicit,
evidence-carrying declaration naming its subject. No mechanism widens by relaxing
a matcher, a shape test, or a predicate."* Its plan is CLOSED (6/6). That ADR also
records the hazard directly: one of its three widenings was attempted by loosening
a matcher and had to be reverted.

**Existing planned step.** `W01.P09.S32` in
`2026-08-14-registry-temporal-coverage-plan` already states the standard, names the
exemplar that satisfies it -
`test_revision_span_matches_published_designs.py::test_no_revision_spans_a_design_relayout`,
"which iterates every modelo and revision in the loaded registry inside one test
and derives epochs dynamically" - and carries its own census: of 3,515 Python test
files, 36 are pegged by a year token in the filename, 33 pinned to an artefact
sha256, and only 38 percent of those are parametrized. It is BLOCKED on
export-fragment S84.

**Adjacent, already counted.** `2026-08-15-registry-temporal-coverage-audit`
finding `how-much-can-prove-coverage`: 12 of 97 declared revisions corpus-proven
clean at that date (97 then, 128 now).

## What this research actually adds

A DETECTION GAP in the existing census, not a new class.

S32 counts files PEGGED BY A YEAR TOKEN IN THE FILENAME. `_GENERATED_TREES` is a
literal `(modelo, revision)` list INSIDE ONE FILE -
`dev/registry/tests/test_generated_export_trees.py` - whose name carries no year
token. The existing metric cannot see it, and it is the larger instance:

    29 of 128 declared revisions enrolled          23 percent
    44 of 58 modelos with ZERO enrolled revisions

So the census should count IN-FILE ENROLMENT LISTS as well as year-pegged
filenames. Both are the same defect - a hardcoded temporal subject standing in for
declared coverage - and only one is currently measured.

## How this folds into the plan

This grounds an ADDITION to `W01.P09.S32`'s scope, not a new feature. The remedy
is already fixed by the narrow-mechanism ADR: derive the enrolled set from the
declared tree, and carry every exclusion as an explicit reasoned pin - the shape
`_SOURCE_DEFECTS` and `_CHECK_MODE_PENDING` already use in that same gate, where a
pin names its subject, cites its sha, and goes dormant when the source is
reissued. An omission says nothing; a pin says why and expires.

NOT DONE HERE: the plan is another writer's active surface (99 open steps) and
S32 is blocked on S84. Proposing the step edit is the operator's call.

## Open questions for the ADR

1. Which gates must project, and which legitimately target one revision (a
   revision-specific adjudication, for instance)?
2. Where does the projection live so both the pipeline CLI and the test harness
   read one home? The `_SOURCE_DEFECTS` split - mechanism in the pipeline, data
   in a test module - is the same class of problem and is currently blocking
   m390-2022 publication.
3. What is the expected coverage denominator: every declared revision, or every
   revision within a supported temporal window? The registry declares revisions
   as far back as 2003; a gate that must pass for all 128 is a different contract
   from one that must pass for the currently filable range.

Question 3 is the one that needs a decision before any code moves: it sets what
"complete" means for every gate that follows.
