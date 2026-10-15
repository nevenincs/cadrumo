---
tags:
  - '#audit'
  - '#session-lifetime-repair'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:aee4fae2c34ebf234b674766333acc9abfc17f491be309d28aab5a2ea65dcba9'
related:
  - "[[2026-10-15-session-lifetime-repair-plan]]"
  - "[[2026-10-04-application-sign-in-adr]]"
---

# `session-lifetime-repair` audit: `Active session renewal and shutdown recovery`

## Scope

Working-tree repairs under session-lifetime-repair S01-S04: runtime authority and receipt renewal, TUI recovery, desktop input and shutdown sequencing. Independent review by receipt_activity; supervisor reviewed receipt/CLI implementation. Existing unrelated changes are outside scope.

## Findings

### activity-logout-overlap | high | Activity helper could reject an explicit logout

Initial desktop implementation used the same nonqueueing mutation lane for activity and sign-out. Trusted pointerdown precedes click, so activity could occupy the lane and reject logout as CliBusy. Revision required. Assigned to TUI worker: separate bounded activity child owner, drain both owners on stop, and verify overlap.

### transient-connection-identity | high | Status refusal discarded recoverable connection identity

Authority now preserves a lease on uncertain native observations, but the host status projection still cleared the connection session id on every denial. Assigned narrow host fix and regression so OS_SESSION_UNAVAILABLE can recover on the same connection; private work remains refused until observation recovers.

### native-crash-evidence | low | Historical dumps prove buffered stdin finalization failure

Both earlier Release minidumps reach CPython fatal_output_debug through _enter_buffered_busy during TextIOWrapper finalization, with daemon reader threads blocked in buffered stdin. Existing source already uses raw os.read. Packaged Debug and Release regression probes exit cleanly with parent stdin still open. Current repair adds client-before-supervisor shutdown and close-trigger diagnostics. Latest Debug 09:44 supervisor exit64 is orderly; its initiating close event remains unproven. See build/crash-symbols/session-crash-findings.txt.

### review-repairs | low | Both high findings repaired and regression-tested

Desktop activity now has its own bounded child owner; explicit logout proceeds while activity is pending. Native shell sign-in tests passed 58/58 and Clippy passed. The host retains connection identity on OS_SESSION_UNAVAILABLE without granting access; a real Windows IPC test proves same-session recovery and irreversible explicit logout. Authority tests passed 73/73, including five-hour input renewal, no resurrection, sibling renewal and unknown-observation recovery. Person-act frontend matrix passed 7/7, plus the added service activity-refusal case. Receipt/custody suites passed 14 integration, 4 adapter and 60 receipt tests; CLI activity/status suites passed 9. Focused TUI, frontend type/lint and trusted-input Playwright checks passed.

### coverage-limits | low | Package verification scope and interactive limits

The first desktop-host target failed before Rust compilation because an unrelated workstream renamed a source file during the documentation fingerprint build. Configured Rust backend tests then passed. Final package verification uses app-payload and the packaged health probe; installer distribution is outside this repair's verification scope. Cross-origin documentation iframe input is outside trusted activity capture; normal shell/TUI keyboard, paste, pointer and scrolling are covered. No interactive reproduction with the user's private profile was attempted.

### final-code-review | low | Independent re-review passed; workspace aggregate remains red

Independent reviewer re-read both repairs and returned code PASS. Global check-code passed style, data format, types, dependency declarations, secure-store and persistence paths, docstring targets, and operation contract manifest. Its early formatting snapshot saw files during editing; a final just check-format passed. Regenerated canonical import-load metadata; isolated probe loaded all 4770 configured first-party non-test modules with zero failures. The aggregate still reported import-boundary failures across the workspace, 2 unreachable modules, 15 unused symbols and 11 unconsumed exports. No full-green aggregate claim is made. Re-running the entire aggregate without addressing those unrelated workstreams is not warranted. Vault MCP validation timed out after 300 seconds; earlier scoped validation identified template prose now repaired.

### activity-profile-handover | high | Late receipt resumption could revoke a newly selected profile

A final race review found that every receipt resume invokes cross-profile sign-out after publishing its own lease and releasing its profile guard. An activity helper for A could finish admission, B could sign in and revoke A, then A could revoke B. Assigned an explicit activity-only receipt-resume intent that cannot run cross-profile sign-out, preserving ordinary receipt sign-in semantics. Also require a successful status before any cross-profile sign-out side effect. Deterministic overlap regression and final package rebuild required; prior code PASS is superseded until this repair passes review.

### handover-race-repair | low | Activity cannot switch profiles and ordinary handovers are ordered

Activity uses an explicit receipt-only intent, omitted from legacy frames when false, that never invokes cross-profile sign-out. Ordinary password/receipt handovers serialize final status revalidation and the cross-profile sweep under a dedicated lock, without holding the profile-map lock or serializing password proof. Revoked/denied completions cannot sweep. Root reviewed lock ordering. All 19 frame/CLI tests and all 4 one-signed-in-profile Windows integration tests pass, including forced late activity completion and overlapping ordinary handovers. Ruff and focused types pass. No high code finding remains. Final incremental Debug rebuild must include this repair.

## Recommendations

Finish staged Debug app verification and record exact outcomes. Preserve the distinction between historical native crash evidence and the unproven initiating event in the latest Debug shutdown. Independent final handover review returned PASS with no lock inversion found. No unresolved high code finding remains.
