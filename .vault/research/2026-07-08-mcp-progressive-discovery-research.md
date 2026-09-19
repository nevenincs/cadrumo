---
tags:
  - '#research'
  - '#mcp-progressive-discovery'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:a739abebf411e56aafcd878addd411826908a8e7996b81b329d64cbc2c346038'
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-audit]]'
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-02-agent-harness-operability-followup-research]]'
  - '[[2026-07-08-mcp-protocol-hardening-research]]'
---

# `mcp-progressive-discovery` research: `MCP console tool-surface discovery architecture`

An operator directive of 2026-07-08 asked for a fresh review of the aeat MCP
console — the agent's progressive-discovery surface over the black-box CLI
universe — against the current state of the MCP protocol, with the chief focus
on the correctness and full utilisation of MCP for agent tool use and
discovery. This document records what a three-way discovery pass found: a
vault-decision digest, a file:line implementation audit of
`src/aeat/entrypoints/mcp/`, and a citation-backed brief on the July-2026 MCP
protocol landscape. Its companion (the `mcp-protocol-hardening` research)
carries the correctness/operations findings; this document carries the
discovery-architecture findings that seed the `mcp-progressive-discovery` ADR.

## Findings

### F1 — Governing decisions and their honest delivery state

The accepted refoundation ADR resolved the console architecture (R1–R9) and
the accepted packaging ADR resolved distribution (D1–D4, amending R8 to the
Claude-plugin path). Both plans are 100% executed; two close honesty reviews
ran; the operability follow-up landed nearly its whole deferred register on
2026-07-03 (live-model measurement, semantic grounding provisioning,
consent-on-floor, evidence-scrubbing gate, e2e gated-session test, hardening).
The console is real, gated, measured, and packaged. What this research
re-opens is narrower and precise: R2's discovery posture as *implemented*
de-utilises the protocol, and no ADR yet covers the discovery-relevant
protocol features that postdate the refoundation decision.

### F2 — The tools/list reality: the flat surface R2 rejected is what ships

R2 chose "domain-grouped toolsets with a meta-tool fallback" and rejected the
flat surface because it "crowds out the user's question and degrades tool
selection". As built, `_list_tools` (`src/aeat/entrypoints/mcp/_server.py`,
line 499) returns the `harness.load` floor tool, the two grounding tools, the
ENTIRE per-verb descriptor set, and the two meta-tools — ~273 tools flat when
no persona is active. The five curated toolsets (`_toolsets.py`,
`build_toolsets`) are implemented, derived from the live manifest, and
unit-tested — and never called from any server registration path: finished,
tested, dead capacity. There is no `tools/listChanged` support (no
notification handlers registered, so the SDK-derived capability declaration
advertises none), no dynamic exposure, and the generated Claude plugin does
not constrain the surface either — its `.mcp.json` launches the full server;
the only scoping lever is the optional `userConfig.persona` env value, fixed
for the process lifetime. The meta-tool pair, designed as the long-tail
fallback, is advertised alongside the very tools it was meant to stand in
for, so it is redundant rather than load-bearing. R2's *intent* (progressive
disclosure) is correct and undelivered at the protocol boundary; its
plan-level "DELIVERED" status is honest only about the grouping metadata,
not about what a client sees.

### F3 — Tool naming exceeds client budgets and duplicates the namespace

`tool_name_for_command` (`_dispatch.py`, lines 30–35) concatenates
`"aeat_" + command_key.replace(".", "_")` with no length budget. The plugin is
named `aeat` (`agent/_workspace.py`, `_PLUGIN_NAME`) and the MCP server is
also named `aeat` (`_server.py`, `_SERVER_NAME`), so Claude-side names carry
the 23-char prefix `mcp__plugin_aeat_aeat__` before the tool's own name
begins. Four current names exceed 64 characters prefixed
(`aeat_modelo_review_package_verify_signature`,
`aeat_modelo_work_preview_maritime_exemption`,
`aeat_config_auth_certificate_secret_remove`,
`aeat_config_profile_subject_access_request`); one sits exactly at 64; twelve
exceed 60. The 2025-11-25 spec codifies tool-name guidance (1–128 chars,
ASCII alnum plus `_`, `-`, `.`), but client-side prefixing regimes make
~64 chars the practical budget, and a third of it is burnt on redundant
namespacing.

### F4 — Tool descriptions cannot discriminate siblings

Descriptions are built as "Run `<cli form>`." plus the FAMILY-level
`operator_question` shared by every verb in a mounted family (`_tools.py`,
lines 77–112). Every `ledger` verb carries the identical trailing sentence;
the four `modelo_review_package_verify*` siblings are indistinguishable
except by their bare CLI path. There is no per-verb when-to-use guidance, no
worked example, and no localization (deliberate or not — undecided). For
both a model choosing among 273 flat tools AND any search-driven discovery
(server meta-search or client ToolSearch/BM25 indexing), the description is
the ranking signal — today it is nearly constant within a family.

### F5 — The meta `search` tool is naive while a hybrid retriever ships in the same wheel

`search_commands` (`_meta_tools.py`, lines 65–119) scores by exact token
substring overlap: +2 for a token in the command key, +1 in the description.
No stemming, no diacritics folding, no Spanish/English cross-vocabulary
recall, no semantic match — while the product ships an FTS5 +
model2vec hybrid retrieval stack (`application/corpus_search/`) built by the
same campaign, provisioned build-on-first-use since the operability
follow-up. A query like "declare quarterly VAT" must coincide lexically with
`modelo.work.calculate`'s description to rank it. The discovery spine the
architecture leans on is the weakest retrieval surface in the product.

### F6 — July-2026 protocol landscape (citation-backed brief, key deltas)

The current stable spec revision is 2025-11-25; a 2026-07-28 release
candidate is finalizing (stateless core, extensions framework, Tasks
redesigned as an extension). The Python SDK stable line is v1.28.0; the
project pins `mcp>=1.12,<2` (`pyproject.toml`, line 143), which admits it.
Discovery-relevant facts, each verified against live docs by the research
pass (frontier surface — re-verify at execution time):

- **Client ToolSearch / deferred loading (Claude Code, default-on since
  January 2026):** past ~10K tokens of MCP tool definitions the client marks
  tools `defer_loading: true`, exposes a ~500-token Tool Search meta-tool
  (regex + BM25), and loads 3–5 tools on demand; measured ~85% context
  reduction and tool-selection accuracy improving 49%→74% (Opus 4). It is
  client-side, transport-agnostic — and silently absent on proxied
  configurations and on every non-Claude client.
- **Server-side precedents:** the GitHub MCP server exposes named toolset
  groups clients enable selectively; the Cloudflare server fronts ~2,500
  endpoints through search+execute meta-tools plus include/exclude filters.
- **2026 consensus for a ~300-verb server:** a small always-on
  orientation/search/invoke core (pattern B) is the client-universal
  baseline, optionally hybridised with dynamic toolsets via
  `notifications/tools/list_changed` (pattern C) for stateful clients;
  full-flat listing relying on client ToolSearch (pattern A) works only when
  Claude Code is the sole consumer.
- **Prompts** surface as `/mcp__<server>__<prompt>` slash commands in Claude
  Code and Desktop; prompt arguments plus the `completions` capability are
  the supported parameterisation path. All 35 shipped prompts declare
  `arguments=[]` (`_server.py`, line 660) — the feature is unused.
- **Resources** are pull-only in practice: Claude Code injects nothing
  without an `@`-mention or a tool result; `resource_link` content items let
  tool results reference large payloads without inlining them. Resource
  templates and cursor pagination are supported; subscriptions have thin
  client support.
- **Elicitation** (form + new URL mode), icons, JSON Schema 2020-12
  defaults, and the sampling tool-calling loop are the other 2025-11-25
  additions; the hardening companion research owns them.

### F7 — The floor tool pays a flat 17KB toll and personas are boot-frozen

`harness.load` returns the off-host consent text plus ALL seven operator
rule files concatenated (~17KB) plus the active persona document — not
scoped to the persona's actual surface (`agent/__init__.py`, lines 64–70).
The persona itself is resolved once from `AEAT_MCP_PERSONA` at process start
(`_server.py`, line 138) and threaded as an immutable closure; switching
persona — or any future notion of activating a narrower/wider tool scope —
requires killing and relaunching the stdio process. A coordinator delegating
to task-scoped roles therefore performs persona handoff as an out-of-band
process restart, and no in-session mechanism can narrow or widen the
advertised surface.

### F8 — Options considered for the discovery architecture (ADR seeds)

- **Option A — status quo plus client ToolSearch:** keep the flat listing
  and rely on Claude Code's deferred loading. Zero work; leaves every
  non-Claude client (and any proxied Claude configuration) with the full
  crowd-out; abandons R2's own rejection rationale; the server stays
  protocol-passive. Rejected as the primary posture.
- **Option B — orientation-core default surface with meta search+execute as
  the spine:** advertise only the floor tool, grounding tools, an
  orientation/overview slice, and the meta pair by default; every long-tail
  verb reachable through `search`→`execute` with per-verb schemas served on
  demand. Client-universal, matches the Cloudflare precedent and the
  Anthropic many-tool guidance.
- **Option C — dynamic toolsets over listChanged:** wire the existing
  `_toolsets.py` groups to a runtime activation surface (an
  `activate`/`deactivate` tool or search-driven auto-activation) that emits
  `notifications/tools/list_changed`; stateful clients re-list and see the
  10–20 tools relevant to the current itinerary. Degrades cleanly to Option
  B semantics on clients that ignore the notification.
- **Option D — per-persona/pre-filtered launch profiles:** extend the
  plugin/server config so an installation chooses a toolset slice at launch
  (GitHub-server pattern). Complementary, not primary — it cannot follow the
  conversation.
- The candidate resolution the ADR should weigh is B as the floor, C layered
  on it, D as configuration sugar, with A's client ToolSearch treated as a
  complementary backstop — plus the enabling sub-decisions: hybrid
  retrieval behind `search`, per-verb description authority, a tool-name
  length budget with the namespace de-duplication, prompt arguments +
  completions, and an explicit ruling on whether persona stays boot-frozen.

### Sources

Implementation audit (this pass, file:line cited inline above); vault
decision digest over the refoundation/packaging ADR chain and their close
audits; protocol brief with live-doc citations: the 2025-11-25 spec and
changelog and the 2026-07-28 RC announcement on `modelcontextprotocol.io`
and `blog.modelcontextprotocol.io`, the Anthropic advanced-tool-use
engineering post, Claude Code MCP/ToolSearch docs on `code.claude.com`, and
the GitHub / Cloudflare MCP server repositories. Frontier caveat per the
packaging ADR discipline: client behaviours (ToolSearch thresholds, prompt
slash-command rendering, listChanged honouring) MUST be re-verified against
live official docs at implementation time.
