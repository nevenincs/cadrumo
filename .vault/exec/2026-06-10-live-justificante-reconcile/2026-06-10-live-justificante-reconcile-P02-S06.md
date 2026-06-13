---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S06'
related:
  - "[[2026-06-10-live-justificante-reconcile-plan]]"
---




# Add a live end-to-end capture test gated by AEAT_LIVE_TESTS_ENABLED that pulls and persists a real justificante, env-driven and never xfail or skip-marker

## Scope

- `src/aeat/application/live/tests/test_justificante_capture_live.py`

## Description

- Add an `aeat_live`-marked, `requires_live_enabled()`-gated live test that
  discovers a real filed period, pulls the signed justificante via the
  orchestrator, and asserts structural invariants only.
- Assert: PDF starts `%PDF`, sha256 matches decoded bytes, official
  `source_kind`, ACTIVE state, and the snapshot is retrievable as the latest for
  the work unit.

## Outcome

Collects and is deselected by default (gated by the `aeat_live` marker);
pyright/ruff clean. Landed as commit in the S06 push.

## Notes

Env-gated via `requires_live_enabled()` and the `aeat_live` marker, never xfail
or skip. No operator data embedded in expectations. Two pyright
`reportPrivateUsage` warnings for reusing the `_default_justificante_*` discovery
helpers — consistent with the file's existing IVA private-import tolerance.
