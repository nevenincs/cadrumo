---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d2b9e7672e20a5792c5451b53cbe763fea8c7b0659d1c67e5293a044cc8242b4'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
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

## Recommendations

Apply the discriminator when reviewing any parametrised test that asserts an
exception type: ask whether the cases vary the input or vary the subject. Varying
the subject under one shared message is the flag, and it is cheap to check by
reading the parametrisation identifiers.

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
