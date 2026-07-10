---
tags:
  - '#adr'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-08'
related:
  - "[[2026-07-02-agent-harness-refoundation-research]]"
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
  - "[[2026-07-08-mcp-protocol-hardening-adr]]"
---

# `agent-harness-refoundation` adr: `black-box tool universe, situation-keyed skills, and the MCP operating console` | (**status:** `accepted`)

## Problem Statement

The accepted `2026-06-30-agent-harness-adr` settled the harness's four-layer shape and its MCP end-state; the proposed `2026-07-01-agent-harness-adr` settled the content of the rules, personas, and skills. Both were authored under a universe definition an operator directive of 2026-07-02 has now corrected, and both left the harness in a state the same directive identifies as unfinished in two defining ways: it was never operable — no live language model has ever driven the CLI through it — and there is no accepted way to measure or operate it.

The corrected universe definition is the load-bearing change. The `aeat` CLI is a **black box**: a bundled, deterministic tool universe for calculating and manipulating tax data, not a codebase to be interfaced with. The agent harness is the **framework of rules, personas, and skills for operating safely and effectively within that confined universe**, and it serves **any** language model the user already runs — there is no bespoke embedded chat runtime. One MCP server is the **operating console**: it must ground user requests, understand the bundled legal corpus, run semantic search, hold deep knowledge of the CLI surface, ask the user questions when input is needed, and actually operate the CLI on the user's behalf. That is materially more than the verb-wrapper server shipped today.

This ADR re-founds the concept against that definition. It records precisely what carries over from the two prior ADRs and what is superseded, and it resolves the nine decisions the `2026-07-02-agent-harness-refoundation-research` document raised: the universe re-definition itself (R1), the console's tool architecture (R2), a first-class grounding surface (R3), how the operating layer reaches an arbitrary client (R4), the situation-keyed skill taxonomy (R5), how the nominal safety gates become real (R6), how the harness is measured by live model-in-the-loop operation (R7), distribution (R8), and the off-host consent posture (R9). It introduces no code; it records the decided shape and its rationale.

## Considerations

**Most of the prior decision surface survives; the universe re-definition re-frames it rather than discarding it.** The accepted ADR's six resolutions (MCP as the validated end-state, `src/aeat/_data/agent/` as the artifact home, defense-in-depth HITL tiers, the advisory-then-blocking faithfulness posture, a golden-scenario eval methodology, and Spanish-stem naming) and the proposed ADR's seven (manifest-as-single-authority, the three-tier skill taxonomy, the verifier owning the export/record-marker boundary, the profile-fact derivation principle of D5, and the rest) remain correct under the corrected definition. What the re-definition changes is which of the shipped delivery mechanisms is primary and how large the console's mandate is — not the safety posture, the artifact home, or the naming discipline.

**The CLI-as-contract substrate already embodies the black-box discipline.** The operator-surface manifest (`build_operator_surface_manifest`, `aeat app contract`), the `SchemaEnvelope`/`Notice`/`ExitCode` reading surface, and the rule-surface drift gate all treat the CLI as the only citable surface and execute every operation by shelling `aeat --format json`. This layer carries over unchanged and is the natural authority the console derives its tools from.

**The console's five required powers exist only in fragments today.** Grounding is half-present (the obligation-derivation verbs exist; natural-language mapping is correctly the model's job). The legal corpus is reachable only as citation metadata — the verbatim legal text never reaches the operator, and no semantic search exists anywhere in the product. Deep CLI knowledge is the strongest pillar but the per-verb argument schemas are absent from the tool surface (a generic `{args: [string]}` bag). Gated execution exists but two of its three gates — the CONFIRM tier and the faithfulness check — are computed in library code and never wired into the serving path. The operating layer (rules, personas, skills, the terminology handbook) ships as reachable wheel data that the server process never imports.

**Client capability is negotiated, not assumed.** Across surveyed MCP clients, `tools` is near-universal, `prompts` and `resources` are widely but not universally supported, and `elicitation` is the newest and least universal capability. This forces a floor/enhancement design rule at every layer: functionality that must always reach the model rides a tool; richer channels are progressive enhancements that must degrade cleanly when absent.

**Measurement must exercise the thing that is actually at risk.** The prose of the rules, personas, skills, and tool descriptions is the code under test; a replay gate that asserts byte-identical re-resolution of recorded calls cannot fail on model misbehaviour. The only faithful measurement is a live model driving the real console.

## Considered options

### R1 — Universe re-definition and supersession of the two prior ADRs

*Continue the prior framing* (the harness as an operating layer over a ~75%-agent-ready backbone, delivered primarily by materialising a workspace): rejected — it treats the CLI as a codebase to be interfaced with and a bespoke workspace as the product, which the 2026-07-02 operator directive explicitly corrects.

**Chosen — the black-box tool universe with one MCP operating console, serving any language model.** The CLI is a confined, deterministic tool universe; the harness is the framework of rules and regulations for operating within it; the console is the single operating surface that any MCP-capable client connects to. This re-founds, not discards, the prior work. **Carried over unchanged:** the accepted ADR's `Q1`–`Q6` (MCP as the end-state tool surface, the `src/aeat/_data/agent/` artifact home behind the `aeat[agent]` extra, the HITL tier taxonomy, the advisory-then-blocking faithfulness posture, the golden-scenario eval methodology, and Spanish-stem naming) and the proposed ADR's `D1`–`D7` (the manifest as the single capability authority, the three-tier skill taxonomy, the verifier owning the export/record-marker boundary, and the D5 profile-fact derivation principle). **Superseded:** the workspace materialiser as the *primary* delivery vehicle (it is demoted to an optional Claude-native mirror under R4), the flat `tools/list` surface (replaced by domain toolsets under R2), and any notion that the harness targets a bespoke future runtime (it targets the user's existing client). The origin of this decision is the operator directive recorded 2026-07-02.

### R2 — Console tool architecture

**Status: AMENDED by the proposed `2026-07-08-mcp-progressive-discovery-adr` (P1–P4).**
The 2026-07-08 review found R2's toolsets shipped as grouping metadata that never
reaches the protocol — `tools/list` still returns the full flat verb surface, the
exact posture R2 rejected. The amending ADR retires the flat listing as the
default advertised surface (orientation core + search/execute spine, P1–P2),
wires the existing toolsets to runtime activation over `tools/listChanged` (P3),
and adds a tool-name length budget (P4). R2's INTENT — progressive disclosure,
toolsets for the common path, meta-tools for the tail — carries over unchanged;
only the delivery posture is amended. The original ruling follows for the
decision trail.

*Flat surface (status quo):* one tool per operator-callable CLI command key, no schemas, no annotations — rejected: dumping the whole verb tree into `tools/list` crowds out the user's question and degrades tool selection, and the `{args: [string]}` bag forces the model to run `--help` per verb.

*Meta-tools only* (a `search`+`execute` pair over the entire surface, the Cloudflare precedent): rejected as the sole architecture — it scales to thousands of endpoints but hides the readily-groupable domain structure and weakens annotation-driven client confirmation for the common path.

**Chosen — domain-grouped toolsets with a meta-tool fallback.** Tools are grouped into domain toolsets (`renta`, `iva`, `ledger`, `censo`, `modelo-lifecycle`) **derived from the live operator-surface manifest** so the console cannot drift from the CLI. Every tool carries `readOnlyHint`/`destructiveHint` annotations so a client renders its own confirmation UI even without elicitation. Per-verb input schemas replace the `{args: [string]}` bag. A `search`+`execute` meta-tool pair is retained as the long-tail fallback for verbs outside the curated toolsets. This uses each pattern for the job it is good at: toolsets for the common domains, meta-tools for the tail.

### R3 — Grounding surface

*Id/topic lookup only (status quo):* citations resolve to metadata, never to legal prose — rejected: the operator cannot read the authoritative text a figure rests on.

*Lexical-only search:* exact citation matching but weak semantic recall — rejected alone: compliance queries need both exact-citation and concept recall.

**Chosen — a hybrid lexical + semantic corpus search tool plus citation-resolving resources.** A single grounding tool searches the bundled BOE/AEAT corpus, registry citations, manuals, and the terminology handbook with hybrid retrieval (lexical for exact citations, embedding for semantic recall — the regulated-domain IR consensus). Paired `aeat://corpus/{ref}` resources resolve any citation to verbatim authoritative text. The index builds from the already-bundled `.extracted.md`/`.extracted.json` triples, so no new extraction pipeline is needed, and it is built and served **on-host**. The embedding/lexical engine, model, and index-build story are undecided and licence-bound (see Constraints); the engine choice is deferred to the plan behind a licence gate.

### R4 — Operating-layer delivery

*Materialise a workspace as the primary vehicle (status quo):* rejected as primary — it is a dead-end export no in-repo consumer reads, is Claude-shaped, and does not reach an arbitrary client through the protocol.

**Chosen — one authored source, four channels, floor-first.** The universal floor is a `harness.load` tool returning the operator rules and active persona as text — the only channel guaranteed to reach a model on a minimal tools-only client. Layered on top: resource templates `aeat://skill|rule|persona/{name}` for enumerable pull; MCP prompts as slash-command guided workflows that embed the matching skill plus its grounding excerpt; and optional `.claude/skills` materialisation (repurposing the existing `aeat app agent` materialiser) as a Claude-native enhancement, never the baseline. A single authored source in `src/aeat/_data/agent/` feeds all four channels, matching the one-authored-source/generated-outputs discipline. Each channel above the floor degrades cleanly when its capability is absent.

### R5 — Skill taxonomy and metadata

*Tax-domain-primary:* rejected — situations and users both span domains, so a domain-primary tree fractures every real itinerary.

*Persona-primary rewrite:* rejected — re-keying the whole executable layer to archetypes reintroduces the lifecycle duplication the proposed ADR's D6 already resolved by making the per-modelo skill the executable unit.

**Chosen — WHO primary, WHEN as an orthogonal overlay, WHICH as the executable leaves.** The regimen/user-type itineraries (WHO) stay primary — the strongest, most stable profile predicates. A new orthogonal **life-situation (WHEN)** layer is added as a temporal overlay that sequences the existing per-modelo skills: six new skills in Spanish stems — `regularizar-atrasos` **first** (its CLI surface, the `overview backlog` past-due/recargo path, is fully built and completely unexposed), then `cierre-trimestre`, `resumen-anual`, `rectificar-declaracion`, `inicio-actividad`, and `cese-actividad`. Per-modelo skills (WHICH) remain the executable leaves. Each skill's selection predicate is **lifted from prose `description` into a structured frontmatter field** (`applies_when` over `TaxpayerProfile` facts and lifecycle state) so routers, MCP prompts, and eval scenarios can query it deterministically. Composition: situation confirms obligations via `overview` → itinerary narrows → per-modelo skill executes.

### R6 — Gate enforcement

*Leave the gates nominal (status quo):* rejected — the CONFIRM tier and the faithfulness check are computed but never wired into the serving path, so only the permanent live-write block is real.

**Chosen — wire all three, floor-aware.** (i) The CONFIRM tier is enforced via MCP **elicitation** (`accept`/`decline`/`cancel`), degrading per a decided capability matrix: where elicitation is absent, the console falls back to `destructiveHint`-driven client confirmation and refuses handoff-tier verbs by default. (ii) The `faithfulness_check` is wired into the live serving path as an advisory notice on narration mismatch, escalating to a **hard block at the export / record-marker boundary**. (iii) Persona scope stays family-granular at serve, **but the console adds per-verb deny rules for the handoff boundary**, closing the proposed ADR's D3 caveat (family scope cannot separate preparer/verifier/reconciler) structurally rather than by prose. (iv) Never-live-submit stays enforced as "no such tool exists" — the strongest form. A hard spec constraint binds (i): **elicitation must never request sensitive information**, so evidence bytes stay on-host and are never elicited.

### R7 — Measurement and live verification

*Replay-only (status quo):* rejected — it asserts registry/CLI determinism but cannot fail on model misbehaviour, which is exactly the risk under the corrected definition.

*External SaaS trajectory eval:* rejected — it ships trajectories (and the figures in them) off-host, against the on-host posture.

**Chosen — a self-hosted live subagent-persona harness** (operator directive, 2026-07-02). Capabilities are measured by **live subagent personas**: spawned language-model subagents playing the harness personas, operating the console end-to-end against golden scenarios. The substrate (a) starts the real `aeat-mcp` server, (b) connects a real MCP client session driven by a subagent persona, (c) captures the full trajectory (tools selected, arguments, elicitation responses, narration), and (d) scores it against the existing golden-scenario models plus the faithfulness and confirmation checks **now applied to observed calls**, not caller-injected verdicts. Hard invariants: **zero live-submit attempts and zero faithfulness violations at the handoff boundary**. Session telemetry — per-call trajectory records with session ids — is persisted locally. A data flywheel promotes live failures into new golden scenarios. A real-client handshake conformance test (`initialize` / tools-list / call round-trip) is the floor beneath the live harness.

### R8 — Distribution

**Status: AMENDED by the accepted `2026-07-03-claude-ecosystem-packaging-adr` (D3a).** The
Claude plugin (marketplace-served, generated from the single authored harness source,
launching the published `aeat` package via `uvx`) replaces the signed `.mcpb` as the
consumer path; the `.mcpb` artifact is demoted to a secondary kept only if measurement
shows classic-Desktop demand. R8's INTENT — one-click install for a non-technical
taxpayer, the identical server reachable by any MCP client — carries over unchanged;
only the vehicle is superseded. The original ruling follows for the decision trail.

**Chosen — a signed `.mcpb` Desktop Extension as the consumer path, the same server for any MCP client.** The console ships as a signed Desktop Extension (a local server beside the encrypted store) so a non-technical taxpayer installs it with one click and no JSON editing; the identical server is reachable by any MCP client for power users. It rides the `aeat[agent]` extra. Transport is `stdio` now; HTTP is deferred and added only if a remote-client need materialises. No alternative was preferred: a developer-only manual-config path is strictly weaker for the target user, and an embedded runtime contradicts the "any client, one console" definition.

### R9 — Off-host consent posture

**Chosen — conversation off-host by the client's nature, evidence bytes never off-host, stated at first run.** Any API-backed client sends the user's typed text and the tool results the model sees to that client's LLM provider; this is treated as consented conversational input. Evidence bytes **never leave the host** — never as tool output, never elicited, never a resource — with the console as the enforcement funnel (evidence stays as on-host references the model never sees expanded). A first-run consent notice states exactly this: your words and the figures the assistant sees go to your chosen LLM provider; your source documents never leave your machine. This preserves the relation to the secure-storage invariant. It is recorded as decided here with operator ratification pending.

## Constraints

**Two parent ADRs.** This refoundation rests on the accepted `2026-06-30-agent-harness-adr` (whose `Q1`–`Q6` it inherits) and the proposed `2026-07-01-agent-harness-adr` (whose `D1`–`D7` it extends). The second is proposed-status; the decisions here that build on it inherit that provisional standing until it is accepted.

**Permanent safety rails.** `aeat-safety-legal-gates` makes live AEAT submission permanently forbidden — no console tool may ever expose it, and R6(iv) is that rail, not a configurable policy. `sensitive-financial-data-secure-storage-only` binds R9 and R6: evidence bytes persist only in encrypted secure storage, are never elicited, and never re-enter the model context expanded.

**Search licensing is a blocking item for R3.** `shipped-search-licence-clean` binds the semantic-search stack: the embedding model, lexical engine, and index-build story must be licence-clean and shippable in the wheel (or a gated extra). The engine choice is **undecided and deferred to the implementation plan behind an explicit licence gate**; R3's hybrid surface cannot ship until that gate is satisfied.

**MCP client capability unevenness.** Client support is negotiated: `tools` near-universal, `prompts`/`resources` partial, `elicitation` newest and least universal. This is the floor/enhancement design rule that binds R2, R4, and R6 — every capability above tools must degrade cleanly. The current spec revision is `2025-11-25`.

**The CLI two-root rule.** `aeat config` and `aeat app` are the only command roots; the console is a **sibling entry point** (`aeat-mcp`), never a third root. The `aeat[agent]` extra rides the acceptance of the product-packaging ADR, exactly as the accepted parent ADR already requires.

## Implementation

A high-level layering; no code accompanies this ADR. Notably, **the CLI surface itself needs almost nothing new** — the black-box discipline holds, and the load-bearing verbs (the `overview` backlog/agenda/explain derivation, `work amend`, the complementaria/sustitutiva path) already exist. The one possible CLI addition is a per-verb schema export from the CLI's own registry to feed R2's input schemas.

- **Console server evolution.** Group the manifest-derived tools into domain toolsets; attach `readOnlyHint`/`destructiveHint` annotations to every tool; surface per-verb input schemas in place of the `{args: [string]}` bag; add the `search`+`execute` meta-tool fallback for the long tail.
- **Grounding surface.** Build the on-host hybrid index from the bundled `.extracted` triples; expose the hybrid search tool over corpus, citations, manuals, and terminology; add `aeat://corpus/{ref}` resources resolving citations to verbatim text.
- **Operating-layer channels.** Add the `harness.load` floor tool; the `aeat://skill|rule|persona/{name}` resource templates; the guided-workflow prompts embedding skill plus grounding; and the optional `.claude/skills` materialisation, all fed from the single `src/aeat/_data/agent/` source.
- **Skill metadata and situation skills.** Lift each skill's selection predicate into the structured `applies_when` frontmatter field; author the six WHEN-layer skills, `regularizar-atrasos` first over the already-built backlog/recargo surface.
- **Gate wiring.** Wire the CONFIRM tier to elicitation with the degradation matrix; wire faithfulness into the serving path with the handoff hard block; add the per-verb handoff deny rules over the family-granular persona scope.
- **Live eval and telemetry.** Build the live subagent-persona harness (real server, real client session, trajectory capture, scoring on observed calls), the local per-call telemetry records, the real-client handshake conformance floor, and the flywheel that promotes live failures to golden scenarios.
- **Packaging.** Assemble and sign the `.mcpb` Desktop Extension behind the `aeat[agent]` extra, `stdio` transport.

## Rationale

Every resolution follows the research directly and re-uses a settled pattern for the job it is good at. R1 records the operator's corrected universe definition and states supersession precisely so the decision trail stays linear rather than re-litigating settled questions — the prior ADRs' safety, home, and naming decisions were never the mistake; the delivery vehicle, the flat surface, and the bespoke-runtime assumption were. R2 resolves the load-bearing progressive-disclosure problem with toolsets for the common domains and meta-tools for the tail, and keeps the console manifest-derived so it cannot drift from the CLI — the same single-authority discipline the proposed ADR's D1 applied to persona scope. R3 gives the product the licence-clean, on-host retrieval surface it lacks, building on already-bundled extracted text. R4's floor-first delivery is the direct consequence of negotiated client capability: the one channel that always reaches the model is a tool, and everything richer is enhancement. R5 uses each skill axis for what it is good at — WHO for stable entry, WHEN for temporal sequencing, WHICH for execution — and makes the selection signal machine-queryable, extending the proposed ADR's D5 derivation principle rather than replacing its D6 per-modelo executable unit. R6 turns three nominal gates into real ones and closes the D3 family-scope caveat structurally. R7 is the operator's measurement directive: the prose is the code under test, so only a live model driving the real console is a faithful gate, and self-hosting keeps trajectories on-host. R8 and R9 make "the user's own client" a real, safe distribution story. Every decision is the project-specific application of a pattern the external landscape and the prior ADRs have already settled.

## Consequences

**Gains.** The harness stops being a static content bundle plus an unwired shell and becomes an operable, measured console: any MCP-capable client gets grounded search, the operating layer over the protocol, real safety gates, and a live model-in-the-loop assurance regime with hard never-submit and faithfulness invariants. `regularizar-atrasos` alone exposes a fully-built, high-value late-filer surface that is currently invisible. The manifest-derived toolsets mean the console tracks the CLI for free.

**Honest difficulties.** The semantic-search engine is undecided and licence-gated; R3 cannot ship until that gate is closed, and a wrong engine choice strands the grounding surface. Elicitation is the least-universal capability the safety story now leans on, so the degradation matrix must be decided and tested, not assumed — and the spec's prohibition on eliciting sensitive data means evidence handling stays a hard on-host constraint. The live subagent-persona harness is a new, non-trivial test substrate whose own reliability (model non-determinism, cost, latency per session) must be managed so it does not become a flaky gate. R9's off-host boundary rests on the console being a perfect evidence funnel; any tool result that leaks raw bytes into the model context breaks it, so the scrubbing boundary needs its own conformance gate. The proposed parent ADR is not yet accepted, so decisions extending its `D1`–`D7` inherit that provisional standing.

**Pathways opened.** The manifest-derived toolset surface and the on-host grounding index feed documentation generation, future personas, and additional situation skills without re-deriving the catalogue. The live harness plus the telemetry flywheel become the standing assurance loop — every rule, skill, prompt, and tool-description change is re-measured against a real model, and every live failure becomes a golden regression — turning the harness from a shipped artifact into a continuously-verified operating system for the black-box tool universe.
