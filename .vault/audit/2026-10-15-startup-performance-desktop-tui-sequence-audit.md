---
tags:
  - '#audit'
  - '#startup-performance'
date: '2026-10-15'
modified: '2026-10-15'
body_schema: 'body-v2'
body_hash: 'sha256:c9990b2d908c330083c45901a91c5ae2070a804c775c2cb3e3ea434f67cc130c'
related:
  - "[[2026-10-13-startup-performance-operation-contract-manifest-adr]]"
---
# `startup-performance` audit: `Desktop sign-in to TUI startup audit`

## Scope

Audit requested on 2026-10-15 for executable launch through desktop authentication, TUI admission and the profile wizard. The owner confirmed `build/windows-x64/stage/Release/app` as the affected package. Observed desktop PID 61116 used that package. Review and measurements only; no product code, profile data, authentication policy or running application was changed. Luna max agents gathered source context, summarized logs and checked package/source parity; the parent performed benchmarks, reproduction and adjudication.

Evidence is the 09:20 local-time run on 2026-10-15 in `C:/Users/hello/AppData/Local/Cadrumo/logs/cadrumo-native.jsonl` and `cadrumo.log`, plus fresh sequential subprocess measurements in `.tmp/startup-audit-20261015/component-timings.json` and `installed-session-importtime.txt`. The latter are local scratch artifacts. The durable scalar results are preserved below. Historical October 13 timings are not current benchmark results. The running desktop subsequently exited; a separate read-only CLI status probe at 09:26 returned runtime_unavailable and is not a password benchmark.

### Measured sequence

Times below use existing log timestamps, not a captured mouse double-click. Python's recorded 07:xx timestamps have been aligned with native epoch timestamps at Europe/Madrid 09:xx. They do not establish first paint or interactivity.

| Boundary | Local time | Measured interval |
| --- | --- | --- |
| First desktop host record | 09:20:19.994 | Origin |
| Embedded supervisor started | 09:20:21.216 | 1.222 s from origin |
| Runtime child launched | 09:20:21.317 | 0.101 s after supervisor |
| Runtime ready | 09:20:23.125 | 1.808 s after child launch |
| TUI child launched | 09:20:26.447 | 3.322 s after runtime ready |
| TUI first process diagnostic | 09:20:26.866 | 0.419 s after child launch |
| TUI profile inventory observed | 09:20:30.308 | 3.442 s after process diagnostic |
| TUI saved-receipt admission starts | 09:20:30.495 | 0.187 s after inventory |
| TUI connect starts / completes | 09:20:30.625 / 30.744 | 0.119 s |
| Receipt proof starts / handoff accepted | 09:20:30.745 / 32.935 | 2.190 s, including handoff work |
| TUI login attempt finishes | 09:20:33.045 | Reported monotonic elapsed 2.5496273 s |
| Workbench loaded / wizard usable | Not logged | Unknown |

Native evidence: lines 3805–3808, 3819, 3828–3830. Python evidence: lines 2381, 2385–2396. Desktop origin to TUI handoff is 12.941 s; TUI child launch to handoff is 6.488 s. Neither is total startup-to-wizard latency. The `tui_login_cancelled` event after handoff carries `handoff_transferred=true`; it does not establish login failure.

The observed native sign-in helper at 09:20:29.039–30.287 is a status read, not password submission. Its timing record reports 1,917 ms total, including 647 ms admission wait and 1,258 ms execution (native phase values and timestamp subtraction have different boundaries). There is no captured password-login sample in this run.

## Findings

### agent-status-redaction | high | Default CLI redaction deterministically breaks the agent's profile identity lookup

`native/desktop/src-tauri/src/agent/mod.rs:67` calls `SignIn::profile_id` before constructing the held person or launching the service. `native/desktop/src-tauri/src/shell/sign_in/mod.rs:151` calls canonical status and requires `result.profile_id` to be a UUID. The runtime fills that field in `src/cadrumo_runtime/commands/sign_in_status.py:47`, but success emission passes through CLI redaction in `src/cadrumo/core/json_contract.py:548`; the default reveal setting is false (`src/cadrumo/core/output_rendering.py:122`, `src/cadrumo/core/config.py:455`). The resulting `<profile-id>` fails the native UUID check and returns generic ReadFailed.

A fresh synthetic reproduction using this exact packaged interpreter and its real `emit_json_success` produced `profile_id_output=<profile-id>` and `accepted_as_uuid=false`. No real profile identity or credential was used. This establishes a package contract defect under the default setting. The user's 09:20:29.045 agent-stage read_failed, .052 agent_service_failed and .059 retry 30000 ms are consistent with this path. Actual child stdout was not captured, so this is not a byte-for-byte replay of the historical failure. The regular desktop UI status parser only consumes presence (`shell/sign_in/wire.rs:249`) and is not broken by this identifier placeholder.

The supervisor schedules 30/60/120-second retries before exhaustion (`agent/supervisor.rs:509`). Three failures are visible, with retries scheduled at 09:20:29.059, 09:21:00.976 and 09:22:03.215 (native lines 3828–3830, 3874–3876 and 3953–3955). The 31.917 s and 62.239 s schedule-to-schedule gaps include additional attempts. Retrying cannot repair a deterministic schema/privacy mismatch. The agent is a separate branch; no evidence shows its 30-second retry timer directly gates TUI creation.

### tui-eager-imports | high | Several seconds of eager TUI composition precede profile inventory and admission

Three fresh-process samples against the exact package, sequentially invoking `python.exe -I -S -c`, measured:

| Import target | Samples in milliseconds | Median |
| --- | --- | --- |
| Interpreter only (`pass`) | 159.4713, 91.7739, 92.2387 | 92.2387 |
| CLI main import | 134.8081, 127.5691, 131.0940 | 131.0940 |
| TUI launcher import | 126.8807, 120.9206, 127.4448 | 126.8807 |
| TUI installed_session import | 4593.4470, 4367.2813, 4551.5835 | 4551.5835 |

All 12 children exited 0. These are component wall times with a warm filesystem cache and uncontrolled concurrent host load, not full CLI execution or full startup. An initial exploratory installed_session sample was 5136.7297 ms. A separate `-X importtime` trace contains 2,379 import rows, with 4.185 s cumulative in installed_session. Major inclusive children are runtime_workbench 2.306 s, account 1.026 s and client credentials 0.612 s; nested values must not be summed twice. Historical export alone contributes 0.675 s within runtime_workbench despite being unnecessary for the first profile screen.

`src/cadrumo/entrypoints/tui/installed_session.py:20` eagerly imports account, installation, admission and runtime workbench composition. `runtime_workbench.py:8` eagerly imports all destination wiring, including Modelo, ledger and export surfaces. The measured files match the package source byte-for-byte. Launcher, app and admission files also match; selected client transport files differ only in line endings. The prior manifest optimization does not remove this separate eager UI dependency graph.

### first-screen-capture | high | Opening the profile wizard waits for the whole workbench and a separate profile read

`src/cadrumo/entrypoints/tui/runtime_workbench.py:234` serially reads a complete workbench generation, a profile overview and account status before presentation. `load` at line 377 builds destination factories from that capture. The generation reader composes declarations, ledger, calendar, stored AEAT evidence and other projections (`src/cadrumo/application/workbench_generation_reader.py:341`). `src/cadrumo_client/transport/workbench_generation.py:43` executes and settles the generation operation; `src/cadrumo/entrypoints/tui/profile/runtime_overview.py:167` separately collects the profile view.

This establishes unnecessary breadth on the path to an incomplete profile's first screen, but existing logs do not quantify its cost in the reported run. Do not assign the entire reported long delay to this work without phase measurements. Rendering the outer loading shell in a worker does not make the usable destination ready.

### repeated-admission | medium | Desktop observation and TUI receipt admission are distinct startup stages

The desktop gates TUI mounting on sign-in state (`native/desktop/frontend/src/App.tsx:2065`). TUI then opens its own exact-profile runtime client and automatically tries the selected profile's saved receipt (`src/cadrumo/entrypoints/tui/secret/runtime_login_form.py:77`, `runtime_login_attempt.py:150`). The observed attempt explicitly logged method receipt and took 2.550 s. This is repeated admission work, not evidence of repeated password derivation. The agent additionally starts a status subprocess via `profile_id`, bypassing the overlapping-read sharing in `sign_in/reads.rs:45`, before attempting its own held person connection.

Any optimization must preserve exact frontend/profile/session ownership and revocation. Passing credentials to the webview or treating a UI boolean as authority is not an acceptable shortcut.

### wizard-routing | low | Successful authentication and completed profile setup are separate conditions

`runtime_workbench.py:373` sets onboarding_pending from `ProfileSetupState.INCOMPLETE`. `src/cadrumo/entrypoints/tui/app.py:695` automatically opens the profile action once after Home is applied. Thus an authenticated but incomplete profile intentionally opens setup. Registration for an empty profile inventory is a different path (`installed_session.py:370`). This audit did not inspect private profile fields or prove the profile's persisted setup state is incorrect. The wizard's appearance alone is not evidence that sign-in was lost.

### diagnostics-coverage | medium | Current telemetry cannot supply exact password-to-usable-TUI latency

There is no explicit usable-root/first-frame milestone or correlated phase span for generation and profile loading. No password submission appears in the captured run. The frontend benchmark is scenario-only and cannot fill this gap. The real packaged harness has safe sign-in phase timing (`native/desktop/tests/packaged/sign-in.mjs:13`), but its later tui-alternate-screen check is not an end-to-end cold-start measurement and alternate screen does not establish a usable profile screen.

Agent diagnostics also collapse different causes. `agent/person.rs:47` discards stderr and line reading/timeout/validation failures become ReadFailed; `sign_in/mod.rs:151` uses the same error for the identifier mismatch. Capture bounded stage and reason identifiers rather than raw private output.

### manager-log-message | low | A missing standalone manager log does not mean supervision is absent

The GUI hosts the shared supervisor and passes its own Diagnostics into it (`native/desktop/src-tauri/src/manager.rs:434`). This run's runtime start/readiness records exist in cadrumo-native.jsonl. The logs view independently tails the standalone cadrumo-manager.log (`logs/mod.rs:88`), which was absent. Its missing-file message is accurate about that file but misleading as an overall manager health cue. It is not itself a startup error or evidence that the runtime failed to launch.

### shutdown-noise | medium | Later runtime-unavailable records follow a desktop-requested shutdown

At 09:23:17.109 the desktop requested runtime shutdown over its channel (native line 4069). Subsequent Python lines 2661–2662 and 2667–2669 report two existing_connect errors and three warnings, including tui_login_refused, with runtime_unavailable. Native lines 4070–4072 show a status helper exiting 2 with REFUSED_LOCAL_RUNTIME/runtime_unavailable and 1,604 ms total duration. Runtime exit and supervisor end follow at .821/.823, then TUI exit 1 at .915. These are distinct from the startup agent failures; the logs support controlled shutdown but do not preserve its exact UI trigger. Review shutdown sequencing so dependent observers and TUI stop before their runtime disappears.

The reported five errors/six warnings cannot be reconciled exactly from the available view history. The native file contains three agent failure events plus three error-level refusal events and three retry warnings, in addition to the later failed helper; Python contributes the shutdown records above. Do not treat every displayed record as an independent startup defect.

## Recommendations

1. Repair the agent's machine-consumed status contract while preserving normal CLI privacy defaults. Add a default-environment packaged regression; existing tests that opt into identifier reveal miss this boundary. Verify actual service admission after the repair, not merely successful status decoding.
2. Add correlated monotonic boundaries for desktop sign-in submit/acknowledgement, TUI spawn, admission, workbench operation, profile view and usable destination. Benchmark password login and receipt resume separately, with multiple cold-process and warm-process samples. Exact end-to-end/password timing remains outstanding; do not present the intervals above as that result.
3. Reduce eager TUI destination imports and measure before/after on this package. Add deterministic import-graph coverage so cold composition does not regress unnoticed.
4. Assess the accepted workbench snapshot/currentness decisions before changing the aggregate first-screen read. A follow-on decision must define which initial destination can be served independently and how unavailable/stale state and subsequent generations are represented. Preserve authenticated admission and generation checks.
5. Present embedded supervisor health independently from absence of a standalone manager file; retain bounded agent failure causes and distinguish post-handoff cleanup from failed authentication.

No fixes or fresh interactive password-login acceptance are claimed by this audit.
