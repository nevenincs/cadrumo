---
tags:
  - "#adr"
  - "#agent-harness-refoundation"
date: '2026-07-02'
related:
  - "[[2026-07-02-agent-harness-refoundation-research]]"
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
  - "[[2026-07-08-mcp-protocol-hardening-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - '[[2026-07-31-semantic-search-precompile-boundary-adr]]'
supersedes:
  - '2026-06-30-agent-harness-adr'
  - '2026-07-01-agent-harness-adr'
modified: '2026-10-12'
body_hash: 'sha256:ed2eec9a896529170807af742ac0bca1ed4ca2aa33f0564c2844381792325327'
---
# `agent-harness-refoundation` adr: `black-box tool universe, situation-keyed skills, and the MCP operating console` | (**status:** `accepted`)

## Problem Statement

Two earlier harness drafts settled the four-layer shape, MCP end-state, rules,
personas, and skills under a universe definition that the 2026-07-02 operator
directive corrected. Their durable decisions are consolidated below; the
predecessor ADRs are retained as superseded history; this ADR is the current harness authority.
The drafts also left the harness unfinished in two defining ways: no live
language model had driven the CLI through it, and there was no accepted way to
measure or operate it.

The corrected universe definition is the load-bearing change. The Cadrumo CLI, exposed through the `aeat` executable, is a **black box**: a bundled, deterministic tool universe for calculating and manipulating tax data, not a codebase to be interfaced with. The agent harness is the **framework of rules, personas, and skills for operating safely and effectively within that confined universe**, and it serves **any** language model the user already runs — there is no bespoke embedded chat runtime. One MCP server is the **operating console**: it must ground user requests, understand the bundled legal corpus, run semantic search, hold deep knowledge of the CLI surface, ask the user questions when input is needed, and actually operate the CLI on the user's behalf. That is materially more than the verb-wrapper server shipped today.

This ADR is the consolidated authority. It records what carries over and what
is superseded, and it resolves the nine decisions the
`2026-07-02-agent-harness-refoundation-research` document raised: the universe
definition (R1), console tool architecture (R2), grounding (R3), client delivery
(R4), skill taxonomy (R5), safety gates (R6), live-model measurement (R7),
distribution (R8), and off-host consent (R9).

## Considerations

**Most of the earlier decision surface survives; the universe re-definition
re-frames it rather than discarding it.** The consolidated decisions below are
binding parts of this accepted ADR. What changes is which delivery mechanism is
primary and how large the console's mandate is — not the safety posture,
artifact home, or naming discipline.

**The CLI-as-contract substrate already embodies the black-box discipline.** The operator-surface manifest (`build_operator_surface_manifest`, `aeat app contract`), the `SchemaEnvelope`/`Notice`/`ExitCode` reading surface, and the rule-surface drift gate all treat the CLI as the only citable surface and execute every operation by shelling `aeat --format json`. This layer carries over unchanged and is the natural authority the console derives its tools from.

**The console's five required powers exist only in fragments today.** Grounding is half-present (the obligation-derivation verbs exist; natural-language mapping is correctly the model's job). The legal corpus is reachable only as citation metadata — the verbatim legal text never reaches the operator, and no semantic search exists anywhere in the product. Deep CLI knowledge is the strongest pillar but the per-verb argument schemas are absent from the tool surface (a generic `{args: [string]}` bag). Gated execution exists but two of its three gates — the CONFIRM tier and the faithfulness check — are computed in library code and never wired into the serving path. The operating layer (rules, personas, skills, the terminology handbook) ships as reachable wheel data that the server process never imports.

**Client capability is negotiated, not assumed.** Across surveyed MCP clients, `tools` is near-universal, `prompts` and `resources` are widely but not universally supported, and `elicitation` is the newest and least universal capability. This forces a floor/enhancement design rule at every layer: functionality that must always reach the model rides a tool; richer channels are progressive enhancements that must degrade cleanly when absent.

**Measurement must exercise the thing that is actually at risk.** The prose of the rules, personas, skills, and tool descriptions is the code under test; a replay gate that asserts byte-identical re-resolution of recorded calls cannot fail on model misbehaviour. The only faithful measurement is a live model driving the real console.

## Considered options

### R1 — Universe re-definition and predecessor consolidation

*Continue the prior framing* (the harness as an operating layer over a ~75%-agent-ready backbone, delivered primarily by materialising a workspace): rejected — it treats the CLI as a codebase to be interfaced with and a bespoke workspace as the product, which the 2026-07-02 operator directive explicitly corrects.

**Chosen — the black-box tool universe with one MCP operating console, serving
any language model.** The CLI is a confined deterministic tool universe; the
harness is the rules and skills for operating within it; the console is the
single operating surface for any MCP-capable client. The workspace materialiser
is optional, flat `tools/list` is replaced by progressive disclosure, and the
harness targets the user's existing client rather than a bespoke runtime.

#### Consolidated Q1–Q6 decisions

- **Q1:** prove the rules and one golden workflow over the manifest-backed JSON
  CLI first, then use the same manifest as the MCP tool authority.
- **Q2:** authored harness data lives at `src/cadrumo/_data/agent/`; MCP is a
  sibling entry point and packaging is governed by the current Cadrumo
  distribution decisions.
- **Q3:** manifest mutability annotations drive client confirmation while the
  CLI's deterministic guards remain the non-bypassable backstop; live submit is
  never exposed.
- **Q4:** faithfulness mismatch is advisory during reversible narration and a
  hard block at export or record-marker handoff.
- **Q5:** golden tasks assert real tool trajectories, argument validity,
  authoritative value oracles, and provenance; replay excludes only explicitly
  non-deterministic fields.
- **Q6:** Spanish tax-domain stems remain Spanish, generic computing vocabulary
  remains English, and tool names are unambiguous. `aeat` is the human CLI;
  product-owned Python and MCP identities are `cadrumo`.

#### Consolidated D1–D7 decisions

- **D1:** persona scope is filtered from the live manifest by `(family,
  mutability)` and pinned by a build-time assertion, never copied into a second
  allowlist.
- **D2:** live reads that write derived local state remain
  `LOCAL_STATE_MUTATING`; the unused `LIVE_READ` fork is retired after a
  zero-consumer check.
- **D3:** an agent may export and record the filed marker exactly as the command line
  can. Telling the person before the hand-off, and having an independent verifier check
  the work first, is conduct the packaged agent text describes, not a product gate; the
  same agent run a second time is not an independent verifier. (Amended 2026-10-12 under
  `2026-10-11-mcp-parity-full-parity-adr`. On 2026-10-10 an agent performed either act
  only after the person approved that exact act in Cadrumo; before that the verifier
  owned both so the preparer could not self-certify the irreversible handoff.)
- **D4:** rules separate behavioural invariants, manifest-derived orientation,
  and lifecycle ordering; a manifest-derived negative gate rejects internal
  package, private-module, and test names in operator rules.
- **D5:** Tier-A itinerary skills derive from explicit taxpayer-profile facts;
  they are never an open-ended hand-curated roster.
- **D6:** the executable unit is one skill per registry-modelled modelo, authored
  by difference from one shared lifecycle spine; category material is reference
  content and personas are thin entry itineraries.
- **D7:** verifier context must be constructible from tool-result JSON without
  the preparer's transcript. Separate invocation is structural enforcement;
  self-report is explicitly degraded trust.

### R2 — Console tool architecture

**Status: AMENDED by the accepted `2026-07-08-mcp-progressive-discovery-adr` (P1–P4).**
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

**Status: AMENDED by the accepted `2026-07-31-semantic-search-precompile-boundary-adr`.**
The operator's 2026-07-31 directive clarified that semantic search is a precompile
step, not a runtime dependency, and an independent audit
(`2026-07-31-corpus-search-model-cache-capability-gap-audit`) found R3's runtime
embedding stack silently dropping its model-revision pin and app storage root on
every load. The amending ADR retires R3's runtime embedding half — the query
embedder, corpus vector build, and hybrid semantic/lexical fusion — and confines
shipped retrieval to lexical search over the bundled corpus plus verbatim citation
resolution; a future laundered, precompiled semantic artefact remains an open
pathway, not a commitment. R3's INTENT — a grounding tool over the bundled
BOE/AEAT corpus with citation-resolving resources, served on-host — carries over
unchanged; only the runtime-embedding mechanism is amended. This is not a
reversal of R3 or a discovered inconsistency: R3 was a deliberate decision, made
behind a licence gate later satisfied, and predates the operator's 2026-07-31
clarification; only its implementation broke its own reproducibility and
storage-root promises. The original ruling follows for the decision trail.

*Id/topic lookup only (status quo):* citations resolve to metadata, never to legal prose — rejected: the operator cannot read the authoritative text a figure rests on.

*Lexical-only search:* exact citation matching but weak semantic recall — rejected alone: compliance queries need both exact-citation and concept recall.

**Chosen — a hybrid lexical + semantic corpus search tool plus citation-resolving resources.** A single grounding tool searches the bundled BOE/AEAT corpus, registry citations, manuals, and the terminology handbook with hybrid retrieval (lexical for exact citations, embedding for semantic recall — the regulated-domain IR consensus). Paired `cadrumo://corpus/{ref}` resources resolve any citation to verbatim authoritative text. The index builds from the already-bundled `.extracted.md`/`.extracted.json` triples, so no new extraction pipeline is needed, and it is built and served **on-host**. The embedding/lexical engine, model, and index-build story are undecided and licence-bound (see Constraints); the engine choice is deferred to the plan behind a licence gate.

### R4 — Operating-layer delivery

*Materialise a workspace as the primary vehicle (status quo):* rejected as primary — it is a dead-end export no in-repo consumer reads, is Claude-shaped, and does not reach an arbitrary client through the protocol.

**Chosen — one authored source, four channels, floor-first.** The universal floor is a `harness.load` tool returning the operator rules and active persona as text — the only channel guaranteed to reach a model on a minimal tools-only client. Layered on top: resource templates `cadrumo://skill|rule|persona/{name}` for enumerable pull; MCP prompts as slash-command guided workflows that embed the matching skill plus its grounding excerpt; and optional `.claude/skills` materialisation (repurposing the existing `aeat app agent` materialiser) as a Claude-native enhancement, never the baseline. A single authored source in `src/cadrumo/_data/agent/` feeds all four channels, matching the one-authored-source/generated-outputs discipline. Each channel above the floor degrades cleanly when its capability is absent.

### R5 — Skill taxonomy and metadata

*Tax-domain-primary:* rejected — situations and users both span domains, so a domain-primary tree fractures every real itinerary.

*Persona-primary rewrite:* rejected — re-keying the whole executable layer to archetypes reintroduces the lifecycle duplication the proposed ADR's D6 already resolved by making the per-modelo skill the executable unit.

**Chosen — WHO primary, WHEN as an orthogonal overlay, WHICH as the executable leaves.** The regimen/user-type itineraries (WHO) stay primary — the strongest, most stable profile predicates. A new orthogonal **life-situation (WHEN)** layer is added as a temporal overlay that sequences the existing per-modelo skills: six new skills in Spanish stems — `regularizar-atrasos` **first** (its CLI surface, the `overview backlog` past-due/recargo path, is fully built and completely unexposed), then `cierre-trimestre`, `resumen-anual`, `rectificar-declaracion`, `inicio-actividad`, and `cese-actividad`. Per-modelo skills (WHICH) remain the executable leaves. Each skill's selection predicate is **lifted from prose `description` into a structured frontmatter field** (`applies_when` over `TaxpayerProfile` facts and lifecycle state) so routers, MCP prompts, and eval scenarios can query it deterministically. Composition: situation confirms obligations via `overview` → itinerary narrows → per-modelo skill executes.

### R6 — Gate enforcement

*Leave the gates nominal (status quo):* rejected — the CONFIRM tier and the faithfulness check are computed but never wired into the serving path, so only the permanent live-write block is real.

**Chosen — wire all three, floor-aware.** (i) No product approval gate stands in front of any operation on MCP; every operation inside the bound profile is served there as on the command line, and authentication, session administration and acts outside the profile are not served (narrowed 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`). An elicitation answer or a client's confirmation hint is never treated as authority. (Amended 2026-10-12 under `2026-10-11-mcp-parity-full-parity-adr`. On 2026-10-10 reserved operations did not admit the MCP frontend until a runtime approval step existed; before that the CONFIRM tier was enforced via MCP elicitation, falling back to `destructiveHint`-driven client confirmation.) (ii) The `faithfulness_check` is an advisory notice on narration mismatch and a measure in R7's live harness. (Amended 2026-10-12; its escalation to a hard block at the export / record-marker boundary is withdrawn, because it would refuse on MCP what the command line does.) (iii) Persona scope narrows what is presented, never what is admitted. (Amended 2026-10-12; the per-verb deny rules the console was to add for the handoff boundary are withdrawn with D3's gate.) (iv) Never-live-submit stays enforced as "no such tool exists" — the strongest form. A hard spec constraint binds (i): **elicitation must never request sensitive information**, so evidence bytes stay on-host and are never elicited.

### R7 — Measurement and live verification

*Replay-only (status quo):* rejected — it asserts registry/CLI determinism but cannot fail on model misbehaviour, which is exactly the risk under the corrected definition.

*External SaaS trajectory eval:* rejected — it ships trajectories (and the figures in them) off-host, against the on-host posture.

**Chosen — a self-hosted live subagent-persona harness** (operator directive, 2026-07-02). Capabilities are measured by **live subagent personas**: spawned language-model subagents playing the harness personas, operating the console end-to-end against golden scenarios. The substrate (a) starts the real `cadrumo-mcp` server, (b) connects a real MCP client session driven by a subagent persona, (c) captures the full trajectory (tools selected, arguments, elicitation responses, narration), and (d) scores it against the existing golden-scenario models plus the faithfulness and confirmation checks **now applied to observed calls**, not caller-injected verdicts. Hard invariants: **zero live-submit attempts and zero faithfulness violations at the handoff boundary**. A data flywheel promotes live failures into new golden scenarios. A real-client handshake conformance test (`initialize` / tools-list / call round-trip) is the floor beneath the live harness.

### R8 — Distribution

**Status: AMENDED by the accepted `2026-07-03-claude-ecosystem-packaging-adr` (D3a).** The
Claude plugin (marketplace-served, generated from the single authored harness source,
launching `cadrumo-mcp` from the published `cadrumo[agent]` distribution via `uvx`) replaces the signed `.mcpb` as the
consumer path; the `.mcpb` artifact is demoted to a secondary kept only if measurement
shows classic-Desktop demand. R8's INTENT — one-click install for a non-technical
taxpayer, the identical server reachable by any MCP client — carries over unchanged;
only the vehicle is superseded. The original ruling follows for the decision trail.

**Chosen — a signed `.mcpb` Desktop Extension as the consumer path, the same server for any MCP client.** The console ships as a signed Desktop Extension (a local server beside the encrypted store) so a non-technical taxpayer installs it with one click and no JSON editing; the identical server is reachable by any MCP client for power users. It rides the `cadrumo[agent]` extra. Transport is `stdio` now; HTTP is deferred and added only if a remote-client need materialises. No alternative was preferred: a developer-only manual-config path is strictly weaker for the target user, and an embedded runtime contradicts the "any client, one console" definition.

### R9 — Off-host consent posture

**Chosen — conversation off-host by the client's nature, evidence bytes never off-host, stated at first run.** Any API-backed client sends the user's typed text and the tool results the model sees to that client's LLM provider; this is treated as consented conversational input. Evidence bytes **never leave the host** — never as tool output, never elicited, never a resource — with the console as the enforcement funnel (evidence stays as on-host references the model never sees expanded). A first-run consent notice states exactly this: your words and the figures the assistant sees go to your chosen LLM provider; your source documents never leave your machine. This preserves the relation to the secure-storage invariant. It is recorded as decided here with operator ratification pending.

## Constraints

**Single authority.** The consolidated Q1–Q6 and D1–D7 decisions above are
accepted here. No deleted predecessor status or wording remains independently
binding.

**Permanent safety rails.** `aeat-safety-legal-gates` makes live AEAT submission permanently forbidden — no console tool may ever expose it, and R6(iv) is that rail, not a configurable policy. `sensitive-financial-data-secure-storage-only` binds R9 and R6: evidence bytes persist only in encrypted secure storage, are never elicited, and never re-enter the model context expanded.

**Search licensing is a blocking item for R3.** `shipped-search-licence-clean` binds the semantic-search stack: the embedding model, lexical engine, and index-build story must be licence-clean and shippable in the wheel (or a gated extra). The engine choice is **undecided and deferred to the implementation plan behind an explicit licence gate**; R3's hybrid surface cannot ship until that gate is satisfied.

**MCP client capability unevenness.** Client support is negotiated: `tools` near-universal, `prompts`/`resources` partial, `elicitation` newest and least universal. This is the floor/enhancement design rule that binds R2, R4, and R6 — every capability above tools must degrade cleanly. The current spec revision is `2025-11-25`.

**The CLI two-root rule.** `aeat config` and `aeat app` are the only command roots; the console is a **sibling entry point** (`cadrumo-mcp`), never a third root. The `cadrumo[agent]` extra rides the acceptance of the product-packaging ADR, exactly as the accepted parent ADR already requires.

## Implementation

A high-level layering; no code accompanies this ADR. Notably, **the CLI surface itself needs almost nothing new** — the black-box discipline holds, and the load-bearing verbs (the `overview` backlog/agenda/explain derivation, `work amend`, the complementaria/sustitutiva path) already exist. The one possible CLI addition is a per-verb schema export from the CLI's own registry to feed R2's input schemas.

- **Console server evolution.** Group the manifest-derived tools into domain toolsets; attach `readOnlyHint`/`destructiveHint` annotations to every tool; surface per-verb input schemas in place of the `{args: [string]}` bag; add the `search`+`execute` meta-tool fallback for the long tail.
- **Grounding surface.** Build the on-host hybrid index from the bundled `.extracted` triples; expose the hybrid search tool over corpus, citations, manuals, and terminology; add `cadrumo://corpus/{ref}` resources resolving citations to verbatim text.
- **Operating-layer channels.** Add the `harness.load` floor tool; the `cadrumo://skill|rule|persona/{name}` resource templates; the guided-workflow prompts embedding skill plus grounding; and the optional `.claude/skills` materialisation, all fed from the single `src/cadrumo/_data/agent/` source.
- **Skill metadata and situation skills.** Lift each skill's selection predicate into the structured `applies_when` frontmatter field; author the six WHEN-layer skills, `regularizar-atrasos` first over the already-built backlog/recargo surface.
- **Gate wiring.** Wire the CONFIRM tier to elicitation with the degradation matrix; wire faithfulness into the serving path with the handoff hard block; add the per-verb handoff deny rules over the family-granular persona scope.
- **Live eval.** Build the live subagent-persona harness (real server, real client session, trajectory capture, scoring on observed calls), the real-client handshake conformance floor, and the flywheel that promotes live failures to golden scenarios.
- **Packaging.** Assemble and sign the `.mcpb` Desktop Extension behind the `cadrumo[agent]` extra, `stdio` transport.

## Rationale

Every resolution follows the research directly and reuses a settled pattern for
the job it is good at. R1 keeps the decision trail linear: the safety, artifact
home, and naming decisions survive; the delivery vehicle, flat surface, and
bespoke-runtime assumption do not. R2 keeps the console manifest-derived so it
cannot drift from the CLI, applying D1's single-authority discipline. R3 gives
the product a licence-clean on-host retrieval surface. R4 is floor-first because
only tools are universal across target clients. R5 preserves D5's derivation and
D6's per-modelo executable unit. R6 makes the nominal gates real and closes D3's
handoff boundary structurally. R7 measures the prose through a live model driving
the real console. R8 and R9 make the user's own client a safe distribution story.

## Consequences

**Gains.** The harness stops being a static content bundle plus an unwired shell and becomes an operable, measured console: any MCP-capable client gets grounded search, the operating layer over the protocol, real safety gates, and a live model-in-the-loop assurance regime with hard never-submit and faithfulness invariants. `regularizar-atrasos` alone exposes a fully-built, high-value late-filer surface that is currently invisible. The manifest-derived toolsets mean the console tracks the CLI for free.

**Honest difficulties.** The semantic-search engine is licence-gated; R3 cannot
ship until that gate closes. Elicitation remains uneven across clients, so the
degradation matrix must be tested. Evidence handling stays on-host. The live
model harness must control non-determinism, cost, and latency, and the R9
scrubbing boundary needs its own conformance gate so raw evidence bytes cannot
enter model context.

**Pathways opened.** The manifest-derived toolset surface and the on-host grounding index feed documentation generation, future personas, and additional situation skills without re-deriving the catalogue. The live harness plus the flywheel become the standing assurance loop — every rule, skill, prompt, and tool-description change is re-measured against a real model, and every live failure becomes a golden regression — turning the harness from a shipped artifact into a continuously-verified operating system for the black-box tool universe.

## Amendment 2026-09-26: shared application execution beneath all entrypoints

Accepted under the operator's instruction to continue the presented mcp-purpose-authentication plan. 2026-09-26-mcp-purpose-authentication-adr replaces the CLI-subprocess-only parts of R1, Q1, the CLI-as-contract consideration and their dependent implementation prose. The application operation/action authorities supply typed contracts and policy; CLI JSON, TUI and MCP are projections over the shared local runtime.

Through the MCP server the agent sees a confined deterministic tool universe: the server offers no arbitrary code, SQL or shell capability and performs no work by invoking the command line. What an assistant does with a terminal of its own is outside this record. MCP may call the public application operation boundary without going through command functions or an aeat subprocess. Catalogue-derived discovery, operating-layer content, provenance, human approval where the operation itself requires it on every frontend and the applicable never-live-submit/data-disclosure rules survive.

Persona/tool filtering can narrow presentation but cannot grant authority. Runtime credential, profile, scope and disclosure checks remain mandatory on every path. Client confirmation hints and an LLM's claimed approval never replace application authorization. API-key enrollment and secret collection are governed by 2026-09-26-mcp-purpose-authentication-profile-access-adr and use trusted local CLI, TUI and desktop channels only. No MCP tool call carries a secret or names one by reference, and the agent never authenticates. (Amended 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`. Earlier that day, under `2026-10-11-mcp-parity-full-parity-adr`, an MCP tool call could carry a typed secret to the runtime's protected frame or name one by reference; before that, trusted local CLI/TUI channels only.) This does not reopen unrelated skill taxonomy or distribution decisions.

## Amendment 2026-10-10: the hand-off belongs to the person

Accepted under the acceptance of `2026-10-10-mcp-parity-admission-rulings-adr` and `2026-10-10-mcp-parity-parity-mechanism-adr`, on the operator's rulings of that day. D3 and R6(i) are reworded in place, each with a note of what it said before. The hand-off rule is kept in intent and applied to a single agent: export and the record marker are the person's to approve, in Cadrumo, each time, and the runtime enforces it. R6(iii)'s per-verb deny rules for the hand-off are met by keeping reserved operations off the MCP frontend until that approval step exists. The implementation line that wires the CONFIRM tier to elicitation is superseded with R6(i). R6(iv), the hard block at the hand-off and the invariant of zero submission attempts are unchanged. The first sentence of the second paragraph of the 2026-09-26 amendment is reworded: the confinement it states is a property of the MCP server, and the operator has ruled that an assistant may also hold Cadrumo's command line and Python as a door of its own.

## Amendment 2026-10-12: parity of the three frontends

Accepted under `2026-10-11-mcp-parity-full-parity-adr`, which supersedes `2026-10-10-mcp-parity-admission-rulings-adr` on the owner's ruling that MCP never refuses anything the command line can do. D3, R6(i), R6(ii), R6(iii) and the 2026-09-26 amendment's secret-collection sentence are reworded in place, each with a note of what it said before. The 2026-10-10 amendment above is history: the person's approval of export and the record marker, and keeping reserved operations off the MCP frontend until an approval step exists, no longer apply. What remains of the hand-off rule is the agent's conduct as the packaged rules, personas and skills describe it. R6(iv), never-live-submit, and R7's invariant of zero submission attempts are unchanged. (Amended later on 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`: as first written, this amendment also let an MCP tool call carry a typed secret or name one by reference, and served every operation on MCP. Parity now holds for operations inside the bound profile only. MCP carries no secret, and the agent never authenticates, administers sessions or acts outside its profile. The 2026-09-26 amendment's secret sentence and R6(i) are reworded again in place.)
