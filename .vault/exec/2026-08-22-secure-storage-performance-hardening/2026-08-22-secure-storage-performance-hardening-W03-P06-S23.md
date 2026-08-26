---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:28f3c2f9e46fee2fa87f3ca6b130a08b4bb76963b75c0a4e408f0bb7065c5b8e'
step_id: 'S23'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---
# Split pure label-head verification from publication, recovery, and repair

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_label_head_repository.py`

## Description

- Replace the mixed repository methods with pure `verify`, explicit
  `publish_initial`, and explicit `recover_pending` operations.
- Keep compare-and-swap advance separate and preserve anchored, no-follow
  filesystem reads and writes.
- Make the application custody port explicitly compose recovery, verification,
  and initial publication without a repository compatibility alias.
- Prove pure verification never publishes, clears, recovers, or repairs state.

## Outcome

Implemented in `2e6801aa9a`. Focused repository, adapter, capsule, and lifecycle
selections pass, including an independent current-HEAD rerun of 18 tests. Ruff
over every changed file and `git diff --check` pass.

## Notes

Independent review found the retired `verify_or_recover_initial` and
`recover_advance` repository APIs absent, anchored filesystem safety preserved,
and no MEDIUM or HIGH finding. The application port remains the owning lifecycle
orchestration contract; it is not a compatibility re-export of the removed
repository behavior.
