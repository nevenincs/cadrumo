---
tags:
  - '#audit'
  - '#operation-cues'
date: '2026-10-17'
modified: '2026-10-17'
body_schema: 'body-v2'
body_hash: 'sha256:cc844ad1060bbbf964d6c617f50c5e18714327c1a1ecf9eeb956c1efa9408bc2'
related:
  - "[[2026-10-17-operation-cues-plan]]"
  - "[[2026-10-17-idle-churn-operation-observation-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace operation-cues with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

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

## Recommendations

- modal-waits-unbounded-on-a-dropped-report: a follow-on amendment of `2026-10-17-idle-churn-operation-observation-adr` must decide how a waiter with no deadline is bounded. Either undelivered reports are retried while the worker lives, which amends "dropped, not retried", or a waiter without a deadline re-observes on a bounded wake while its operation runs, which amends "never on a fixed interval".
- reporter-thread-not-replaced: clear the recorded thread when `_run` ends, so the next commit starts a fresh one, and cover it in `src/cadrumo_runtime/host/tests/test_operation_progress_reporter.py`.
- status-cue-publisher-proof-is-a-bare-pid: bind the publisher proof to the process's start time as the instance lock does, and extend the `status_cue` unit tests.
- records-describe-a-cue-and-pace-the-code-does-not-have: amend the ADR Implementation bullet, correct the S05 and S08 rows, and note the superseded ledger entry.
- attendance-cue-withheld-on-expiry: state the harness wait's bound beside the ask lifetime, or cue waiters on expiry.
