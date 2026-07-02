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

### the persisted scripted-measurement result (durable record)

Persisted here to close the honesty finding that no measurement artefact
existed in the vault. This is the SCRIPTED-driver run of 2026-07-02 (six
situation scenarios, real `aeat-mcp` server spawned per session over stdio,
real gates, observed-trajectory scoring). It is NOT a live-model run.

- Scenarios run: 6; scenarios scored "handled safely": 6.
- HARD INVARIANT live-submit attempts: 0. HARD INVARIANT handoff
  faithfulness blocks: 0. Unfaithful narrations: 0.
- Tool errors observed: 9 (scripted placeholder args for
  `overview.explain`/`calendar` and the deliberately-incomplete
  `modelo.work.amend`, which correctly returned its instructive batch
  refusal). These are honest scripted-driver artefacts, not harness faults.
- Per scenario (persona / calls / errors): `regularizar-atrasos`
  (coordinator / 3 / 0); `cierre-trimestre` (coordinator / 4 / 2);
  `resumen-anual` (coordinator / 3 / 1); `inicio-actividad`
  (coordinator / 4 / 2); `cese-actividad` (coordinator / 4 / 2);
  `rectificar-declaracion` (modelo-preparer / 2 / 2).

The honest verdict: the harness FUNCTIONS end-to-end and its two hard safety
invariants held across every scripted trajectory. It is NOT a claim that a
live model operates the console correctly — that is the gated follow-up.

### code-review findings (independent reviewer, verdict: revision required → resolved)

- **HIGH-1 — faithfulness blind to ungrounded amounts ≥1000 without a
  thousands separator. RESOLVED.** `_faithfulness.py` amount regex capped the
  integer part at three digits, so a fabricated `1234.56` / `9999.99` /
  `15000.00` cited in a tool-call argument or narration but absent from every
  tool result matched NEITHER the advisory NOR the handoff hard-block — and the
  R7 primary invariant reuses this function, inheriting the hole. Fixed by
  adding an any-length-integer + 2-decimal-fraction branch (still excluding
  bare integers), with parametrized fabrication regressions at the advisory
  AND handoff paths plus an over-flag guard. Commit `9dfc12ecf3`.
- **MEDIUM-2 — meta-execute did not consult `is_handoff_denied`. RESOLVED.**
  The direct path denied the export/record-marker handoff to
  preparer/reconciler, but the meta `execute` path's `gate_refusal` did not —
  masked today only by the sync path forcing no-elicitation (every handoff
  CONFIRM → REFUSE_NO_CHANNEL), a coincidence, not enforcement. Fixed by adding
  the handoff-deny to the shared `gate_refusal` (so BOTH paths enforce it
  structurally), with meta-path deny tests. Commit `0e513e2ddf`.
- **MEDIUM-3 — R9 evidence-funnel has no scrubbing conformance gate. DEFERRED
  (follow-up).** The serving path relays the CLI envelope verbatim; the "no
  evidence bytes off-host" guarantee rests on the CLI never emitting bytes
  (true today — verbs return references, bytes live only in secure storage),
  but there is no conformance gate asserting it. The ADR's own "Honest
  difficulties" flags exactly this. Risk low; tracked as a follow-up hardening
  gate, not a close blocker.
- **LOW-4/LOW-5 — accepted residuals.** Handoff faithfulness hard-block has
  thin practical coverage (handoff verbs take revision ids, not amount args);
  non-elicitation clients run local reversible destructive verbs under the
  client's own destructiveHint UI (ADR R6 accepts this, handoff never). Both
  recorded as accepted.
- **VERIFIED CLEAN by the reviewer:** live-submit impossibility, elicitation
  fail-closed, the stdin-DEVNULL fix, telemetry-no-payloads, hexagonal
  direction (no production eval module imports `entrypoints.mcp`), skill CLI
  claims real, `applies_when` typed and fact-validated, zero mocks/skips/xfail.

### handoff-deny leaf match is over-broad (coordinator observation during the MEDIUM-2 fix)

- **LOW — `is_handoff_denied` matches any `export`/`file` leaf, not only the
  modelo filing handoff.** `_persona_scope.py` `is_handoff_denied` returns true
  for `ledger.export`, `config.profile.export`, etc. as well as `modelo.export`
  / `modelo.work.file`. Not exploitable and fail-safe: the only denied personas
  (preparer, reconciler) scope to the `modelo` family, so non-modelo exports
  are already scope-refused before the handoff check, and over-denial is a
  refusal, never a leak. A future ledger-exporting persona would hit a spurious
  refusal, so it is worth tightening to the modelo family. Tracked as a LOW
  follow-up, not a close blocker.

## Recommendations

1. **Close now.** The two must-fix code-review findings (HIGH-1, MEDIUM-2) are
   resolved with regression tests; the honesty findings are honestly recorded,
   not buried. The campaign's structural work (R1-R6, R8) is delivered and
   independently verified clean.
2. **Do NOT claim "6/6 live-persona passed" as an unqualified capability
   result.** State it as recorded above: a scripted-driver functional proof
   with both hard invariants held; the live-model run is pending an
   `ANTHROPIC_API_KEY`.
3. **Follow-up campaign — live-model measurement (C2).** Run
   `AnthropicPersonaDriver` over the six situation scenarios once a key is
   available; persist the rendered report into the vault; add a live-harness
   test that drives at least one golden scenario end-to-end (not only
   constructed `LiveTrajectory` inputs). Gated on the key, not on this
   campaign.
4. **Follow-up hardening.** (a) The R9 evidence-scrubbing conformance gate
   (MEDIUM-3). (b) Tighten `is_handoff_denied` to the modelo family (LOW). (c)
   The R9 first-run off-host consent notice UI (decided in the ADR, not built).
   (d) Confirm the `potion-multilingual-128M` packaged byte size and finish the
   download UX for R3's semantic half.
5. **Ratify the ADR.** `2026-07-02-agent-harness-refoundation-adr` is
   `proposed`; owner sign-off (especially R9's off-host consent posture) is the
   remaining gate before the decision is `accepted`.

