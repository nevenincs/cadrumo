---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:18d118328482f7de2e86206cf59789246cfb5886e1ff02ca26af03e734bafd16'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S07 committed capsule lifecycle review`

## Scope

Independent review of `W02.P03.S07` against the approved custody roll-up ADR and
the completed S01-S06 execution and audit evidence. The review covered the
committed-capsule aggregate and repository, the lifecycle service, facade
exports, the custody inventory seam, focused real-filesystem tests, and the
production consumers of the replaced public repository, aggregate, and
lifecycle contracts. S08, S09, production remediation, and plan mutation were
excluded.

## Findings

### s07-incomplete-public-cutover | high | Replaced public contracts break live application paths

The new `ProfileRepository`, `ProfileAggregate`, and `ProfileLifecycleService`
are coherent in isolation, but they replace existing facade-exported types in
place without migrating their production consumers. `_orchestration.py` still
constructs `ProfileRepository` with `secure_objects` and `schema`, constructs
`ProfileLifecycleService` with `repository`, `validator`, and `events`, and
calls removed `create`, `delete`, `reactivate`, `complete_setup`, `select`, and
`rename` repository methods plus removed `read` and `edit_fields` lifecycle
methods. Calculation, filing, wizard, overview, modelo-work, and configuration
CLI consumers still require the removed aggregate `record` or `status` fields.
A direct BasedPyright gate over the changed surface and representative live
consumers reports 86 errors, including each of these contract breaks. Thus the
normal application cannot use the refrozen S07 surface even though its two new
focused tests pass.

### s07-duplicate-lifecycle-authority | high | Retired record and manifest writers remain live beside the new sole writer

`UserProfileLifecycleRepository` remains facade-exported and production-wired
through `_orchestration.py`, with live `save` and `delete` mutation surfaces.
The same orchestration module continues to describe and execute manifest,
secure-object record, pointer, tombstone, reactivation, setup-completion, and
rename flows outside the new custody lifecycle service. This is not merely a
downstream read-model dependency: it leaves multiple active lifecycle writers
and retired bucket/manifest authority in the exact application boundary S07 is
required to make capsule-only and single-owner.

### s07-label-collision-publication | high | Duplicate labels can publish committed capsules before becoming ambiguous

`ProfileLifecycleService.create` and `restore` publish the immutable capsule
before `ProfileRepository.set_label`, while `set_label` performs no exact-label
collision preflight or serialized uniqueness check. Two committed UUIDs can
therefore receive the same label and both operations report success; subsequent
label resolution refuses because it finds multiple matches. This regresses the
existing duplicate-label refusal contract and cannot be repaired by a check
after capsule publication. The focused tests cover one successful label only
and do not exercise sequential or concurrent collision.

### s07-inventory-root-follow | high | Capsule discovery enumerates a followed storage-root directory

`list_current_profile_custody_capsule_ids` begins with `Path.is_dir()` and
`Path.iterdir()` on the capsules root. Both follow a symlink or reparse point at
that root before per-candidate current-format recognition applies its anchored
checks. Although a candidate may later be refused, discovery has already
traversed and enumerated an attacker-selected external directory. The sole
application inventory seam therefore does not preserve the established
no-follow storage boundary, and the two focused lifecycle tests contain no
root-link/reparse case.

Verification evidence: the focused lifecycle plus custody transaction selector
passes 29 tests in 28.45 seconds and scoped Ruff passes. Those green gates prove
the isolated happy path and transaction regression only. The production
call-graph BasedPyright gate fails with 86 errors attributable to the S07 public
contract replacement; no unrelated collection failure was involved in that
result.

## Recommendations

S07 remains open. Complete one hard cutover rather than adding compatibility
shims: migrate every production constructor, method call, and aggregate-field
consumer to the capsule-backed boundaries; remove the retired lifecycle writer
and manifest/bucket mutation routes from production composition and the facade;
then run static analysis across the entire affected call graph and real
application lifecycle tests, not only the new module.

Make label uniqueness an application-owned, root-serialized precondition that
is proven before capsule publication for create and restore. Add real sequential
and sibling-process collision tests that prove a refused duplicate leaves no
new capsule, projection, journal ambiguity, or pointer change.

Replace root discovery with the canonical descriptor-relative POSIX and
ancestor-pinned Windows directory primitives, refusing a linked/reparse
capsules root before enumeration. Add real root symlink/reparse tests and retain
the current-format marker validation for every UUID candidate.

## Stable-candidate re-review

The re-review closes the original duplicate-writer and root-follow findings:
the mixed orchestration module and live fact repository were removed, current
fact consumers use the session-bound record repository, and capsule-root
enumeration delegates to the anchored custody primitive. Label uniqueness is
now root-serialized, the label is staged and inventory-bound with the capsule,
and corrupt label state fails closed. The original public-cutover finding is
improved but remains open through the compatibility finding below.

### s07-record-storage-event-authority | high | Current facts bypass the decided secure-object database and lose event history

The amended state ADR requires one encrypted row in the profile-local
secure-object database and an atomic record-plus-bucket-event transaction. The
candidate instead stores a custom encrypted `profile-record.v1.json` data file.
Each replacement embeds one event in the replacement artifact and atomically
replaces the entire file, so the preceding event is discarded on the next
mutation. The focused test proves only that the latest artifact contains its
latest event; it does not prove durable event history or a database transaction.
This creates a second bespoke persistence and crypto path and cannot satisfy
the canonical fact owner or audit contract.

### s07-record-lineage-cross-binding | high | Artifact revision metadata is not bound back to the decrypted record

`ProfileRecordSession.create_initial` accepts any valid `UserProfileRecord`
without requiring record revision one and an absent predecessor. The artifact
is then stamped as revision one regardless of the record's own revision.
Decode checks UUID and content digest only; it never proves artifact revision
equals `record_revision`, nor that artifact predecessor equals the record's
`previous_record_digest`. A valid encrypted artifact can therefore carry two
contradictory lineage claims and still authenticate. Existing tests construct
the matching happy path but contain no mismatched record/artifact revision or
predecessor cases.

### s07-restore-record-validation | high | Restore publishes caller data without proving the canonical current record

`ProfileCapsuleLifecycle.restore` forwards arbitrary `data_files` directly to
capsule creation. It neither requires exactly one current profile-record member
nor authenticates and decodes that record through a session before
publication. It therefore does not prove current schema, immutable UUID,
record lineage, or envelope/epoch binding, and it can publish a committed
restored capsule with no semantic root or with caller-selected record bytes.
This contradicts the amended restore contract and recreates the
post-publication unusable-profile state the staged record decision forbids.

### s07-retired-lifecycle-compatibility | high | Tombstone and manifest compatibility remains on production surfaces

The old mixed classes are gone, but compatibility remains reachable.
`read_profile_bucket`, `resolve_profile_identifier`, and
`list_profile_buckets` still accept `include_tombstoned` and silently discard
it, while configuration reset, status, and inspection still call that retired
shape. Production custody reconciliation still reads and writes
`BucketManifest.recovery_enrolled`, and other operator surfaces still read
manifest labels. These are not harmless names: they preserve caller contracts
and a competing plaintext projection writer explicitly removed by the hard
cutover. The production negative search also retains tombstone-specific
operator semantics and tests rather than removing their call sites.

Re-review verification: the real profile-record, lifecycle, repository,
registration, and domain selectors pass 20 tests in 10.42 seconds; custody
capsule and transaction selectors pass 40 tests in 49.75 seconds. Scoped Ruff
and Ty pass, BasedPyright reports zero errors and warnings across custody,
profile application/domain code, and representative wizard, calculation,
modelo, filing, and CLI consumers, and representative production imports
succeed. Those results validate type and happy-path integration but do not
close the four authority defects above. Verdict remains **FAIL** with four HIGH
findings; `W02.P03.S07` stays unchecked.

## Stable-candidate recommendations

Store the current record through the profile-local secure-object database
inside staged capsule data and commit every mutation with an append-only bucket
event in the same database transaction. Remove the standalone record-crypto
file and latest-event field rather than retaining parallel authorities.

Cross-validate record revision and predecessor against artifact or database
metadata on both create and read; revision one must be the only initial shape.
Add real wrong-revision, wrong-predecessor, wrong-DEK, ciphertext/AAD tamper,
stale sibling writer, and multi-mutation event-history tests.

Make restore require the one canonical encrypted record from the authenticated
archive and validate its UUID, exact schema, envelope/epoch binding, and
lineage before stage verification and publication. Add missing, duplicated,
wrong-UUID, old-schema, tampered, and valid restore tests.

Delete the `include_tombstoned` compatibility parameters and every production
caller, remove tombstone/reactivation output behavior and fixtures, and remove
all profile lifecycle reads or writes of `BucketManifest`. Discovery and label
consumers must use only committed capsule projections; recovery enrollment
must be queried only from its custody owner.

## Final stable-candidate re-review

The secure-record remediation closes the database, lineage, and restore
findings. The current record is exactly one authenticated secure-object row;
initial creation requires revision one without a predecessor; replacement
cross-binds the custody envelope, password generation, DEK epoch, record
revision, content digest, and predecessor; and the row plus its append-only
bucket event are committed through one repository batch. Restore refuses
arbitrary data members and authenticates the staged database, exact profile
namespace cardinality, schema, UUID, custody binding, revision, predecessor,
content digest, and source event before capsule publication.

### s07-retired-profile-integrity-surface | high | Manifest and tombstone compatibility remains public and consumed

The hard cutover is still incomplete. `_integrity.py` remains production code
whose public contract explicitly treats a plaintext `manifest.toml` status and
label as mirrors of encrypted `UserProfileRecord.status` and
`UserProfileRecord.display_name`, fields that no longer exist in the approved
record schema. `application.user_profile` still facade-exports its
`ProfileIntegrityError`; the wizard checkpoint owner still imports and catches
that compatibility exception and documents manifest-based eligibility; and
the central error registry retains the retired type. The production bucket
event enum also still exposes `PROFILE_TOMBSTONED` and `PROFILE_REACTIVATED`.
No current lifecycle path calls `verify_profile_integrity`, so these symbols do
not provide a working safety gate; they preserve a contradictory public
manifest/tombstone authority and caller contract after the required hard
cutover. This leaves the prior compatibility finding open.

Final verification evidence: the real capsule-record and lifecycle tests pass
11 tests; the corrected custody capsule and transaction selector passes 40
tests in 36.86 seconds; and scoped Ruff, Ty, and BasedPyright are clean. The
initial broader selector matched zero tests under the configured unit-only
selection and was not counted as evidence.

## Final stable-candidate recommendation

Delete `_integrity.py`; remove `ProfileIntegrityError` from the user-profile
facade and error registry; remove the wizard import, catch arm, and manifest
mirror documentation; and remove the unused tombstone/reactivation event enum
members and their obsolete tests. Repeat the production negative search for
`manifest_status`, `manifest_label`, `record_status`, `record_display_name`,
`ProfileIntegrityError`, `PROFILE_TOMBSTONED`, and `PROFILE_REACTIVATED`.
S07 remains unchecked until that hard-cutover residue is absent.

## Final hard-cutover cleanup re-review

The last production compatibility finding is closed. `_integrity.py` is
deleted; `ProfileIntegrityError` is absent from the facade and central error
registry; the wizard checkpoint path imports only `ProfileNotFoundError` and
loads the authenticated current record; and the tombstone/reactivation event
enum members are removed. Exact production searches for the retired exception,
integrity function, tombstone/reactivation members, `include_tombstoned`, old
lifecycle repositories/services, and tombstone/reactivate methods are empty.
The secure-object database, atomic record/event batch, lineage, staged revision
one, authenticated restore, capsule-only discovery, and sole lifecycle-writer
closures remain present in the current implementation.

### s07-current-schema-test-cutover | high | The profile test corpus still constructs the removed record schema

The required hard cutover did not migrate the full profile test corpus. Running
the complete application user-profile suite produces 43 attributable failures
and 196 passes: projection, capability, preflight, presence, overview, and
related tests still construct `UserProfileRecord(display_name=...)`, which the
approved exact-current schema correctly rejects as an extra field. These are
not an unrelated peer collection error and cannot be ignored in favour of the
curated green selectors: they are direct tests of the fact consumers whose
contract S07 changed. A coding step whose authoritative application suite is
red does not yet have current, non-tautological regression evidence.

The integrated custody regression selector also produces one failure and 63
passes. `test_unavailable_canonical_root_has_no_weaker_supervision_fallback`
still expects an absent configured root to fail, while the accepted
first-enrollment lease implementation deliberately materialises that root.
The isolated test repeats the same failure. This is another stale contract
test, not evidence that the current containment behavior passed.

Static validation remains clean: scoped Ruff and Ty pass, and BasedPyright
reports zero errors and warnings. The focused current record/lifecycle selector
passes 11 tests. Those green results do not override the directly attributable
red authoritative suites. Verdict remains **FAIL** with one HIGH test-cutover
finding; S07 stays unchecked.

## Final hard-cutover cleanup recommendation

Migrate every affected user-profile test to construct the exact-current
`UserProfileRecord` schema without `display_name`, using production models and
fact inputs rather than a compatibility helper, fake, or mirrored business
logic. Preserve each test's existing projection/capability/preflight assertion.
Update the KDF unavailability test to create a genuinely unavailable canonical
root condition (for example, a non-directory or otherwise refused anchored
parent) while retaining the accepted first-enrollment creation case. Then rerun
the complete application user-profile suite, the custody adapter/transaction
suite, the focused lifecycle suite, and static gates before re-review.

One stale non-runtime workflow docstring still claims profile discovery scans
`buckets/*/manifest.toml`; the implementation uses committed-capsule
projections. Correct that documentation during the same cutover cleanup, but it
is not itself a runtime authority finding.

## Test-cutover remediation re-review

The final HIGH is closed. The complete application user-profile suite now
passes 237 tests. Its only two failures are independently attributable to the
external Modelo 202 registry review gate: five legal references used by
revision `2025-y-siguientes` remain `agent_reviewed`, while filing-grade
snapshot construction correctly requires `operator_reviewed`. Both failures
occur before the tested user-profile preflight behavior and are not caused by
the S07 record, repository, lifecycle, or test cutover.

All former `display_name` constructions are absent from the affected
application, domain, and custody test trees. Exact searches also find no
retired integrity exception/function, tombstone/reactivation event, old status
enum, `include_tombstoned`, legacy lifecycle repository/service, or
tombstone/reactivate method in production or the scoped S07 tests. The test
trees contain no fake, stub, mock, monkeypatch, skip, or expected-failure use;
the only search matches are prose explicitly documenting their absence or why
real behavior is required.

The KDF regression is corrected with two real behaviors in one test: an absent
first-enrollment root is created and successfully used, while a configured root
below a real non-directory parent fails closed with
`KDF_SUPERVISION_UNAVAILABLE`. The custody adapter plus transaction selector
passes 64 tests, and the current record/lifecycle selector passes 11, providing
75 passing custody/lifecycle tests. The focused record, lifecycle, repository,
and registration selector passes 11 tests. Scoped Ruff and Ty pass,
BasedPyright reports zero errors and warnings, and representative imports of
the lifecycle, record repository, committed repository, discovery projection,
and current domain record succeed. A separately attempted domain selector
matched zero tests under the configured marker and is not counted as evidence.

The workflow documentation now describes committed-capsule projections; the
only scoped `manifest` search match is the lifecycle statement that it never
writes manifests. The previously closed secure-object row plus append-only
event transaction, custody lineage cross-binding, staged revision-one create,
authenticated exact-record restore, label and UUID projection, sole lifecycle
writer, capsule-only discovery, session binding, and hard consumer cutover
remain intact.

Final verdict: **PASS**. No CRITICAL or HIGH finding remains attributable to
`W02.P03.S07`. The executor is authorized to create exactly one S07 execution
record and canonically check S07 only. S08 and S09 remain out of scope.
