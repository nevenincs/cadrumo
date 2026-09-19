---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:750f40e5e599593b7689aa9585955a9150e0aeb405e6c20cf683c294db906232'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S03 KDF supervision review`

## Scope

Independent review of S03 finite-grid Argon2id calibration, canonical cross-process leasing, supervised child containment, strict framed IPC, envelope-bound sentinel proof, deadline and reaping behavior, ratchet proposals, public exports, and real-process tests against the accepted custody decisions and plan verification contract.

## Findings

### calibration-timeout | high | A slow strongest candidate collapses calibration directly to the fixed fallback

`calibrate_profile_kdf` stops the entire strongest-first search on the first sample `TimeoutError` and returns the fixed 64 MiB, t=3, p=1 fallback. A two-second timeout only establishes that the current point is too slow; weaker eligible grid points can still meet the 250-500 ms target. This violates the accepted finite-grid selection rule and can enroll a materially weaker fallback even when a stronger measured point is available. Continue the ordered search after a per-point sample timeout while preserving the 15-second total deadline, and use the fixed fallback only after the eligible grid has been exhausted or the total deadline prevents further measurement.

### cross-process-lease | high | The concurrency lease is process-local and permits unbounded sibling KDF workers

`_KDF_LEASE` is a `threading.BoundedSemaphore`, so each Cadrumo process owns an independent permit. Concurrent CLI or application processes can therefore each launch a worker with a one-GiB memory ceiling, defeating the accepted global/cross-process resource boundary and allowing local memory exhaustion. Replace or compose it with an application-owned cross-process lease whose acquisition obeys the same deadline and whose stale-owner recovery cannot create permanent denial.

### sentinel-authority | high | Caller-selected sentinel metadata does not prove the required profile and epoch binding

`unlock_profile_custody` accepts the sentinel ciphertext, associated data, and expected plaintext as unconstrained caller arguments; `_verify_sentinel` only authenticates those supplied values. The adapter never constructs or validates the required binding to product, profile UUID, `dek_epoch`, data-format version, and sentinel purpose. A caller can therefore authenticate a valid DEK against an unrelated or weakly labelled sentinel and receive `ProfileCustodyUnlock`, so the parent proof is not the accepted capsule identity proof. Make the sentinel record and canonical AAD derivation part of the custody contract and derive the expected proof from the envelope/capsule identity rather than accepting arbitrary proof metadata.

### supervision-proof | high | Required containment and failure paths are neither self-proved nor covered by real tests

The worker emits the constant ready frame before processing a request, but that frame carries no evidence of its Job Object membership or POSIX limits. On Windows the parent starts the child before `AssignProcessToJobObject`; if assignment fails, `_launch_worker` closes the unassigned job and drops the live `Popen` without explicit termination or reaping. The focused tests exercise only ordinary calibration, unwrap, password/sentinel failure, a proposal, and one tiny deadline. They do not prove ready-before-secret ordering, malformed or oversized frames, sanitized environment and neutral cwd, exact inherited handles or file descriptors, Windows Job limits and assignment failure, POSIX process group/rlimits/close-from, child escape, sample/total deadlines, five-sample median behavior, cross-process leasing, forced termination, or reaping. S03 therefore lacks the plan-mandated evidence for its security boundary. Contain Windows launch so the child cannot execute outside the assigned job, make readiness attest the established boundary, and add real subprocess/OS proofs for every required failure and cleanup route before closure.

### remediation-disposition | high | Two supervision-boundary gaps still block S03 closure

The calibration-timeout and sentinel-authority findings are remediated: a per-point timeout now records an incomplete candidate and continues unless the total deadline has expired, while the strict sentinel record, envelope-derived AAD, fixed plaintext proof, UUID, epoch, data-format version, and purpose are verified before returning the DEK. Windows assignment failure now kills and reaps the launched process, handle inheritability is cleared, readiness is accepted only after exact Job membership or POSIX process-group verification, and successful responses require clean worker exit and EOF. However, `profile_kdf_lease` calls `resolve(strict=True)` on an arbitrary caller-supplied `lease_root`; it does not derive or verify the one canonical installation/storage root. Two processes can pass different existing directories and each acquire a distinct `profile-kdf.v1.lock`, so the global concurrency invariant remains bypassable. In addition, the revised real tests still do not prove Windows handle-list exclusivity, Job limits and assignment-failure cleanup, POSIX rlimits/close-from/exact `pass_fds`, sanitized environment and neutral cwd, child-process escape containment, per-point timeout continuation under the real supervisor, total-deadline termination, or failure-path tree reaping. The process-local lease defect is fixed only when all callers happen to choose the same path, and the original supervision-proof finding remains open without the mandated OS-specific evidence. S03 therefore still has unresolved high findings and must not close.

### final-remediation-disposition | low | No unresolved critical or high finding remains in S03

The final revision closes both remaining high findings. `profile_kdf_lease` no longer accepts a path: it derives the sole lock owner from `storage_path(StorageCategory.BUCKETS, settings).parent`, and the real sibling-process test proves contention plus operating-system release after owner death against that same core-resolved root. Before accepting readiness, the parent now verifies the exact neutral cwd and allowlisted environment, POSIX rlimit and descriptor attestation plus process-group identity, or Windows Job PID membership and read-back CPU, memory, process-count, and kill-on-close limits; inherited transport handles are cleared after launch, assignment failure terminates and reaps, process-tree escape is refused or killed, deadline failure reaps, framed replies require one bounded frame followed by clean child exit and EOF, and no weaker fallback exists. Calibration still discards an individually timed-out point and continues until the total deadline, sentinel proof remains strictly envelope-bound with the S04 publication seam, and only a 32-byte DEK can cross the result channel. The focused real-process module passed all 17 tests on Windows. The POSIX assertions are platform-conditioned and were source-reviewed here rather than executed on this Windows host; they directly verify process-group, hard-limit, and exact descriptor invariants when run on POSIX. No unresolved critical or high finding remains in S03.

## Recommendations

All four original high findings and the two residual remediation gaps are closed by the final implementation and real-process evidence. No follow-on recommendation remains for S03; retain the platform-conditioned POSIX containment lane alongside the passing Windows-focused suite.
