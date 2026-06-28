---
tags:
  - '#adr'
  - '#aeat-cli-gap-closure'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-gap-closure-plan]]'
  - '[[2026-05-08-aeat-cli-gap-discovery-audit]]'
  - '[[2026-04-24-aeat-cli-wireframe-research]]'
  - '[[2026-05-12-cli-design-research]]'
  - '[[2026-06-04-aeat-cli-gap-closure-research]]'
---

# `aeat-cli-gap-closure` adr

## Context

The 2026-05-08 gap-discovery audit turned the remaining AEAT CLI drift
into a bounded closure backlog. The branch already carries the broader
hardening direction, so this feature exists to close the still-open and
newly discovered rows without reopening settled CLI/backend boundaries.

## Decision

- Treat the gap-closure slice as a follow-on to CLI hardening, not a new
  CLI redesign.
- Keep the CLI transport-only: parsing, routing, formatting, and exit-code
  emission stay in the entrypoint layer while behavior lands in backend
  services.
- Execute closure work as granular, single-subject steps tied directly to
  audit rows and live-command verification.

## Consequences

- Remaining CLI drift is resolved against an explicit audit inventory
  instead of ad hoc opportunistic cleanup.
- Backend ownership remains centralized, which limits shim regression.
- Progress is traceable at the audit-row level during execution.
