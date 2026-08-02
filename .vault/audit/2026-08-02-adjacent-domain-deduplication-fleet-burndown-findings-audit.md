---
tags:
  - '#audit'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:ef9c7b7682a8179accf3c79e3196fd8b215132b0026c23e58ee18f84d5ddb8f4'
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

