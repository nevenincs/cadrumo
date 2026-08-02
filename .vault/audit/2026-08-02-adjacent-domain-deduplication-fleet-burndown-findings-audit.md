---
tags:
  - '#audit'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:861f1ca25158d043b88df1cbc6d36b171401fb470e0c55aaee2b0bb23ea866cd'
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
