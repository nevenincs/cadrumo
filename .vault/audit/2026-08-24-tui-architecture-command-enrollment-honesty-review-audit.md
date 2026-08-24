---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:9bb098a12857429095c4c016191065ee2d5130c158e8ad8ab45c09f6bd17709b'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-architecture-command-enrollment-parity-reference]]"
---

# `tui-architecture` audit: `TUI command enrollment honesty review`

## Scope

Fresh-context review of the command graph, every production full-screen launch
site, option ownership, runtime dispatch, tests, and the amended architecture boundary.

## Findings

### enrollment-inventory | high | Six callable interfaces were falsely refused

Resolved by joining all production launch sites to the command graph and enrolling
login, profile status, descendiente, apoderado configure, and both Modelo wizards
alongside profile create and edit.

### option-ownership | high | Profile leaves duplicated the global flag

Resolved by deleting the leaf-local option and reading only the root-owned request.
The root help advertises `--tui`; profile leaf help does not.

### migration-truth | high | Availability was conflated with target topology

Resolved by the approved ADR amendments. `AVAILABLE` now states that a callable
full-screen interface exists today. It cannot be used as evidence that the dedicated
launcher, package migration, reverse-consumer removal, or legacy deletion is complete.

### dormant-review-screen | medium | Modelo review has no production launcher

`ModeloWorkReviewApp` remains unenrolled because no command constructs it. Exporting a
screen class is not a callable command route.

### console-fallback | high | Available flows could still choose line mode

Resolved centrally in `enforce_tui_request`: an explicit request on a host without
full-screen capability now returns the registered unsupported-console refusal before
the handler can select a line-mode frontend.

## Recommendations

Keep the eight-node fixed-point test aligned with real launch sites. Add new enrollment
only in the same change as its runnable interface. Keep the dedicated migration gate
separate and red until the transitional imports are removed.
