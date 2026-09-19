---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:3185031fe6b7a92915026742800cb9c6f549ceedcad364e9233f82e98c7eaec6'
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

### Correction: the creation door is right and the read path is wrong

The section above concluded that whatever creation door is sanctioned "must mint
the wrapped bucket key BEFORE publishing the capsule". **That is wrong, and
acting on it would have regressed the security property this campaign exists to
establish.** The corrected diagnosis follows from a live reproduction through
the sanctioned door reaching an actual record read.

The DEK is not missing. Registration mints it and wraps it into the password
custody envelope, and never writes the master-key keystore artefact -- which is
correct, because the capsule establishes PASSWORD custody. The schedule resolver
is what is wrong: it reports the master-key schedule purely because a capsule
exists, reading no stored enrolment at all, so it equates "registered" with
"enrolled in the master-key schedule" when the capsule never established that
schedule. The read path then demands a second copy of the key under a different
KEK that nothing was ever asked to write.

In one sentence: the resolver mis-states which custody a bucket is under.

Minting the keystore artefact would have created a second wrapped copy of the
same DEK under a different KEK, permanently, for every profile. A keychain or
master-key compromise would then yield the bucket DEK **without the operator's
passphrase** -- defeating precisely the property the capsule cutover was
undertaken to establish. It would also enrol every bucket in two schedules at
once, which is the one ambiguity a key schedule exists to prevent.

The correct shape is for the resolver to report the schedule a bucket is
actually enrolled in, read from stored custody rather than inferred from capsule
existence, with the master-key schedule left to buckets that genuinely carry the
keystore artefact. That change is not being made autonomously: it alters which
key opens a bucket, and key-schedule and derivation changes are owner-gated
under this project's rules. It is escalated with its own decision record.

Two things worth carrying beyond this instance.

The ordering was never decided by anyone. The nearest candidate record concerns
format enrollment for the compatibility checkpoint and states in its own
consequences that it touched no key derivation or wrapping. So what exists is
not a decision to overturn but a gap left when the cutover moved custody and the
resolver kept answering the question it had always answered.

And this is the third time in one campaign that a search by meaning returned a
confident, correct answer about a DIFFERENT subject sharing one word --
after the profile-session versus authority-session collision and the reserved
"binding" term. Here "enrollment" named both format enrollment and key-schedule
enrollment. In every instance the defence was the same: confirm the hit is about
your artefact before building on it, by reading what the source says it touches.

### Correction and disposition: the pre-capsule buckets were already written off

A halt was called on the key-schedule deletion because four buckets in the
operator's live store carry the legacy keystore artefact with real encrypted
databases -- 5.3 MB, 516 KB, 311 KB and 106 KB, two of them labelled for the
operator's own account, the others `sync-test` and `operator`, and two of them
already tombstoned. The stated reason was that deleting the legacy route would
strand roughly six megabytes.

**That framing was wrong and is corrected here.** Those buckets are already
unreadable by the current tree, three independent refusals deep, and none of the
refusals is the branch proposed for deletion. None carries a profile capsule, so
the schedule resolver returns nothing and the legacy read arm is never reached.
Their manifests declare schema version 2 while both the current version and the
durability floor are 3. And the strict manifest model refuses their extra
fields outright.

The floor is the decisive fact, because it is a decision rather than an
accident. The manifest tier carries no upgrade dispatch, so the floor sits equal
to the current version by design, and the code states the consequence directly:
raising the version forces raising the floor with it, dropping older manifests,
which is the pre-release posture. **Version-2 manifests were written off when
the version reached 3.** These four are unreadable because that decision was
taken, not because anything is pending.

So the deletion changes RECOVERABILITY, not reachability, which is already zero
-- and recoverability is not destroyed either, only moved into git history on a
pre-release tree carrying no released data.

The operator has since ruled directly that no data needs preserving, and the
deletion proceeds. Recorded because the corrected reasoning outlives this
instance: **before claiming a deletion will strand data, establish whether the
data is reachable TODAY.** A gate that fires on the presence of an artefact
rather than on its reachability produces a true observation and a false
conclusion, and costs a round trip to the owner.

One corroboration from the same measurement, pointing the other way. There are
zero capsule artefacts anywhere on the operator's real disk -- no commit record,
no envelope, no sentinel, no custody directory. Every bucket the operator
actually holds predates the cutover. The campaign's target state has never been
materialised on real disk, which supports the read-path finding from the
opposite side: nothing in production has ever produced the state the read path
expects.

### Retraction: there is no unopenable-bucket defect, and this section was wrong

The two sections above -- the "structural floor" and the read-path correction --
are **retracted**. Both rest on a measurement taken without logging in, and the
conclusion drawn from it is false.

Registration closes the session in a `finally` block and returns an INCOMPLETE
setup state. A freshly registered profile is therefore **locked, not broken**,
and authenticating is the design rather than a missing step. Instrumented
properly -- create through the sanctioned door, then log in, then read -- records
come back normally, the keystore route is entered **zero** times on the whole
path, and no keystore artefact is written at all.

So: no production path is missing. No bucket is structurally unopenable. The
resolver is not mis-stating custody. What the earlier sections described as a
security-shaped defect requiring an owner ruling was a probe that stopped one
step short of the operator's own workflow.

**What survives the retraction, because it was measured rather than inferred.**
The keystore route genuinely is dead code -- entered zero times on the working
path, written by nothing -- so deleting it remains correct, and is now plainly
removal of dead code rather than a repair. The four pre-capsule buckets remain
unreachable for the three reasons already recorded, none of which involves that
route. And the ownership analysis distinguishing a key handed to one caller from
a shared module-level object stands on its own; only the premise that prompted
it was false.

**Why this belongs in the audit rather than being quietly edited out.** The
claim travelled. It was written here, escalated to the operator as a live defect
making every newly created profile unreadable, used to park another agent's
conversion sweep as structurally blocked, and used to widen a blast radius from
"modules that read records" to "modules that need a usable profile at all". Each
of those was a reasonable step from the one before, and the whole chain rested
on a single unexamined assumption about what a fresh profile should be able to do.

The lesson is the campaign's own, met from a new direction. A plausible symptom
invites a plausible cause, and the cheaper the cause is to believe, the less
likely anyone is to probe the step before it. **The defence is to reproduce
through the operator's actual workflow, not through the shortest path that
produces the symptom** -- and specifically, when a refusal says "not ready", to
establish what would make it ready before concluding that nothing can.

### Correction: scripted creation was retired by design, and the design is legible

The scripted-creation item above is **partially withdrawn**. It was recorded as a
capability removed without a decision, on the evidence that the router refuses,
an accepted decision record still promises creation, and the operator surfaces
still advertise it. Measurement now shows the decision is legible in the design.

Creation is not gone. **Non-interactive creation is gone.** The verb still
exists and is still the advertised entry point in the curated help; on a capable
terminal it diverts to the profile manager, which registers through the
credential-first door. On a host without a usable console -- which is every test
process -- it reaches the command and refuses.

So the retired capability is precisely SCRIPTED creation, and the retirement is
coherent with password custody rather than incidental to it: a passphrase cannot
be safely supplied on a command line, so a creation path that accepts one
without a console is a surface the custody model cannot honour. That reasoning
was never written down, which is why the removal read as accidental, but it is
not arbitrary and it is not a mistake.

**What survives the correction.** The accepted decision record still promises a
creation flow it no longer describes accurately, and the operator-facing help
still advertises the verb without stating the terminal requirement, so an
operator on a console-less host meets a refusal the documentation did not
prepare them for. That is a documentation and decision-record gap rather than a
lost capability, which is a materially smaller item than the one first recorded.

**And the 294 stale tests are reframed rather than resolved.** They assert
non-interactive creation, which is retired by design, so they are testing a
capability the product deliberately does not offer. They should be re-founded on
the surviving surfaces rather than preserved as evidence of a lost contract --
the opposite of the instruction this audit originally gave, which was to leave
them alone pending a decision. The decision existed; only its record did not.

The correction was found by an agent that nearly reported the opposite. It wrote
"no CLI surface exposes credential registration" into its own working notes
while the search it had just run returned two hits in that very file, and caught
it by reading the output rather than its own summary of the output. Had the
label been trusted, this audit would have gained a false escalation -- that
operators cannot create a profile at all -- about a shipped product.

### The deletion chain is blocked at its input, and a legal-hold gap sits behind it

Profile deletion cannot run on any real profile, and the reason is one level
below every previous diagnosis in this chain.

The custody deletion preflight assesses two owners -- filing retention and legal
holds -- and both read persisted snapshots. **Nothing in production writes
either snapshot.** Both recorders have exactly one reference each in the whole
tree: their own definitions, plus test modules. Measured on a profile whose
owner facts were never recorded, which is every profile, all four entry points
refuse on an absent snapshot.

So the earlier finding that the deletion preflight refuses for want of an
authenticated retention assessment was accurate and incomplete: wiring the
assessment in would trade one refusal for another, and the fifteen failing
modules would stay red with a different message.

**The two owners are NOT symmetric, and treating them alike would be a safety
defect rather than a wrong count.** Their recorders' signatures decide it. The
filing recorder takes the application's own modelo records, so that owner's
facts are derivable from state the application already holds. The legal-hold
recorder takes case identifiers supplied from OUTSIDE; nothing the application
owns can produce that list.

Filing is therefore a missing producer, and the preflight refreshing the
snapshot from the profile's own records is the fix -- rowed, and available now.

**Legal holds are fail-closed by design, and correctly so.** An absent
legal-case snapshot means nobody has been asked, which is not the same as no
holds existing, and no refresh can close that gap because the answer lives
outside the system. Defaulting it to empty would permit erasing a profile under
an open legal case because the application had never been told. That is rowed as
an operator-surface question -- how open cases reach the application at all --
rather than as wiring.

**The subsystem's tests pass only by supplying what production cannot.** The
deletion fixture writes both snapshots itself before every delete test. That is
the second such case found in this one subsystem, after a test that pinned a
clock the public facade cannot pin -- which had concealed a guard that refused
every deletion. One instance is a fixture; two is a pattern, and it explains why
this area has read as healthier than it is. Both were found the same way: by
removing something the test supplied and watching the production path fail.
