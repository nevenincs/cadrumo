---
tags:
  - '#audit'
  - '#runtime-manager-architecture'
date: '2026-10-05'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:a553acc6e17babfc683c5d4df5edc5cd5f94da575e182c3f642d4d5a4a23ff72'
related:
  - "[[2026-10-04-runtime-manager-architecture-plan]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `runtime-manager-architecture` audit: `Manager lane checkpoint review`

## Scope

Review of S23, the four-file B5 working-tree change against bcdce3f752, on 2026-10-05. Covers claim ownership from initial S11 admission through restart backoff, launch, readiness, adoption and final outcomes. Other manager Steps and external B4 source changes are outside this checkpoint.

## Findings

### restart-claim-checkpoint | low | S23 passes scoped review and Windows verification

PASS for S23. The supervisor reserves the cross-session start claim before backoff, checks active-session and Quit state while retaining it, and reports changed ownership without starting another runtime. `run_with_permit` accepts the initial S11 guard, validates the pinned root and prevents a pre-readiness retry from contending with its own caller. Readiness, adoption and final outcomes release the guard. Root inspected all four modified files and requested the initial-permit correction before acceptance. Evidence from B5: 121 Windows Rust tests, then 42 affected tests after the final permit-root cleanup, clippy with warnings denied, rustfmt and diff checks passed. Build output is `build/b5-manager-cargo`; commands and environment are in the S23 ledger and conversation tool transcripts. No extra test execution was needed for this review.

### manager-composition-pending | low | this checkpoint does not establish an operational manager

The production `native/manager/src/main.rs` still accepts only `--version` and performs no lifecycle composition. S08/S10/S12/S13 and B4's ordered settle, exact operation counts and record grammar remain open. Windows fixtures establish this Step's claim behavior; Linux compilation and installed-package acceptance are not established here.

### canonical-environment-checkpoint | low | S08 environment subset passes Windows review; composition remains pending

2026-10-05 root review traced the seven-file manager-only change from B2's installed-default resolver through Strict environment construction to the actual fixture child. Developer/authority overrides are refused for managed locations; resolved root and selected-package authority are pinned. A review correction removed retention of raw ambient values: first spawn prepares and caches only canonical filtered output, preserving preparation timing, stable restarts and diagnostic omission. Final affected suite: 85 tests pass; all-target fixture clippy, formatting, release build and diff checks pass using `build/b5-manager-cargo` and the existing B1 generated inputs (executor completions `22caa0`, `7edfba`). No new high or critical finding in this subset. S08 verdict remains PENDING for bounded installed-interpreter probes and the shared Settings projection; no production-manager or Linux acceptance is claimed.

### native-manager-admission | low | 2026-10-05

Reviewed B5 bounded entrypoint admission using existing process identity and B2 desktop evidence. Session zero, missing session/elevation, full UAC token and unavailable desktop fail before state or launch; version inspection remains available. Eight tests pass in Session 0; fixture-feature all-target Clippy and fmt pass. This is partial S10: bare admitted startup still does not compose or launch the runtime. B4 ordered shutdown, exact operation counts and record grammar remain unavailable, and S08 shared Python-owned identity/version projection is still required.

### windows-startup-checkpoint | low | scoped startup and runtime prerequisites pass

2026-10-07 root review covers S04/S22 and partial S08/S10. Exact nullable worker counts replace hosted-profile bounds; idle fencing retains pre-fence requests and never reuses a late observation as proof of idleness. Real Windows tests independently retain a process handle and confirm death, INTERRUPTED/ORPHANED durable settlement and confirmed lease release within the session-end bound. S04/S22 have applicable passing evidence.

Root personally reviewed and completed Rust startup: bounded installed-interpreter identity/version queries under strict environment, physical-root checks, ownership-permit transfer, direct same-session adoption, foreign-owner refusal, one breakaway attempt and the hidden Windows session-end window. The review's visible-refusal finding is fixed by an admitted-interactive native diagnostic; any failed-version marker now conservatively blocks startup/adoption. Ordinary tests avoid launching admitted managers against real interactive-user storage. No remaining Rust work was delegated after the operator's explicit instruction.

PASS for the implemented subset: 139 native manager tests, including four composed startup cases and actual hidden-window queue delivery; a real packaged native runtime launched by the new Rust composition reached Ready and exited on SessionEnd with its boot record removed (25.16 seconds); 13 cross-language protocol tests; 51 Python unit, four ordered-settlement, 17 runtime integration and three final native worker/count cases. Manager/application Clippy, formatting, scoped Python quality checks, optimized manager-only build and release Windows manifest/admission checks pass. See build/manager-startup-verification.json for source/binary hashes and exact logs.

PENDING for full S08/S10 and desktop acceptance: shared Settings projection, shell-dispatch fallback, actual session-1 GUI/logoff and installed-package acceptance. IPC/tray and version catalogue/cutover remain later work. The pre-existing desktop package was not rebuilt or updated. Git initially rejected the checkpoint because another process held the shared index lock; no lock was removed and no hook bypassed.

## Recommendations

B5 resumes composition from the open manager Steps after receiving the concrete B1/B2/B4 contracts. Use `run_with_permit` when composing the initial ownership result into the blocking supervisor. Preserve the distinction between S23 completion and product readiness.
