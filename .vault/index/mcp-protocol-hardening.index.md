---
generated: true
tags:
  - '#index'
  - '#mcp-protocol-hardening'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:20d8415ca59e6c495010872d1550180eedc8b8d2e7b061a0fb1e7b9bf807918b'
related:
  - '[[2026-07-08-mcp-hardening-conformance-plan]]'
  - '[[2026-07-08-mcp-protocol-hardening-P01-S01]]'
  - '[[2026-07-08-mcp-protocol-hardening-P01-S02]]'
  - '[[2026-07-08-mcp-protocol-hardening-P01-S03]]'
  - '[[2026-07-08-mcp-protocol-hardening-P01-S04]]'
  - '[[2026-07-08-mcp-protocol-hardening-P02-S05]]'
  - '[[2026-07-08-mcp-protocol-hardening-P02-S06]]'
  - '[[2026-07-08-mcp-protocol-hardening-P02-S07]]'
  - '[[2026-07-08-mcp-protocol-hardening-P02-S08]]'
  - '[[2026-07-08-mcp-protocol-hardening-P03-S09]]'
  - '[[2026-07-08-mcp-protocol-hardening-P03-S10]]'
  - '[[2026-07-08-mcp-protocol-hardening-P03-S11]]'
  - '[[2026-07-08-mcp-protocol-hardening-P03-S12]]'
  - '[[2026-07-08-mcp-protocol-hardening-P03-S13]]'
  - '[[2026-07-08-mcp-protocol-hardening-P04-S14]]'
  - '[[2026-07-08-mcp-protocol-hardening-P04-S15]]'
  - '[[2026-07-08-mcp-protocol-hardening-P04-S16]]'
  - '[[2026-07-08-mcp-protocol-hardening-P04-S17]]'
  - '[[2026-07-08-mcp-protocol-hardening-P05-S18]]'
  - '[[2026-07-08-mcp-protocol-hardening-P05-S19]]'
  - '[[2026-07-08-mcp-protocol-hardening-P05-S20]]'
  - '[[2026-07-08-mcp-protocol-hardening-P06-S21]]'
  - '[[2026-07-08-mcp-protocol-hardening-P06-S22]]'
  - '[[2026-07-08-mcp-protocol-hardening-P06-S23]]'
  - '[[2026-07-08-mcp-protocol-hardening-P06-S24]]'
  - '[[2026-07-08-mcp-protocol-hardening-P06-S25]]'
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-plan]]'
  - '[[2026-07-08-mcp-protocol-hardening-research]]'
---

# `mcp-protocol-hardening` feature index

Auto-generated index of all documents tagged with `#mcp-protocol-hardening`.

## Documents

### adr

- `2026-07-08-mcp-protocol-hardening-adr` - `mcp-protocol-hardening` adr: `long-running call contract, schema fidelity, and declared protocol boundaries` | (**status:** `accepted`)

### exec

- `2026-07-08-mcp-protocol-hardening-P01-S01` - Add the supervised subprocess runner: per-tier timeout table keyed off the command classification, cooperative cancellation, and Windows process-tree termination
- `2026-07-08-mcp-protocol-hardening-P01-S02` - Route the direct and meta call paths through the supervised runner and emit notifications/progress heartbeats (elapsed plus coarse stage) when the client supplied a progress token
- `2026-07-08-mcp-protocol-hardening-P01-S03` - Author the localized timeout and cancellation refusal strings through the locales CLI across all four catalogues
- `2026-07-08-mcp-protocol-hardening-P01-S04` - Add real-behaviour runtime tests: a deliberately slow subprocess hits its tier timeout, cancellation terminates the full process tree on Windows, and the refusal names the tier and retry guidance
- `2026-07-08-mcp-protocol-hardening-P02-S05` - Render JSON-safe real defaults (paths as strings, tuples as arrays) instead of dropping non-scalar defaults to null
- `2026-07-08-mcp-protocol-hardening-P02-S06` - Support boolean off-tokens: the schema accepts explicit false and the argv renderer emits the secondary no-flag token for default-on pairs
- `2026-07-08-mcp-protocol-hardening-P02-S07` - Convert the silent lazy-subcommand resolution fallback into a build-time schema-coverage gate failure naming the broken verb
- `2026-07-08-mcp-protocol-hardening-P02-S08` - Extend the descriptor tests for real defaults, off-token round-trips, and the loud-degradation gate
- `2026-07-08-mcp-protocol-hardening-P03-S09` - Add the typed per-command classification record (destructive, idempotent, handoff, live-write, open-world) co-located with the operator-surface manifest
- `2026-07-08-mcp-protocol-hardening-P03-S10` - Re-home annotation derivation onto the classification table and populate openWorldHint for the sede-interacting live family
- `2026-07-08-mcp-protocol-hardening-P03-S11` - Re-home the HITL confirmation-tier derivation onto the same classification table so client hints and server gates read one authority
- `2026-07-08-mcp-protocol-hardening-P03-S12` - Add the manifest parity gate: every mutating verb in the manifest carries an explicit classification and an unclassified new verb fails loudly
- `2026-07-08-mcp-protocol-hardening-P03-S13` - Extend the annotation tests for openWorldHint coverage and classification-table consumption
- `2026-07-08-mcp-protocol-hardening-P04-S14` - Add resource templates and read handlers for the bulk payload classes (calculation observations, evidence rows, corpus excerpts) resolved from persisted state
- `2026-07-08-mcp-protocol-hardening-P04-S15` - Emit resource_link content items in place of inlined bulk arrays on the identified verbs while keeping structuredContent the typed summary
- `2026-07-08-mcp-protocol-hardening-P04-S16` - Update the affected per-verb output schemas in lock-step with the thinned payload shapes
- `2026-07-08-mcp-protocol-hardening-P04-S17` - Add the structured-summary size-budget conformance check flagging verbs over budget
- `2026-07-08-mcp-protocol-hardening-P05-S18` - Add the localization-boundary gate asserting the model-facing surface is English and the operator-facing strings ride the locale catalogues
- `2026-07-08-mcp-protocol-hardening-P05-S19` - Add the untrusted-content gate over the live family result schemas: no raw portal markup reaches a tool result and portal-sourced free text carries its source kind
- `2026-07-08-mcp-protocol-hardening-P05-S20` - Add the no-secret-elicitation gate asserting no elicitation schema collects secret-like fields, recording the local-CLI-only secret stance
- `2026-07-08-mcp-protocol-hardening-P06-S21` - Add telemetry retention pruning (age and count based, newest-N protected) at server start with a documented read path
- `2026-07-08-mcp-protocol-hardening-P06-S22` - Add telemetry retention tests proving pruning bounds growth and never touches the newest sessions
- `2026-07-08-mcp-protocol-hardening-P06-S23` - Add the capability-set conformance test pinning the exact negotiated server capabilities
- `2026-07-08-mcp-protocol-hardening-P06-S24` - Pin the potion model revision to a commit hash and route the model download through the app-controlled cache directory
- `2026-07-08-mcp-protocol-hardening-P06-S25` - Regenerate the API reference stubs for the new modules via the apidocs CLI

### plan

- `2026-07-08-mcp-hardening-conformance-plan` - `mcp-hardening-conformance` plan
- `2026-07-08-mcp-protocol-hardening-plan` - `mcp-protocol-hardening` plan

### research

- `2026-07-08-mcp-protocol-hardening-research` - `mcp-protocol-hardening` research: `MCP console protocol correctness and operations hardening`
