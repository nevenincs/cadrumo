---
tags:
  - '#research'
  - '#mcp-protocol-hardening'
date: '2026-07-08'
modified: '2026-07-08'
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
  - '[[2026-07-02-agent-harness-operability-followup-research]]'
  - '[[2026-07-08-mcp-progressive-discovery-research]]'
---

# `mcp-protocol-hardening` research: `MCP console protocol correctness and operations hardening`

Companion to the `mcp-progressive-discovery` research (same 2026-07-08
discovery pass: implementation audit of `src/aeat/entrypoints/mcp/`, vault
decision digest, citation-backed July-2026 MCP protocol brief). Where the
discovery document owns the tool-surface architecture, this document owns the
correctness, faithfulness-of-schema, and operations findings: the places
where the console's use of the protocol is incomplete, lossy, or fragile in
ways that will bite a real client regardless of how the surface is shaped.

## Findings

### F1 — Long-running live pulls: no timeout, no progress, no cancellation

Every tool call is one blocking `subprocess.run(["aeat", "--format",
"json", ...])` with NO `timeout=` argument and no intermediate output
(`src/aeat/entrypoints/mcp/_server.py`, lines 225–271). The `_call_tool`
handler (line 502) takes no progress token and never sends
`notifications/progress`. The Playwright-backed live-pull family
(`app.live.expedientes.pull`, `notifications.pull`, `justificante.pull`,
`iva-wallet.pull*`, `filed.pull*`, censo pull) legitimately runs for
minutes; a network stall or a changed AEAT DOM selector hangs the MCP call
indefinitely. Many MCP clients apply their own call timeout well under a
minute, so a legitimate slow pull reads as a failure, and a hung one is
unkillable except by killing the server. This is the single most concrete
will-bite-in-practice gap on the console.

Protocol state (July 2026, cited in the brief): the 2025-11-25 Tasks
mechanism is *experimental*, already deprecated in Python SDK v1.28.0, and
redesigned (breaking) in the 2026-07-28 release candidate as a formal
extension — do NOT build on the v1.x Tasks API. The stable, universally
supported alternative is a blocking `tools/call` that (a) sends
`notifications/progress` heartbeats/stage updates while the subprocess runs,
(b) applies a per-tier timeout (generous for the live family, tight for
local reads), and (c) honours client cancellation. Migration to the
redesigned Tasks extension is a post-v2-SDK follow-up, not a today decision.

### F2 — Per-verb input schemas are faithful on enums, lossy on defaults and flag pairs

`_input_schema.py` renders Typer enum choices as JSON-schema `enum` arrays
correctly (lines 87–88). Three lossy spots: `_json_safe_default` (lines
159–163) silently drops any non-scalar default (a path, a tuple, a factory)
to null, so a client cannot show the real default; boolean flags expose only
the "on" token and `cli_argv_for` (lines 307–309) emits the flag only for a
truthy JSON value, so a `--flag/--no-flag` pair whose click default is true
cannot be turned OFF through the MCP surface at all — an expressiveness hole,
not just cosmetics; and `_resolve_command`'s tree walk (lines 229–236)
swallows any exception while materialising a lazy subcommand and silently
degrades that verb to an argument-free schema — a genuine Typer declaration
bug would ship as a silently empty schema rather than failing a gate.

### F3 — Annotation axes: heuristic leaf lists, and openWorldHint never set

Only the family-level read-only/local-mutating axis comes from the operator
manifest. `destructive` and `idempotent` are inferred by matching the
command key's FINAL segment against hand-listed frozensets
(`_annotations.py`, lines 30–36), and the handoff/live-write tiers likewise
(`_hitl.py`, lines 21–29). A future verb ending in an unlisted destructive
leaf (`purge`, `wipe`) silently classifies non-destructive; the existing
coverage gate proves only internal consistency of the heuristic's output,
not semantic correctness — this contradicts the spirit of
`aeat-schema-central-config` (closed regulatory-adjacent axes are declared
data, not scattered literals). `openWorldHint` is never populated anywhere
(`_annotations.py` lines 39–53, `_server.py` lines 213–218) although the
live-pull family interacting with the external AEAT sede is the textbook
open-world case. Spec trust model (cited): annotations are untrusted client
HINTS, never security — the server-side gates remain the enforcement, which
the console already gets right; the gap is purely hint completeness and
declaration authority.

### F4 — Result-size economics: everything is inlined, resource_link unused

Every tool result double-emits the full CLI envelope as text `content` plus
`structuredContent` (roughly 2x tokens by construction). Large payloads —
full casilla sets with legal_refs/source_refs provenance, evidence row
arrays, corpus excerpts — are always inlined; the 2025-11-25 `resource_link`
content type (return a URI the client fetches on demand) is never used.
Guidance from the brief: keep `structuredContent` to the typed summary a
client acts on; move bulk provenance/evidence to `resource_link` URIs
resolved by the existing resource read handlers. This also reinforces the
R9 evidence funnel: references-not-bytes is already the CLI posture, and
resource links make it the protocol posture too.

### F5 — Prompts and completions: parameterisation entirely unused

All 35 prompts declare `arguments=[]` (`_server.py`, line 660) — a workflow
prompt cannot carry the modelo/year/period it orchestrates, so the model
must re-elicit them conversationally after invocation. The `completions`
capability (argument autocompletion for prompt args and resource-template
params; ranked suggestions with pagination, context-aware via
`context.arguments`) is not implemented. Client reality: Claude Code renders
prompts as slash commands but does not yet surface completions in chat UI;
the cost to serve completions is small and the natural sources are typed
(the `Modelo` enum, period tokens, filing years). Prompt titles are naive
English slug transforms (`_prompts.py`, lines 84–85), unlocalized — while
every refusal/notice string in the same package rides `tr()`.

### F6 — Localization boundary is undeclared

Tool descriptions and prompt titles are English-only by construction
(`_tools.py` has zero `tr()` calls); elicitation messages, refusals, and
notices are localized. No decision records whether the model-facing surface
(descriptions, schemas) is deliberately English (a reasonable stance — the
model reads English best and the operator never sees tool descriptions) or
an oversight. It should be decided explicitly, gated, and documented, so the
locale parity gates know their boundary.

### F7 — Telemetry grows without bound

Per-session JSONL trajectory rows are payload-free (hashes only — correct
per the secure-storage rule) but nothing prunes or rotates the telemetry
directory across sessions (`_telemetry.py`, lines 78–134). A long-lived
installation accretes files indefinitely. A retention policy (age- or
count-based) is needed, plus a documented read path.

### F8 — Faithfulness window: sound, narrow, and honestly bounded

The serving-path check is argument-faithfulness (regex amount-shapes in call
arguments vs a 32-result FIFO grounding window of prior tool-result JSON,
`_faithfulness.py` lines 33–125); narration stays client-side and
structurally unreachable, as the module docstring records. No action needed
beyond keeping the eval-side narration scorer the compensating control; noted
here so the hardening ADR can decline to over-promise.

### F9 — SDK and capability posture

Pin is `mcp>=1.12,<2` (`pyproject.toml`, line 143); current stable is
v1.28.0, which carries every 2025-11-25 feature used or proposed here (form
+ URL elicitation, completions, icons, structured output, resource
subscriptions) and deprecates experimental Tasks. Capabilities are whatever
`create_initialization_options()` derives from registered decorators
(`_server.py`, line 747) — nothing is declared explicitly, so adding
handlers (completions, listChanged) auto-advertises correctly, but the
posture should be pinned by a conformance test asserting the negotiated
capability set. The 2026-07-28 RC (stateless core, Tasks extension, v2 SDK)
is explicitly out of scope until the v2 SDK is stable; a migration note
belongs in the ADR's consequences.

### F10 — Residual minor hardening carried from the operability follow-up

Two already-recorded residuals ride naturally with this feature:
pin `POTION_MODEL_REVISION` from `"main"` to a commit hash, and route the
model2vec download through the app-controlled cache dir instead of the
default HF hub cache (both recorded in the operability follow-up research's
resolution table).

### F11 — Security posture check against the July-2026 best-practice sheet

The console already holds the load-bearing lines: stdio-only transport,
annotations-as-hints with server-side gate enforcement, no token
passthrough, evidence bytes never in tool results (conformance-gated),
payload-free telemetry. Two items from the brief deserve explicit ADR
treatment: (a) third-party content sanitisation — AEAT portal HTML /
justificante text relayed through pull results is untrusted input to the
model (prompt-injection vector) and currently flows verbatim; (b) URL-mode
elicitation exists in 2025-11-25 for out-of-band secret collection — the
console's stance (secrets are entered via the local CLI, never through any
MCP channel) should be recorded as the decided alternative rather than left
implicit.

### Sources

Implementation audit with file:line citations (2026-07-08 pass); protocol
brief citations: 2025-11-25 spec changelog, tasks/elicitation/tools/
completion/security-best-practices spec pages on `modelcontextprotocol.io`,
the 2026-07-28 RC announcement on `blog.modelcontextprotocol.io`, Python SDK
release notes on GitHub/PyPI, the Anthropic advanced-tool-use engineering
post, and Claude Code MCP docs on `code.claude.com`. Frontier caveat: client
behaviours and SDK deprecation timelines MUST be re-verified against live
official docs at implementation time.
