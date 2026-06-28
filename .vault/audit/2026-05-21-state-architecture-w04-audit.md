---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-state-read-projection-adr]]"
  - "[[2026-05-21-state-architecture-w02-audit]]"
---

# `cli-workflow-redesign` audit: state-architecture W04 close

Closing note for Wave 4 (canonical operator state read-projection) of
the state-architecture plan.

## What landed

| Commit | Content |
|---|---|
| `b5beba04c` | `OperatorStateProjection` + `build_operator_state_projection`; rewire `overview status` / `auth status` / `auth test` / `modelo readiness` |
| (revision) | corrected misleading `pending_obligations` docstrings; swallowed backend/schedule failures now logged |

One canonical typed projection, one producer. The four operator-facing
surfaces now read the same object, so they cannot disagree.
`configured` is computed exactly once - `auth status` and `auth test`
report the identical value (the old split where `auth test` sourced it
from the live backend is gone). `overview status` now carries `drafts`
(legacy `ModeloDraft`) and `work_units` (`WorkUnitCatalogue`) as
distinct counters, fixing the testimonial-reported "`overview` shows
0 drafts after `modelo work`" bug.

## Review trail

Review verdict: 6 of 8 axes clean (one producer, `configured` once,
work-units fix, surfaces consume the projection, strict typed models,
correct layering, honest real-behaviour tests). One MAJOR: the
`pending_obligations` field had no consumer and two docstrings falsely
claimed the `NO_PENDING_OBLIGATION` engine gate "reads the same
datum." Revision: docstrings corrected to state the truth - the field
is carried for a future rewire and the engine gate is not yet wired
to it. The MINOR bare `except Exception` blocks (backend probe,
schedule computation) now log via `get_logger` rather than swallowing
silently.

## Verification

- `application/test_state_projection.py`: 5 passed.
- `application/overview` + `application/auth` + projection: 115 passed.
- Full `entrypoints/cli` tree: 476 passed, 3 failed - the same three
  foreign-WIP-blocked failures carried from W02 (`test_workflow_surface.py`
  x2, `test_backend_boundary.py` x1).

## Deferred / handed off

- The `WorkflowEngine._stage_computing_deadlines` `NO_PENDING_OBLIGATION`
  gate is not rewired to consume `projection.pending_obligations`.
  `_engine.py` carries another campaign's uncommitted WIP and the ADR
  brief said not to refactor the engine when risky. The projection
  already carries the field; the rewire is tracked as a follow-up in
  the plan's W04 section. Note the field will need reshaping to the
  gate's decision datum (next/target obligation, filtered) when the
  rewire happens.
- The three foreign-WIP-blocked CLI failures remain; they close when
  the owning campaigns commit.
