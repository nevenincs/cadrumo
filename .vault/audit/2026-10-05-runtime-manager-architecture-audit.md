---
tags:
  - '#audit'
  - '#runtime-manager-architecture'
date: '2026-10-05'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:41ea790a633b2705a1c17e3ca2271aa0907d6db1fd0dfde831e5c2da08460440'
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

### headless-load-and-interference | low | S25 passes scoped runtime review and benchmarks

2026-10-07 root personally implemented and reviewed S25 under the operator's backend/runtime, headless, performance and adversarial-testing instruction. A native regression was demonstrated before the fix: a peer closing before ConnectNamedPipe admission raised runtime_unavailable and terminated the listener. The fix translates only disconnected-pipe errors, resets the same retained instance with DisconnectNamedPipe and preserves continuous first-instance ownership; unexpected errors still fail closed. Real native tests verify failed competing ownership, recovery, 512 abrupt connections, wrong image/root/version and healthy-client survival. No authority or credential checks were relaxed.

The request loop now backs off from 1ms to its existing 50ms idle ceiling, resetting after input. Frame deadlines, operation dispatch, slot limit and stop-event cancellation are unchanged. The integrated review traced cleanup through the existing connection owner and shutdown path; 16 silent/partial-header clients close before their five-second handshake deadlines. Two old test assertions were corrected to the already-existing nullable sign_in field and accept-tick availability only after the loop starts.

PASS for scoped correctness and quality: 60 combined native transport/cleanup/full headless runtime tests, the additional stalled-shutdown case, the strengthened 512-connection case, and 34 cached current-source Rust manager adversarial tests. Scoped Ruff/format/ty and diff checks pass. A transient three-second fixture setup timeout on the loaded shared host passed unchanged on targeted rerun; no deadline was loosened. Native source hashes confirm cached Rust test applicability. No Rust work was delegated.

Evidence: build/runtime-load-benchmark.json and its listed logs. Native IPC p50 at 1/8/24 connections changed from 61.46/59.79/58.94ms to 15.20/12.75/13.93ms. At 24 connections throughput changed from 468 to 1436 requests/s. The complete current source runtime reached readiness in 18.93s, served eight concurrent connections at p50 9.63ms/p95 17.01ms, and exited on session-end in 2.75s. These are finite shared-host status/refusal benchmarks, not authenticated-mutation or production SLA claims; short Windows CPU observations cannot prove zero idle CPU. Startup remains a measured optimization opportunity.

Repository-wide import gates and unrelated builds were not rerun under the requested fast scoped verification approach. No package/frontend/docs build, release, different-user/session exercise or GUI acceptance occurred. Other sessions' diagnostics changes in server.py, runtime main.py and worker.py were preserved and excluded from this checkpoint.

### S26 React startup skeletons | low | PASS scoped startup UX and readiness review

The desktop keeps its existing asynchronous Tauri manager dispatch. React now observes startup as a gated starting phase, renders shared non-interactive skeletons, and accepts runtime availability only from the existing canonical status read. Initial loading does not open a blocking sign-in dialog or list profiles before availability. Read failures and the 90-second startup/read deadlines expose recovery; timed-out promises do not indefinitely hold later retries. Status generation guards and component cleanup preserve unmount behavior. Manual startup remains deduplicated and shows a loading heading. No Rust changes or additional state library were required.

Verification: 18 focused startup/manager Playwright scenarios passed, followed by 2 passing targeted checks after final retry-title refinement. TypeScript, scoped ESLint/Prettier, Ruff and ty passed. All 16 desktop chrome catalogue tests passed after enrolling the existing four-locale startup message. A fresh real Windows runtime passed 8-connection/128-request headless native IPC and interference acceptance in 24.17 seconds. Screenshot inspected with translated text. Detailed evidence/source hashes are in build/runtime-startup-ui/verification.json. These checks do not assert session-1 GUI acceptance, a rebuilt package or improved backend initialization time. Shared Git index.lock prevents the Step commit; preserve other workstreams and do not remove their lock.

## Recommendations

B5 resumes composition from the open manager Steps after receiving the concrete B1/B2/B4 contracts. Use `run_with_permit` when composing the initial ownership result into the blocking supervisor. Preserve the distinction between S23 completion and product readiness.
