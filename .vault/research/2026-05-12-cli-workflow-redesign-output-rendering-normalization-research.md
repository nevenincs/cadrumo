---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `output-rendering-normalization`

## Findings

Root format capture and shared `_emit(ctx, payload, lines)` already exist, but
retained commands do not use them consistently. The deadlines package renders
Rich-only text for list, next, and explain. Inventory uses
`json_output_requested()` and `emit_json_success()` without `ctx` or `_emit`.

The target contract is one rendering path: every retained command receives
`ctx: typer.Context`, drops command-local JSON flags, and routes structured
payloads and text lines through `_emit`. The root `--format json|text` option
is the only output selector.

Reject Rich-only retained surfaces, command-local `--json`, `--json` aliases,
command-specific schema emitters, and NDJSON as the command contract.
