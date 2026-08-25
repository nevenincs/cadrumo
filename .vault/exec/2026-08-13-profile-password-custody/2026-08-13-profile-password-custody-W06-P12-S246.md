---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:60ba69e7d2098c48b51b5fead5eefe9d2602ba1bd33ed2d49a6125dbc2a085a4'
step_id: 'S246'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Repair the harness serial watchdog kill-switch and disarm lifecycle so the full integration suite terminates cleanly without weakening timeout enforcement

## Scope

- `src/cadrumo-harness/`

## Description

- Add a single generation-owned watchdog cancellation event and an idempotent disarm entry point.
- Disarm the active generation in the real server's unconditional shutdown path.
- Make Windows waits bounded and cancellation-aware while retaining immediate genuine-client death handling.
- Make POSIX polling cancellation-aware and replace prior generations before arming another.
- Add a canonical MCP settings-cache reset and real subprocess proofs for disarm and later-work safety.
- Repair the orphan-worker environment so its base interpreter imports both distributions and emits real lifecycle events.

## Outcome

The stdio watchdog still hard-exits on a genuine lost client or confirmed orphan, but normal completion, startup failure, and replacement now cancel the exact active generation. A cancelled Windows waiter checks cancellation again after a simultaneous target signal before invoking `os._exit`, closes held handles, and cannot kill later in-process work.

The exact serial watchdog lane passes 19 tests. Ruff and ty pass on every changed harness file.

## Notes

Vaultspec RAG was attempted first. The shared daemon refused a client-version mismatch; isolated fallback reported an empty local code index, so the required absence/ownership conclusions were corroborated by targeted symbol search and whole-file inspection.

The full serial harness integration run progressed beyond 62 percent and demonstrated normal termination across the repaired watchdog lane, but was stopped for the execution boundary after unrelated failures had already accumulated. No skip, mock, timeout inflation, or sleep-based weakening was introduced.
