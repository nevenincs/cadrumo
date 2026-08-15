---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:62d944f411eef10a3a6694f30f9f9134049d57e532a0314c72b817cba8fc29c6'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
  - '[[2026-08-01-wrong-surface-gates-audit]]'
---

# `registry-campaign-sequencing` audit: `Preflight test vacuity: how a passing test proves nothing`

## Scope

A defect class found while repairing fixtures in the development registry test
tree, then deliberately hunted across the registry domain suite to establish
whether it was systemic. This records the class, the discriminator that
identifies it, the structural precondition that predicts where it can occur, and
the measured result of the sweep — including a null result and a false positive
produced by the first version of the detector.

The class is not specific to the registry. It applies wherever a test asserts on
an exception type.

## Findings

### preflight-vacuity | high | A test asserting an exception type passes on any matching exception, including one raised before its own subject

A test of the shape "inject a defect, assert the operation refuses" passes when
*any* matching exception escapes. It is vacuous when the exception came from a
gate the code crosses *before* reaching the injected defect. The test is then
green, permanently, while proving nothing about the behaviour it is named for —
and it reports as coverage.

Six cases were found in one parametrised test of the generated export-tree check
path. Each injected a different defect — a semantic-map mutation, an output-byte
mutation, two provenance-manifest mutations, a missing output, an extra output —
and every one was caught by the same unrelated refusal: the registry's
filing-grade review gate, raised partway through the operation because the test
corpus carried an unattested legal reference. None of the six ever reached the
comparison it existed to exercise. Five sibling cases in the same parametrisation
were genuine, which is what made the group look healthy.

The failure is worse than an absent test. An absent test is visible; this one
occupies the name of the check, so nobody writes the real one.

### vacuity-discriminator | high | Frequency does not identify the class; a changing defect subject under an unchanging message does

The first detector clustered refusals by message and flagged any message caught
by several distinct tests. That is wrong, and it produced a 32-cluster inventory
that was almost entirely noise. Every well-formed parametrised negative test
shares one message across its cases: a projector fed `' 2026'`, `'+2026'` and
`'2026.0'` should refuse all three identically, and that identity is correctness,
not a smell.

The discriminator is the relationship between what varies and what does not:

- **Legitimate.** The parametrisation varies the *input* within a single defect
  class, and one shared message is the correct outcome.
- **Vacuous.** The parametrisation varies the *subject* — different kinds of
  defect, in different components — and still yields one identical message. The
  shared message cannot be each case's own refusal, because the cases do not
  share a cause.

The tell is legible in the parametrisation identifiers. Cases named for distinct
subjects that all report one refusal are the signature; cases named for variant
inputs that all report one refusal are healthy.

### vacuity-precondition | medium | The class requires a multi-stage path that leaves its own subsystem

Vacuity of this kind needs somewhere for the early refusal to come from. A test
that calls one function and asserts its refusal has no preflight to trip over:
the only exception available is the one under test.

The precondition is an operation that crosses a *foreign* subsystem's gate
partway through. The instance found sits in a check that renders a candidate
tree, then validates it through the production registry authority, then compares
published bytes. The authority call is the foreign gate — it belongs to
registry validation, not to export checking — and it refuses on a subject
(review attestation) unrelated to every defect the test injects.

This predicts where to look: publication, export, filing assembly, cross-period
carry, and any path that resolves an authority mid-operation. It also predicts
where not to bother.

### sweep-null-result | medium | The registry domain suite is clean of this class, measured rather than assumed

A sweep over the registry domain suite observed 1417 caught exceptions, 497 of
them bare and passing, and produced 32 candidate clusters. Every cluster resolved
to a false positive or a legitimate test. Zero confirmed vacuous tests.

The result is trustworthy only because the detector was validated first: pointed
at the known instance with its guards disabled, it independently rediscovered
exactly the six cases already found by hand, and no others. A null result from an
unvalidated detector would have been worthless.

Two limits are recorded so the null is not overstated. Roughly 730 tests could
not be assessed because they were already failing for unrelated reasons, and a
failing test can be neither confirmed nor cleared. And the method cannot see a
vacuous test whose preflight refusal happens to be unique to it, because that is
indistinguishable from a test catching its own refusal without toggling the
injected defect off.

### detector-false-positive | medium | An accumulating validator defeats first-line message clustering

The sweep's strongest candidate was an artefact of the detector. Seventeen cases
across five tests all reported the refusal `registry validation failed:`, which
looked like a textbook preflight.

It was not. The registry validator accumulates every failure into one multi-line
message, and the detector compared only the first line. Re-running with full
message capture showed each case's own defect present in the body, and the tests
already asserted on it by name. Any message-similarity method must compare the
whole message wherever an accumulating validator is in play, or it will
confidently flag correct tests.

### proof-never-reached | high | Two ways a bite proof passes without exercising its subject

The findings above concern a test that passes for the wrong reason. Two further
instances were produced *while proving the repairs*, and they share a shape
distinct from preflight vacuity: the proof appears to exercise something it never
reached. Both are silent and both read as convincing evidence.

The first is **pinning prose**. A bite proof asserted the literal sentence
`"DO NOT choose the grade by inspecting"` appeared in a refusal message. It broke
on a reword of that same message by its own author, having detected no change in
behaviour whatsoever. A proof that pins prose ages the way prose ages. A related
instance keyed an assertion on the substring `FILING.value`, which failed because
the message legitimately contains the word "filing" while explaining every rung —
re-keying to `"blocked pending evidence"`, a marker that can only appear for the
reason under test, fixed it. Pin the property, or pin a marker chosen so that no
other cause can produce it.

The second is **sabotaging a parametrised collection by addition**. A proof
attempted to demonstrate a vocabulary-containment gate had teeth by adding a
foreign member to a parametrised dict. It reported `5 passed`, and the sabotage
was at fault rather than the gate: `pytest.mark.parametrize` freezes its case ids
at import, so a key added afterwards generates no case and is never evaluated.
The proof exercised nothing. Mutating an *existing* key instead made all three
sabotage directions bite.

The general rule for both: a bite proof is only evidence if the sabotage provably
reached the assertion. Where that is not obvious, confirm the sabotaged run
*fails*, and confirm it fails for the intended reason rather than any reason.

### proof-wrong-surface | high | A proof that exercises the consumer and not the validator

A fourth member of the same family, and the most expensive of them, because the
proof was genuinely rigorous and still cleared a change that broke the tree.

A migration moved a row field's scalar type out of application code and into a
`data_type` key on the binding selector. It was proved per binding rather than in
aggregate: thirty declarations against precedent, thirty prior ones unchanged,
eight hundred and twenty-nine scalar bindings still resolving to `decimal`, zero
mismatches. Every one of those assertions was true.

The key was already taken. `data_type` in that same flat selector mapping already
meant *"this binding projects to a fixed-width export field of this type"*, and it
obliges `offset` and `length` — seven hundred and seventy-five of the seven
hundred and eighty-three bindings then carrying the key used it that way. The new
declarations therefore read as malformed fixed-width projections. Thirty-two were
refused outright at registry build; the remaining thirty-three were invisible only
because their revisions declare no export layout yet, so they would have broken
the moment that capability was authored.

The proof measured **emission** — the consumer being changed — and never
**registry validation**, the surface being collided with. Two further conditions
hid it. The tree was deliberately red at load, so thirty-two fresh refusals did
not stand out against a large failing total. And the masking was supplied by the
absence of the very capability the campaign exists to build, which is the most
dangerous form: a defect concealed by an unfinished feature, timed to surface when
that feature lands.

The rule: when a change adds a KEY to a shared mapping, or a value to a shared
vocabulary, identify every reader of that mapping and prove against each — the
validator as well as the consumer. Measuring how EXISTING holders of the key use
it is cheap and would have settled it before a line was written. And where a suite
is substantially red, never read a total: classify failures by signature and diff
the SET, because a total cannot show a new cause arriving.

### static-gate-blind-spot | medium | The repo already gates tautologies; this class is invisible to it by construction, and that is not a weakness

A static AST guard already ships, `test_no_tautology.py`, roughly three hundred
lines, carrying its own non-triviality proof. It was found by searching for the
CONCEPT rather than the name, after several hours of keyword search failed to
surface it — the point being that a name cannot be grepped for by someone who does
not know it exists.

Its classifier was measured against four shapes rather than assumed:

| shape | flagged |
| --- | --- |
| `assert True` | yes |
| `assert x == x` | yes |
| a generated value compared to the literal its generator emits | no |
| a comparison against a single-valued literal that cannot vary | no |

Two distinct classes fall out, and conflating them is what would lead someone to
"fix" the existing gate:

- **Structurally guaranteed to pass.** Decidable from the syntax tree alone. Fully
  gated today.
- **Semantically self-referential.** Not structurally tautological at all — the
  attribute could hold anything, so no syntactic rule can see it. It is circular
  only because the same author wrote both sides. That is a fact about
  **provenance, not syntax.**

So the generator-echo assertions survived a repository that already gates
tautologies because they sit precisely in the blind spot. **The existing gate is
not weak; it is complete for what a static check can decide.** Recording that
plainly is the point of this finding: the next reader to discover these tests will
otherwise conclude the shipped gate is broken and go weaken or rewrite it.

This class is a sibling of the fixture-built-from-the-check's-own-predicate shape
already recorded in the earlier wrong-surface gates audit, not a rediscovery of
it. There, the assertion is sound and the FIXTURE is constructed to satisfy the
property under test. Here, the fixture is sound and the ASSERTION restates a value
the code under test produced. Same family — self-reference somewhere other than
where the reader is looking — opposite location.

**Deliberately left unsolved, and that is a decision rather than an omission.** A
provenance-based discriminator is probably not statically decidable, and a
detector that approximated it would flag the many legitimate assertions in this
codebase that compare against a known constant. The same audit already records a
narrow screen for an adjacent shape that was built, measured, and abandoned
because it fired only on the corrected code, with the standing instruction not to
rebuild it; that adjudication is not disturbed here and should be read before
anyone proposes automating this one. An honest description of an open problem is
worth more than an instrument that cries wolf on correct tests.

## Recommendations

Apply the discriminator when reviewing any parametrised test that asserts an
exception type: ask whether the cases vary the input or vary the subject. Varying
the subject under one shared message is the flag, and it is cheap to check by
reading the parametrisation identifiers.

Before building any gate, search by MEANING for the gate that may already cover
it. Every "does this already exist?" question has the property that the answer
cannot be grepped for, because the searcher does not yet know its vocabulary. The
static tautology guard above was found that way after keyword search had not.

Ask of any expected value in a test: **did the code under test produce this?** If
so the assertion is circular regardless of how it reads, and the remedy is either
an independent authority or removal. Removal is correct, not lazy, when the type
system already refuses every one-sided divergence — as it did for the five
single-valued literal axes, where a coordinated two-sided change was the only
thing the assertions could have caught, and they passed under it.

When bite-proofing a parametrised gate, mutate an existing case rather than
adding one, and treat a sabotaged run that still passes as a defect in the
sabotage until proven otherwise. When bite-proofing a refusal, assert a property
or a cause-unique marker rather than the message's wording.

Read a vocabulary from its declaring model (via `typing.get_args`) rather than
restating its members in the test, so the assertion cannot drift into checking
its own copy. Where several assertions are measured against one baseline claim,
assert that baseline first: otherwise the whole file can pass while measuring the
wrong set.

Before adding a key to a shared selector, config or payload mapping, enumerate
its existing holders and how they use it. Where the answer is a large majority
using it one way, that is the key's meaning, and a second meaning is a collision
regardless of how well the new use is proved.

Derive a gate's expected set from the declaring enum minus stated exclusions,
never from a restated member list. A hand-written expectation must be edited by
hand whenever the domain grows, and the miss surfaces as a coverage failure that
is really a bookkeeping one — the shape that left one source kind registered with
a selector and a validator while its gate reported the registry over-complete.

Where a test exercises an operation that crosses a foreign subsystem's gate,
assert enough to distinguish the subject's own refusal from that gate's. Pinning
the full expected message is one way; asserting that the refusal is *not* the
foreign gate's is a weaker but cheaper guard that needs no per-case message and
cannot mask a genuine detection. The second form was used for the six cases
found, which turned a silent pass into a visible, self-explaining failure naming
the real blocker.

Do not schedule a sweep over a suite that is substantially red. A method that can
only evaluate passing tests produces a null dominated by unassessable cases, and
that null will be mistaken for evidence of health.

A follow-on decision record, if this is pursued further, must rule on whether the
"refusal is not the foreign gate's" guard becomes a standing convention for
cross-subsystem tests, or stays a case-by-case judgement.
