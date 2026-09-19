---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:16423d94c5a91b075f2fd62411d804739e3938e9e66668967a0e976333b98d74'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S05 journal, pointer CAS, and local deletion review`

## Scope

Independent review of `W01.P02.S05` only: bounded canonical creation and deletion journals, root-before-profile locking, captured-byte pointer compare-and-swap and recovery, current-capsule no-follow inventory, legal and filing-hold preflight, target-bound confirmation, atomic rename to a transaction-owned tombstone, owner receipts, idempotent crash recovery, local-only scope, retained-external-state reporting, taxonomy and error authority, and real-behavior tests against the accepted custody decisions and binding plan. This review does not authorize production edits, plan closure, Git operations, product storage, remote or service state, or `W01.P02.S06`.

## Findings

### tombstone-identity | high | Recovery can delete an arbitrary pre-existing directory instead of the prepared capsule

In `ProfileCustodyTransactionService._resume_delete`, the `POINTER_CLEARED` branch accepts an existing tombstone when it is merely a real directory. It does not prove that the source capsule is absent, that the tombstone commit marker names the journal profile UUID, or that its exact inventory equals the journal witness. A preplanted directory at the caller-selectable transaction tombstone name therefore bypasses the atomic capsule rename and is recursively removed while the prepared capsule remains. Recovery must recognize only the exact transaction-owned post-rename state: source absent, no-follow tombstone marker UUID valid, inventory equal to the journal, and no ambiguous source-plus-tombstone combination.

### windows-inventory | high | Windows inventory traversal does not anchor nested directories

`_inventory_windows_directory` anchors only the capsule root. It lstat-checks a nested directory and then recursively traverses that child by path without holding a no-delete, no-reparse handle for the child and every ancestor. A hostile replacement between the check and recursion can redirect inventory through a junction or reparse directory. The leaf handle does not repair an already redirected ancestry. Apply the component-wise Windows anchoring discipline from S04 to every directory level and read each leaf from its exact verified handle; add real nested junction/reparse and concurrent-substitution proofs.

### deletion-owners | high | Local deletion omits required secret and session owner steps and receipts

The accepted deletion sequence revokes process secrets and deletes local session acceleration before pointer clearing and capsule removal. The candidate owns only one `application-local-custody` receipt and invokes neither owner. A successful return can therefore leave the deleted profile's DEK/session usable in memory or accelerated locally while claiming completion. Add explicit application-owned owner steps in the journal state machine, each with durable idempotent receipts, fail-closed recovery, and tests for crashes before and after every owner receipt. External state must remain report-only.

### create-journal-binding | high | Create recovery ignores its staged path and proposed generation

`prepare_create` records `staged_relative_path` and `proposed_generation`, but `_current_create_inventory` consults only the final UUID capsule and compares only its inventory digest. It never reconciles the recorded sibling stage and never validates the committed password-envelope generation. An independently published or replayed capsule with matching inventory bytes can satisfy the journal and cause pointer publication even though it is not the transaction's proposed stage/generation. Bind recovery to the named stage/final publication identity, transaction UUID, envelope generation and digest, and refuse every stage/final ambiguity before exact-byte pointer CAS.

### hold-authority | high | Destructive hold authorization is a caller-authored assertion

`prepare_delete` accepts `ProfileCustodyHoldAssessment(legal_hold=False, filing_hold=False)` from any caller and immediately persists it as authorization. No canonical legal-hold or filing-hold owner is queried, no source evidence is bound, and the test helper manufactures the clear result. This makes the preflight bypassable by construction. The service must obtain or verify current hold evidence from the canonical application owners under the transaction locks, persist its provenance and immutable target context, and revalidate it before destructive execution according to the accepted policy.

### journal-filesystem | high | Journal and receipt paths are check-then-open on Windows and path-raceable on both platforms

The repository checks roots and leaves with `is_link_like` and then performs path-based opens or atomic replacement. On Windows `O_NOFOLLOW` is unavailable, so a reparse leaf can redirect `_read_bounded` and `_write_exclusive`; root checks do not pin ancestry against substitution. On POSIX the parent is likewise not descriptor-anchored across leaf operations. Strict canonical bytes do not protect a record read from or written to the wrong filesystem object. Use component-wise no-follow directory handles and exact leaf handles for create, read, replace, and receipt idempotency, with root and leaf reparse/link plus race tests.

### verification-depth | high | Focused tests do not prove the destructive state machine or concurrency contract

The seven tests construct capsule layout manually rather than publishing through the production capsule owner, do not test journal or receipt canonical parsing, duplicate or unknown members, byte limits, reparse roots/leaves, lock contention/order, wrong confirmations, source-plus-tombstone ambiguity, tombstone inventory mismatch, receipt-before-journal crash, removal-before-journal crash, session-owner failures, external-call absence, or create stage/generation binding. The two crash tests manually place one state and do not adversarially exercise the pointer-CAS-before-journal and rename-before-journal windows with both valid and hostile combinations. Add real production-path filesystem and sibling-process tests for every state transition and crash boundary.

### hold-authority-rereview | high | Missing hold evidence is still converted into permission to delete

The remediation introduces `ProfileCustodyHoldAuthority`, but `assess` creates and persists a fresh `legal_hold=False`, `filing_hold=False` assessment whenever the evidence file is absent. Absence of authoritative legal and filing evidence is therefore treated as proof that no hold exists. Its public `record` method also accepts any caller-constructed assessment. This remains fail-open destructive authorization, only moved behind a new class. Missing evidence must refuse deletion; the authority must derive its result from canonical filing/legal owners or require their independently authenticated durable attestations, and arbitrary callers must not be able to mint a clear assessment.

### retired-session-owner | high | New deletion code imports the retired shared-master session provider

`_revoke_process_secrets` imports `active_bucket_session_serves`, `close_active_bucket_session`, and `close_live_bucket_sessions_for_bucket` from `adapters.persistence.storage.master_key`. This creates a new current-format dependency on the provider family the accepted hard cutover requires removed, and will obstruct the later deletion Step. The S05 owner must revoke the current per-profile custody/session authority through its canonical facade. If the final bounded-DEK session owner does not exist until its planned Step, define an application-owned revocation seam now that can operate without importing retired custody, then integrate its current implementation later; do not bridge through `master_key`.

### pointer-filesystem-rereview | high | Captured-byte CAS still follows link and reparse pointer paths

`ProfileCustodyPointerSnapshot.capture` delegates to core `capture_pointer`, whose `Path.read_bytes` follows a substituted pointer leaf or ancestor. `compare_and_swap_profile_pointer` then delegates replacement/clear to path-based `restore_pointer`. Root/profile locks coordinate compliant writers but do not make hostile filesystem substitution safe. The accepted S05 boundary requires exact captured-byte CAS under the same no-follow threat model as journals and capsules. Add an anchored pointer capture/CAS primitive that refuses root and leaf links/reparse points, compares the exact locked object, and atomically clears or replaces only that witness; prove leaf/parent substitution and the CAS-before-journal recovery window.

### journal-write-rereview | high | Journal, receipt, and hold writes remain check-then-path operations

The remediation centralizes reads through `read_profile_custody_local_record`, but `_write_exclusive`, `_write_replace`, and `_write_canonical_file` still check parents with `is_link_like` and then use path-based `os.open` or `atomic_write_hardened_bytes`. On Windows `O_NOFOLLOW` is absent for exclusive create; on both platforms the parent can be substituted after the check. The added link tests exercise static links, not a concurrent parent/leaf race. Use descriptor-relative POSIX creation/replacement and component/leaf handle-anchored Windows creation/replacement with durable parent metadata, or expose a canonical storage primitive that provides those guarantees, then prove substitution refusal.

### remediation-progress | medium | Tombstone, inventory, create binding, and owner state ordering are materially improved

The stable remediation correctly rejects source-plus-tombstone ambiguity, binds a deletion marker to profile UUID, transaction UUID and prepared inventory, inventories tombstones before removal, recursively anchors Windows inventory directories, validates create transaction UUID, stage name, envelope generation and inventory digest, and orders idempotent owner receipts before pointer CAS. The expanded focused suites pass 22 tests and Ruff, ty and basedpyright are clean. Those improvements close the original tombstone, Windows inventory and create-journal findings, but the destructive hold authority, retired session dependency, pointer filesystem boundary and record-write race findings above remain high severity.

### windows-no-replace-final-rereview | high | Windows publish-once records can overwrite a raced destination

`write_profile_custody_local_record(..., publish_once=True)` pins the Windows ancestry, checks `os.path.lexists(path)`, and then calls `atomic_write_hardened_bytes`, whose publication is a replacing write. A destination created after the check is therefore replaced instead of producing the required collision refusal. This boundary creates journals and immutable owner receipts, so the race can change transaction identity and make an unperformed owner step appear complete. Implement Windows publish-once through an exclusive `CreateFileW(..., CREATE_NEW, ...)`/exact-handle durable write or a native no-replace handle rename rooted under the pinned parent; never compose no-replace from a path existence check plus replace. Add a real sibling-process collision race that proves one winner, one refusal, and byte preservation.

### deletion-owner-effect-final-rereview | high | Owner receipts attest effects that the current authorities cannot perform

The retired provider imports are gone, but `ProfileCustodySessionAccelerationAuthority.clear` is an unconditional no-op and `_CURRENT_PROCESS_SECRETS` has no registration path or consumer outside this new module. Deletion nevertheless writes successful durable receipts for both owners. The test proves only that receipt files exist; it never establishes a real current secret/session, observes zeroization/removal, or interrupts between effect and receipt. A receipt must attest a real idempotent owner effect, not a placeholder. Wire the authorities to the actual current custody secret/session owners, or bind a distinct verified-absence result when that owner truly has no artifact; then test real enrollment/unlock/session state, zeroization/removal, and recovery before and after each receipt.

### lock-path-and-concurrency-final-rereview | high | Root-profile serialization is path-following and remains unproven under contention

`profile_custody_transaction_lock` creates the capsule directory and passes path-derived targets to the generic `exclusive_file_lock`; that primitive creates its sidecar with path-based `mkdir` and `os.open` and no no-follow or reparse ancestry protection. A linked/reparse storage root or capsule directory can redirect the lock, and aliasing can give concurrent transactions different lock identities. The S05 tests contain no sibling-process proof of root-before-profile blocking, release after failure, or concurrent pointer/journal recovery. Move the transaction locks behind a custody-specific anchored lock primitive (descriptor-relative on POSIX and pinned component/exact-handle on Windows), reject linked/reparse ancestors, and add real sibling-process tests covering global-before-profile ordering, contention, crash release, and concurrent CAS/recovery.

### hold-producer-final-rereview | high | The deletion path still has no production authority capable of issuing hold evidence

Missing evidence now correctly refuses and arbitrary callers can no longer call a public recorder, closing the fail-open branch. However, the only producer is the private `_record_authoritative` method, and repository search finds it used only by S05 tests through `service._holds`; production has no legal/filing owner integration that can create or refresh the evidence. Consequently the successful deletion path is reachable only through a private test backdoor, while the test authors the very assertion under test. Connect assessment to the canonical legal and filing owners under the transaction locks, with durable provenance and freshness, and exercise that public production route. If those owners do not yet exist, S05 must remain fail-closed and cannot claim a successful held-preflight/deletion implementation.

### final-gate-evidence | info | Focused runtime and static gates are green but do not discharge the remaining safety findings

The final independent run completed 25 focused custody/S05 tests in 34.67 seconds. Ruff and ty passed, and basedpyright reported zero errors and warnings for the changed transaction and capsule surfaces. The clean gates establish ordinary-path consistency; the absent real collision, owner-effect, hold-producer and sibling-process lock proofs leave the high-severity findings above open.

### final-remediation-closures | info | Windows no-replace, owner effects, and anchored custody locks now satisfy their reviewed contracts

The frozen reconciliation moves the shared custody filesystem operations into the canonical `_filesystem.py` surface used by S05, implements Windows publish-once with an exclusive create under pinned ancestry, and proves one real sibling-process winner without overwrite. Root-before-profile locks now use custody-owned no-follow kernel locks, reject a real reparse capsule root, serialize different profiles at the root lock, and release after process death. Deletion now invokes the existing application session owner: the tests create a real live session and persisted session record, then prove live sealing, active-reference clearing, persisted removal, effect-bound receipts, verified absence, and replay. These changes close `windows-no-replace-final-rereview`, `deletion-owner-effect-final-rereview`, and `lock-path-and-concurrency-final-rereview`.

### pointer-cas-concurrency-final-rereview | high | Captured-byte pointer CAS is still a check followed by an independently replaceable write

`compare_and_swap_profile_pointer` captures the pointer through the anchored custody reader, compares it with the journal witness, and only afterwards calls the replace or clear primitive. The custody root/profile locks do not coordinate the existing active-pointer transaction owner, which locks the pointer through a different generic sidecar. An independent compliant pointer transaction can therefore publish after the equality check and before S05 replacement, and S05 will overwrite or unlink those independently changed bytes. This violates the accepted exact-CAS rule that recovery never overwrites an independently changed pointer. Unify all active-pointer writers on the custody transaction lock before enabling S05, or implement a platform-native exact-object/version CAS that couples comparison and publication; add a real sibling-process interleaving proof where a writer wins after capture and deletion/create recovery must refuse without changing its bytes.

### hold-producer-authority-final-rereview | high | Public hold producers still persist caller-selected dispositions without reading their named source records

The candidate separates legal and filing evidence and revalidates both fail-closed before destruction, but `refresh_from_legal_record` and `refresh_from_filing_record` each accept an arbitrary source-record string and caller-selected `cleared` or `held` disposition. Neither method loads, authenticates, or evaluates the named legal/filing record. The successful test path therefore still manufactures two clear assertions directly, now through public wrappers, so any deletion caller can mint the evidence that authorizes its own destructive request. Each producer must derive disposition from its canonical owner record or consume an independently authenticated owner attestation that callers cannot forge; tests must create actual legal and filing owner records and prove their production projections, including held, absent, stale/replaced, and clear cases.

### frozen-rereview-gates | info | Reconciled focused runtime and static gates are green

The independent frozen-candidate run completed 53 S05 and custody tests in 37.90 seconds. Ruff and ty passed, and basedpyright reported zero errors, warnings, or notes across the reviewed transaction and custody surfaces. These gates confirm the landed no-replace, lock, and owner-effect implementations, but they do not exercise the independent-pointer-writer interleaving or establish non-forgeable legal/filing source authority.

### pointer-cas-final-closure | info | Production pointer writers and custody CAS now share one re-entrant root lock

The refrozen candidate routes every production active-pointer mutation through `active_profile_pointer_transaction`, which now acquires the same anchored `profile_custody_root_lock` used internally by custody CAS. The lock is re-entrant only for the same root, process, and thread. The spawned-writer test proves the sibling cannot enter between comparison and mutation, then proves its later write wins and a stale subsequent CAS refuses without changing those bytes. This closes `pointer-cas-concurrency-final-rereview`.

### hold-source-mint-final-rereview | high | The new owner-record facade still lets any caller author the destructive disposition

Hold evidence now binds the strict canonical owner-record digest and execution revalidates source drift, but the source record itself is publicly constructible through `ProfileCustodyHoldOwnerRecord.create(disposition=...)` and publicly writable through the facade-exported legal and filing record repositories. The S05 tests use exactly those APIs to mint `cleared` records. Moving the caller-selected outcome one record upstream therefore does not establish an independent authority or satisfy the asserted no-caller-mint property; the test claiming no invention simultaneously calls the minting surface. The legal and filing owners must derive the deletion disposition from their actual canonical domain facts, or issue a capability/authentication-bound attestation unavailable to the deletion caller. The custody facade should consume only a read/projection interface and must not export owner-record construction or mutation. Prove the boundary through real owner workflows and a negative test that the deletion-facing API cannot create or alter either source disposition.

### refrozen-final-gates | info | Pointer regression and custody gates pass on the refrozen candidate

The independent refrozen run completed 56 S05 and custody tests in 41.09 seconds plus 17 orchestration and login pointer-regression tests in 9.44 seconds. Ruff and ty passed; basedpyright reported zero errors, warnings, or notes. An earlier command named a nonexistent pointer-test module and consequently collected zero tests; it was discarded and replaced by the successful concrete orchestration/login run above.

### hold-authority-final-closure | info | Custody now consumes independently derived legal and filing owner projections

The final candidate removes the custody hold-owner record constructors, repositories, disposition refresh methods, and `ProfileCustodyHoldEvidence.create`; none is exported from the user-profile facade. Legal ownership persists bounded canonical open-case snapshots and derives blocking solely from whether canonical open case identifiers exist. Filing ownership accepts profile-bound real `ModeloRecord` inputs and delegates erase blocking to the domain retention-floor authority. Custody dynamically consumes only their read projections, binds each canonical source digest, refuses absent or corrupt facts, and reprojects both owners before destructive execution so source drift refuses. Real tests cover absent facts, an open legal case, a retention-bound filing, post-preflight filing drift, clear facts, facade non-exports, and the absent evidence constructor. This closes `hold-source-mint-final-rereview` and the prior hold-authority findings.

### s05-pass-attestation | info | No critical or high finding remains in the final S05 candidate

The independent final run completed 23 transaction tests in 23.70 seconds, the combined 56-test S05 and custody lane in 41.58 seconds, and 17 orchestration/login pointer regressions in 12.32 seconds. Ruff and ty passed, and basedpyright reported zero errors, warnings, or notes across the reviewed hold and transaction surfaces. All previously recorded critical/high concerns have been remediated and independently adjudicated; `W01.P02.S05` is approved for executor-owned execution record creation and canonical plan checking.

## Recommendations

PASS. No critical or high finding remains. The executor is authorized to create the `W01.P02.S05` execution record and check the Step through the canonical VaultSpec command. This review does not authorize production changes or beginning `W01.P02.S06`.
