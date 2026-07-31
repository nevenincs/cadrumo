---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-07-17'
body_hash: 'sha256:e3f0fc4c830fcd0e4bae51b3d604c0208b9644f372ae878faadd945f1fe6d31d'
step_id: 'S559'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-28-codebase-solidification-adr]]'
---

# `codebase-solidification` `W09.P38.S559`

Added `KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH` markers on the four snapshot-dispatch hooks, mirroring the borrador W08.P36.S551 pattern.

- Modified: `src/aeat/application/live/_censo.py`
- Modified: `src/aeat/application/live/_expedientes.py`
- Modified: `src/aeat/application/live/_notifications.py`
- Modified: `src/aeat/application/live/_snapshot_base.py`

## Description

Each `_derive_snapshot_id` abstract hook now carries a block-comment `KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH` marker immediately before the definition, explaining that `**kwargs: Any` is required by the polymorphic dispatch contract of `SnapshotService[T]` and `StatelessSnapshotService[T]`. Both abstract base classes in `_snapshot_base.py` were updated (the lifecycle-based `SnapshotService` at line 210 and the stateless `StatelessSnapshotService` at line 346).

## Tests

Covered by the S561 parametrised inventory test `test_snapshot_dispatch_hooks_carry_kwargs_any_rationale`. Commit: `1c2b02e82`.
