---
tags:
  - '#plan'
  - '#mcp-progressive-discovery'
date: '2026-07-08'
modified: '2026-07-08'
tier: L2
related:
  - '[[2026-07-08-mcp-progressive-discovery-adr]]'
  - '[[2026-07-08-mcp-progressive-discovery-research]]'
---

# `mcp-progressive-discovery` plan

### Phase `P01` - Surface policy core

Retire the flat default listing: a surface-policy module computes the orientation core (floor, grounding, meta pair, manifest-derived overview and contract slice, persona-filtered) and an env toggle preserves the full surface for opt-out and A/B measurement (ADR P1).

- [x] `P01.S01` - Add the surface-policy module computing the default orientation core (floor, grounding, meta pair, manifest-derived overview and contract slice, persona-filtered) plus the activated-set union; `src/aeat/entrypoints/mcp/_surface.py`.
- [x] `P01.S02` - Read the AEAT_MCP_SURFACE toggle (core default, full opt-out) at serve start, thread the surface policy into build_server, and render tools/list from the policy instead of the flat descriptor concatenation; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P01.S03` - Declare the surface userConfig option on the generated plugin with core as the shipped default and a migration note in the plugin description; `src/aeat/agent/_workspace.py`.
- [x] `P01.S04` - Add surface-policy tests covering core composition, full opt-out, persona filtering, and gate invariance across surfaces; `src/aeat/entrypoints/mcp/tests/test_surface_policy.py`.

### Phase `P02` - Command index and discovery search

Make the search meta-tool the real discovery spine: hybrid lexical plus semantic retrieval over a manifest-derived command index, verb-specific descriptions from the CLI help authority, and search results actionable in one round-trip (ADR P2).

- [x] `P02.S05` - Derive verb-specific description first lines from the per-verb Typer help text with the family operator_question demoted to a suffix; `src/aeat/entrypoints/mcp/_tools.py`.
- [x] `P02.S06` - Build the command-retrieval index (FTS5 lexical with Spanish stemming plus optional model2vec vectors, RRF fusion, lexical-only degraded mode) over tool name, CLI path, per-verb help, and toolset; `src/aeat/application/command_search/_index.py`.
- [x] `P02.S07` - Re-back search_commands with the hybrid command index, keeping the token-overlap scorer as the no-index fallback; `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `P02.S08` - Make search results actionable in one round-trip: carry annotations, confirmation tier, and the per-verb input schema (or add a describe meta-tool if measurably cheaper); `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `P02.S09` - Add command-index tests including a cross-vocabulary recall case the token-overlap scorer misses and the lexical-only degraded mode; `src/aeat/application/command_search/tests/test_command_index.py`.
- [x] `P02.S10` - Extend the meta-tool tests for enriched, schema-carrying search results; `src/aeat/entrypoints/mcp/tests/test_meta_tools.py`.

### Phase `P03` - Toolset activation over list-changed

Wire the existing manifest-derived toolsets to runtime activation with tools/list_changed notifications, damped auto-activation, and persona-scope filtering (ADR P3).

- [x] `P03.S11` - Add per-session toolset activation state with damping and a hard activation cap over the existing manifest-derived groups; `src/aeat/entrypoints/mcp/_toolsets.py`.
- [x] `P03.S12` - Add the toolsets management meta-tool (list, activate, deactivate) filtered by the active persona scope; `src/aeat/entrypoints/mcp/_meta_tools.py`.
- [x] `P03.S13` - Emit notifications/tools/list_changed on activation change, declare the capability, and include activated groups in the advertised surface; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P03.S14` - Add toolset-activation tests covering activation, deactivation, notification emission, damping, persona filtering, and byte-identical gate refusals on activated tools; `src/aeat/entrypoints/mcp/tests/test_toolset_activation.py`.

### Phase `P04` - Tool naming budget

De-duplicate the client-side namespace prefix and enforce a prefixed tool-name length budget with a conformance gate (ADR P4).

- [x] `P04.S15` - De-duplicate the client prefix pair by renaming the server or plugin identity after verifying live prefix composition and slash-command impact against official client docs; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P04.S16` - Add the prefixed tool-name length budget with declared short forms for the over-budget verbs; `src/aeat/entrypoints/mcp/_dispatch.py`.
- [x] `P04.S17` - Sweep the generated plugin and marketplace trees for the renamed identifiers so generator output and marketplace cannot drift; `src/aeat/agent/_workspace.py`.
- [x] `P04.S18` - Add the naming-budget conformance gate failing any prefixed name over budget; `src/aeat/entrypoints/mcp/tests/test_tool_naming_budget.py`.

### Phase `P05` - Prompt arguments and completions

Give the guided-workflow prompts typed arguments and serve completion/complete suggestions from the typed sources (ADR P5).

- [x] `P05.S19` - Add typed arguments (modelo, filing year, period where the skill itinerary needs them) to the guided-workflow prompt declarations and substitute them in the prompt get handler; `src/aeat/entrypoints/mcp/_prompts.py`.
- [x] `P05.S20` - Implement the completion/complete handler serving ranked suggestions from the typed sources (core Modelo enum, period tokens, plausible filing years) and register the capability; `src/aeat/entrypoints/mcp/_completions.py`.
- [x] `P05.S21` - Extend the prompt tests for argument declaration and substitution and add completions handler tests; `src/aeat/entrypoints/mcp/tests/test_prompts.py`.

### Phase `P06` - Live measurement and packaging alignment

Prove the core surface with the live persona harness (discovery scenario, core-vs-full A/B), align the plugin generator and conformance floor, and regenerate the docs stubs (ADR Implementation, R7 discipline).

- [x] `P06.S22` - Author the live discovery golden scenario: an unprimed persona must locate and correctly invoke a long-tail verb through the core surface; `src/aeat/agent/eval/scenarios/descubrimiento_verbo.toml`.
- [x] `P06.S23` - Extend live scoring with discovery metrics (rounds-to-correct-verb, selection quality) and the surface A/B comparison surface; `src/aeat/agent/eval/_live_scoring.py`.
- [x] `P06.S24` - Run the live core-vs-full A/B measurement over the golden scenarios and persist the rendered report as a vault audit record; `.vault/audit/2026-07-08-mcp-progressive-discovery-measurement-audit.md`.
- [x] `P06.S25` - Update the real-client handshake conformance floor for the core surface, the list-changed capability, and the renamed identity; `src/aeat/entrypoints/mcp/tests/test_client_handshake.py`.
- [x] `P06.S26` - Regenerate the API reference stubs for the new and renamed modules via the apidocs CLI; `docs/api`.

## Description

Implements the proposed `mcp-progressive-discovery` ADR (P1 to P6): the aeat
MCP console stops advertising the flat ~273-verb surface and instead defaults
to an orientation core with a hybrid-retrieval `search` + gated `execute`
discovery spine, runtime toolset activation over `tools/list_changed`, a
tool-name length budget with namespace de-duplication, typed prompt arguments
with a completions handler, and a live-measured core-vs-full comparison. The
ADR amends the accepted agent-harness refoundation R2 delivery posture; the
research document carries the file-and-line evidence and the July-2026
protocol brief this plan builds on. The companion `mcp-protocol-hardening`
plan owns the call-runtime, schema-fidelity, and classification-table work;
where the two touch shared modules the sequencing note below applies.

## Parallelization

`P01`, `P02`, and `P05` are mutually independent and may run in parallel.
`P03` depends on `P01` (activation extends the surface policy) and touches
`_meta_tools.py` after `P02.S07`/`P02.S08` land, so it follows both. `P04`
is independent of `P01` to `P03` except `P04.S15`, whose rename lands before
`P06.S25` re-pins the handshake floor. `P06` is strictly last: measurement
runs against the completed surface. Cross-plan: the companion hardening
plan's classification table (its P03) feeds annotations this plan's search
results expose; land whichever first, but do not edit `_annotations.py`,
`_meta_tools.py`, or `_server.py` concurrently across the two campaigns in
the shared worktree.

## Verification

- The default tools/list of a fresh un-personified session advertises the
  orientation core only (order of a dozen tools), proven by
  `test_surface_policy.py` and the updated `test_client_handshake.py`;
  `AEAT_MCP_SURFACE=full` restores the flat surface byte-compatibly.
- A cross-vocabulary discovery query returns the correct verb ranked first
  where the token-overlap scorer provably misses it
  (`test_command_index.py`), and a search hit carries enough (schema,
  annotations, tier) to execute correctly with zero further round-trips
  (`test_meta_tools.py`).
- Toolset activation adds exactly the persona-permitted group, emits the
  list-changed notification, damps churn, and every activated tool's gate
  refusals are byte-identical to the direct path
  (`test_toolset_activation.py`).
- No prefixed tool name exceeds the budget (`test_tool_naming_budget.py`)
  and the generated plugin/marketplace trees carry the de-duplicated
  identity (`test_plugin_workspace.py`, `test_marketplace_generation.py`
  stay green).
- Prompts declare and substitute typed arguments; completions serve ranked
  Modelo/period/year suggestions (`test_prompts.py`).
- The live discovery scenario passes with the two hard safety invariants at
  zero, and the core-vs-full A/B measurement is persisted as a vault audit
  record before the plan is declared complete (R7 discipline).
- Full-tree gates: `uv run --no-sync pytest src/aeat/entrypoints/mcp -q`
  green; `uv run --no-sync pytest --collect-only -q` clean;
  `python -m dev.docs.apidocs scaffold --check` clean after `P06.S26`.
