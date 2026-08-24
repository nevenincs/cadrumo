---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1c5ad7c5dd790f417d57020aab716a714440a34c14d99af268b9acb2aa1db70e'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S224 refusal snapshot review`

## Scope

Formal review of `W06.P12.S224` against the accepted custody decision, the approved Step, and the corrected campaign-close finding. The review inspected all three durable-state snapshot call sites in `test_machine_secret_channels_subprocess.py`: the shared subprocess source used by the POSIX and native Windows HANDLE harnesses, plus the in-process `_storage_snapshot` helper. It also reconciled the claimed native and WSL matrices and static checks with the exact uncommitted diff.

## Findings

### s224-snapshot-implementation | high | The reviewed diff does not implement the required lock-safe durable snapshot

The uncommitted diff is formatting-only. Both subprocess harnesses still receive the same pre-existing `durable_snapshot` implementation through `_DURABLE_SNAPSHOT_SOURCE`, and `_storage_snapshot` retains the same pre-existing predicate. Each predicate includes session and receipt files incidentally because it excludes only filenames containing `log`; however, none excludes `.lock` debris. This directly conflicts with the supplied evidence that the tightened suite first detected `.session.v2.json.lock` churn and then passed after a precise `.lock` exclusion. The claimed resolving implementation is absent from the reviewed worktree, so the 70-test native and 70-test WSL results cannot attest the current diff as described. The broad substring check for `log` is also not a precise expression of the permitted diagnostic-log exclusion.

The two subprocess harnesses deliberately share one source string, so the formatting adjustment does not create divergence between native Windows HANDLE and POSIX/WSL behavior. The separate in-process helper remains pre-existing semantic duplication, but this diff neither introduces nor worsens it. It also does not create a competing secret-channel or snapshot mechanism. The blocking defect is instead that no semantic S224 change is present across either implementation path.

## Recommendations

Do not approve or close S224. Apply the same explicit durable-file predicate to `_DURABLE_SNAPSHOT_SOURCE` and `_storage_snapshot`: include session and receipt artifacts, and exclude only precisely identified diagnostic logs and `.lock` debris. Then rerun the exact native Windows and WSL matrices, Ruff, and ty against that saved diff and repeat this focused review. Preserve the shared subprocess implementation so unread-channel, native HANDLE, and POSIX/WSL harness behavior cannot drift.
### s224-snapshot-implementation-resolved | high | The lock-safe durable snapshot is now present and the blocker is resolved

Re-review confirmed that `_DURABLE_SNAPSHOT_SOURCE`, shared by the ordinary subprocess harness and native Windows HANDLE harness, now excludes `.lock` suffixes while continuing to include session and receipt artifacts. The local `_storage_snapshot` applies the matching predicate across the host/runtime boundary. Diagnostic logs and lock debris are the only excluded categories; custody, session, and receipt state remains observable. Centralizing the two embedded implementations in one source reduces the earlier risk of harness drift. The local helper remains necessarily separate because it executes in the host test runtime, but it matches the embedded predicate and is not a competing production mechanism.

The final implementation is supported by the complete native matrix at 70 passed, the WSL matrix reaching 68 passed before two tests were interrupted by a transient syntax error in a concurrently edited peer module, and the exact affected descriptor subset subsequently passing 8 of 8 on both native Windows and WSL after that peer module compiled again. Ruff and ty are clean. The transient peer syntax error is outside the reviewed file and does not challenge unread-channel, HANDLE inheritance, POSIX descriptor, or durable-snapshot semantics. The original HIGH is resolved; no unresolved CRITICAL, HIGH, MEDIUM, or LOW finding remains in S224 scope.

## Final disposition

Approve S224. The reviewed diff closes the refusal-snapshot witness gap without changing production secret-channel behavior or creating a parallel authority. The Step may be closed using the stated native, WSL, subset, and static evidence.
