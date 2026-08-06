---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:0884cdfdb8979d277fb3952c4f4029163be064e22d0c4ac7c4b2c8d2fb71b715'
step_id: 'S22'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run an uncached fresh-process import graph and require all five contracts with no unmatched ignore

## Scope

- `.importlinter`

## Description

- Confirm `.importlinter` names `cadrumo` as its root package and declares five unmatched-ignore-error contracts.
- Run `uv run --no-sync lint-imports --no-cache --show-timings` in a fresh process.
- Record graph size, every contract verdict, timing evidence, and unmatched-ignore diagnostic absence.

## Outcome

The graph built without cache in 0.505 seconds and analyzed 3,418 files with 16,140 dependencies. Every declared contract was kept:

- `Calculations registry must not import directly from domain.renta` — KEPT in 0.011 seconds.
- `Domain must not import application` — KEPT in 0.017 seconds.
- `Domain must not import adapters` — KEPT in 0.018 seconds.
- `Core must not import outer layers` — KEPT in 0.020 seconds.
- `AEAT layered architecture` — KEPT in 0.132 seconds.

The process exited successfully with `Contracts: 5 kept, 0 broken.` Its complete output contained no warning or message for an unmatched ignore; because every contract configures `unmatched_ignore_imports_alerting = error`, the successful result also proves no unmatched ignore was suppressed.

## Notes

No `.importlinter`, source, or test file was changed. No incidents or skipped verification.
