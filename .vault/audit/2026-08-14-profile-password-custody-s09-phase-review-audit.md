---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b0abbd4d889e60f1c9030090f345200a29958f200826e60979ce85cf04925784'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-state-aggregate-successor-adr]]"
  - "[[2026-08-13-profile-bucket-lifecycle-successor-adr]]"
---

# `profile-password-custody` audit: `S09 lifecycle and discovery phase review`

## Scope

Phase-ending integrated review of `W02.P03.S07` and `W02.P03.S08` against the
accepted state-aggregate, lifecycle-successor, and custody roll-up decisions.
The review covered lifecycle and transaction surfaces, secure-record authority,
label and aggregate provenance, committed discovery, retired refusal, selection
pointer compare-and-swap, local deletion holds and receipts, workflow health,
live consumer cutover, real regression tests, and scoped static analysis. S10
and production remediation were excluded.

## Findings

The encrypted record, anchored discovery, existence-only retired refusal,
selection pointer transaction, and local-delete transaction remain internally
coherent. Record reads require a UUID-bound authenticated session; mutations
enforce revision and content-digest compare-and-swap and co-write the encrypted
row with its event. Deletion revalidates legal and filing holds, applies
process-secret and local-session owners with durable receipts, clears the
pointer by compare-and-swap, renames to a transaction-bound deleting path, and
reports local-only retained external state. Workflow health remains
observation-only and current discovery has no manifest parser.

### s09-public-physical-lifecycle-bypass | high | Low-level custody transaction service remains facade-public

`ProfileCustodyTransactionService` is exported from the public
`application.user_profile` facade and declares its own public `create_capsule`,
`prepare_delete`, `confirmation_for`, `execute_delete`, and recovery methods.
Production currently calls it through `ProfileCapsuleLifecycle`, but any live
consumer can import the facade service and invoke physical creation or deletion
without the lifecycle's initial-record, restore-database, or committed-profile
preconditions. This contradicts the binding decision that the lifecycle is the
sole physical writer and leaves a supported bypass rather than an internal
implementation seam.

### s09-public-semantic-replacement-bypass | high | Lifecycle exposes a generic current-record replacement door

`ProfileCapsuleLifecycle.replace_current_record` is a public method accepting a
caller-built `UserProfileRecord`, event type and payload, expected revision, and
content digest. `ProfileRecordRepository` uses it internally, but the method is
available to every lifecycle consumer and can publish arbitrary exact-schema
fact sequences or caller-selected event semantics without going through the
repository's explicit setup-completion and fact-command boundaries. The
semantic repository is therefore not the sole mutation authority and the
decided ban on public generic save or prepared-write escape hatches is not met.

### s09-label-provenance-and-projection | high | Valid label rewrites are accepted without authoritative provenance

The committed repository reads `data/profile-label.v1.txt` after validating the
current marker, but the marker deliberately contains no inventory binding and
the read validates only no-follow regular-file shape, UTF-8, and label syntax.
A post-publication attacker can replace the label bytes with a different valid
canonical label; listing and exact-label selection then accept the substituted
value. Stage-time journal inventory verification does not authenticate later
reads. `CommittedProfileView` carries no label revision/digest/source witness
that could expose this drift, and it implements neither the decided locked
typed-unavailable projection nor an unlocked record-revision/content-digest
projection. Thus label selection lacks canonical provenance and the aggregate
does not satisfy the accepted locked/unlocked projection contract.

Verification evidence: the integrated custody, transaction, record, lifecycle,
workflow discovery, and health selector passes 92 tests in 43.19 seconds; the
focused record/repository selector passes 11 tests in 8.35 seconds. Scoped Ruff
and Ty pass, and BasedPyright reports zero errors and warnings. These gates show
the covered paths work but contain no adversarial valid-label substitution or
public-surface authority test. Verdict is **FAIL** with three HIGH findings;
S09 remains unchecked.

## Recommendations

Remove `ProfileCustodyTransactionService` from facade exports and make its
physical verbs an internal lifecycle implementation seam. Add a public-surface
negative test proving consumers can reach only `ProfileCapsuleLifecycle` for
create, restore, selection, and deletion.

Make record replacement internal to the collaboration between the physical
lifecycle and `ProfileRecordRepository`; the public lifecycle must not accept a
caller-built replacement or event. Retain only explicit semantic commands with
revision and digest compare-and-swap, and add a facade/method negative test.

Give the mutable label owner a strict UUID-bound, revisioned, self-digested and
collision-serialized projection record, or another accepted provenance scheme
that authenticates every label read without changing the intentionally minimal
commit marker. Initial label publication must remain ordered with capsule
creation and refusal must leave neither authority visible alone. Add a real
post-publication valid-label substitution test, stale/concurrent label CAS
tests, and projection tests for locked typed-unavailable fields and unlocked
record revision/content-digest provenance. Do not repair this by treating
capsule data bytes or the aggregate as a second authority.

## Final remediation re-review

The two public-writer findings are closed. The low-level transaction class is
now the private `_ProfileCustodyTransactionCapability`, is absent from the
facade, and has no production consumer except `ProfileCapsuleLifecycle`.
`replace_current_record` is absent; the lifecycle exposes only a private
`_replace_record_for_profile_command` collaboration used by the explicit
semantic repository commands. A public-surface test verifies both removals.

The projection shape is also improved: locked views carry explicit
`UNAVAILABLE_LOCKED` fact and setup-state values, and `load_unlocked` requires
the current authenticated record session before exposing setup state, fact
count, record revision, and content digest. Label mutation is serialized by the
root-then-profile lock and compares the expected revision and content digest;
the real two-profile concurrency test admits one collision winner and refuses
the other.

### s09-label-self-authentication-has-no-trusted-head | high | Same-UUID valid substitution remains accepted

The label finding is not fully closed. The replacement file now carries UUID,
revision, previous digest, content digest, and self digest, but every one of
those values is caller-computable from the same replaceable bytes.
`load_committed_profile_custody_label_record` validates only that internal
self-consistency and the requested UUID; it compares neither revision nor
digest against a separately authoritative current head. An actor can construct
`ProfileCustodyCapsuleLabel.create(profile_id=<same UUID>, label=<different
valid label>, label_revision=1)` and replace `profile-label.v1.json`; listing
and exact-label selection accept it. The new substitution test copies the
second profile's record into the first profile and therefore proves only that a
different UUID is refused. It does not test a freshly canonical, same-UUID
substitution. The view also omits label revision, content digest, self digest,
and source provenance, so callers cannot carry the decided label witness even
when the official CAS path was used.

Verification evidence: the integrated custody, transaction, record, lifecycle,
workflow discovery, and health selector passes 96 tests in 40.12 seconds; the
lifecycle/label selector passes 8 tests in 7.95 seconds. Scoped Ruff and Ty
pass, and BasedPyright reports zero errors and warnings. These gates establish
official-path CAS and cross-UUID refusal but not same-UUID valid substitution.
Verdict remains **FAIL** with one HIGH finding; S09 stays unchecked.

## Final remediation recommendation

Anchor the accepted label revision and digest in an independently verified
current-head authority rather than relying on hashes stored only inside the
replaceable label record. Every locked repository read must compare the label
record to that head before returning it, and rename must atomically/CAS advance
the record and head under the existing root-then-profile lock with crash
recovery for either publication order. Add a real same-UUID forged canonical
record replacement test, plus head/record tear tests. Carry label revision,
content digest, self digest, and explicit provenance source in both locked and
unlocked `CommittedProfileView` forms. Preserve the minimal commit-marker
contract and do not require record decryption for locked listing.

## Governed label-head re-review

The final HIGH is closed. The label record is now checked against an
independent `ProfileLabelHead` stored outside the capsule. Repository reads
acquire the canonical root-then-profile lock, load the committed creation
journal named by the marker transaction, and require its exact revision-one
label, content digest, self digest, UUID, operation, and journal digest as the
initial reconstruction witness. Missing initial authority can therefore be
reconstructed only from the durable transaction that published that capsule;
a later-revision label with no head is refused.

Rename holds the same lock order, checks expected label revision and content
digest, performs collision preflight, writes a bounded canonical pending
advance containing the exact old label/head and next label/head, CAS-replaces
the label bytes, and deterministically advances or clears the head. Recovery
accepts only the three attributable durable combinations: old label plus old
head, new label plus old head, or new label plus new head. Every mixed or
unrelated state refuses. The real subprocess crash test proves recovery after
the label replacement but before head publication, and the sibling concurrency
test proves one collision winner.

The adversarial test now constructs a fresh canonical same-UUID next label with
valid internal revision and digest lineage and replaces the capsule member
without advancing the governed head. Locked repository loading refuses it as
different from the trusted head. Both locked and unlocked
`CommittedProfileView` projections now carry label revision, content digest,
self digest, and source witness; unlocked facts additionally carry the
authenticated record revision and content digest, while locked facts remain
explicitly unavailable.

The earlier public-authority closures remain intact: the low-level transaction
capability is private and has only the lifecycle as a production consumer, and
the generic lifecycle record replacement method remains absent. Exact scoped
negative searches find no retired service, replacement method, manifest
reader/writer, status/tombstone compatibility, integrity exception, provider,
or keyring side authority.

Verification evidence: the proportional custody and authority selector passes
42 tests in 41.51 seconds; the lifecycle and record selector passes 18 tests in
13.14 seconds, including same-UUID forgery and crash recovery. Scoped Ruff and
Ty pass, and BasedPyright reports zero errors and warnings. Broader collection
is independently blocked by the peer-owned missing `StrEnum` import in
`domain/modelos/_calculation_revision.py`; that unrelated failure is neither
counted as S09 evidence nor attributed to this review.

Final verdict: **PASS**. No CRITICAL or HIGH finding remains attributable to
`W02.P03.S09`. One S09 execution record and the canonical S09-only plan check
are authorized; S10 remains out of scope.
