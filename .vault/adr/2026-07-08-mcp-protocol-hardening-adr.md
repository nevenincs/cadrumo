---
tags:
  - '#adr'
  - '#mcp-protocol-hardening'
date: '2026-07-08'
modified: '2026-07-17'
related:
  - "[[2026-07-08-mcp-protocol-hardening-research]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
---

# `mcp-protocol-hardening` adr: `long-running call contract, schema fidelity, and declared protocol boundaries` | (**status:** `accepted`)

## Problem Statement

The 2026-07-08 review of the aeat MCP console (companion
`mcp-progressive-discovery` ADR owns the tool-surface architecture) found a
second class of gaps: places where the console's use of the protocol is
incomplete, lossy, or fragile regardless of how the surface is shaped. The
sharpest is operational: every tool call is one blocking subprocess run with
no timeout, no progress notification, and no cancellation
(`src/cadrumo/entrypoints/mcp/_server.py`, lines 225–271), so a Playwright-backed
AEAT portal pull that legitimately takes minutes hangs the client — and many
clients time out a `tools/call` well under a minute, reading a legitimate
slow pull as failure. Around it cluster: per-verb input schemas that
silently drop non-scalar defaults and cannot express turning OFF a
default-on boolean flag; annotation axes inferred from hand-listed leaf
frozensets with `openWorldHint` never populated; every result inlining its
full payload with the spec's `resource_link` mechanism unused; 35 prompts
with `arguments=[]` and no completions handler; an undeclared localization
boundary; unbounded telemetry growth; and two protocol-security stances
(untrusted portal content, secret collection) that are held in practice but
recorded nowhere. This ADR decides each so the paired plan can close them.

## Considerations

- **The protocol offers two long-running mechanisms and one is a trap.** The
  2025-11-25 Tasks utility is experimental, already deprecated in the Python
  SDK v1.28 line, and redesigned with a breaking wire change in the
  2026-07-28 release candidate. Progress notifications on a blocking call
  are stable, universally supported, and sufficient for a local console.
- **The CLI is a black box.** Progress signal must come from the boundary
  the console owns (subprocess lifetime, heartbeats, coarse stages), not
  from instrumenting CLI internals; per-verb timeout tiers can key off the
  same annotation/HITL classification the gates already use.
- **Declared data beats heuristics** (`aeat-schema-central-config`): the
  destructive/idempotent/handoff/live-write axes are closed sets scattered
  as leaf-name frozensets today; a new mutating verb outside the lists
  silently classifies as non-destructive.
- **Result-size economics.** Structured output double-emits by spec
  (text content + structuredContent, roughly 2x tokens); large provenance
  and evidence arrays inflate every calculation result; `resource_link`
  lets bulk payloads ride as on-demand URIs and doubles as protocol-level
  reinforcement of the R9 references-not-bytes funnel.
- **Client validation reality.** Clients SHOULD validate structuredContent
  against outputSchema; the console already registers per-verb output
  schemas, so payload trimming must stay schema-conformant.
- **Security best-practice sheet (2025-11-25).** Annotations are untrusted
  hints (already honoured — server-side gates enforce); form-mode
  elicitation MUST NOT collect secrets (already honoured — no secret ever
  rides any MCP channel); third-party content relayed into the model
  context is a prompt-injection vector (currently un-marked).

## Considered options

### H1 — Long-running call contract

- *2025-11-25 Tasks API:* protocol-pure non-blocking handles. Rejected:
  deprecated in the v1.x SDK, breaking redesign in the RC — building on it
  buys a forced migration.
- *Status quo (block forever):* rejected — hangs are unkillable and client
  timeouts misread slow pulls as failures.
- **Chosen — blocking call + progress notifications + tiered timeouts +
  cancellation.** The subprocess runner gains a timeout tier derived from
  the verb's classification (generous for the live/sede family, tight for
  local reads, explicit table in the plan); while a call runs the server
  emits `notifications/progress` heartbeats (elapsed + coarse stage) when
  the client supplied a progress token; client cancellation and timeout
  expiry terminate the subprocess and return an instructive, localized
  refusal naming the timeout tier and retry guidance. Migration to the
  redesigned Tasks extension is explicitly deferred until the v2 SDK is
  stable.

### H2 — Input-schema fidelity

- *Leave lossy spots:* rejected — a client literally cannot express
  disabling a default-on flag, and a Typer declaration bug ships as a
  silently empty schema.
- **Chosen — faithful defaults, expressible flag pairs, loud degradation.**
  JSON-safe renderings of real defaults (paths as strings, tuples as
  arrays); boolean options with a secondary off-token accept explicit false
  and emit it; a lazy-subcommand materialisation failure fails the
  schema-coverage gate (build-time) instead of silently yielding an
  argument-free schema.

### H3 — Annotation completeness and declaration authority

- *Keep leaf frozensets:* rejected — fail-open on new verbs, contradicts
  the declared-data discipline.
- **Chosen — manifest-adjacent declaration plus openWorldHint.** The
  destructive/idempotent/handoff/live-write axes become declared data
  keyed by command key (one typed classification table co-located with the
  operator-surface manifest), with a parity gate asserting every mutating
  verb in the manifest carries an explicit classification — a new verb
  without one fails loudly. `openWorldHint=true` is derived for the
  live/sede-interacting family. Annotations remain hints; the server-side
  gates keep consuming the same classification, so client UI and
  enforcement cannot drift.

### H4 — Result-size policy

- *Inline everything (status quo):* rejected — pays double-emit on bulk
  provenance every call.
- **Chosen — typed summary inline, bulk payloads as resource links.**
  structuredContent stays the typed summary a client acts on; large
  provenance/evidence collections ride as `resource_link` URIs resolved by
  the existing resource read handlers; a size-budget conformance check
  flags verbs whose structured summaries exceed the budget. Output schemas
  update in lock-step so results stay conformant.

### H5 — Localization boundary (explicit ruling)

- **Chosen — the model-facing surface (tool names, descriptions, input
  schemas, prompt names) is deliberately English; the operator-facing
  surface (elicitation prompts, refusals, notices, prompt display titles
  where clients render them to humans) is localized.** Recorded and gated
  so the locale parity gates know their boundary and the next audit does
  not read English descriptions as drift.

### H6 — Telemetry retention

- **Chosen — bounded retention.** Age- and count-based pruning of
  per-session trajectory files at server start, a documented read path,
  and a conformance test that the pruning never touches the newest N
  sessions. Payload-free posture unchanged.

### H7 — Untrusted external content boundary

- *Relay portal-derived text verbatim (status quo):* rejected as
  undocumented — AEAT portal HTML/justificante text is untrusted input to
  the model (prompt-injection vector).
- **Chosen — typed-fields-only relay, marked provenance.** Live-pull
  results already flow through typed envelopes; the ruling makes it a
  contract: no raw portal HTML/markup reaches a tool result, free-text
  fields sourced from portal content are tagged with their source kind in
  the envelope, and a conformance gate asserts the no-markup invariant on
  the live family's result schemas.

### H8 — Secret collection stance (explicit ruling)

- *URL-mode elicitation for credentials (the spec's new channel):*
  rejected for now — the console's decided posture is stronger and
  simpler: secrets are entered only through the local CLI
  (`config auth certificate secret set`) into encrypted storage; NO secret
  ever rides any MCP channel, form or URL. Recorded as the decided
  alternative so the unused spec feature reads as a choice, not a gap.

### H9 — Capability and SDK posture

- **Chosen — pin the negotiated surface.** A conformance test asserts the
  exact capability set the server negotiates (tools, prompts, resources,
  completions and list-changed once the discovery ADR lands); the SDK stays
  `mcp>=1.12,<2` with the v2/RC migration explicitly deferred; the two
  residual grounding-stack hardenings ride along (pin the potion model
  revision to a commit hash; route the model download through the
  app-controlled cache dir).

## Constraints

- **Parent stability.** The refoundation ADR (accepted) and its wired gates
  are the substrate; nothing here alters gate semantics — H1's cancellation
  and timeouts happen outside the gate sequence, and H3 re-homes the data
  the gates already read without changing their decisions.
- **Frontier surface.** SDK deprecation timelines, the RC's Tasks redesign,
  and client progress-token behaviour are July-2026 facts that MUST be
  re-verified against live docs at implementation time (packaging-ADR
  discipline).
- **Sibling coupling.** H3's classification table and H4's resource links
  are consumed by the discovery ADR's search results and resource surface;
  the two plans must sequence the shared modules (annotations, resources)
  to avoid cross-campaign collisions in the shared worktree.
- **Windows process semantics.** Subprocess termination on timeout/cancel
  must be proven on Windows (the primary dev host) — process-tree kill, not
  a dangling Playwright child.
- **Safety rails unchanged.** Never-live-submit, evidence-bytes-never-off-
  host, and the secure-storage rule bind every decision here; H7 and H8
  strengthen their protocol-level expression.

## Implementation

High-level layering; the paired plan owns steps and sequencing.

- **Call runtime.** Replace the bare subprocess run with a supervised
  runner: tiered timeout table keyed off the H3 classification, streamed
  stderr-silent heartbeat progress via the session's progress token,
  cooperative cancellation, process-tree termination, localized timeout
  refusals.
- **Schema fidelity.** Extend the input-schema builder for real defaults
  and off-tokens; convert the silent lazy-resolution fallback into a
  build-time gate failure; extend the argv renderer for explicit-false
  flags.
- **Classification table.** One typed per-command classification record
  (destructive, idempotent, handoff, live-write, open-world) beside the
  operator-surface manifest; annotations and HITL both read it; parity
  gate over the manifest verb inventory.
- **Result thinning.** Identify the bulk-payload verbs (calculation
  observations, evidence lists, corpus excerpts); move bulk arrays to
  resource links backed by the existing read handlers; update output
  schemas; size-budget check.
- **Boundaries and retention.** The localization-boundary gate; the
  no-markup live-family conformance gate; telemetry pruning; the
  capability-set conformance test; the potion revision pin and cache-dir
  passthrough.

## Rationale

Every ruling picks the stable protocol mechanism over the deprecated or
absent one and converts implicit posture into declared, gated contract. H1
follows the research's unambiguous guidance (F1): progress-on-blocking is
the only long-running mechanism that is simultaneously spec-stable,
client-universal, and migration-free, and the timeout/cancellation half is
plain operational hygiene the audit showed missing. H2 and H3 are the same
discipline the CLI boundary already follows (instructive gates, declared
closed sets) applied to the console's schema and annotation surfaces —
F2/F3 showed both are currently heuristic or lossy in ways that fail open.
H4 aligns token economics with the R9 funnel using the spec's own
mechanism (F4). H5, H7, and H8 record stances that were true-in-practice
but invisible, exactly the class of gap the campaign-close honesty reviews
keep re-finding; deciding them now is cheaper than re-litigating them in
every future audit. H6 and H9 are small operational debts named by the
audit (F7, F9, F10). The companion discovery ADR consumes H3's
classification and H4's links; the two are separable campaigns with an
explicit sequencing note rather than one oversized landing.

## Consequences

**Gains.** Minutes-long AEAT pulls become first-class: visible progress,
bounded hangs, clean cancellation — the single most will-bite-in-practice
defect closed. Schemas stop lying about defaults and gain full flag
expressiveness. A new mutating verb can no longer ship unclassified.
Calculation results get materially cheaper for clients while bulk evidence
stays one fetch away. Five implicit postures (localization, external
content, secrets, capabilities, retention) become declared, gated
contracts.

**Honest difficulties.** Progress heartbeats depend on the client having
sent a progress token — without one the call is still blocking-silent
(timeouts still bound it). Coarse stage reporting from a black-box CLI is
genuinely limited; over-promising granularity would be dishonest, so the
heartbeat is elapsed-time-plus-stage, not percentage. The classification
table is a new authored surface that must be seeded correctly once
(mis-seeding a destructive verb as safe is the same risk the frozensets
carry today — the parity gate reduces omission risk, not judgment risk).
Result thinning changes payload shapes consumers may have scripted
against; output schemas version the change but downstream notebooks/tests
need a sweep. Windows process-tree termination is fiddly and needs real
tests, not mocks.

**Pathways opened.** The classification table becomes the one queryable
authority for per-verb risk posture (useful to docs, the harness router,
and future clients); the supervised runner is the natural seam for the
eventual Tasks-extension migration once the v2 SDK stabilises; resource-
link plumbing generalises to future large surfaces (workbook exports,
review packages).
