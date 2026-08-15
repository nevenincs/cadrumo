---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:946bb5e6197ebc6c32b7d953c2f4a8d5760be09822a1a71672575d2f253c4f78'
related: []
---

# `profile-password-custody` audit: `capabilities removed without a decision`

## Scope

Two operator capabilities are absent from every surface, neither retirement is
recorded anywhere in the decision corpus, and in both cases an accepted decision
record still governs the capability while shipped surfaces still promise it.
Both were found while investigating something else, and both require an operator
ruling rather than an engineering one.

## Findings

### credential-rotation-has-no-surface | critical | The profile passphrase cannot be changed by any route

An operator cannot rotate their profile credential. The command does not resolve;
there is no application-layer rotation function; and the custody package exposes
only unorchestrated primitives -- envelope creation, material wrapping, password
validation -- with nothing built on them.

This application's load-bearing guarantee is that all sensitive financial data
lives solely under that credential. A credential that cannot be rotated cannot be
retired after exposure, cannot be changed when shared, and cannot be strengthened.
The absence is therefore a property of the security posture rather than a missing
convenience.

The orphaned test that asserted it is the cheapest surviving specification: its
documentation describes three passphrases riding one bounded secret-input object.
That assertion is deliberately left RED with an inline comment stating the
capability is absent and the question open, so the gap cannot be closed by
deleting a test.

### scripted-profile-creation-dead-ends | critical | Two layers hold contradictory intent, in live code

Creating a profile non-interactively refuses unconditionally, and the refusal was
introduced silently inside a commit whose message described custody authority and
never mentioned retiring a creation door. That commit is already recorded as the
traced origin of eight separate defects in this campaign.

**The retirement is unrecorded.** Searching the whole decision corpus for the
refusal's own wording returns nothing -- no decision record, no audit, no
execution record.

**An accepted decision record still governs it.** The profile setup-flow record
remains `accepted` rather than superseded and explicitly governs the creation
verb, including that a re-run resolves to resume and that several doors converge
on one flow. The campaign's own rollup record covers custody mechanics and never
touches the creation door.

**The replacement does not reach the scripted case.** Registration with
credentials is a genuine non-interactive function at the application layer, but
its only operator surface is a full-screen interactive one. And the routing layer
deliberately sends the scripted invocation AWAY from that screen: its rule
returns false for scripted invocations, and its own documentation states that
"what still belongs to the flow is the genuinely non-interactive contract". So
the router documents scripted creation as the contract, routes to it, and the
flow refuses it.

That contradiction is in **live executable code with a load-bearing docstring**,
not in prose making a stale claim -- which distinguishes it from the five
documentation defects this campaign has already found and fixed.

The consequence is measurable: two hundred and ninety-four tests assert this
capability, roughly twenty-three percent of the entire integration lane's
failures, and they are currently the only executable evidence in the tree that
scripted creation was ever the contract.

## Recommendations

Both need an operator decision, and neither can be closed by an implementer
without ratifying a change nobody recorded.

For scripted creation the reviewer recommends RESTORE, on the grounds that the
router's documented contract, the shipped flags, the shipped help text in all
four catalogues and the published documentation all still promise it, and that a
headless creation door is what automated operators require. The alternative is a
formal retirement -- which needs an amendment superseding the setup-flow record's
creation clauses, and which under this project's rules is not self-executing: the
implementing rows must be opened in the same action, and the router documentation,
the locale help strings and the published documentation swept with it.

Do not rewrite the two hundred and ninety-four tests before that decision.
Retiring them would ratify the drift and destroy the last executable evidence of
the contract.

The common shape is worth recording independently of either outcome: **a
capability disappearing inside a commit whose subject describes something else,
leaving an accepted decision record still governing it and every operator-facing
surface still promising it.** Both instances were found while investigating an
unrelated failing test, which means the detection was accidental in both cases
and there is no standing mechanism that would have caught either.

## Third instance: a data-protection obligation, and the detection held

A third capability fits the same shape, and it is the most serious because it is
a legal obligation rather than a convenience.

The subject-access-request surface survives in the tree as a JSON schema
declaration, an operator risk-table row, a dispatch reference, and a
one-hundred-and-fifty-six-line test module. That test module asserts a WORKING
implementation: it writes an archive and parses it back, asserts the envelope
lists its data categories, and asserts the verb defaults to the active profile.
Tests of that specificity are not written against a surface that never existed.

There is no application implementation behind any of it, and the deletion is
this campaign's own: the commit that made the custody capsule the sole profile
authority is what removed it, together with the sandbox implementation and a
dozen bucket-maintenance and bundle-export test modules. Its subject describes
the capsule cutover and says nothing about retiring an operator capability,
which is the shape the two earlier instances share.

The consequence is measurable rather than theoretical. The schema registry
declares twenty-nine profile keys and seventeen cannot resolve to a registered
verb, so the schema-coverage gate refuses at build time -- twenty-five failures
in a single test module, the second-largest identified bucket in the integration
lane.

Two corrections to how the earlier instances were framed follow from this one.

Sixteen of the seventeen are RESIDUE rather than retired capability in dispute:
the operator manifest declares none of them and no verb is registered, so a
retirement was already executed and what survives are orphaned declarations
claiming a surface that does not exist. Removing those claims is honesty about a
completed retirement, not a new decision, and it must not be read as answering
whether the capabilities should return.

And restoration is cheaper than first estimated in two of the three families.
The sandbox and archive families kept their application layer, so restoring them
is wiring. The subject-access-request surface is recoverable from history rather
than greenfield. An estimate of "restore means write it" was reasonable from the
current tree alone and wrong once history was consulted -- worth recording,
because the cost estimate is what a retirement argument leans on.

One thing improved since the earlier instances were written. Those two were
found accidentally while investigating unrelated failures. This one was found
because an agent refused to invent a ruling it could not locate and reported the
absence instead. That is not yet a standing mechanism, but it is the behaviour a
standing mechanism would have to encode: an unpersisted decision must be
reported as missing rather than reconstructed.

## The scripted-creation gap has a structural floor, not just a refused verb

The scripted-creation item above was framed as a refused door: the wizard
creation path declines, an accepted decision record still promises it, and the
operator-facing surfaces still advertise it. Measurement while converting test
helpers shows the gap is deeper than a refusal, and this is the strongest
evidence yet that it needs an operator ruling rather than a sweep.

A bucket counts as REGISTERED purely because its profile capsule exists. The
key-schedule lookup derives that answer from capsule recognition rather than
reading any stored enrolment, and returns the current schedule the moment a
capsule is published.

Registration then permanently refuses minting. That is deliberate and pinned:
a shipped test asserts that a registered bucket without its key refuses and
never mints, alongside its three siblings covering the other combinations. So
the only window in which a bucket's wrapped key can be created closes at the
instant the capsule is published.

The flag that opens that window defaults to false, and **no production code
anywhere passes it true** -- only tests do. Combined, those two facts mean no
production path creates a bucket the storage layer will subsequently open. A
profile registered through the surviving credential door has a capsule and a
custody envelope, and its bucket refuses every command that reads or persists a
record.

The refusal raised in that state says so in its own prose: it instructs the
operator to log in to an existing profile, and then states that if no profile
exists yet, **this build has no command that creates one**. The condition the
earlier sections of this audit inferred from decision records and operator
surfaces is asserted directly by production error text.

Two consequences for how the standing question should be answered.

Restoring scripted creation is not only re-enabling a verb. Whatever door is
sanctioned must mint the wrapped bucket key BEFORE publishing the capsule, or it
produces the same structurally unopenable profile. The ordering is the
requirement; the verb is the surface.

And the failure is invisible to a large class of tests. Anything that stops at
registry validation never reaches a bucket record and passes cleanly; only work
that reads or writes records surfaces it. So a green suite is not evidence that
a creation door produces a usable profile, and the conversion sweep's early
successes should not be read as clearing this.
