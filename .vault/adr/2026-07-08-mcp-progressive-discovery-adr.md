---
tags:
  - '#adr'
  - '#mcp-progressive-discovery'
date: '2026-07-08'
modified: '2026-07-09'
related:
  - "[[2026-07-08-mcp-progressive-discovery-research]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
  - "[[2026-07-08-mcp-protocol-hardening-adr]]"
---

# `mcp-progressive-discovery` adr: `the console advertises an orientation core; the verb universe is discovered, not listed` | (**status:** `accepted`)

## Problem Statement

The agent-harness refoundation's R2 decided the console tool architecture as
"domain-grouped toolsets with a meta-tool fallback", explicitly rejecting the
flat surface because dumping the whole verb tree into the tools list "crowds
out the user's question and degrades tool selection". As shipped, that
rejection never reached the protocol: the server's tools/list handler returns
the floor tool, the two grounding tools, the ENTIRE ~273-verb descriptor set,
and the two meta-tools (`src/aeat/entrypoints/mcp/_server.py`, line 499). The
five manifest-derived toolsets (`_toolsets.py`) are implemented and
unit-tested but never called from any serving path — finished, tested, dead
capacity — and no `tools/listChanged` capability exists, so every MCP client
today sees the exact flat surface R2 set out to prevent. The meta-tool pair,
designed as the long-tail fallback, is advertised alongside the very tools it
was meant to stand in for. The generated Claude plugin does not constrain the
surface either; its only lever is the boot-frozen persona env var.

An operator directive of 2026-07-08 asked for this review with a chief focus
on the correctness and full utilisation of MCP for agent tool use and
progressive discovery. This ADR resolves the discovery architecture against
the July-2026 protocol landscape recorded in the research; the companion
`mcp-protocol-hardening` ADR owns the correctness/operations findings from
the same pass.

## Considerations

- **The protocol landscape moved under R2.** The research records the
  July-2026 facts: Claude Code's client-side ToolSearch defers tool loading
  past ~10K definition tokens (default-on since January 2026, BM25 + regex
  over names/descriptions), the Anthropic many-tool guidance advocates a
  small always-on core plus search/invoke meta-tools for hundreds of verbs,
  the GitHub MCP server ships named toolset groups clients enable
  selectively, and the Cloudflare server fronts ~2,500 endpoints through a
  search+execute pair. `tools/listChanged` is the spec's dynamic-exposure
  channel and Claude Code honours it. None of this existed when R2 was
  ruled; all of it bears on how the ruling should be implemented.
- **The console must serve any client, not only Claude Code.** Client-side
  ToolSearch is a Claude-specific backstop that silently disappears on
  proxied configurations and non-Claude clients; a server-side architecture
  must not depend on it (the refoundation's floor/enhancement design rule).
- **The discovery spine is only as good as its ranking signal.** Meta
  `search` is naive token-substring overlap; descriptions are family-level
  boilerplate that cannot discriminate the four modelo review-package verify
  siblings; and search results do not carry input schemas, so a model that
  finds a verb still cannot call `execute` correctly without another
  round-trip. The product ships an FTS5 + model2vec hybrid retrieval stack
  (provisioned since the operability follow-up) that the command surface
  does not use.
- **Names overflow client budgets.** Four Claude-prefixed tool names exceed
  64 characters because the flat underscored-command-key builder has no
  length budget and the plugin (`aeat`) and server (`aeat`) names duplicate
  into a 23-char client-side prefix.
- **Existing gates carry over untouched.** Persona scope, handoff deny,
  CONFIRM elicitation, the live-write block, and argument-faithfulness run
  identically on the direct and meta paths (verified in the refoundation
  close); nothing here may weaken them. The `harness.load` floor and the
  grounding tools are always-on by R3/R4 and stay so.

## Considered options

### P1 — Default advertised tool surface

- *Flat listing, rely on client ToolSearch (status quo):* zero work; Claude
  Code defers past 10K tokens anyway. Rejected as primary: abandons every
  non-Claude client and proxied Claude configuration to the crowd-out R2
  already rejected, and leaves the server protocol-passive.
- *Meta-tools only, no per-verb tools ever:* maximal thrift. Rejected:
  discards annotation-driven client confirmation UI and per-verb schemas on
  the common path — the exact weakness R2 named.
- **Chosen — an orientation core as the default surface, everything else
  discovered.** By default tools/list advertises only: the `harness.load`
  floor, the two grounding tools, the meta discovery pair, and a small
  manifest-derived orientation slice (the overview/contract family — the
  verbs the operator rules mandate reading first). The full per-verb
  universe remains addressable through discovery (P2) and dynamic activation
  (P3). An `AEAT_MCP_SURFACE` env toggle (`core` default, `full` opt-out)
  preserves the flat surface for users who want it and for A/B measurement.

### P2 — Discovery spine quality

- *Keep token-overlap search:* rejected — it cannot bridge Spanish/English
  or concept/verb vocabulary gaps, and its results are non-actionable (no
  schema).
- **Chosen — hybrid retrieval + self-sufficient results + verb-specific
  descriptions.** `search` reuses the shipped corpus-search retrieval
  pattern (FTS5 lexical with Spanish stemming + model2vec semantic, RRF
  fusion, lexical-only degraded mode) over a command index built from tool
  name, CLI path, per-verb help text, and toolset. Search results carry
  enough to act: description, annotations, and the per-verb input schema (or
  a `describe` meta-tool returns the full descriptor — the plan decides the
  cheaper shape). Descriptions gain a verb-specific first line derived from
  the CLI's own per-verb help (the black-box authority), with the family
  `operator_question` demoted to a suffix.
- **Accepted limitation (honesty-review 2026-07-09) — the semantic side
  RE-RANKS the lexical candidate set; it does not admit pure-semantic
  candidates.** `CommandIndex.search` builds the candidate universe lexically
  (per-column BM25 over the diacritic-folded / Spanish-stemmed columns plus the
  curated outcome aliases), then RRF-fuses a model2vec semantic rank OVER THAT
  SET. A query with zero lexical token overlap with any command — no shared token
  in key/name/description/help and no matching alias — is not surfaced whatever
  its embedding similarity; the semantic rank re-orders and breaks homonym ties,
  it does not rescue a no-overlap concept query, and `total_matches` / `truncated`
  count the lexical set only. This is an accepted bound, not the full dense
  retrieval the phrase "hybrid retrieval" might imply: the command corpus is
  small and closed, the curated aliases cover the outcome-phrased gaps, and the
  pinned golden set proves the target cross-vocabulary cases. Admitting the
  semantic top-k into the candidate universe is a deferred enhancement if a
  future recall gap needs it.

### P3 — Dynamic toolsets

- *Drop toolsets entirely:* honest about today's dead code but discards the
  one mechanism that gives stateful clients a curated common path.
- **Chosen — wire the existing toolsets to runtime activation over
  `tools/listChanged`.** The five manifest-derived groups become
  activatable: an explicit activation surface (a lightweight `toolsets`
  tool: list / activate / deactivate) plus automatic activation when
  `search` or `execute` shows sustained use of one domain. Activation adds
  that group's per-verb tools to the advertised list and emits the
  list-changed notification; deactivation reverses it. Clients that ignore
  the notification keep working through P1+P2 semantics unchanged — the
  floor/enhancement rule.

### P4 — Tool naming budget

- *Leave names as-is:* rejected — four names already break the ~64-char
  prefixed budget and any new deep verb path silently joins them.
- **Chosen — de-duplicate the namespace and enforce a budget.** The plugin
  and server must not both spend "aeat" in the client prefix (the plan
  decides which side renames, weighing that a server rename changes prompt
  slash-command names). The tool-name builder gains an explicit budget with
  declared short forms for the over-length verbs, and a conformance gate
  fails on any prefixed name over budget so the class cannot recur.

### P5 — Prompt arguments and completions

- *Keep argumentless prompts:* rejected — a workflow prompt that cannot
  carry modelo/year/period forces conversational re-elicitation of exactly
  the typed values the CLI already models.
- **Chosen — typed prompt arguments plus the completions capability.** The
  guided-workflow prompts accept the arguments their skill itinerary needs
  (modelo, filing year, period, profile where applicable);
  `completion/complete` serves ranked suggestions from the typed sources
  (the core `Modelo` enum, period tokens, plausible filing years). Cheap to
  serve, spec-clean, future-proof for argument-completing clients.

### P6 — Persona and floor-payload posture (explicit ruling)

- *In-session persona switching:* rejected — persona is a safety identity
  binding list-time scope, call-time refusals, and handoff denial; making
  it mutable in-session would turn a structural boundary into a negotiable
  one.
- **Chosen — persona stays boot-frozen; in-session dynamism is toolset
  activation only (P3), which only ever widens or narrows the advertised
  list WITHIN the active persona's scope filter. The `harness.load` floor
  keeps returning the full rules corpus** — the operating layer's safety
  prose must always reach the model whole; payload thrift is not worth a
  partial rulebook. Both are recorded as deliberate so the next audit does
  not re-litigate them as oversights.

## Constraints

- **Parent decisions are stable.** The refoundation ADR is accepted; this
  ADR AMENDS its R2 implementation posture (flat listing retired as the
  default; toolsets become runtime-real) while preserving R2's intent and
  everything else (R3 grounding always-on, R4 floor-first delivery, R6
  gates, R9 evidence funnel). The packaging ADR's plugin path carries over;
  the generated plugin config gains only the surface env toggle.
- **Frontier surface.** Client ToolSearch thresholds, list-changed
  handling, and slash-command rendering are July-2026 client behaviours
  that MUST be re-verified against live official docs at implementation
  time, and the live-client proof (R7 discipline) — not documentation
  reading — is the acceptance gate.
- **Gate invariance is non-negotiable.** Every discovery path (core tools,
  activated toolset tools, `execute`) must produce byte-identical refusals
  through the one shared gate sequence; the existing conformance tests
  extend to the new surface rather than being weakened.
- **Search-stack licensing is already settled** per
  `shipped-search-licence-clean` (potion/model2vec provisioned behind the
  search extra with a lexical-only degraded mode); the command index
  inherits that posture and must not regress it.
- **SDK pin `mcp>=1.12,<2`** supports everything used here (list-changed
  notifications, completions, prompts with arguments); no v2/RC feature is
  required.

## Implementation

High-level layering; the paired plan owns steps and sequencing.

- **Surface builder.** Split descriptor construction from advertisement: a
  surface-policy module computes the default core (floor + grounding + meta
  + orientation slice, persona-filtered) and the activated set; the
  tools/list handler renders the current surface; `AEAT_MCP_SURFACE=full`
  restores the flat listing.
- **Command index and search upgrade.** Build a small command-retrieval
  index (FTS5 + optional vectors, RRF fusion) from the manifest and
  per-verb Typer help; re-back the `search` meta-tool with it; enrich
  results with annotations and input schema (or add `describe`); derive
  verb-specific description first lines from the CLI help authority.
- **Toolset activation.** A `toolsets` management tool over the existing
  toolset groups; per-session activation state; emit the list-changed
  notification; damped auto-activation heuristics from discovery usage;
  persona scope filters activation output.
- **Naming.** De-duplicate the plugin/server prefix pair; add the length
  budget plus short-form table to the tool-name builder; conformance gate.
- **Prompts.** Add typed arguments to the workflow prompts; implement the
  completions handler over the typed sources; keep prompt content fed from
  the single authored harness source.
- **Measurement.** Extend the live persona harness with a discovery
  scenario: an unprimed model must locate and correctly invoke a long-tail
  verb through the core surface; score selection quality and round-trips;
  A/B the core vs full surface with the existing golden scenarios and
  persist the comparison in the vault.

## Rationale

The research is unambiguous that the shipped surface contradicts the
accepted R2 ruling at the protocol boundary (finding F2: the toolsets never
reach a client), and the July-2026 landscape (F6) supplies the patterns R2
lacked names for: the orientation-core plus search/invoke spine is the
client-universal baseline the Anthropic guidance and the Cloudflare
precedent converge on, and list-changed-driven toolsets are the stateful
overlay the GitHub precedent and Claude Code support make real. P1 plus P3
therefore implement R2's own intent with the protocol features that now
exist, rather than superseding its reasoning. P2 exists because discovery
quality is the load-bearing risk of a search-first surface (F4/F5): the
ranking signal must discriminate siblings and results must be actionable in
one round-trip, and the product already ships the retrieval stack to do it.
P4 closes a hard client-compatibility defect (F3). P5 activates a paid-for
protocol feature that maps one-to-one onto the typed axes the CLI already
declares. P6 records deliberate non-changes so the boot-frozen persona and
the full-rules floor stop reading as gaps. The env toggle in P1 keeps the
change honest and measurable: the flat surface remains one setting away
until live A/B evidence justifies deleting it.

## Consequences

**Gains.** A client connecting to the console sees a dozen-odd purposeful
tools instead of ~273; the user's question stops being crowded out; tool
selection quality rises (the client-side ToolSearch numbers in the research
indicate the direction and magnitude); non-Claude clients get first-class
discovery instead of depending on a Claude-only backstop; the dead toolset
capacity finally earns its tests; and the four over-budget tool names stop
breaking clients. Discovery becomes measurable — rounds-to-correct-verb
becomes a scored metric in the live harness.

**Honest difficulties.** The default surface change is behaviour-visible to
every existing client configuration — the flat-surface toggle and a
migration note in the plugin release notes are mandatory, and muscle-memory
tool names vanish from the default list (still callable via `execute` and
via toolset activation). Auto-activation heuristics can thrash
(activate/deactivate churn emitting notification storms) and need damping
plus a hard cap. The command index is a second retrieval surface to keep
licence-clean and fresh against the manifest (build-time derivation, no
hand-listing). List-changed behaviour varies by client and must be proven
live, not assumed. Renaming either the plugin or the server invalidates
users' existing allowlist/permission entries once, and the choice interacts
with prompt slash-command names.

**Pathways opened.** The command index doubles as the substrate for future
in-console help, documentation generation, and the harness router; toolset
activation is the natural hook for itinerary-driven surfaces (a skill
activating its own toolset); the A/B surface toggle gives the eval flywheel
its first controlled experiment.
