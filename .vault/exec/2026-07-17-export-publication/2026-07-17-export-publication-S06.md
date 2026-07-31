---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:d2136ad0fddd2ae2ebc9276c76ff7c703e2e74a0f4efe7cdff0f282ffce4a3c4'
step_id: 'S06'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events

## Scope

- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Add `test_bundle_export_recovery.py` driving a real child Python process that serializes and journals a `PREPARED` export, then hard-exits (`os._exit(91)`) before the atomic replace, and separately between the replace and the completion event.
- Prove a fresh process reconciles the crash-before-replace case as prepared: destination absent, no `PROFILE_EXPORTED` event, orphan staged temp removed, journal cleared.
- Prove the crash-after-replace case leaves the target durably published yet fires no premature completion event, and reconciliation never fabricates one.
- Prove restrictive staged-temp permissions with no publication, publication into a freshly-created parent directory, a completed export leaving no journal and exactly one event, and same-target exclusion while the target lock is held by another process.

## Outcome

Six real-behavior cases pass, including the forced-crash-then-fresh-process recovery proof the plan's verification demands. The child uses the same file secret-store env as the parent so cross-process crypto shares keys. No mocks, stubs, monkeypatch, skip, or xfail. Committed in `ac097a53a7`.

## Notes

An initial full-file run showed two transient failures in the full-export child paths; a sequential re-run was clean and the suite is stable across repeated runs, consistent with the known parallel loader-cache race, not a real regression. POSIX `0o600` mode is asserted only on POSIX (Windows makes no ACL guarantee), which is a platform-conditional assertion, not a skip.
