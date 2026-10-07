---
tags:
  - '#plan'
  - '#desktop-environment-readiness'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:8588bea11ffeaaaa96c8bb32d54e76a659e75306caf03410d1d2243f676f1054'
---

# `desktop-environment-readiness` plan

## Description

Approved 2026-10-07

The user requests environment management across CADRUMO binaries, a CADRUMO-specific console cwd, available runtime and automatic CLI/TUI/development attachment to the open authenticated runtime. Use the canonical root and typed workspace location, project through existing native contracts, and preserve profile/receipt authentication ownership. Canonical environment governs resolution and inheritance; desktop shell's home-cwd ruling is amended under this explicit instruction; runtime manager remains sole supervisor. Semantic discovery is unavailable (unverifiable empty index), so bounded direct source reads supply evidence. Preserve concurrent work.

## Steps

- [x] `S01` - Prepare canonical console workspace and consistent packaged command environments; `core storage taxonomy, native projection generator, desktop environment and terminal owners with focused tests`.
- [x] `S02` - Trace and repair authenticated runtime attachment across CLI TUI and development commands; `Python runtime frontend admission and environment composition, development command entrypoints and focused tests`.
- [x] `S03` - Verify integrated environment readiness and document binary launch behavior; `native CONTRACT, environment audit, manager readiness and packaged or isolated integration checks`.

## Parallelization

S01 worker owns storage taxonomy additions, native generation/projection, desktop environment/terminal code and corresponding tests. S02 worker independently owns Python frontend admission/composition and development environment paths and tests; it first establishes existing behavior and repairs concrete gaps only. Supervisor owns all vault writes/commits, manager interaction review, documentation and shared expensive integration checks. S01 and S02 may execute concurrently; S03 integrates their results. No worker reverts other edits.

## Verification

Verify canonical workspace creation and path pinning, all terminal kinds selecting the bundled command path, preservation of the existing runtime/storage identity after cwd changes, automatic authenticated receipt attachment without credentials in environment, typed unavailable/signed-out behavior and manager lifecycle ownership. Run focused Rust/Python tests and configured formatting/lint/types checks. Exercise real owner boundaries; report platform/session/package acceptance gaps without claiming unrun results.
