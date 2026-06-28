---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W47.P233'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W47.P233`

De-shim / de-stub phase. The boundary test
`test_bindings_list_and_preview_emit_no_bucket_event` enforces the
read-only contract: neither verb may emit a bucket event.

## Description

The legacy `bindings` single command stayed read-only; this
phase pins the new `list` and `preview` subcommands at the same
contract. The boundary test inspects the canonical module's
source for any bucket-event emission pattern (`emit_bucket_event`,
`append_bucket_event`, `bucket_event(`) and fails fast if a future
change wires one in.

`bindings preview` is the natural temptation point: an override
that resolves into a Decimal could plausibly be persisted as a
draft revision. The boundary guard makes that smell visible.

Closed plan rows: `W47.P233.S1393`, `W47.P233.S1394`,
`W47.P233.S1395`, `W47.P233.S1396`, `W47.P233.S1397`,
`W47.P233.S1398`.

## Tests

Boundary test passes as part of the
`src/aeat/entrypoints/cli/test_modelo.py` suite.
