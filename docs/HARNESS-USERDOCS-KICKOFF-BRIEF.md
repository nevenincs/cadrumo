---
orphan: true
---

# Harness userdocs initiative — kickoff brief ("Working with an AI assistant")

**Audience of this brief:** the team/session that will author the user-facing
documentation for the **agent harness** — the AI-assistant surface that operates
the `aeat` CLI on a taxpayer's behalf.
**Status:** kickoff. Read fully, then **hold for the operator's instruction**
(final section) before authoring anything.
**Companion brief:** `docs/USERDOCS-KICKOFF-BRIEF.md` is the kickoff for the
*existing CLI* userdocs (the human typing `aeat` commands themselves). This brief is its
sibling for the *harness* (a human letting an LLM assistant drive `aeat` for
them). The binding principles, gates, and worktree discipline in that brief apply
here verbatim; this brief adds the harness-specific corpus, reader, and scope.

---

## 1. What the harness is (and why it needs docs)

The `aeat` CLI is a deterministic black box that computes Spanish tax forms and
exports filing artifacts (it **never files live** — a human submits to AEAT). The
**harness** is a separate product surface: a **Model Context Protocol (MCP)
server** (`aeat-mcp`) that lets *any* LLM client (Claude Desktop, an IDE agent, a
custom client) operate that CLI as an AI tax-advisor — grounding requests in the
bundled legal corpus, understanding the CLI, running the on-host search, and
driving the commands on the user's behalf under safety gates.

Today the harness has **zero user-facing documentation**. It is unusable by a
real person without it: they cannot discover that `aeat-mcp` exists, how to
connect a client, what a "persona" is, what the assistant will and will not do,
or why they still have to file themselves. The agent-facing operating corpus
(§3) is written *for the LLM*, not the human — it must be **distilled** into a
simple, followable, human-facing section, not copied.

**The one-line framing for every page:** *"`aeat` computes your tax; the
assistant helps you operate it; you still file with AEAT yourself and remain
responsible for every declaration."*

## 2. Who the reader is

The reader is a **non-technical taxpayer or their gestor** who wants an AI
assistant to help them prepare a filing — NOT a developer and NOT the LLM. They
have installed (or want to install) `aeat`, and they want to point an AI client
at it. Assume they know their tax situation ("I'm behind on my quarterly VAT")
but nothing about MCP, personas, tool scopes, or the CLI internals.

Explicitly **out of audience:** the LLM operator (it reads the agent-facing
corpus in §3 directly, at session load, via the `harness.load` tool — that corpus
is not user documentation and must not be surfaced as such); and the engineer
(the API/architecture reference already exists under `docs/api/`).

## 3. The corpus to distil (grounded file references)

Everything the docs describe is real and shipped. Read these to understand the
surface; **distil, never transcribe** — they are agent instructions, not prose.

**The operating layer (agent-facing product data, `src/aeat/_data/agent/`):**
- `src/aeat/_data/agent/README.md` — the corpus's own overview: rules /
  personas / skills, and "the CLI is the backbone, the harness is the operating
  layer; the agent never computes a tax value itself."
- `src/aeat/_data/agent/rules/` — the **operator operating contract** (7 rules
  the assistant always obeys): `operator-operating-rules`, `operator-grounding`,
  `operator-envelope-reading`, `operator-honest-declaration`,
  `operator-lifecycle-ordering`, `operator-orientation-routing`,
  `operator-safety-handoff`. These are the *behaviours* a user should be able to
  expect and trust — the raw material for an "what the assistant will and won't
  do" explanation.
- `src/aeat/_data/agent/personas/` — the **7 roles** the assistant can take,
  each with a scoped tool ceiling: `coordinator`, `onboarding`, `ledger-groomer`,
  `classifier`, `modelo-preparer`, `verifier`, `reconciler`. Selected at runtime
  via the `AEAT_MCP_PERSONA` environment variable; unset = the full unscoped
  surface. The persona split is a *safety* feature (e.g. only `verifier` can
  produce the irreversible export/filing artifact) — a user-facing concept worth
  one clear page.
- `src/aeat/_data/agent/skills/` — **30+ workflow playbooks**. Two families:
  - *Situation itineraries* keyed off the user's life-situation:
    `regularizar-atrasos` (behind on filings), `cierre-trimestre` (quarter
    close), `resumen-anual` (annual summary), `inicio-actividad` /
    `cese-actividad` (start/stop activity), `alta-contribuyente`, `arrendador`
    (landlord), `retenedor-empleador` (employer/withholder),
    `intra-community-operator`, `autonomo-estimacion-directa` /
    `autonomo-modulos`, `pyme-sociedad`, `rectificar-declaracion`. **These are
    the natural spine of the user-facing How-to section** — each is already a
    goal→steps recipe, just written for the LLM.
  - *Per-modelo preparation* (`preparar-modelo-{130,303,390,100,111,115,…}`) and
    supporting skills (`llevar-libro`, `clasificar`, `reconciliar`,
    `exportar-declaracion`).

**The runtime the user connects to (`src/aeat/entrypoints/mcp/`):**
- `aeat-mcp` — the console script (`pyproject.toml [project.scripts]`,
  `aeat-mcp = "aeat.entrypoints.mcp:main"`). This is what a client spawns.
- `_harness_tools.py` — the `harness.load` **floor tool**: the first thing a
  client loads; returns the operating rules + active persona **and the R9
  off-host privacy disclosure surfaced first** (see §6). Read
  `off_host_consent_text()` — it is the exact, already-written privacy language;
  the docs should paraphrase it, not contradict it.
- `_persona_scope.py` — how `AEAT_MCP_PERSONA` selects a persona and scopes the
  tool set; the handoff-deny boundary (only `verifier` files).
- `_hitl.py` / `_elicitation.py` — the **CONFIRM** gate: irreversible verbs
  (export, file) pause and ask the user's client to confirm; a decline refuses.
- `_faithfulness.py` — the assistant may not put a figure in front of the user at
  a filing handoff that no CLI output produced (anti-fabrication).
- `_corpus_tools.py` / `_terminology_tools.py` — the on-host grounding search
  (legal corpus + glossary) the assistant uses; never leaves the machine.
- `_server.py`, `_tools.py`, `_toolsets.py`, `_annotations.py` — the tool surface
  itself (every CLI leaf as an MCP tool, mutability-annotated).

**Distribution (updated 2026-07-03, `claude-ecosystem-packaging` ADR):** the
consumer path is the **Claude plugin** — generated from the harness source by
`aeat app agent --output=<dir> --layout=plugin`, served from the marketplace tree under
`packaging/marketplace/`, installable one-click across Claude Cowork / Claude
Code / Claude Desktop. Its `.mcp.json` launches the server via
`uvx --from "aeat-cli[agent]==<version>" aeat-mcp` from the published PyPI package (slim
~39 MB wheel; corpus source binaries ride the two optional `aeat-data-*`
companions via `aeat-cli[corpus-sources]`). The old `.mcpb` bundle under `packaging/mcpb/` is
a DEMOTED secondary — do not document it as the install path. See RELEASING.md
for the publish sequencing and `docs/verification/claude-code-install-proof.md`
for the live install proof and verified support matrix.

**The capability catalogue** the assistant reads first is
`aeat app contract --format json` — useful for the docs author to see the whole
two-root surface (`config`, `app`) the assistant can reach.

## 4. Grounding decisions and rationale (ADRs / research / audits)

Read for the *why* before writing. The harness was designed and hardened across
three ADR generations; **R1–R9 in the refoundation ADR is the load-bearing
decision set**:
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md` — **the primary
  source** (accepted). R1 toolsets, R3 on-host grounding, R4 the four delivery
  channels (floor tool / resources / prompts / skills mirror), R6 the safety
  gates (persona scope, CONFIRM, faithfulness, handoff-deny), R7 measurement, R8
  distribution/signing, R9 the off-host consent + evidence-never-leaves-host
  guarantee.
- `.vault/adr/2026-07-01-agent-harness-adr.md` (accepted) — the persona model,
  the two-root operator surface, the never-live-submit boundary.
- `.vault/research/2026-07-02-agent-harness-refoundation-research.md` and
  `.vault/research/2026-07-02-agent-harness-operability-followup-research.md` —
  the problem framing and the resolution table for the operability findings.
- `.vault/audit/2026-07-03-agent-harness-operability-followup-audit.md` — the
  live-model measurement (a real Opus persona operating the CLI); a good source
  of concrete, real assistant behaviour and known rough edges to set user
  expectations honestly.
- `.vault/audit/2026-07-02-agent-harness-content-review-audit.md` — a review of
  the corpus content itself.

## 5. How to author (binding — inherited from the CLI userdocs brief)

The rules in `docs/USERDOCS-KICKOFF-BRIEF.md §3–§5` are **binding here too**:
- **Diátaxis is binding.** Every page is exactly one of Tutorial / How-to /
  Explanation / Reference. Rules:
  `.claude/skills/vaultspec-documentation/references/diataxis-rules.md`.
- **Agent-driven, multi-reviewed, prose-verified.** Produce each doc through the
  `vaultspec-documentation` skill pipeline (wireframe → refinement → context →
  draft → technical review → editorial); two independent lenses per doc (Diátaxis
  purity + zero-context newcomer clarity). Prose style:
  `.claude/skills/vaultspec-documentation/references/prose-style-rules.md`.
- **Simple, imperative, singular.** Per the `aeat-user-docs-hardening` and
  `aeat-documentation-workflow` project rules: "Create profile." not "We will now
  set up the profiles." Taxpayer-general terms (NIF/CIF/DNI/NIE), not "autónomo"
  only.
- **Single-source / relocation-resilient.** Reference stable CLI *verbs* and MCP
  *tool/persona/env-var names*, never internal module paths. **Do not reuse the
  runtime locale keys** (`src/aeat/locales/*.yml`) and **do not transcribe the
  agent-facing corpus** — both are different audiences with their own single
  source. Distil into fresh human prose.
- **Ground against the live surface.** Verify every `aeat` verb via its live
  `--help`; verify MCP behaviour by actually running `aeat-mcp` against a client
  (or the serving-path tests under `src/aeat/entrypoints/mcp/tests/`). Never
  invent a tool name, persona, env var, or flow.

**Gates:** the docs conformance gate
(`src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` / the
`docs`-marked educational-docs conformance test) checks every cited `aeat` verb
resolves and every relative link is real — run it on every prose change. The
`-n -W` Sphinx build (`src/aeat/tests/test_docs_build.py`) is the full gate.
There is also an operator-harness rule-surface gate
(`src/aeat/agent/tests/test_rule_surface_conformance.py`) that keeps the
*agent-facing* corpus citing live verbs — a useful cross-check that the flows you
document are real, though it governs the corpus, not your prose.

## 6. Harness-specific constraints (non-negotiable)

- **Never implies live submission.** The assistant builds, checks, and exports;
  the human uploads to AEAT and stays responsible. Every harness page must carry
  the same boundary the CLI docs do. The `verifier` persona produces the export;
  filing is still the human's step.
- **Off-host privacy is a first-class user concern (R9).** When a person points a
  cloud LLM at `aeat`, *their words and the figures the assistant works with go to
  that LLM provider; their source documents (invoices, statements, evidence bytes)
  never leave their machine* (encrypted local storage). The harness surfaces this
  as a consent disclosure on first load (`off_host_consent_text()` in
  `_harness_tools.py`). The docs must state this plainly, in the user's terms, and
  early — especially for gestors handling third-party data.
- **The assistant will refuse, by design.** Document the safety behaviours as
  *features to trust*, not bugs: it asks the client to CONFIRM before an
  irreversible export/file; it will not show a filing figure it did not get from
  the CLI; a preparer/reconciler persona cannot file (only `verifier` can); it
  cannot be argued into filing live.
- **Distinguish the two documentation audiences sharply.** The agent-facing
  corpus (`src/aeat/_data/agent/`) is product data the LLM reads; your output is
  human prose the taxpayer reads. Do not cross-link users into the raw corpus.

## 7. Candidate scope (for the operator to prioritise — do NOT start yet)

A plausible new documentation section — working title **"Working with an AI
assistant"** — sitting alongside the existing CLI how-to/tutorial/explanation
tree in `docs/index.md`. Illustrative, not authorised:
- **Explanation** — "What the AI assistant is (and isn't)": the operating-layer
  model (CLI computes, assistant operates, you file), the safety gates, the
  off-host privacy boundary, why it never files live. One page, understanding-only.
- **How-to: connect a client** — install the aeat plugin from the marketplace
  (Cowork/Desktop plugin browser or `claude plugin install`), choose a persona
  in the plugin's configure step (the `persona` option feeds
  `AEAT_MCP_PERSONA`); power users wire `uvx --from "aeat-cli[agent]==<version>" aeat-mcp`
  into any MCP client's config; confirm the first-run privacy notice. State the
  verified support matrix honestly (see
  `docs/verification/claude-code-install-proof.md`).
- **How-to: situation itineraries** — a tight user-facing recipe per situation
  skill, led by `regularizar-atrasos` ("I'm behind — what have I missed?"),
  `cierre-trimestre`, `resumen-anual`. Each: what to ask the assistant, what it
  will do, where it will pause for your confirmation, and the file-it-yourself
  handoff. Distilled from the `skills/` corpus.
- **Tutorial** — one on-rails "prepare your first filing with the assistant,
  start to finish" once a flow is verified green end-to-end via a real client.
- **Reference** — a short lookup of personas, their scopes, and the key
  environment variables; link to the generated CLI/API reference, do not
  re-author it.
- **Troubleshooting** — the assistant refused / paused / degraded (schedule-only
  calendar, lexical-only search without the `aeat-cli[search]` extra); how to read a
  `notice`.

## 8. Known state and constraints

- **The harness is landed and hardened** (all R1–R9 accepted; the operability
  follow-up items resolved — see the resolution table in
  `2026-07-02-agent-harness-operability-followup-research.md`). The behaviours
  you document are real today.
- **Live-model measured (PASS)** for the `regularizar-atrasos` path; the
  `2026-07-03-…-audit` has concrete, quotable real assistant output.
- **Unsigned `.mcpb`** — document install honestly (unverified-publisher warning);
  the signing mechanism is wired but awaits a release identity.
- **Semantic search is opt-in** behind the `aeat-cli[search]` extra (a ~0.5 GB model
  download on first use); the default is lexical-only. Set expectations.
- **Shared multi-agent worktree.** NEVER use destructive git; commit
  explicit-path only; `git diff -- <file>` before editing and abort on
  non-authored WIP. (Same discipline as the CLI userdocs brief §5.)

## 9. HOLD FOR INSTRUCTION

**Do not begin authoring or dispatching work from this brief alone.** It
establishes context and the operating frame only.

Before any wireframe, draft, or commit, **STOP and present to the operator:**
1. a one-paragraph read-back of the harness surface and the biggest documentation
   gaps you see;
2. a proposed prioritised scope drawn from §7 — as options (which pages, breadth
   vs depth, which situation itineraries first), not a fait accompli;
3. clarifying questions (target reader precision, first deliverable, first-wave
   size, whether this is a new top-level docs section or nested under the existing
   how-to tree).

Then **wait for the operator's explicit instruction** on scope and priority. The
operator drives; this brief does not authorise autonomous execution.
