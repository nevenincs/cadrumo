---
tags:
  - '#research'
  - '#agent-harness-operability-followup'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:a472361f5a2bc2a7acaf8052afacb54610c40925b7c3d5e81b1c2425ca6bc0cc'
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-audit]]'
  - '[[2026-07-02-agent-harness-refoundation-plan]]'
---

# `agent-harness-operability-followup` research: `operability and grounding completion (deferred from refoundation close)`

The `agent-harness-refoundation` campaign delivered the harness as a FRAMEWORK
(rules, personas, situation skills, the MCP operating console, the wired safety
gates, and the measurement/eval substrate) and landed it structurally complete
after a two-reviewer close. That close honestly recorded that the campaign is a
framework landing, not a MEASURED or FULLY-GROUNDED one: four decisions carry
gaps that were deferred rather than claimed done. This document is the
follow-up campaign reference the close required, so each deferred item has a
durable, gate-tracked home. It is the research seed for a follow-up campaign,
authored at close time; the implementing waves are scoped when the campaign is
picked up.

## Findings

### Resolution status (2026-07-03 execution pass)

A drive-the-remaining-work pass on 2026-07-03 landed the concrete operability
and hardening items; the large/blocked items are dispositioned honestly below.

| Item | Status | Commit / disposition |
| --- | --- | --- |
| 9a contract brittleness (MEDIUM) | LANDED | `9a3ad86f96` graceful `app contract` degradation + resilience gate |
| 9b regularizar-atrasos work-state (MEDIUM) | LANDED | `59317b5b47` `overview backlog`/`calendar` degrade to a `work_units_degraded` notice; derive from the deadline schedule, not persisted work state |
| 9c misleading exit-6 hint (LOW) | LANDED | `e49c9c7520` unexpected-boundary suggests `config repair logs`, not integrity repair |
| 9d citations-view mojibake (cosmetic) | LANDED | `1d1fd1c739` — was a real harness bug: MCP subprocess decoded CLI UTF-8 as the platform default (cp1252); pinned `encoding="utf-8"` |
| 6 evidence-scrubbing gate (MEDIUM-3) | LANDED | `563e811e46` no result schema emits raw bytes (recursive type walk over the registry) |
| 7 e2e gated-session test (M3) | LANDED | `e95c0f9a90` CONFIRM elicitation decline/cancel/not-confirmed fired over the memory-transport wire |
| 8 handoff-scope tighten (LOW) | LANDED | `cc8f5aa7cd` `is_handoff_denied` gated on the modelo family |
| 8b corpus_search errors → AeatError (L1) | LANDED | `34607acf8f` registered as REFUSED/ERROR codes (they had collapsed to exit-6 INTERNAL) |
| 4 off-host consent notice (H3) | LANDED | `5aa6f79f75` standing R9 disclosure on the `harness.load` floor, surfaced first |
| 1 live-model measurement (C2) | LANDED | `3452e24265` live Opus persona (PASS) + persisted vault measurement (`2026-07-03-agent-harness-operability-followup-audit`) |
| 2 + 3 semantic grounding provisioning + footprint (H1/H2) | LANDED | `cc1504bfa4` — S79↔S87 resolved (vectors BUILT behind the extra, never shipped; `pyproject` comment corrected to match the gate); `ensure_corpus_embeddings` build-on-first-use wired into `search_corpus`; REAL potion hybrid recall proven (cross-lingual hit lexical-only misses); footprint measured (~0.5 GB weight / ~2.1 GB HF cache). Residual minor hardening: pin `POTION_MODEL_REVISION` from `"main"` to a commit hash, and perfect the app-cache-dir passthrough (this model2vec version routes the download to the default HF hub cache). |
| 5 bundle signing (M1) | MECHANISM LOCKED; signing blocked on identity | `a5bb01f279` — the sign path is proven-wired and honest (unsigned + never fabricated without a signer; invokes `mcpb sign` when a signer exists). The actual signature still needs a real release identity/certificate that must never be faked; when one exists `python packaging/mcpb/build.py` signs with no code change. |

### Deferred items carried forward from the refoundation close

Each item names its close-review origin (C/H/M/L finding in
`2026-07-02-agent-harness-refoundation-audit`) and its acceptance gate.

**1. Live-model measurement (C2) — the operator's headline goal, unfinished.**
The R7 measurement ran SCRIPTED persona drivers, not live LLM subagents. The
`AnthropicPersonaDriver` is built and wired but never ran (no
`ANTHROPIC_API_KEY` on the build host). Deliver: run it over the six situation
scenarios, capture the trajectories, score them against the golden scenarios
with the real gates, PERSIST the rendered measurement report into the vault,
and add a live-harness test that drives at least one golden scenario
end-to-end (the current live-harness test feeds constructed `LiveTrajectory`
inputs to the scorer; only a single benign `harness.load` call is captured from
a real session). Gate: a persisted report with the two hard invariants
observed at zero under REAL model behaviour, and one e2e-driven golden scenario.

**2. R3 semantic grounding provisioning (H1) — the second emphasised goal.**
The lexical + citation grounding half is delivered and functional; the semantic
(model2vec potion) half is code-complete but UNPROVISIONED: `embed_corpus` has
no caller, no corpus vectors ship, and the query-embed model is not installed.
Reconcile the S79↔S87 contradiction (S79 planned "ship the numpy matrix"; S87
asserts and enforces that no matrix ships) by DECIDING the model explicitly —
vectors shipped as licence-clean build-time data, OR built at release, OR built
on first run behind the `aeat[search]` extra — then wire the build step that
runs `embed_corpus`, and prove hybrid retrieval actually fuses lexical +
semantic. Gate: a real hybrid query returns a semantically-recalled hit that
lexical-only misses, with the shippability/licence gate still green.

**3. R3 model footprint + download UX (H2).** The research doc's one explicit
open verification item — the packaged byte size of `potion-multilingual-128M`
— was reframed, not measured. Measure it; finish the `aeat[search]` runtime
download UX (pinned revision, app cache dir, install hint, offline behaviour).
Gate: a documented footprint and a working first-use download-or-refuse path.

**4. R9 off-host consent notice (H3).** The ADR decides a first-run consent
notice ("your words and the figures the assistant sees go to your chosen LLM
provider; your source documents never leave your machine"); it is neither built
nor was it a plan step. Build it as a console first-run surface. Gate: the
notice is emitted before the first off-host-visible interaction, tested. Depends
on R9 ratification.

**5. R8 bundle signing (M1).** The `.mcpb` builds UNSIGNED (honestly — signing
runs only with a real identity, never faked). Sign it once a release identity
exists. Gate: a signed bundle that installs without an unverified-publisher
warning.

**6. R9 evidence-scrubbing conformance gate (MEDIUM-3).** The serving path
relays the CLI envelope verbatim; the "evidence bytes never leave host"
guarantee rests on the CLI never emitting bytes (true today) but has no
conformance gate. Add one driving the amount-bearing surface and asserting no
base64/byte-blob shape in any relayed envelope. Gate: the conformance test is
green and would fail if a verb ever emitted bytes.

**7. e2e gated-session test (M3).** The safety gates (elicitation CONFIRM,
handoff-deny, argument-faithfulness block) are wired and unit-verified but never
FIRED over a real gated client session. Add an e2e test that drives a
handoff/CONFIRM verb through full dispatch and observes the gate fire over the
wire.

**8. LOW hardening.** Tighten `is_handoff_denied` to the modelo family (it
currently matches any `export`/`file` leaf — fail-safe and masked by scope
today, but a future ledger-exporting persona would hit a spurious refusal).
Promote the `corpus_search` errors from plain `Exception` to registered
`AeatError` (L1) once the contested locale catalogues settle.

**9. Findings from the live-model persona measurement (2026-07-02).** Three
real Claude-Opus personas operating the harness surfaced these — none reachable
by a scripted driver, which is why they matter:
- **The grounding entry point is brittle (MEDIUM) — RESOLVED
  (commit `9a3ad86f96`).** `aeat app contract` — the manifest the operator rules
  mandate reading first — crashed when ANY payload module was broken, because
  `_ensure_result_schemas_registered()` eagerly walked every payload module and
  let the first bad import propagate. Now each payload-module import is isolated:
  a failure contributes one typed `SchemaModuleLoadFailure`, the walk continues,
  and the manifest degrades by exactly one command while naming the failing
  module in a `contract.schema_module_load_failed` warning notice
  (`cli.contract.schema_module_load_failed`, translated en/es/ca/hu).
  `command_schema_refs()` stays resilient for the MCP tool builder / conformance
  consumers. Gate: `test_app_contract_resilience.py` drives a deliberately-broken
  payload module on `sys.path` and asserts failure-collected-not-raised,
  degrade-by-one, warning-notice-projection, and clean-load-yields-no-notices.
- **`regularizar-atrasos` presupposes work state the target taxpayer lacks
  (MEDIUM).** `overview backlog`/`calendar` refuse without persisted work-unit
  state, and `--allow-incomplete` does not relax it — but a behind-on-everything
  taxpayer has no work units yet, so the situation skill's own step 1 is
  dead-on-arrival for its own persona. Rework the WHEN-layer entry so it can
  answer "what have I missed" for a fresh-but-behind profile (derive from
  obligation applicability + the deadline schedule, not from persisted work
  state).
- **Misleading exit-6 recovery hint (LOW).** The INTERNAL error suggests
  `aeat config repair integrity`, but a code import error is not corrupted
  state; the hint is wrong for that failure class and could send an operator to
  a pointless or mutating action.
- **Mojibake in `registry citations view` error text (cosmetic).**
  Double-encoded UTF-8 in an error message.

### Not in scope here

ADR ratification (L3) is an owner decision, not a research/build item: the
refoundation ADR is `proposed` and extends the also-`proposed` 2026-07-01 ADR;
owner sign-off (especially R9) gates treating the D1-D7 / R1-R9 decisions as
accepted. The measurement and grounding work above can proceed in parallel with
ratification, but should not be declared "accepted-harness" behaviour until the
ADRs are.
