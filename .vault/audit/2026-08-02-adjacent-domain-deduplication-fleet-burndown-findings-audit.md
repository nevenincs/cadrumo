---
tags:
  - '#audit'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:498f6adcf4566d1f20770ee2e2d48f71c381afc6e10b19f553a7188c46b28f93'
related: []
---

# `adjacent-domain-deduplication` audit: `Fleet burndown: findings, methodology, and held work`

## Scope

A seventeen-agent fleet worked findings 260 through 532 of the adjacent-domain
deduplication audit, partitioned by source area so no two agents owned the same
file. A separate cluster held findings 1 through 259 concurrently. This document
records what the fleet found beyond its assigned findings: defects surfaced while
fixing others, audit findings whose stated remedy would have broken a real
contract, methodology that proved transferable, and work written but not landed
when the fleet reached its session limit.

It is not a closure record. At the time of writing a tree-wide gate run had not
completed and one verified fix remained uncommitted, so no claim is made here
about campaign completeness.

## Findings

### fleet-burndown | high | passphrase verification is unthrottled on two of three doors

`_login_throttle.py` states that the caller evaluates the remaining wait before
running any Argon2id derivation, so the KDF can never become a passphrase-testing
oracle. Three production doors verify an operator secret by unwrapping the master
key. Only the login door honoured the throttle. `change_passphrase` in
`application/user_profile/_custody.py` was measured at six consecutive wrong
guesses, roughly 0.04s each, with the failure counter never moving; it has been
fixed and now shares the login budget, refusing before derivation and refusing a
throttled operator even with the correct passphrase. `profile_create_storage_span`
remains a free door onto the same secret and was deliberately not fixed: the
throttle is keyed per bucket while the secret it guards is store-wide, and that
call takes the bucket id as its argument, so a throttle there keys on whatever
bucket the caller names and an attacker picks a fresh identifier per guess. The
mnemonic recovery door is unthrottled by design and correctly so. Report this as
an unthrottled verification oracle on additional entry points, not as a
timing-oracle break: elapsed time was flat in every probe, so the side channel is
genuinely absent and it is the passphrase-testing half of the claim that is false.

### fleet-burndown | high | an accepted decision record rested its safety argument on a comparison that could not hold it

The Cl@ve session guard compared the profile tax identifier against the provider
identifier with a bare inequality on two unconstrained string fields, so a
punctuation variant falsely refused a legitimate session while two equal
malformed values falsely confirmed ownership. An accepted censal-autofill decision
record cited that guard as the pre-existing fail-closed control underwriting its
own safety argument. The comparison now routes both sides through the canonical
Spanish tax-identifier validator, measured per case in both directions. The
general hazard is that a reviewer checking whether a path was defended would have
read the decision record and stopped.

### fleet-burndown | high | the Sede write guard was described as structural while the mechanism is behavioural

A module docstring claimed every boundary-crossing record carries a read-mode
marker as part of a structural write guard, and that the module is incapable of
mutating AEAT state. The marker has zero production readers; the read-only HTTP
assertion guards only first-party calls and is never reached by a browser form
POST; the forbidden-verb scan explicitly permits `click`, `fill` and `press`; and
the landing refusal exists in one of nine modules that interact with forms. No
path that mutates AEAT state was found, the filing tool itself carries a
purpose-built guard with a live-simulator proof, and every control clicked
elsewhere is a consulta submit. The property holds; the stated mechanism did not.
The prose has been corrected across four sibling claims to describe the actual
layers and to name the residual outright.

### fleet-burndown | high | revision-lineage tamper detection covers four of nine stamped columns

A storage crypto docstring claimed that a tamper of any single lineage column
that does not also recompute the revision id is detected and can be failed
closed. Probed by tampering one stamped column at a time through raw SQL and
re-reading through the real repository, five of nine were accepted undetected,
including the revision ancestry chain and two audit-attribution fields. The
detected set is exactly the set mixed into the derivation, so the gate is sound
for what it covers and the claim overreaches. Not remotely reachable: it requires
direct database write access and the payload bytes remain protected.

### fleet-burndown | high | amendment records drop the member identity silently

The amendment builder derives the filing-record identifier without the member
identity, and the record constructor omits it too, so the field defaults to
absent and the aggregate's own invariant re-derives with the same absent value
and matches. The validator passes because both halves dropped it consistently.
The catalogue enforces one current record per coordinate including that member
field, so the amendment lands on the absent key and can collide with a
single-filer record or a second member amending the same period, surfacing as a
duplicate-current-record error pointing at an unrelated row.

### fleet-burndown | high | XML dictionary export verification ignores root metadata

The export verifier computes its verdict solely from mismatched casilla
identifiers; the parser it calls builds the element tree only to walk entry paths
and read element text, and never inspects root attributes. Root metadata appears
only at the write site. A file with matching casillas but the wrong modelo,
exercise, period or schema version therefore verifies as a match. Established
against a pristine extraction of the committed tree rather than a working copy.

### fleet-burndown | medium | a persisted approval basis is never re-verified against its own contents

The review checksum has exactly one call site, on the write path. The identifier
appears at nine non-test sites and none recompute and compare; the refresh path
tests only for absence. A persisted basis whose checksum was tampered, or whose
contents were tampered while the checksum stood, survives reload unchallenged.

### fleet-burndown | medium | six audit findings would have broken a real contract if implemented as written

Confirmed by the agents who implemented them and reverted, or who measured the
shipped corpus first. Unique-casilla enforcement contradicts multi-row
informativas, which legitimately repeat a casilla per declared item. Binding the
schedule year to the obligation filing year had already been built by an earlier
campaign, found to refuse twenty-two real engine schedules, and pinned in a
negation-named guard test to stop it being re-proposed. Binding legal-reference
effective windows to revision applicability would reject thirty-six legitimate
shipped citations, because the effective stamp is a consolidated-wording date
rather than an applicability window. Unifying two observation source taxonomies
would let a capture-provenance token read as filing-grade evidence. A profile
repository guard was declined on a caller flow with zero production callers. A
gross-invariant catalogue was assumed closed while the field carries two
taxonomies.

### fleet-burndown | high | a guard's existence is not evidence of its coverage

Reached independently by eight agents through eight mechanisms during the
campaign: mutation testing that removed the fix and watched the test still pass;
an anti-vacuity floor requiring a minimum compared-row count; a detector fed a
deliberately unguarded field to prove it discriminates; a probe that disposed a
connection pool and measured nothing because the pool reconnects; file history
substituted for symbol history; a validator's existence substituted for its
coverage of the case a finding named; a refusal with no test asserting it fires;
and a guard defended against a future change that would make it vacuous. The
common form: only a construction that should fail can establish that a guard
covers the case in question.

### fleet-burndown | high | prose asserting a property that nothing maintains

No gate in this project can catch it. Two probing passes over crypto, storage,
identity, auth and the accepted decision corpus produced three violations and two
imprecisions against nineteen holds. The discriminating predicate is
cross-object, unconditional and unenforced: prose describing a neighbour's
behaviour, stated without a precondition, with nothing that would catch it if it
drifted. The one-minute question is whether anything would fail if the property
stopped being true. Same-object claims produced zero problems in nine, but that
sample is biased toward claims true by construction, so the honest reading is
that no same-object claim in the sample failed and some of them could not have.
The predicate collapses in the decision corpus, where prose is about other
modules by construction; there the ordering signal is symbol presence, filtered
for declined alternatives, external supersession, and in-document amendment.

### fleet-burndown | medium | a defect can appear at the seam between two correct changes

One agent added a mechanical docstring cross-reference; another was editing the
same docstring for an unrelated guard. The combination produced an incomplete
parameter block that existed in neither change alone. Both agents followed the
shared-file drive correctly and neither could have seen it from inside its own
diff. Every instrument this campaign built measures one change against the tree,
and a seam defect is a property of two.

### fleet-burndown | high | correction: the login door is unthrottled too, and per-bucket is the wrong scope everywhere

The passphrase finding above records the login door as correctly throttled and
the remaining exposure as a per-bucket counter guarding a store-wide secret,
with the bucket identifier supplied by the caller. Both halves are wrong and
the correction makes the finding larger rather than smaller.

The login door resolves the master key through a bucket-less provider while
recording failures against the target bucket. Measured: six failures against one
bucket throttle that bucket, and a second bucket testing the same store-wide
secret is not throttled and has recorded no failures. An operator with several
profiles therefore hands an attacker that many times the budget, at the door
this document recorded as sound. The defect is not that one door was missed. It
is that the counter is keyed per bucket while the secret it guards is store-wide,
so every door inherits the same scope error and the door that appeared correct
was correct only for a single-profile operator.

The reasoning about a caller-supplied bucket identifier was also wrong. Six
consecutive wrong guesses reusing one fixed identifier are equally unmetered:
no failures recorded, no sidecar written, and a correct passphrase accepted
immediately afterwards with no backoff. That door consults no counter at all, so
identifier freshness was never the mechanism. Store-scoping the budget is
necessary but not sufficient; the door must also be wired to consult it.

The surface is not dead. Seven production call sites reach it, one of them
threading an operator-chosen passphrase from the registration screen.

The governing decision record adopts a store-scoped budget keyed to the secret
rather than the bucket, and keys all three doors to it. It prices the cost
rather than dismissing it: the backoff is capped at sixty seconds, there is no
permanent lockout, and any success clears it, so the worst case is a rolling
delay across buckets rather than a lockout, and raising that ceiling would
reopen the decision. It also ranks itself as hardening rather than urgent
remediation, on the ground that against an attacker with local code execution
this buys nothing, since the key material is readable by the same user and
offline attack beats any interface path. Its constituency is the walk-up
attacker at an unlocked terminal.

The original reading that this is not a timing oracle is confirmed with numbers.
Wrong guesses complete in well under a fifth of a second and a correct one takes
longer, but only because provisioning and key enrolment run after a successful
unwrap. Discrimination is by exception, not by clock.


### fleet-burndown | high | a guard can be on the path, raise correctly, and have its refusal discarded downstream

The coverage finding above concerns guards absent from a path. A third form is
harder to see, because every instrument built for the absent-guard family
reports it as present and working. The duplicate-tax-identifier guard in
`application/user_profile/_profile_repository.py` loaded each candidate through
the verifying load, which raises `ProfileIntegrityError`; that inherits
`ProfileNotFoundError`, which is a `CadrumoError`, which the surrounding
unreadable-profile handler caught and converted into `continue`. The duplicate
was admitted with a warning. Call-site scans, enrollment gates and coverage of
the guard itself all pass on that arrangement. Only following the exception's
fate reveals it. The general form: a broad `except` that cannot distinguish
"this input is unavailable" from "this input is inconsistent" converts a refusal
into a skip, and the two are indistinguishable at the catch site by
construction.

The predicate that matters is not syntactic. An abstract-syntax sweep found
eleven sites carrying a broad handler downstream of a verifying call and exactly
one defect. Ten returned a named unknown the caller can branch on; one used
`continue`. That split is the symptom rather than the axis, and stating it as
the axis is actively misleading, because it licenses the wrong disposition. The
rule is that the handler must hand back a value the caller can distinguish from
the healthy negative. A `None` colliding with the legitimate "nothing here"
answer is not a named unknown whatever its syntax: in a resume path, `None`
meaning "this profile has nothing to resume" is the same value a legitimately
ineligible profile produces, so the caller cannot separate *ineligible* from
*could not tell* — a return-default in shape and a `continue` in effect. The
greppable form, a broad `except` whose body is `continue` inside an iteration
that constitutes a guard, remains a useful finder and currently has one
occurrence, deliberate and no longer able to swallow a status disagreement. It
is a search heuristic, not the predicate.

### fleet-burndown | medium | subclassing a family root is sound; subclassing a specific condition is impersonation

The exception hierarchy carries the same hazard latently, independent of whether
any handler catches the parent today. A child can impersonate its parent only
where some handler catches the parent, which makes the absorbing-parent set the
bound: 650 error classes, 611 subclass edges among them, 392 edges whose parent
is caught in production, and 47 distinct absorbing parents. Forty-three of those
are unmistakable domain family roots, where subclassing is sound because every
child means the parent condition with a reason. Four are specific conditions,
and those are the whole risk surface. `ProfileNotFoundError` means one thing —
this profile does not exist — so an integrity child impersonates it at every
handler. `MasterKeyUnavailableError`, `DecryptionError` and
`AeatLoginAssertionError` read as candidates by name and are sound on their own
declarations: a wrong passphrase genuinely is one way the key could not be
obtained, and a session that cannot be trusted is literally the second clause of
the login assertion error's own docstring.

Two consequences. The subclass relation is not a mechanical discriminator — it
over-selects, and in the eleven-site sample it separated nothing. And the
judgement is per class rather than greppable, so the useful output is the
enumerated parent list rather than a rule.

### fleet-burndown | high | find the smallest edit that should break the property, not the first edit that does

A partial net does not merely fail to catch; it certifies. Demonstrated from
both directions. A vacuous assertion inside the live AEAT write guard
(`test_url_method_guard_includes_canonical_write_verb_tokens`) compares the
forbidden-token constant against a set built by unpacking that same constant, so
containment holds at every value; deleting a canonical write verb left the test
green. The obvious mutation against a neighbouring gate *was* caught — by a
companion assertion checking fixture presence — and that partial coverage is
exactly what hid the real hole, because a caught mutation reads as a covered
property.

The shapes are enumerable and worth checking directly. A filter feeding an
assertion vacates it while the surrounding assertions still constrain the arm; a
filter feeding `parametrize` deletes the case outright, because nothing
downstream constrains what no longer exists — measured at twenty-two collected
cases falling to three with zero failures. A bound derived from the value under
test moves both goalposts together. A count pinning a total but not its
partition stays green while one partition collapses. The review question on
landing any guard is what the smallest edit is that should break it, and whether
it does.

### fleet-burndown | high | an instrument that has never detected a known instance is not evidence

Four confident zeros in one session, none caught by tooling. A multiline pattern
search returned zero where the searcher's own known site had to match; a
several-hundred-file shell glob passed to a search tool rather than letting it
walk produced what read as a clean corpus-wide negative, twice; a probe aimed at
a module path where the entry did not live reported the entry missing. A
wrong-path negative is indistinguishable from a real one, and in every case the
only thing that caught it was the result being implausible against something
already known.

The transferable remedy is mechanical rather than attentional: carry a positive
control that aborts unless the instrument rediscovers an instance already known
to carry the shape. An instrument that cannot find the one case you know exists
cannot be trusted to report zero others. Where a filter is meant to clear as
well as detect, the control must be two-sided — a negative arm requiring a
known-sound case to be excluded, without which a filter passing everything
through still shows the positive arm green.

Applied to a predicate rather than a scan, the same check is one question: would
this pattern separate the known good from the known bad? A greppable proxy for a
semantic property gets adopted because greppable feels rigorous, and a mechanical
tell that does not discriminate selects a confidently wrong set — worse than
admitting the judgement is manual.

### fleet-burndown | medium | two kinds of all-clear, and only one survives a re-run

The constructive counterpart to the preceding finding. *These files did not
appear in my results* depends on what a run happened to return and must be
re-established whenever anything changes. *My scans key on class definitions and
`except` handlers, and these files contain zero of each* is a property of the
instrument and the subject, so it holds regardless of run: the files could not
have appeared rather than did not.

Prefer the structural form wherever the instrument's keys are enumerable. It is
usually one command more expensive and it converts a result that decays into one
that does not. Two constraints on its use. Name which kind is being claimed,
because a structural claim hedged like an incidental one teaches the reader the
author cannot distinguish them. And it does not rescue a bad instrument: if the
keys are wrong for the question, "the subject has none of my keys" is true and
useless, so it strengthens a sound instrument's negative rather than replacing
the control that proves the instrument works at all.

### fleet-burndown | high | a mutation is an artificial instance of exactly the defect being hunted

Restoring a mutation correctly protects the tree and does nothing for peers
reading during the window. That is a different failure and it is the one that
fires. It burns readers symmetrically: a peer sampling during the window reports
a defect that does not exist, and a peer sampling afterwards sees clean and
concludes the reporter was careless. The mutation runner never notices, because
their own restore verified fine. Eleven windows occurred in one session against
a fleet sampling continuously, so "seconds" is not short at that ratio.

There is no test-file exemption. The discriminator is not production-versus-test
but whether the mutated state resembles what a peer is currently looking for.
Two test-file windows presented, mid-window, as a vacuous gate — an emptied
refusal tuple feeding a parametrized contract, and renamed discriminator
literals in a filter — which was that period's highest-priority category. A peer
would have reported either in good faith, and it would have read as a
confirmation of the prevailing thesis, which is far worse to unwind than a false
production defect, because a finding that fits gets absorbed rather than
checked.

The rule has two halves. Announce the file and rough duration before any
mutation window. Name the files afterwards if the announcement was missed,
because prospective disclosure helps nobody who has already sampled, and
retroactive disclosure is the only route by which a peer holding an observation
can settle it. Two reader-side discriminators make most cases resolvable without
interrupting anyone: read the committed state by content rather than by a line
offset measured in the working tree, since offsets are not portable between the
two and a range slice will silently return a different region; and re-read once
after a short interval, since a mutation window closes while a defect persists.

### fleet-burndown | medium | a sweep that finds nothing new can be the reason a later fix is correct

A hierarchy sweep's headline result was one defect, already known. Its actual
output was preventing a subsequent fix from silently recreating that defect: the
fix's author ordered its `except` arms as it did because the sweep had published
the shape, and the coarser guidance then in circulation would not have caught
it. The obvious handler for that site would have swallowed an integrity refusal
and restored the hole with every other test passing.

The triage consequence is that a null-result sweep's value is not measured by
its findings count. It is measured by whether its predicate reaches anyone
before they need it.

### fleet-burndown | medium | accidental coverage reads as defence in depth

The inverse of the coverage findings above: not a gap that looks covered, but a
coverage that is genuinely accidental. A wizard manifest grant reaches no write
on either path — one stopped by a resume-eligibility fix, the other by an
already-registered check in `ProfileRepository.create`. Neither guard's tests,
comments or docstrings mention the other, so whoever refactors either has no
signal that they are load-bearing together, and the configuration looks safe
until one is changed for an unrelated reason.

Worth noting how it surfaced: an initial claim that the non-interactive path was
ungated reasoned from the absence of a checkpoint store without checking whether
anything further down refused. An unchecked "nothing gates this" is the same
shape as an unchecked "something gates this".

### fleet-burndown | medium | check for a prior refutation, and measure the shipped corpus, before enforcing an invariant

A refutation of a proposed invariant usually lives as a guard test rather than a
decision record, so a search of the decision corpus misses it. One finding asked
that a schedule year be bound to a period's filing year; the tree already
carried a negation-named test written specifically to stop that being
re-proposed, after an earlier attempt found it refuses twenty-two real engine
schedules. Implementing it broke twenty-three tests for no net change.

Two cheap pre-flight checks, both before writing code: grep the owning package's
tests for the negation of the invariant, and count how many shipped records
would violate the rule. A nonzero violation count on legitimate data means the
rule is wrong rather than the data — which is what scoped one source-reference
rule to revision level after finding zero violations there against 212 at modelo
level, and what refused a legal-reference window rule outright after finding it
would reject thirty-six legitimate citations.

### fleet-burndown | high | correction: the claim that this class of defect concentrates in newly-landed guards does not survive its own evidence

Recorded because how it failed is more useful than the claim. It was
generalised from one sweep, then a second was cited as corroboration without
checking its direction, and a third contradicted it outright.

The first sweep, over four vacuity signatures, found the pre-existing corpus
clean with every live instance in campaign-landed instruments, and supports the
claim. A mutation pass found a live vacuity in a pre-existing gate, reached by a
fifth signature neither sweep enumerated, and contradicts it. A swallowed-refusal
sweep found all eleven candidates including the sole defect predating the
campaign — last-touch dates spanning three months against a single campaign day,
and zero campaign-landed instances against a denominator of 373 commits and
roughly 15,900 production insertions that day — and contradicts it.

Two shapes pointing opposite ways is a reason not to generalise from either. The
claim also required a distinction that was elided: a defect in pre-existing code
that a campaign *finds* is not a defect the campaign *authored*, and only the
second supports a claim about authorship. What survives independently is that
instruments carry the defect they hunt, true regardless of who landed them, and
the review question on landing a guard, which stands on its own merits.

### fleet-burndown | medium | correction: three git measurements that answered a different question than the one asked

Each was run correctly, returned real output, and was about something other than
the subject.

`git status --short` is not a working-tree change check in this repository. With
`core.autocrlf=true` a file touched by any tool shows as modified with zero
content change; measured at 48 phantoms in 104 modified entries, a 46% false
rate. Findings were skipped as blocked by peer work that was never blocked. Use
`git diff --numstat -- <file>`, and note that it answers whether you would
overwrite someone, never whether the work has already been done — that second
question needs the file's history.

File history is not symbol history. A finding was twice reported as fixed before
the campaign, once by taking a commit that merely touched the file as the commit
that introduced the symbol. `git log -S <symbol> -- <paths>` is the only
instrument for when something entered the tree; the finding was genuinely open.

Blame co-occurrence is not common authorship. Three sites including a defect
blamed to one commit, which was a 196-file bulk landing of accumulated
working-tree changes. That nearly became a mechanism finding — the same commit
produced both dispositions, so the disposition is situational rather than policy
— and is worthless. The sound half of the same measurement survives: blame gives
last-touch, an upper bound on introduction, so "last touched before a given
date" proves pre-existence even though it attributes nothing about authorship.

### fleet-burndown | medium | correction: a pathspec commit takes working-tree content, so a stale working copy reverts landed work

A commit whose subject concerned an unrelated transport change silently reverted
a landed typing fix across four result classes in
`entrypoints/cli/_config/_config_payloads.py`, restoring `str` where `BucketId`
had been landed. The author committed from a stale working copy and used a
pathspec commit, whose pathspec captured their stale content for the whole file.
This is distinct from the working-tree hazards the shared rules already cover:
the peer work lost here was already committed. A pathspec commit is only safe if
your working copy of that file is current, so read the file's most recent commit
before committing a file you have held for any length of time.

## Recommendations

Close the passphrase-oracle class properly. A follow-on decision record must
rule on whether the login throttle gains a store-scoped counter beside the secret
store, which changes that module's own per-bucket contract. Bolting a per-bucket
throttle onto the remaining door would be ineffective by construction, because
the caller supplies the bucket identifier.

Extend the Sede landing refusal from one module to the remaining eight that
interact with forms, with per-module live-fixture evidence. That is what would
make the corrected prose's weakest clause earned rather than merely accurate.

Rule on the revision-lineage overclaim. Mixing the remaining stamped columns into
the derivation changes every stored revision identifier, which is a durability
floor event and needs its own decision; narrowing the prose to the covered set is
the cheap alternative, with the ancestry column tracked separately because it is
the one the lineage claim is actually about.

Build a fault-injecting filesystem layer at the storage substrate boundary, one
the production code already writes through. Two findings closed structurally
without a failing pre-fix test because their defect is the ordering of real
writes against a real path, and a double placed at that boundary would exercise
the test's own scaffolding and pass identically against the unfixed code. Four
orphan and partial-write findings in this campaign alone would have been
provable with it.

Rule on three dead surfaces identified on the same evidence pattern: a profile
duplication service method already deleted, a profile listing method with zero
production callers whose test asserted a shape the storage contract forbids, and
a related-party materializer that structurally cannot represent the text fields
it claims to materialise because its value type is decimal.

Run the softer-phrasing prose pass as its own task rather than an extension. The
absolute-language collection method cannot reach claims phrased as consequences,
and the verb-shaped query that can costs real triage per hit. The highest-signal
sub-pattern is the consequence clause, because that is where an author states
what a mechanism achieves and where the two come apart.

Do not reimplement the scan-verification fold held uncommitted at the session
limit. It is written, verified, and extends the landed load-side guard; three
findings across two agents are held behind it. A second implementation would be
the duplication this campaign exists to remove.

### Correction to the dead-surface recommendation, recorded on later evidence

The three dead surfaces above were identified on a single evidence pattern.
When each was ruled on individually with a positive control, that pattern held
for two and misfired on one.

The related-party materializer is not a dead surface. Its premise was that the
value type is decimal, so the text fields it claims to materialise cannot be
represented. At the current tree the value type carries text at all three
layers: the producer edit model, the row-cell protocol, and the domain
authority whose docstring states the split deliberately as text for the
identifier and coded fields and decimal for the amount. The assembler routes
text and money through separate coercions. The claimed capability is present
and acting on the original finding would have deleted working code. Whether
the premise was ever true could not be established: a history search on both
type spellings returns only a package-root rename that rewrote the file
wholesale and cannot discriminate.

The profile listing method is confirmed to have no production callers, and its
contract defect is stronger than first stated but different in kind. The claim
that its test asserted a shape the storage contract forbids was not
confirmable, because clearing a fact stores an absent value and no validator
rejecting a whitespace-only value was found. The provable defect is a union
mismatch: the signature accepts a text-only mapping while the storage contract
admits text, boolean, integer, decimal, date, or absent, and the method calls a
text-only operation on the value. Four of five contract-legal types are
rejected. The recommendation to split the method from its test stands, with one
correction: only the single test bound to the dead method retires with it. The
module that contains it pins a cross-surface presence predicate that is live and
exists because three surfaces once disagreed.

The profile duplication service method is confirmed absent, but the phrase
already deleted invites a wrong inference. The operator-facing duplicate verb is
live, with tests, an envelope, help text, a documented sequence, and four locale
catalogues, and it routes through profile registration rather than any service
method. Deleting the residue does not drop a guard: a removed source already
fails to resolve because tombstoned profiles are excluded by default, so
behaviour is preserved and only the refusal message degrades. The residue is a
type-forbidden branch, its message constant, four locale keys, and a package
docstring naming two operations that do not exist.

One sequencing constraint applies to that removal. The locale key's only code
reference is inside the unreachable branch, so deleting the branch orphans the
key in every catalogue and the locale drift gate fails until the key is retired.
The branch deletion and the key retirement must land in the same change, with
the key removed through the locale command rather than by editing the catalogue
files.

### Correction to the preceding correction: the materializer finding was right

The paragraph above claiming the related-party materializer is not a dead
surface is wrong, and the original finding was correct. It is retained rather
than deleted because how it went wrong is the useful part.

The audit named its subject by description rather than by exact symbol, and the
description resolves to two different functions in the same area. One agent
read it as the shared row-value authority, which returns text or decimal per
field, is consumed by revision replay, and is correctly alive. Another read it
as the observation materializer, which produced observation values typed
decimal while four of five fields per row are text, coerced through a decimal
constructor that raises on any of them. That second function had no callers and
carried a latent crash that never fired. It has been deleted.

Both agents verified carefully and neither made an error. The finding was
ambiguous, and two independent readings of one sentence produced opposite
verdicts about whether working code was at stake. An audit finding that
identifies its subject by behaviour rather than by name is resolvable to more
than one subject, and the ambiguity is invisible to whoever writes it, because
the author knows which one they meant.

The surrounding module is not dead either way. Only the observation materializer
was removed, and the capacity refusal it carried was retargeted onto the
surviving authority rather than dropped.

One further correction from that work, on the retargeted test. Its first version
derived both the accepted and the refused row counts from the same constant it
was meant to pin, so raising that constant moved both goalposts together and the
test passed at any value. A previously value-pinning test had been made vacuous
while staying green, during a cleanup. The bound is now pinned to the count of
slots the official form actually provides.

### Sharpening the materializer correction: the ambiguity was created, not written

The correction above attributes the split verdict to a finding that named its
subject by description rather than by exact symbol. That is true and it
understates the mechanism.

The two functions were one function when the finding was written. The shared
row-value authority was split out of the observation materializer by a refactor
that landed the same morning the finding was worked, giving replay a shared
authority. Before that commit the description resolved to a single function that
both materialised observations and mapped identifiers. So the finding was
unambiguous when authored and became ambiguous while queued.

That is a different and more common failure than imprecise wording, and it is
not fixable by writing findings more carefully. In a tree where refactors land
hourly, any finding that names a subject rather than pinning a commit is
resolving against a moving target, and the longer it sits in a queue the more
likely its subject has been split, merged, or renamed underneath it. The
practical remedy is at the working end rather than the authoring end: re-resolve
a finding's named subject at the current tree before acting, and treat a subject
that now resolves to more than one symbol as a signal that the finding predates a
refactor rather than as a defect in the finding.

