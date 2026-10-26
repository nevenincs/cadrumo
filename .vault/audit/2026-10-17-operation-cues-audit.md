---
tags:
  - '#audit'
  - '#operation-cues'
date: '2026-10-17'
modified: '2026-10-21'
body_schema: 'body-v2'
body_hash: 'sha256:f198fea41fbb7e16a562e645bed398eda4e25bc937847912c1d3cd1714fc4c34'
related:
  - "[[2026-10-17-operation-cues-plan]]"
  - "[[2026-10-17-idle-churn-operation-observation-adr]]"
---

# `operation-cues` audit: `Operation cues plan-close review`

## Scope

Plan-close review of `2026-10-17-operation-cues-plan` Steps S01-S05 and S08, from the diff bases `1df38663dc` and `8a7146653f` to `4cb41a4749`, against `2026-10-17-idle-churn-operation-observation-adr` and its amendments. The review was read-only and reused each Step's recorded verification. S06, the packaged proof on both stages, is pending for Release and changes no code. Uncommitted edits under `src/cadrumo_agent_service/` at review time belonged to another writer and were out of scope.

The review passed. The watch is recorded before the observe reply is written (`src/cadrumo_runtime/host/profile_connection_operations.py:171`), and a prior watch survives the next observation's window (`:193-209`). Every loop arms before it observes and observes once more after first subscribing. The live operation is always the newest watch, so the 64-watch bound cannot evict it, and a disconnect clears its watches (`src/cadrumo_runtime/host/profile_connection_sessions.py:517`). Reports are accepted only from the owned worker's verified pid (`src/cadrumo_runtime/adapters/worker_authorization.py:362-378`), and publication filters the exact profile and session. `UNKNOWN` handling is unchanged.

## Findings

### modal-waits-unbounded-on-a-dropped-report | medium | The operation modal is the one converted waiter with no deadline, so a dropped report leaves it waiting

`src/cadrumo/entrypoints/tui/operations/modal.py:269` waits without bound, while every other converted loop waits on the cue or its deadline. Reports are droppable by the ADR's constraint: the reporter removes a batch before sending and logs a failure at DEBUG (`src/cadrumo_runtime/host/operation_progress_reporter.py:65-76`), and the worker authorization endpoint closes a connection when its eight slots are taken (`src/cadrumo_runtime/adapters/worker_authorization.py:147`). If the one report naming a settled operation is dropped, the modal shows it running until the person closes it; the previous 200 ms poll converged at once. The constraint's premise, that the client's deadline bounds what a dropped report costs, does not hold for a waiter with no deadline.

### reporter-thread-not-replaced | low | A reporter thread that ends abnormally is never replaced

`_run` guards only the send (`src/cadrumo_runtime/host/operation_progress_reporter.py:58-76`). Anything raised elsewhere in the loop, the failure diagnostic included, ends the thread, and `committed` starts a thread only while none is recorded (`:44-46`), so every later cue from that worker is lost.

### status-cue-publisher-proof-is-a-bare-pid | low | A stale status record naming a reused pid suppresses the desktop's paced fallback

`native/manager/src/session/status_cue.rs:106-108` treats the record's publisher as live when its pid opens. A manager that crashed leaves its record; if the pid is reused while an older manager that does not publish owns the session, `native/manager/src/desktop_host.rs:437-441` drops the 1 s observation and nothing rewrites the record. The session-lock release still wakes the host at takeover, so the cost is a stale displayed status, not a missed takeover.

### records-describe-a-cue-and-pace-the-code-does-not-have | low | The ADR Implementation, two Step rows and a ledger note lag the shipped S05 cue and S08 pace

The ADR Implementation (`.vault/adr/2026-10-17-idle-churn-operation-observation-adr.md:52`) and Step S05 say the harness waits on `attendance_changed`; the code added an `attendance_answered` cue and its runtime publication (`src/cadrumo_client/contracts/session_events.py:92`, `src/cadrumo_runtime/host/profile_connection_attendance.py:376-382`), which the ADR's hypothesis list allows. Step S08 says the 1 s external-owner pace was removed, while the amendment keeps it as the fallback for an owner that does not publish. The ledger's first S08 note is superseded by `ac366af11f`.

### attendance-cue-withheld-on-expiry | low | The answered cue is not sent when an ask expires, which couples two unwritten constants

An expired ask cues holders only (`src/cadrumo_runtime/host/profile_connection_attendance.py:291-296`). This is harmless while an ask lives 120 s and the harness waits 90 s, but nothing states that the second must stay below the first.

### Resolutions at plan close

reporter-thread-not-replaced is fixed: a reporting thread that ends for any reason clears its record and starts a replacement while work is pending (`src/cadrumo_runtime/host/operation_progress_reporter.py:66-75`), and `test_a_reporting_thread_ended_by_an_escaping_error_is_replaced` fails against the previous reporter. records-describe-a-cue-and-pace-the-code-does-not-have is fixed: the ADR Implementation names `attendance_answered`, and the S05 and S08 rows and a ledger note match the code. attendance-cue-withheld-on-expiry and status-cue-publisher-proof-is-a-bare-pid stay open until a fix is verified.

modal-waits-unbounded-on-a-dropped-report is resolved on the operator's ruling by S09: a report the runtime does not take is queued again ahead of later commits and retried after a backoff from 50 ms to 1 s, and closing gives each pending report one try (`src/cadrumo_runtime/host/operation_progress_reporter.py:77-108`). `test_an_undeliverable_report_is_retried_ahead_of_later_commits` and `test_a_refused_report_waits_out_a_backoff_before_its_retry` fail against the dropping reporter, and `test_a_close_while_the_runtime_refuses_gives_each_pending_report_one_try` guards against a retry that spins after close.

The re-review of `c8ab950631`, `6ef45e9c73` and `ae86f24325` passed. It traced that the backoff is waited with the lock released, so a commit never blocks, that re-queueing keeps the oldest-first order without duplicates, and that close stays within its join bound when the runtime refuses. It also read the working-tree `status_cue.rs` fix as correct and fail-closed for older records. Its one finding follows.

### escaped-send-still-loses-its-batch | low | The amended constraint promised a retry the escape path does not give

An error that is not an `Exception` ends the reporting thread and loses the batch it took (`src/cadrumo_runtime/host/operation_progress_reporter.py:66-75`); that loss is what makes the replacement threads end with the backlog. The constraint now states this exception, so the record matches the code. Only a non-`Exception` out of the worker authorization client reaches it.

status-cue-publisher-proof-is-a-bare-pid is fixed: the status record carries the publisher's creation stamp in schema 2, and an observer counts a publisher only when the named pid is running with that stamp (`native/manager/src/session/status_cue.rs:113-122`). A schema 1 record, a reused pid and an unknown version all read as no publisher, so the desktop keeps its one-second fallback. Both status_cue tests and the desktop host's status-change tests pass in `manager.rust`, with `manager.supervision` and the clippy check also green.

## Observed during S06

### kdf-calibration-timeout-at-clean-exit-logged-as-error | low | A calibration sample that runs out its budget is logged as a failed operation when the timeout lands in its clean-exit wait

One Release `concurrent_sessions_probe` run at `d2db5f6e1d` failed only `no_error_records`, on a `kdf_worker_lifecycle` event with `kdf_operation` `calibrate-v1`, `stage` `clean_exit`, `error_type` `TimeoutError`, `exit_code` 0, 2.06 s elapsed and `outcome` `failed` (`build/acceptance/cadrumo-concurrent-uzk6oa9m`). An over-budget calibration sample is an expected rejection, logged at DEBUG as `sample_rejected`, but only when the timeout lands in `result_wait` (`src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py:340-347`). When the result arrives just inside the budget, the clean-exit wait gets none and the same rejection is logged at ERROR. The next run passed every check. This is outside the operation cues; the custody KDF owner should decide whether a calibration sample's clean-exit timeout is also a rejected sample.

## Plan close

S06 closed with both stages rebuilt. Release at `d2db5f6e1d` passed `concurrent_sessions_probe` and `backend_probe`. Debug at a HEAD including `d2db5f6e1d` and `9d7c4cb381` passed both probes, run by CADRUMO-FIX1. The plan-close review and its re-review passed. Every finding is resolved except attendance-cue-withheld-on-expiry, a low with no current effect, and kdf-calibration-timeout-at-clean-exit-logged-as-error, which belongs to the custody KDF owner. All Steps are closed and the plan is complete.

## Recommendations

- modal-waits-unbounded-on-a-dropped-report: a follow-on amendment of `2026-10-17-idle-churn-operation-observation-adr` must decide how a waiter with no deadline is bounded. Either undelivered reports are retried while the worker lives, which amends "dropped, not retried", or a waiter without a deadline re-observes on a bounded wake while its operation runs, which amends "never on a fixed interval".
- reporter-thread-not-replaced: clear the recorded thread when `_run` ends, so the next commit starts a fresh one, and cover it in `src/cadrumo_runtime/host/tests/test_operation_progress_reporter.py`.
- status-cue-publisher-proof-is-a-bare-pid: bind the publisher proof to the process's start time as the instance lock does, and extend the `status_cue` unit tests.
- records-describe-a-cue-and-pace-the-code-does-not-have: amend the ADR Implementation bullet, correct the S05 and S08 rows, and note the superseded ledger entry.
- attendance-cue-withheld-on-expiry: state the harness wait's bound beside the ask lifetime, or cue waiters on expiry.
