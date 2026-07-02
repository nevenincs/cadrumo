---
tags:
  - '#audit'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-plan]]'
  - '[[2026-07-02-agent-harness-refoundation-research]]'
---



# `agent-harness-refoundation` audit: `campaign close honesty review and code review`

## Scope

The mandatory close-out for the `agent-harness-refoundation` campaign, which
re-founded the agent harness as a black-box tool universe operated by any LLM
client through one MCP console (ADR decisions R1-R9, all 91 plan steps closed).
Two independent fresh-context reviews were commissioned per
`aeat-campaign-close-honesty-review`: a code review (safety / architecture /
quality over the authored surface) and a persona-switch honesty review
(promise-vs-delivery, degraded-but-recorded-done, measurement-claim honesty).
This document records the honest delivered-vs-promised status, the live
measurement result with its exact caveats, and the two reviews' findings.

## Delivered-vs-promised status (coordinator self-record, pre-review)

Recorded honestly BEFORE the independent reviews land, so the reviews can
contradict it:

- **R1 universe re-definition / R2 console tool architecture — DELIVERED.**
  Per-verb input schemas replaced the args bag, manifest-derived toolsets,
  `search`+`execute` meta-tools, prompts/resources capabilities negotiated. A
  latent argv bug (27 hyphenated commands mis-dispatched) was fixed in passing.
- **R3 grounding surface — DELIVERED with a documented degradation.** The
  lexical FTS5 half, the structured citation lookup (all 453 catalogue
  citations resolve to verbatim text), the corpus + terminology MCP tools, and
  the `aeat://corpus/{ref}` resources are all live and tested. The SEMANTIC
  half (model2vec potion embeddings) is code-complete but the model is not
  installed on this host, so hybrid retrieval runs in its lexical-only degraded
  mode here; the exact packaged model byte-size remains the one open
  verification item, deferred to the download-UX. This is honestly the
  research doc's stated shape, not a hidden gap.
- **R4 operating-layer delivery — DELIVERED.** `harness.load` floor tool,
  `aeat://skill|rule|persona/{name}` resource templates, 35 guided-workflow
  prompts, and the optional Claude-native `.claude/skills` mirror; one authored
  source feeding four channels.
- **R5 situation-keyed skills — DELIVERED.** The structured `applies_when`
  schema validated against the live `TaxpayerProfile`, 28 predicate lifts, and
  the six coordinator-authored WHEN-layer skills with golden scenarios.
- **R6 gate enforcement — DELIVERED.** Elicitation-backed CONFIRM (fail-closed
  on every non-explicit-yes path), faithfulness wired into the serving path
  (advisory off-handoff, hard block at export/record-marker), per-verb handoff
  deny (verifier-only, enforced at list-time AND call-time), never-live-submit
  as no-such-tool. A real serving bug was found and fixed during measurement:
  the CLI child stdin was inherited from the MCP client pipe and deadlocked the
  first CLI-backed call; isolated to DEVNULL.
- **R7 measurement — DELIVERED as the SUBSTRATE + a SCRIPTED-driver run; the
  LIVE-MODEL run is one API key away (see the measurement finding below).**
- **R8 distribution — DELIVERED, honestly unsigned.** The `.mcpb` manifest and
  build script produce a bundle; signing is a real path only when an identity
  is present, never faked.
- **R9 off-host consent — DECIDED, ratification pending.** Recorded in the ADR;
  no first-run consent notice UI was built this campaign (it is a documented
  future surface, not claimed done).

## Findings

### measurement-scripted-not-live-model | high | The R7 measurement ran SCRIPTED persona drivers, not live LLM subagents; "6/6 passed" proves the harness FUNCTIONS end-to-end, not that a live model operates it correctly.

ADR R7 promises "live subagent personas — spawned language-model subagents
playing the harness personas." The measurement run
(`scratchpad/measurement-report.md`, this session) used
`ScriptedPersonaDriver`, which replays each golden scenario's declared
trajectory, NOT `AnthropicPersonaDriver` (the real-model driver, which is built
and wired but needs an `ANTHROPIC_API_KEY` that is absent on this host). What
the run genuinely proves: a REAL MCP client session against the REAL spawned
`aeat-mcp` server, over stdio, with the REAL gates and REAL trajectory
capture+scoring, completed all six situation scenarios with both hard
invariants observed at zero (zero live-submit attempts, zero handoff
faithfulness blocks) and zero unfaithful narrations. What it does NOT prove:
that a live model, choosing its own tool calls and narration, stays within the
gates — because the scripted driver's calls and (absent) narration were
author-fixed. Nine of the scripted tool calls ERRORED (placeholder args for
`overview.explain`/`calendar` and the deliberately-incomplete
`modelo.work.amend`, which correctly returned its instructive batch-refusal);
the scenarios still score "passed" because trajectory coverage and lifecycle
order held and no invariant was breached — but "passed" here means "the harness
handled the trajectory safely," not "a model completed the task cleanly."
Disposition: **honestly re-recorded as a scripted-driver functional proof; the
live-model measurement is a gated follow-up** (unblocks the moment a key is
provided — the driver and scorer are complete). This was surfaced to the
operator in-session, not buried.

## Recommendations

