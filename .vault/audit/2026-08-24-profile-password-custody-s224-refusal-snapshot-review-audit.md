---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:5e2aa9afcac2723b117700952377fc82a113b577515d6a7d97c70ad3e98b1d3e'
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
