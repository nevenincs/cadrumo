---
tags:
  - '#plan'
  - '#mcp-protocol-hardening'
date: '2026-07-08'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-research]]'
---

# `mcp-protocol-hardening` plan

### Phase `P01` - Supervised call runtime

Replace the bare unbounded subprocess call with a supervised runner: tiered timeouts keyed off the command classification, progress-notification heartbeats when the client supplies a progress token, cooperative cancellation with Windows process-tree termination, and localized instructive timeout refusals (ADR H1).

- [x] `P01.S01` - Add the supervised subprocess runner: per-tier timeout table keyed off the command classification, cooperative cancellation, and Windows process-tree termination; `src/aeat/entrypoints/mcp/_call_runtime.py`.
- [x] `P01.S02` - Route the direct and meta call paths through the supervised runner and emit notifications/progress heartbeats (elapsed plus coarse stage) when the client supplied a progress token; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P01.S03` - Author the localized timeout and cancellation refusal strings through the locales CLI across all four catalogues; `src/aeat/locales`.
- [x] `P01.S04` - Add real-behaviour runtime tests: a deliberately slow subprocess hits its tier timeout, cancellation terminates the full process tree on Windows, and the refusal names the tier and retry guidance; `src/aeat/entrypoints/mcp/tests/test_call_runtime.py`.

### Phase `P02` - Input-schema fidelity

Make the per-verb schemas faithful: real JSON-safe defaults, expressible boolean off-tokens, and loud build-time failure instead of silently empty schemas on lazy-resolution errors (ADR H2).

- [x] `P02.S05` - Render JSON-safe real defaults (paths as strings, tuples as arrays) instead of dropping non-scalar defaults to null; `src/aeat/entrypoints/mcp/_input_schema.py`.
- [x] `P02.S06` - Support boolean off-tokens: the schema accepts explicit false and the argv renderer emits the secondary no-flag token for default-on pairs; `src/aeat/entrypoints/mcp/_input_schema.py`.
- [x] `P02.S07` - Convert the silent lazy-subcommand resolution fallback into a build-time schema-coverage gate failure naming the broken verb; `src/aeat/entrypoints/mcp/_input_schema.py`.
- [x] `P02.S08` - Extend the descriptor tests for real defaults, off-token round-trips, and the loud-degradation gate; `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`.

### Phase `P03` - Command classification table

Move the destructive, idempotent, handoff, live-write, and open-world axes from leaf-name frozensets to one typed declared classification beside the operator-surface manifest, consumed by annotations and HITL alike, with a manifest parity gate (ADR H3).

- [x] `P03.S09` - Add the typed per-command classification record (destructive, idempotent, handoff, live-write, open-world) co-located with the operator-surface manifest; `src/aeat/application/operator_surface/_classification.py`.
- [x] `P03.S10` - Re-home annotation derivation onto the classification table and populate openWorldHint for the sede-interacting live family; `src/aeat/entrypoints/mcp/_annotations.py`.
- [x] `P03.S11` - Re-home the HITL confirmation-tier derivation onto the same classification table so client hints and server gates read one authority; `src/aeat/entrypoints/mcp/_hitl.py`.
- [x] `P03.S12` - Add the manifest parity gate: every mutating verb in the manifest carries an explicit classification and an unclassified new verb fails loudly; `src/aeat/application/operator_surface/tests/test_classification_parity.py`.
- [x] `P03.S13` - Extend the annotation tests for openWorldHint coverage and classification-table consumption; `src/aeat/entrypoints/mcp/tests/test_annotations.py`.

### Phase `P04` - Result thinning via resource links

Keep structuredContent the typed summary and move bulk provenance and evidence arrays to resource_link URIs resolved by the resource read handlers, with output schemas updated in lock-step and a size-budget check (ADR H4).

- [x] `P04.S14` - Add resource templates and read handlers for the bulk payload classes (calculation observations, evidence rows, corpus excerpts) resolved from persisted state; `src/aeat/entrypoints/mcp/_resources.py`.
- [x] `P04.S15` - Emit resource_link content items in place of inlined bulk arrays on the identified verbs while keeping structuredContent the typed summary; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P04.S16` - Update the affected per-verb output schemas in lock-step with the thinned payload shapes; `src/aeat/entrypoints/mcp/_tools.py`.
- [x] `P04.S17` - Add the structured-summary size-budget conformance check flagging verbs over budget; `src/aeat/entrypoints/mcp/tests/test_result_size_budget.py`.

### Phase `P05` - Declared protocol boundaries

Turn the implicit postures into gated contracts: the English model-facing localization boundary, the no-raw-markup untrusted-content boundary on the live family, and the no-secret-over-MCP elicitation stance (ADR H5, H7, H8).

- [x] `P05.S18` - Add the localization-boundary gate asserting the model-facing surface is English and the operator-facing strings ride the locale catalogues; `src/aeat/entrypoints/mcp/tests/test_localization_boundary.py`.
- [x] `P05.S19` - Add the untrusted-content gate over the live family result schemas: no raw portal markup reaches a tool result and portal-sourced free text carries its source kind; `src/aeat/entrypoints/mcp/tests/test_untrusted_content_boundary.py`.
- [x] `P05.S20` - Add the no-secret-elicitation gate asserting no elicitation schema collects secret-like fields, recording the local-CLI-only secret stance; `src/aeat/entrypoints/mcp/tests/test_elicitation.py`.

### Phase `P06` - Retention and posture

Bound telemetry growth, pin the negotiated capability set with a conformance test, and land the residual grounding-stack hardenings (ADR H6, H9).

- [x] `P06.S21` - Add telemetry retention pruning (age and count based, newest-N protected) at server start with a documented read path; `src/aeat/entrypoints/mcp/_telemetry.py`.
- [x] `P06.S22` - Add telemetry retention tests proving pruning bounds growth and never touches the newest sessions; `src/aeat/entrypoints/mcp/tests/test_serving_gates.py`.
- [x] `P06.S23` - Add the capability-set conformance test pinning the exact negotiated server capabilities; `src/aeat/entrypoints/mcp/tests/test_client_handshake.py`.
- [x] `P06.S24` - Pin the potion model revision to a commit hash and route the model download through the app-controlled cache directory; `src/aeat/application/corpus_search/_query_embed.py`.
- [x] `P06.S25` - Regenerate the API reference stubs for the new modules via the apidocs CLI; `docs/api`.

## Description

Implements the proposed `mcp-protocol-hardening` ADR (H1 to H9): the aeat MCP
console's call runtime gains tiered timeouts, progress heartbeats,
cancellation, and Windows process-tree termination; the per-verb input
schemas become faithful (real defaults, boolean off-tokens, loud
degradation); the destructive/idempotent/handoff/live-write/open-world axes
move to one typed classification table beside the operator-surface manifest;
bulk result payloads thin to resource links; the localization, untrusted
external-content, and no-secret-over-MCP postures become gated contracts;
and telemetry, capability, and grounding-stack residuals are bounded. The
research document carries the file-and-line evidence and the July-2026
protocol brief. The companion `mcp-progressive-discovery` plan consumes the
classification table in its search results; the sequencing note below
governs the shared modules.

## Parallelization

`P02`, `P05`, and `P06` are mutually independent and may run in parallel
from the start. `P01` depends on `P03` for the timeout-tier keying
(`P01.S01` reads the classification), so land `P03.S09` first or stub the
tier table against the current HITL classification and re-key in the same
phase. `P04` is independent of the rest but shares `_server.py` and
`_tools.py` with `P01`/`P02`; serialize edits to those files. Cross-plan:
do not edit `_annotations.py`, `_server.py`, `_meta_tools.py`, or
`_resources.py` concurrently with the companion discovery campaign in the
shared worktree; land whichever campaign's touching phase is ready first
and rebase-by-reading before the second starts (per the shared-worktree
discipline, no destructive git).

## Verification

- A deliberately slow subprocess is terminated at its tier timeout with a
  localized instructive refusal, and cancellation kills the whole process
  tree on Windows, proven by real-behaviour tests in
  `test_call_runtime.py` (no mocks, no fakes).
- A default-on boolean flag can be turned OFF through the MCP surface and
  a lazy-resolution failure reds the schema-coverage gate instead of
  shipping an empty schema (`test_tools_and_dispatch.py`).
- Every mutating verb in the operator-surface manifest carries an explicit
  typed classification and the live family carries `openWorldHint`
  (`test_classification_parity.py`, `test_annotations.py`); annotations and
  HITL provably read the same record so hints and gates cannot drift.
- Thinned verbs emit `resource_link` items whose URIs resolve through the
  resource read handlers, structured summaries stay within the size budget
  (`test_result_size_budget.py`), and the existing evidence-scrubbing gate
  stays green.
- The localization-boundary, untrusted-content, and no-secret-elicitation
  gates are green and each would fail on a seeded violation
  (anti-tautology proof per the roundtrip discipline).
- Telemetry pruning bounds directory growth without touching the newest
  sessions; the capability conformance test pins the negotiated set; the
  potion revision is a commit hash and the model download lands in the
  app cache directory.
- Full-tree gates: `uv run --no-sync pytest src/aeat/entrypoints/mcp -q`
  green; `uv run --no-sync pytest --collect-only -q` clean;
  `python -m dev.docs.apidocs scaffold --check` and
  `python -m aeat.locales scaffold --check` clean after `P01.S03` and
  `P06.S25`.
