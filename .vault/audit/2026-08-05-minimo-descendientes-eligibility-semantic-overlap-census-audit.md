---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:f43cde95ba8a9361a1209303b18d21a83a2743a4269aadd2d376a88a5c323af0'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# `minimo-descendientes-eligibility` audit: `Semantic-overlap census: one confirmed duplicate, six cleared, and the drift source`

## Scope

A deliberate axis-seven semantic-overlap pass over the descendant, maternidad and
registry-parameter surfaces, run under an operator directive to admit no drift or
semantic fragmentation.

It is recorded because the campaign had never run one. Every canonicalisation before
this was REACTIVE — found while doing something else — so the duplication set had
never been enumerated independently of the work, and no completeness claim over it
was available. The largest find of the campaign, a second aggregation loop summing
the same quantity under its own inline age test, was caught only because a new field
prompted the question "what consumes this?" That is luck, and a census is the
non-luck version.

Method: search by MEANING for where each concept lives, then confirm exact sites
with a fixed-string pass. Concepts, not symbol names, because the guardia
duplication shared no identifier with its canonical twin and no name-based search
could have found it.

Cleared results are recorded at equal weight to findings. A near-neighbour proven
NOT to be a duplicate yields a precedent to cite rather than a parallel authority to
defend, and only opening the neighbour produces that.

## Findings

### legal-parameter-reader-duplicated | medium | One helper implemented twice in two domains, identical but for the error it raises

The helper that reads one legal-parameter value out of the validated registry mapping
exists twice, once in the fincas domain and once in the iva domain. The bodies are the
same three statements: fetch the attribute, reject a non-string, return it. They differ
only in the domain error type and the article named in the message.

Bounded precisely rather than assumed: a fixed-string sweep for the exact attribute
read returns exactly two sites tree-wide, and only those two domains load legal
parameters at all. It is a pair, not a family, so the canonical form is one reader
owned by the package that already owns the parameter loading, with each domain wrapping
the refusal into its own error rather than restating the read.

This sits outside the feature that found it. Recorded here rather than patched into
this campaign's plan, because a cross-domain move belongs to whoever owns those two
domains.

### drift-source-is-the-broad-checkpoint-commit | high | Four commits took working-tree snapshots older than HEAD and silently reverted what landed between

The most consequential finding is not a duplicate. Four broad commits titled as
checkpoints, refreshes or WIP snapshots each captured a working-tree state older than
HEAD, silently reverting whatever had landed in the interval.

Traced consequences, each independently measured: a constant deleted from a test-support
module while its consumer's import was left standing, which broke the whole-tree collect
gate at HEAD for every agent; thirty-eight staged deletions armed against another
campaign's decision records, all of which existed on disk and at HEAD, so any bare commit
would have destroyed them; an agent's execution record swept into an unrelated commit;
another agent's Step swept mid-edit so its author committed only the residue; two plan
rows reverted minutes after landing; and a type erasure in a campaign test.

The shape is one mechanism, not six incidents. A commit that names a pathspec takes the
WORKING TREE for those paths, so a snapshot assembled before a peer landed will revert
that peer on the way in. The only check that sees it runs AFTER the commit, because the
pre-commit check cannot observe a landing in the same instant. Two separate agents hit
the identical shape on this campaign within hours and both caught it the same way, which
is the strongest available evidence that the discipline works and the pre-check alone
does not.

### one-convention-moving-in-two-directions | high | Two commits hours apart moved the same convention opposite ways on one surface

One commit replaced a typed diagnostic tuple with a tuple of bare object, deleted the
typed import, replaced explicit fixture parameters with a kwargs splat, and added six
type-ignore directives. A sibling commit on the same surface, hours apart, removed
exactly that kwargs-splat pattern from a neighbouring module.

The divergence is the finding, more than either commit alone. A convention being
enforced and abandoned simultaneously is drift whichever direction turns out to be
right, and it leaves the next author two contradictory precedents to cite.

The mechanism will recur: this Phase widened a core record twice, which breaks fixtures
that name their fields explicitly. Erasing types makes a file COMPILE; updating fixtures
makes it CORRECT. The first is mechanical, the second requires reading what the test
asserts — so under time pressure the sweep wins, and it wins silently because the suite
stays green either way.

### locale-orthography-has-no-gate | medium | Accent-stripped prose satisfies both locale gates

Operator help shipped ASCII-stripped in three locales. In a Spanish filing product this
is not cosmetic: the text read "menor de 3 anos", and that is not the word for years.

Neither gate catches it. The parity gate checks that every key exists in every
catalogue; the translation-honesty ratchet checks that a value is not byte-identical to
English. An accent-stripped Spanish sentence satisfies both comfortably.

The guarding test made it worse: its marker for one locale was chosen against the
stripped prose, so it silently PINNED the degradation and correcting the language failed
the test. The gap is recorded rather than closed, because inventing a gate under time
pressure is precisely how that marker came to exist.

### cleared-with-evidence | low | Six near-neighbours proven sound, recorded so they are not reopened

Month arithmetic has one canonical helper and both Art. 81.1 limbs call it; the
recargo-period calculation in the deadlines domain is a different concept.

Decimal coercion has one canonical home and the two production wrappers genuinely
delegate to it, each adding only its own domain gate. The two remaining bare
constructions sit on the persisted-read path where values are canonical strings this
application wrote, and every operator-input path routes through the canonical parser.

Registry snapshot resolution and registry parameter resolution answer different
questions and are correctly separate.

The casilla-id validator has one home in the core layer.

The two input-casilla-id validators are a genuine type split, not a duplicate: one takes
a revision and rejects undeclared casillas, the other strips whitespace from text leaves.
Different contracts.

The notice type has one canonical declaration. Ninety-five direct constructions across
thirty-eight files are USAGE of one type, not duplication of a concept, and counting them
as a finding would have inflated the census.

## Recommendations

Re-home the duplicated legal-parameter reader into the package that owns parameter
loading, with each domain wrapping the refusal rather than restating the read. It is a
cross-domain move and belongs to those domains' owners.

Treat the broad checkpoint commit as the campaign's principal structural hazard rather
than as an occasional nuisance. Every instance traced here was avoidable by naming an
explicit pathspec and verifying the landed set afterwards. Nothing in the tooling
prevents it.

Do not add a locale-orthography gate reactively. The failure it would guard is real, but
the pinned marker in this same area shows what happens when a guard is written against
whatever text happens to be present. Decide the check first, then write it.

Run this census on a cadence rather than once. It found one duplicate the campaign had
not seen and cleared six candidates that would otherwise have stayed open questions; both
halves decay as the tree moves.
