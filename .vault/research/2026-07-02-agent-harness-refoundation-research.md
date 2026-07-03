---
tags:
  - '#research'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - '[[2026-06-30-agent-harness-adr]]'
  - '[[2026-07-01-agent-harness-adr]]'
  - '[[2026-07-01-agent-harness-research]]'
  - '[[2026-07-02-agent-harness-close-audit]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `agent-harness-refoundation` research: `black-box tool universe, situation-keyed skills, and the MCP operating console`

This research re-founds the agent-harness concept after an operator correction
recorded 2026-07-02. The prior `agent-harness` campaign shipped harness
*content* (7 operator rules, 7 personas, 28 skills, an operator-surface
contract, an MCP verb-wrapper server, a replay-only golden eval) but the
operator identified two defining mistakes: the harness was never operable (no
live agent has ever driven the CLI through it, and no accepted way of
measuring or operating it exists), and — more fundamentally — the project
universe was mis-defined. This document records the corrected universe
definition, grounds what exists at HEAD against it, and researches the three
pillars the corrected concept requires: a user-situation skill taxonomy, an
MCP operating console, and an operational measurement regime.

## Findings

### The corrected universe definition (operator directive, 2026-07-02)

The `aeat` CLI is a **black box**. It bundles the rule-based operations for
calculating and manipulating tax data; it is not a codebase to be interfaced
with. The only surface that exists, from the harness's point of view, is the
CLI itself. The agent harness is a **framework of rules and regulations for
operating within a confined tool universe** whose central tool is the
aeat-cli.

Three consequences:

1. **Skills and personas key off the USER, not the code.** If the user is a
   small company, a skill defines exactly how that tax regimen operates and
   how it maps onto aeat-cli operation. The tax system is numerous: tax
   domains may map to skills, modelo work may map to skills, and the user's
   *situation* may map to skills — e.g. "the user is behind on their tax
   obligations" is a loadable skill that helps any LLM operate the CLI
   effectively for that situation.

2. **The harness serves ANY large language model.** There is no bespoke
   embedded chat runtime. The LLM client is whatever the user already runs;
   the harness makes it effective and safe inside the tool universe.

3. **One MCP server is the operating console.** It must be able to ground
   user requests, understand the bundled legal corpus, operate semantic RAG
   search, hold extensive knowledge of the aeat-cli surface, ask the user
   questions when input is needed, and actually operate the CLI on the
   user's behalf. This is materially more than the current verb-wrapper
   server.

### What exists at HEAD, re-read against the corrected concept

Verified first-hand this session (inventory on disk, gates run):

- **CLI-as-contract substrate — sound and reusable.** The operator-surface
  contract (`build_operator_surface_manifest`, `aeat app contract`), the
  `SchemaEnvelope`/`Notice`/`ExitCode` reading surface, and the drift gate
  (`test_rule_surface_conformance`) all treat the CLI as the only citable
  surface. This layer already embodies the black-box discipline and carries
  over unchanged.
- **Harness content — right material, partially wrong key.** 7 operator
  rules and 7 personas exist as shipped wheel data. Of the 28 skills, six
  are already situation-shaped (`autonomo-estimacion-directa`,
  `autonomo-modulos`, `intra-community-operator`, `retenedor-empleador`,
  `pyme-sociedad`, `arrendador`), five are cross-cutting task skills, and
  seventeen are per-modelo procedures. The per-modelo tier remains the
  executable substrate, but the situation axis — the axis the corrected
  concept makes primary — is the thin, deferred layer (the prior plan's
  `P07.S20`/`S21` deferral).
- **MCP server — a verb wrapper, not an operating console.** The current
  `entrypoints/mcp/` server exposes CLI leaves as typed tools with
  HITL/faithfulness/persona-scope gates. It has no grounding tools, no
  corpus search, no RAG search, no skill/rule delivery to the client, and
  no user-elicitation surface.
- **Assurance — replay-only.** The 50-scenario golden eval replays recorded
  trajectories; no live model has ever operated the harness, and no
  operational metrics or acceptance criteria for live operation exist.
- **Never-live-submit remains a permanent rail** (accepted 2026-06-30 ADR,
  `aeat-safety-legal-gates`): the console operates local state and the
  filing handoff only; a human files outside the app.

### Thread A — what is runnable today and the console gap analysis

Findings from the dispatched read-only researcher pass (2026-07-02), verified
with file:line evidence.

**Headline: the harness is a static content bundle + an stdio MCP shell + a
replay/registry eval — never once driven by a live LLM.** Two of the three
advertised safety gates are computed in library code but NOT wired into the
live serving path.

**MCP server (the console shell today).**

- Transport is stdio only (`src/aeat/entrypoints/mcp/_server.py:211-215`);
  no HTTP/SSE. Launched via the `aeat-mcp` console script
  (`pyproject.toml:92`), gated behind the `aeat[agent]` extra
  (`mcp>=1.12,<2`); bare-core refuses with an install hint and exit 3.
- One tool per operator-callable registry command key
  (`_tools.py:86-128`), sourced from the operator-surface manifest + CLI
  schema registry. Every tool call shells out to
  `aeat --format json <path> <args>` via `subprocess.run`
  (`_server.py:140-150`) — the black-box discipline is already the
  execution mechanism.
- **Persona scope IS live** (resolved from `AEAT_MCP_PERSONA` at serve,
  `_persona_scope.py:249-274`; `_list_tools`/`_call_tool` filter and
  refuse, `_server.py:171-194`) but family-granular only:
  preparer/verifier/reconciler all resolve to `families={"modelo"}`, so the
  scope gate cannot separate them (`_persona_scope.py:36-48`).
- **The HITL CONFIRM tier is NOT enforced.** `_call_tool` acts only on
  `ConfirmationPolicy.BLOCK` (`_server.py:195-199`); a `CONFIRM` verdict
  (destructive / export / file handoffs, `_hitl.py:43-58`) falls through
  and executes with no human prompt. Only the permanent live-write BLOCK is
  real.
- **The faithfulness check is NOT wired.** `faithfulness_check`
  (`_faithfulness.py:54-78`) is never imported by the server; it exists
  only for tests/eval. No PostToolUse path exists.
- **Zero telemetry.** No per-call logging, latency, session id, or
  trajectory record; the subprocess wrapper discards everything but the
  JSON envelope.
- **No real client handshake has ever run**, in test or otherwise:
  `_run_server` is `pragma: no cover`; all MCP tests exercise
  SDK-independent pure functions; nothing initialises a session or calls a
  tool over the wire. An external MCP client (Claude Desktop/Code) COULD
  connect today (`aeat-mcp` + `AEAT_MCP_PERSONA` env), but nothing proves
  it.

**Workspace materialiser.** `aeat app agent --output DIR`
(`_app_agent_workspace.py:26-66`) writes a flat `rules/ personas/ skills/`
tree (`_workspace.py:39-88`). It is NOT a Claude Code project layout (no
`.claude/` root, no manifest, no settings); no in-repo consumer reads it —
a dead-end export today.

**Eval substrate — replay/static only, confirmed.** The determinism replay
(`eval/_replay.py:33-57`) asserts byte-identical re-resolution of recorded
`GoldenToolCall`s; the golden runner asserts trajectory keys resolve
against the live CLI, lifecycle order holds, and the skill playbook
matches. Every model-behaviour dimension (faithfulness, confirmation tier,
contradiction halt) is caller-injected as a pre-computed verdict
(`eval/_models.py:97-513`), never generated. Scenarios cannot fail on
model misbehaviour, only on registry/CLI drift.

**Prior art: a real LLM client exists in-tree but is one-shot.**
`src/aeat/adapters/outbound/llm/` is a full async completion stack
(`LLMClient.complete()`, `_client.py:77-148`) with cache, usage recording,
cost estimation, and provider adapters for Anthropic, OpenAI, Gemini, and
local Ollama, configured via `Settings`. It has no tool-calling loop and
no multi-turn state; its only consumers are the invoice/evidence
classifiers. Deps: `anthropic>=0.74.1,<1` (extra), `mcp>=1.12,<2` (agent
extra); no agent-framework dependency.

**Console capability inventory — which of the five console powers exist
today.** The server exposes one tool per operator-callable CLI command key
and nothing else, so capability reduces to "is there a CLI verb for it":

- *(a) Ground user requests — PARTIAL (deterministic half).* The grounding
  verbs exist as tools: `aeat app overview status/calendar/agenda/explain`
  (obligation derivation from profile facts) plus the profile wizard. The
  natural-language→profile-facts mapping is correctly left to the model.
- *(b) Legal corpus — ID/TOPIC LOOKUP ONLY, no search, and the legal TEXT
  never reaches the operator.* `registry citations list|view|verify` and
  `registry manuals list|view|rules|verify` are real read-only tools
  (`_registry_corpus.py:46-195`), but they return citation METADATA
  (numero/titulo/permalink/cite), not corpus prose. The only code that
  opens a `corpus_ref` file and returns its text is `_legal_corpus_text`
  (`domain/calculations/registry/_legal.py:104-115`), called exclusively
  from the verify-time `required_text` cross-check gates — a validation
  path, not a retrieval API. At runtime a `legal_ref` travels as an id.
  Notably for a future search tool: the 799 normatives ship as raw HTML
  plus `.extracted.json` + `.extracted.md` triples — clean extracted text
  already exists to index; alongside manuals, manual oracles, diseños de
  registro, and parity replays under `src/aeat/_data/corpus/`.
- *(c) Semantic RAG — ABSENT from the product.* No embedding/semantic
  search exists anywhere in `src/aeat/`; everything RAG-ish (pagefind,
  glossary, vaultspec-rag) is dev tooling, not shipped. Must be built.
- *(d) Deep CLI knowledge — EXISTS, strongest pillar.* `aeat app contract`
  is exposed as the READ_ONLY manifest tool. Caveat: it is a summary —
  per-verb argument schemas are not in it; the MCP tool inputSchema is a
  generic `{args: [string]}` bag (`_tools.py:33-44`), so the agent must
  run `--help` per verb.
- *(e) Gated execution — EXISTS with the caveats above* (CONFIRM and
  faithfulness nominal; persona scope family-granular; live-write BLOCK
  real).

**No MCP prompts or resources.** The server registers only `list_tools` +
`call_tool` (`_server.py:177,184`); zero `list_prompts`/`list_resources`
hits. Skills/rules/personas cannot ship through the protocol today.

**The operating layer is shipped, reachable, and completely unsurfaced.**
`aeat.agent` exposes `iter_operator_rules()`, `iter_personas()`,
`iter_skill_documents()`, `operator_rules_text()` via
`importlib.resources` (`src/aeat/agent/__init__.py:29-75`) — the server
process could load every document with no new dependency, but never
imports `aeat.agent`. The `AEAT_MCP_PERSONA` wiring maps only to a
family/mutability scope; persona prose is never loaded. The terminology
handbook (~40+ concept TOMLs in `src/aeat/_data/terminology/`) has zero
product-side consumers — dead product data a console glossary tool could
revive.

**Skill anatomy supports situation keying without body rewrite — but the
selection signal is unstructured.** All 28 skills share a uniform shape:
YAML frontmatter with exactly TWO fields (`name`, `description`), then
`Preconditions` → numbered `Procedure` → `Success assertions` → hand-off;
14 of 17 per-modelo skills carry a progressive-disclosure
`reference/casillas.md` leaf. The six situation-shaped entry skills
already encode their gating predicate over `TaxpayerProfile` facts — but
as PROSE inside `description`, with no structured `applies_when`/
`profile_facts`/`situation` field a router or MCP prompt could query
deterministically. Re-keying to a first-class situation taxonomy is a
frontmatter METADATA addition (lift the predicate from prose into a
structured field), not a body rewrite. What is missing besides that: a
delivery vehicle, and the life-situation (temporal) entries — all six
existing itineraries are steady-state; no remediation/backlog skill
exists.

**Console gap summary.** Missing: live CONFIRM enforcement with a
user-elicitation mechanism; a wired faithfulness path; corpus/semantic
search tools; per-verb tool schemas; MCP prompts/resources carrying the
operating layer; per-verb persona scope; session telemetry; life-situation
skills; and any real-client or model-in-the-loop test surface.

### Thread B — MCP operating-console patterns, skill delivery, and measurement practice

First researcher pass received 2026-07-02 (citations verified with access
dates by the researcher); the MCP-primitives deep-dive (prompts/resources/
elicitation, progressive disclosure, skill-delivery tradeoffs) is a pending
follow-up. Findings relevant under the corrected universe:

**Client delivery channel.** Claude Desktop supports one-click MCP server
installation via Desktop Extensions (`.mcpb` bundles: dependencies bundled,
no JSON editing) — the consumer-grade install path for a non-technical
taxpayer (anthropic.com/engineering/desktop-extensions, accessed
2026-07-02). Packaging the aeat console as a Desktop Extension makes "the
user's own LLM client" a realistic distribution story rather than a
developer-only one. Caveat the researcher flagged: a third-party client's
generic tool-approval dialog replaces any bespoke tiered-confirmation UX,
so the console's own gates (CONFIRM enforcement, elicitation) must carry
the safety story server-side.

**Embedded runtimes — rejected/deferred under the corrected universe.** The
Claude Agent SDK (PyPI `claude-agent-sdk`) would supply a full turn loop,
skills loading, and permission hooks, but bundles a Node CLI dependency
into a pure-Python product and builds a second, bespoke client — contrary
to the "any LLM, one console" definition. A raw Messages-API loop
re-implements everything for one provider. A local-model mode (Ollama
tool-calling reliability ~93-96% on 27-32B models in 2026,
docs.ollama.com/capabilities/tool-calling, accessed 2026-07-02) is a
future privacy-max opt-in, not the launch shape — current local tool
reliability is marginal for regulated tax guidance. All three are recorded
as considered-and-not-chosen for the ADR.

**The off-host boundary question (flag for operator decision).** ANY
API-backed LLM client — including Claude Desktop over the console — sends
the user's typed text plus tool results (as context) off-host. This is
compatible with `sensitive-financial-data-secure-storage-only` only if
(a) typed conversational text is treated as consented input, and (b) tool
RESULTS returned through the console are scrubbed of raw evidence
bytes/PII before re-entering the model context (the console is the
enforcement funnel — evidence stays as on-host references the model never
sees expanded). This is a design decision the ADR must record, not a
research answer.

**Measurement and operation of a live agent surface (2026 practice).**

- Evaluate TRAJECTORIES, not just outputs: tool selection, argument
  correctness, decision order, grounding (langchain.com/resources/
  llm-evaluation-framework; confident-ai.com agent-evaluation guide,
  accessed 2026-07-02).
- Metrics for THIS surface: task completion verified on end state;
  tool-call accuracy; steps/loops, cost and latency per session; plus the
  domain gates — HITL-override rate, live-submit-attempt rate (MUST be
  zero), and faithfulness-violation rate (narration contradicting
  registry/legal grounding).
- Frameworks: LangSmith (trajectory eval, OTel ingestion), MLflow,
  DeepEval/Confident AI (self-hostable — fits the on-host posture best).
- Operating cadence: a data flywheel — capture live trajectories + session
  telemetry, route failures to expert (tax-professional) annotation,
  promote each failure into a golden regression scenario. The existing
  replay corpus is the offline gate; live capture feeds it. Re-run
  model-in-the-loop eval on every rule/persona/skill change and on model
  bumps.

**MCP primitives (spec revision 2025-11-25 is current;
modelcontextprotocol.info/specification/2025-11-25/changelog, accessed
2026-07-02).** Client support is a negotiated capability, not an
assumption (canimcp.dev matrix, 32 clients × 12 capabilities): `tools` are
near-universal; `prompts` and `resources` widely but not universally
supported; `elicitation` is newest and least universal. Design rule:
tools carry the floor of functionality; prompts/resources/elicitation are
progressive enhancements.

- *Prompts* — user-controlled templates surfaced as slash commands
  (`prompts/list` + `prompts/get` with typed arguments). A prompt's
  returned messages can EMBED resources, so invoking a guided workflow can
  inline the matching skill document plus corpus excerpt into the
  conversation. User-initiated pull, not auto-resident.
- *Resources / resource templates* — application-controlled documents by
  URI (`resources/list|read|subscribe`, `list_changed` for central
  versioning; RFC 6570 templates like `aeat://skill/{name}`,
  `aeat://corpus/{ref}`). The portable channel for rules/skills/personas —
  but pull-only; a client may list and never read them.
- *Elicitation* — server-initiated `elicitation/create` with `{message,
  requestedSchema}` (flat primitives only: string/number/integer/boolean/
  enum with formats and bounds); the client renders a form and returns
  accept/decline/cancel. This is the MCP-native HITL mechanism the unwired
  CONFIRM tier needs. Hard limits: the spec forbids requesting SENSITIVE
  information via elicitation, and support must degrade (to a tool
  argument or notice) when the client lacks the capability.

**Progressive disclosure of a large tool surface (the load-bearing design
problem).** A flat dump of the whole CLI verb tree into `tools/list`
crowds out the user's question and degrades tool selection. Mature
patterns: GitHub's server groups tools into TOOLSETS (which bundle the
relevant resources and prompts, with a dynamic-discovery mode that starts
near-empty); Cloudflare's API server exposes 2,500+ endpoints through just
TWO meta-tools, `search()` + `execute()`; progressive schema disclosure
defers verbose bodies until used (~98% input-token reduction reported);
and tool annotations (`readOnlyHint`/`destructiveHint`) drive the client's
own confirmation UI even without elicitation. Recommendation for aeat:
domain toolsets (renta/iva/ledger/censo/lifecycle) derived from the live
operator-surface manifest so the console cannot drift, each bundling its
corpus resources and guided prompts; a `search`+`execute` fallback for the
long tail; annotations on every tool.

**Skill delivery to arbitrary clients (ranked).** The universal floor is a
`harness.load` TOOL that returns the operating rules/persona as text —
the only channel guaranteed to reach a model on a minimal tools-only
client (the community approximation of the roadmapped "skills over MCP").
Layer on: resource-templated `aeat://skill|rule/{name}` for enumerable
pull; prompts for high-value guided workflows that embed the matching
skill; and optionally materialise the same authored files into
`.claude/skills/` as a Claude-native enhancement (auto-preloaded
name+description, progressive body) — an enhancement layer, never the
baseline. Single authored source feeding all channels, matching the
one-authored-source/generated-outputs discipline.

**Grounding-tool precedent.** Knowledge-base MCP servers expose
search/retrieve TOOLS plus the source documents as RESOURCES (`kb://`
URIs) so a citation resolves to verbatim authoritative text; semantic
search as a named tool is established practice (OpenMetadata). Regulated-
domain IR consensus is HYBRID retrieval (lexical + embedding) because
compliance queries need exact citation matching AND semantic recall —
directly applicable to the bundled BOE/AEAT corpus.

### Thread C — the user-situation skill taxonomy

**The registry capability envelope.** 41 modelos ship in the registry
(`src/aeat/_data/registry/aeat/modelos/`): 036, 100, 111, 115, 117, 123,
126, 128, 130, 131, 151, 180, 184, 187, 188, 190, 193, 194, 200, 202,
210, 231, 232, 296, 303, 308, 309, 322, 347, 349, 353, 360, 361, 369,
390, 714, 720, 721, 840. Only 17 have Tier-B skills. M037 is retired
(merged into 036), so "alta" keys off 036 — and no 036 census-filing
skill path exists at all despite the registry directory existing.

**Skill-selection predicates already exist as typed profile facts.**
`TaxpayerProfile` (`src/aeat/domain/deadlines/_models.py:404`) carries the
axes: `entity_type` (most consequential), `legal_entity_form`,
`irpf_income_categories`, `irpf_estimation_regime`, `iva_regime`,
`irpf_special_regime` (impatriado→151), `fiscal_residency` (→IRNR 210),
the withholding flags (`has_employees`, `pays_professionals_with_
retencion`, `pays_rent_with_retencion`), the intracomunitario/347/720/721
flags, and the lifecycle facts `activity_start_date`/`activity_end_date`
(the direct alta/cese predicates). Obligation derivation is ALREADY
implemented: the overview coverage engine reconciles profile→registry and
partitions every modelo into surfaced/excluded/advised/out-of-scope, so
situation skills never hard-code obligation sets — they read `overview
calendar/agenda/explain`. This satisfies the prior content-ADR's D5
principle (itineraries derived from profile facts, never hand-enumerated)
with machinery that now exists.

**The "behind on obligations" situation is fully built in the CLI and
completely unexposed in the harness — the highest-value gap.** `aeat app
overview backlog` lists past-due obligations oldest-first; the recargo
extemporáneo of LGT art. 27 is fully modelled (`_recargo.py` + the
`ley-58-2003-recargo-bands.toml` legal registry entry: 1%+1% per completed
month, 15% + intereses at ≥12 months, post-Ley 11/2021, cited to
`ley-58-2003:art-27.2`); every OVERDUE deadline carries its band,
legal_ref, and a runnable `next_command`; rendering emits days_overdue,
recargo band/pct and an "AVISO: plazo vencido" notice; the engine stamps
`extemporanea=true`. Corrections likewise exist: `modelo work amend` plus
the complementaria/sustitutiva path with typed casilla deltas. The CLI can
already tell a late filer what is overdue and at what surcharge; only the
harness skill is missing. (Minor fidelity gap: the bands omit the art.
27.5 25% prompt-payment reduction.)

**Recommended taxonomy.** PRIMARY axis stays regimen/user-type (WHO) — the
strongest, most stable profile predicates, already gating the six entry
itineraries (four mutually-exclusive bases: `autonomo-estimacion-directa`,
`autonomo-modulos`, `arrendador`, `pyme-sociedad`; two composable
fact-driven overlays: `intra-community-operator`, `retenedor-empleador`).
Tax-domain must NOT be primary (situations and users both span domains);
it becomes a tag on Tier-B skills. ADD life-situation (WHEN) as an
orthogonal temporal overlay keyed off deadline/lifecycle state
(backlog/agenda results, `activity_start_date`/`activity_end_date`) that
SEQUENCES the existing per-modelo skills. Composition:
situation (WHEN) → overview confirms obligations → itinerary (WHO)
narrows → `preparar-modelo-*` (WHICH) executes → helpers do cross-cutting
work.

**Candidate new situation skills (Spanish stems):**

- `regularizar-atrasos` — backlog OVERDUE items; highest value, surface
  exists and is unexposed.
- `cierre-trimestre` — quarter boundary, reads agenda.
- `resumen-anual` — annual window (390/190/180/193/100/200/347).
- `rectificar-declaracion` — drives `work amend` + complementaria.
- `inicio-actividad` — `activity_start_date` / 036 alta (036 is a
  registry+skill gap).
- `cese-actividad` — `activity_end_date` / 036 baja (gap).

**Coverage gaps for the plan:** 24 registry modelos lack Tier-B skills
(036, 347, 720/721, 714, 210, 184, 187/188/194/231/232/296, 360/361,
117/123/126/128, 840); no 036 census-filing path exists.

Legal sources: iberley.es on LGT art. 27; garrido.es on the Ley 11/2021
recargo reform; crowd.legal on declaración extemporánea (accessed
2026-07-02).

### Licence gate — the grounding retrieval stack (resolved 2026-07-02)

The ADR's R3 blocking constraint is resolved by a dedicated licence-research
pass (all licences cited by URL, accessed 2026-07-02; overlaps with and folds
in the licence findings of the docs-terminology-search research):

- **Lexical:** stdlib `sqlite3` FTS5 (`unicode61 remove_diacritics 2`), zero
  added dependency, present in every standard CPython 3.10+ build. FTS5's
  `porter` stemmer is English-only, so Spanish folding rides a second stemmed
  column via `snowballstemmer` (pure-Python, BSD-3, already transitive via
  Sphinx). Exact citations ("art. 27.2 LGT", "ley-58-2003") do NOT go through
  FTS: the wheel already ships typed citation data (registry
  `legal_refs`/`corpus_ref`/BOE permalinks) — a direct structured lookup keys
  on citation id, FTS covers in-prose mentions. `tantivy-py` (MIT, real
  Spanish Snowball) is the named upgrade path if recall demands it.
- **Semantic:** `model2vec` `potion-multilingual-128M` static embeddings —
  MIT code AND MIT weights; runtime deps only numpy + tokenizers (no torch,
  no onnxruntime); 256-d, 101 languages incl. es/ca/hu/en; ~90.9% of LaBSE;
  CPU-instant (static lookup, no forward pass). Licence nuance recorded:
  weights MIT but distilled from BGE-m3 (MIT) on C4 (ODC-BY) — an
  attribution line lands in third-party notices. `fastembed` +
  `multilingual-e5-small` (Apache-2 / MIT, onnxruntime) is the quality
  upgrade path; SPLADE remains hard-rejected (CC BY-NC-SA, gated).
- **Vector store:** brute-force numpy cosine over a precomputed matrix —
  50k×256 f32 ≈ 51 MB, sub-10 ms per query; no ANN/faiss/qdrant earns its
  keep at this scale. Optional `sqlite-vec` (MIT/Apache dual) only for
  single-file co-location with the FTS index.
- **Fusion:** Reciprocal Rank Fusion (k=60, cap each side ~top-50) in plain
  Python; no reranker (a cross-encoder would reintroduce heavy weights for
  marginal small-corpus gain).
- **Packaging (the load-bearing move):** the corpus is static and bundled,
  so its embeddings are PRECOMPUTED AT BUILD TIME and shipped as plain data
  — model outputs are shippable per the licence-clean rule. The model
  download (behind a capability-gated `aeat[search]`-style extra, pinned
  revision, app-controlled cache dir) is needed ONLY to embed the live
  query. Degraded no-download mode = lexical-only FTS5 + citation lookup,
  with the shipped corpus vectors still powering a query-model-free
  "more-like-this-document" mode. Wheel ships no weights, no onnxruntime,
  no caches.
- **Build timing:** FTS index in seconds; corpus embeddings well under a
  minute on CPU via model2vec.
- **Open verification item (the only one):** confirm
  `potion-multilingual-128M`'s exact packaged byte size before committing
  the download UX (estimated 0.2-0.5 GB).

## Synthesis — the recommended shape

One on-host MCP server is the operating console; the harness content is
the operating law it serves. Concretely:

1. **Tools carry the floor.** Domain toolsets (renta / iva / ledger /
   censo / modelo-lifecycle) derived from the live operator-surface
   manifest, each bundling its corpus resources and guided prompts;
   `readOnlyHint`/`destructiveHint` annotations on every tool; a
   `search`+`execute` meta-tool pair as the long-tail fallback; per-verb
   input schemas surfaced (closing the `{args: [string]}` bag).
2. **Grounding becomes first-class console tools.** A hybrid
   (lexical + semantic) search tool over the bundled BOE/AEAT corpus,
   registry citations, manuals, and the terminology handbook, paired with
   `aeat://corpus/{ref}` resources so every citation resolves to verbatim
   authoritative text — the licence-clean, on-host retrieval surface the
   product currently lacks. The corpus already ships clean
   `.extracted.md`/`.extracted.json` text alongside the raw HTML, so the
   index builds from bundled data with no new extraction pipeline.
3. **The operating layer ships through the protocol.** A `harness.load`
   tool (universal floor) returning the operator rules and active
   persona; resource templates `aeat://skill|rule|persona/{name}`;
   prompts as slash-command guided workflows that embed the matching
   skill plus grounding; optional `.claude/skills` materialisation as a
   Claude-native enhancement — one authored source, four channels.
4. **Skills re-key to the user.** Keep WHO (regimen itineraries) primary
   — the six existing entry skills already carry profile-fact gates; add
   the WHEN layer (`regularizar-atrasos` first — the CLI surface is built
   and unexposed; then `cierre-trimestre`, `resumen-anual`,
   `rectificar-declaracion`, `inicio-actividad`, `cese-actividad`);
   per-modelo skills remain the executable leaves the situation layer
   sequences. Lift each skill's selection predicate from prose
   `description` into a structured frontmatter field so routers, MCP
   prompts, and eval scenarios can query it deterministically.
5. **Close the nominal gates.** Enforce the CONFIRM tier via elicitation
   (degrading to client-annotation-driven confirmation where
   unsupported); wire the faithfulness check into the serving path with
   its hard block at the export/record boundary; keep never-live-submit
   as "no such tool exists" — the strongest form.
6. **Make it operable and measured.** Session telemetry (per-call
   trajectory records, session ids, latency); a real-client handshake
   test; a self-hostable model-in-the-loop trajectory eval whose hard
   invariants are zero live-submit attempts and zero faithfulness
   violations at handoff, run on every change to rules/skills/prompts/
   tool descriptions (the prose IS the code under test); the data
   flywheel — live trajectories feed new golden scenarios.
7. **Distribution.** A signed `.mcpb` Desktop Extension (local server
   next to the encrypted store) as the consumer path; the same server
   reachable by any MCP client for power users.

## Open questions for the ADR

- **Off-host consent framing.** Any non-local client sends the user's
  typed text and the tool results the model sees to that client's LLM
  provider. Evidence bytes stay on-host (never tool output, never
  elicited), but the conversation is off-host by the client's nature.
  The ADR must record the consent posture ("your words and the figures
  the assistant sees go to your chosen LLM provider; your source
  documents never leave your machine") and its relation to
  `sensitive-financial-data-secure-storage-only`.
- **Semantic-search engine choice.** Hybrid retrieval needs an on-host,
  licence-clean embedding/lexical stack shippable in the wheel (or as an
  extra) — engine, model, and index-build story are undecided
  (`shipped-search-licence-clean` binds the licensing).
- **Toolset granularity and the meta-tool threshold.** Static domain
  toolsets first; at what surface size does the `search`+`execute` pair
  take over?
- **Persona scope granularity.** Family-granular scope cannot separate
  preparer/verifier/reconciler; does the console adopt per-verb scopes
  (closing the prior content-ADR's D3 caveat) or keep persona discipline
  prose-level?
- **Elicitation degradation contract.** Exact fallback semantics per
  missing client capability (prompts absent, resources absent,
  elicitation absent) need a decided, tested matrix.
- **Relation to the prior agent-harness ADRs.** This refoundation
  implements the accepted 2026-06-30 framework ADR's end-state (MCP as
  the tool surface) and extends the proposed 2026-07-01 content ADR
  (situation layer atop D5/D6 tiers); the ADR must state supersession
  precisely rather than re-deciding settled questions.
- **Eval substrate.** Which self-hostable framework (DeepEval-style vs
  bespoke over the existing golden-scenario models) runs the
  model-in-the-loop gate, and which model(s) drive it.
