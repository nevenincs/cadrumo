---
tags:
  - '#research'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related: []
---

# `agent-harness` research: `AEAT CLI agent-harness framework`

## Intent

The `aeat` CLI is a deterministic, machine-facing toolkit for Spanish tax
calculation, ledger management, and filing-handoff. Its *target operator is an
LLM agent* — an "agentic tax advisor" — not a human at a terminal. The CLI's
user-facing UX (instructive errors, curated help, localised prose) exists, but
the agentic operators it was built for do not exist yet.

This research grounds a new feature: the **agent-harness framework** — the
cognitive / operating layer that sits on top of the CLI backbone and lets an LLM
agent drive it reliably and safely. The framework is, concretely, three authored
artifact families (operating *rules*, tax-advisor *personas*, workflow *skills*)
plus the wiring that exposes the CLI to an agent as typed tools.

The central reframing: the CLI is the **backbone** (deterministic, it computes
the tax); the harness is the **operating layer** (the agent orchestrates,
extracts, classifies, narrates, and hands off — but never computes a tax value
itself). This division is exactly the architecture every production financial-AI
system surveyed has converged on (see *External landscape*).

## Finding 1 — The backbone is already ~75% agent-ready

The CLI is a thin Typer transport over `aeat.application`/`aeat.domain`, with a
console entry `main()` → `app(prog_name="aeat")` in
`src/aeat/entrypoints/cli/__init__.py`. It already carries the machine-facing
scaffolding an agent operator needs. This is the project's biggest asset: the
hard part (a typed, deterministic, instructive tool surface) is done.

**Two-root command tree.** Exactly two namespaces — `aeat config` (local
config, on-ramp, diagnostics) and `aeat app` (operational tax work, sub-groups
`overview, ledger, live, modelo, registry, review`). The architecture rule pins
the surface to these two roots. The authoritative set of machine command
identifiers is the `SCHEMA_REGISTRY` key set (the strings passed to
`_emit_envelope(command=...)`), e.g. `ledger.add`, `modelo.calculate`,
`modelo.reconcile.pull` — note the envelope drops the `app.` prefix.

**A versioned JSON envelope contract.** Owner: `src/aeat/core/json_contract.py`.
Every `--format json` response is a `SchemaEnvelope` with a shared spine
(`schema_version`, `command`, `status`, `result`, `notices`),
`ENVELOPE_SCHEMA_VERSION = "2"`. `result` is a strict, frozen pydantic schema
(`extra="forbid"`, `strict=True`). The error envelope (on stderr,
`core/errors/_registry.py`) shares the *same spine* with a nested `error`
(`code, category, message, suggestion, retryable, runbook_id, context,
trace_id`). An agent reads one `status` field rather than branching on
stdout-vs-stderr.

**The typed `Notice` channel — how an agent learns "what to do next".** `Notice`
(severity `info`|`warning`, stable machine `code`, `message`, optional
copy-paste `suggestion`, structured `context`) is the *single* non-blocking
diagnostic surface (rule `cli-notices-are-the-only-diagnostic-channel`).
Next-step hints ride as `info` notices with a `suggestion`; advisories the
operator must act on ride as `warning` and flip the envelope `status`. Blocking
failures are not notices — they raise `AeatError` to the structured stderr
envelope.

**An `ExitCode` table with agent-meaningful semantics.** `_exit_codes.py`:
`SUCCESS=0, ERROR=1, REFUSED=2, AUTH=3, INTEGRITY=4, FAIL=5, INTERNAL=6,
LOCKED_BY_DESIGN=7, LOCKED_BY_CONCURRENCY=8, NO_NETWORK=10, USAGE=20`. The
load-bearing distinction for an operator: **`1` is an expected, actionable
domain verdict** (e.g. a verify that resolves BLOCKED/INCOMPLETE), while **`6`
is reserved for genuine crashes only**. An agent must not treat a `1` as a
failure to abort on — it is a verdict to act on.

**Instructive-failure surface (self-correction fuel).** Bad `--year`/`--period`
raises a `BadParameter` that *enumerates the declared period tokens for the
modelo*; the root `--language` is a `Choice`; `AeatTyperGroup` layers a
synonym/typo "did you mean" table; every error envelope carries a runnable
`suggestion` + `runbook_id` + `retryable`. The CLI gate is, by rule, never a
silent black hole — it always names the accepted set. This is exactly what lets
an agent recover from a mis-call without human help.

**Operator state model.** The profile/bucket is the unit of isolation, addressed
by operator *label* (never the UUID). `AEAT_LOCAL_STORAGE_ROOT` is the single
state root an agent sets to isolate a run. A `modelo work` unit is addressed by
`--modelo` + `--year` + `--period` (composed separately). Single-subject verbs
take a positional id (8-char prefix accepted).

**Safety rails that are permanent, not configurable.** `LiveSubmitForbiddenError`
makes live AEAT submission permanently forbidden ("produce → verify → export and
upload the file yourself in the AEAT portal"); the entire `app live` tree is
read-only / fail-closed. Destructive verbs require `--yes`/`--confirm`; mutating
imports support `--dry-run`. A storage write-policy guard refuses profile-bound
mutations routed to the root fallback DB before any verb body runs.

## Finding 2 — The single highest-leverage gap: an *unexposed* capability manifest

`src/aeat/application/operator_surface/_contract.py` already defines an
`OperatorSurfaceContract` that enumerates: the two roots and their
`required_children`; every `MountedCommandFamily` with its `domain`, `commands`,
a one-line `operator_question` (intent), `service_owner`, and an
`OperatorMutability` (`READ_ONLY` / `LOCAL_STATE_MUTATING`); the
`CALCULATE → VERIFY → FILE` modelo lifecycle; and source-kind aliases. There is
also a curated typed help model in `operator_surface/_help.py`
(`HelpDocument`/`HelpSection`/`HelpEntry`, plus a `build_root_landing_report`
that points at the next action).

**This is, essentially, an agent's tool catalogue — but it is consumed only by
conformance tests; no CLI command emits it.** Today an agent would have to scrape
`--help`. Exposing the contract and the `SCHEMA_REGISTRY` schemas as a
discoverable, machine-readable manifest (e.g. `aeat app contract --format json`)
is the single highest-leverage, lowest-cost piece of the harness: it hands the
agent its capability map, per-command intent, mutability annotations, and the
lifecycle ordering for free, and it is the natural input to an MCP `tools/list`.

## Finding 3 — The operator harness is the *positive inverse* of the existing persona harness

The repo's only harness-shaped precedent is the `cli-persona-testimonials`
lineage (catalogue `2026-05-20-cli-persona-task-catalogue-reference`, the
testimonial-driven verification playbook, the live `2026-06-30` hardening plan).
It is a mature instrument — but it is the **opposite** of what we are building,
and the contrast is the clearest possible spec for the new harness:

| Axis | Persona harness (today) | Operator harness (needed) |
|---|---|---|
| Goal | Find UX walls / defects | Reliably execute the tax work end-to-end |
| Information rule | **Forbidden** to read source/docs/JSON internals; must stumble like a human | **Must** be *given* the capability map, JSON contract, and operating rules up front |
| Surface used | `--help` text (human-readable) | `--format json` envelopes, `Notice.suggestion`, the contract manifest |
| Output | A subjective testimonial + graded bug list | A correct, provenance-grounded filing artefact + audit trail |
| Mistakes | *Desired* (they surface friction) | *Prevented* by guardrails and playbooks |
| State | Throwaway isolated scratch | Durable, secure, profile-scoped operator state |

The persona harness is a *negative* instrument: it withholds knowledge to expose
gaps. The operator harness is the *positive* inverse: it must **supply** exactly
the knowledge the persona is forbidden. The persona brief therefore cannot be
reused — the harness must be authored anew.

What an autonomous LLM tax-advisor operator needs that the repo does NOT yet
provide:

1. **Agent-facing *operating* rules**, distinct from the dev/vaultspec rules.
   Today's `.claude/rules/*` govern how *engineers build the repo*. The safety
   invariants for an *operator* (never invent a casilla value; relay CLI JSON
   verbatim with `legal_refs`/`source_refs` intact; never claim a local export
   is official AEAT evidence; never submit live; treat `verified_complete` +
   zero findings on positive income as suspect, per `no-silent-under-declaration`;
   stop and surface `warning` notices rather than proceed) exist *in code* but
   are not packaged as an agent operating contract.
2. **Tax-advisor role personas** (positive, not adversarial) — a coordinator and
   task-specialised subagents that are *given* the contract and told to execute
   correctly, with tool access scoped to their role.
3. **Workflow skills/playbooks** — the canonical end-to-end flows as executable
   operator procedures (preconditions, command sequence, success assertions,
   JSON-field checks), not human prose under `docs/how-to/`.
4. **The exposed capability manifest** (Finding 2).
5. **An MCP wrapper or Agent-SDK bundle** — none exists today.

## Finding 4 — The canonical operator workflows (candidate skills)

From the 28 `docs/how-to/` guides and the quickstart, the happy path is:
**profile → ledger → classify → modelo create → calculate → verify → export →
(human files) → record marker → reconcile.** The discrete workflows a
tax-advisor agent must execute — each a candidate *skill* — are: onboard
taxpayer (profile); establish AEAT read access (auth); determine obligations
(`overview explain`/`calendar`); build the ledger (import, correct, dedup);
classify & apportion (IRPF/IVA categories, ratios, prorrata); attach evidence;
prepare a modelo (`work create → calculate → revision review`); verify (read
findings, fix, re-verify); export & hand off (`.boe`, SHA-256, manual upload,
record marker); reconcile (`pull` justificante, compare); live reads (censo,
notifications, filed); work the review queue; data custody & recovery.

## External landscape — the design is validated, the patterns are settled

(Web research, mid-2026; primary sources listed at end. Vendor/press material
treated as positioning; arxiv items are non-peer-reviewed preprints flagged as
preliminary.)

**Production financial agents have converged on LLM-over-deterministic-engine.**
No production system lets the LLM do the arithmetic — it orchestrates, extracts,
classifies, and communicates while a deterministic engine computes. Thomson
Reuters CoCounsel (2025) automates extraction, memo drafting, and error
detection but keeps humans for strategy, sign-off, and filing, with **mandatory
citation on every output**. Pilot (Feb 2026) claims the first fully-autonomous
SMB bookkeeper, but it is the bleeding edge; most systems retain human gates.
This directly validates our backbone/harness split and the
`aeat-calculation-grounding` provenance discipline.

**"Never auto-submit" is now explicit industry standard**, reinforced by the EU
AI Act's August-2026 high-risk human-oversight obligations and liability that
shifts to whoever "should have known" an agent might misfire. Our permanent
`LiveSubmitForbiddenError` rail is exactly the posture the field is mandating.

**The harness decomposition the field uses matches our three artifact families.**
(a) Project rules (CLAUDE.md / AGENTS.md) — prose behavioural boundaries loaded
every session; (b) per-workflow `SKILL.md` — lazy-loaded procedural knowledge
(only name+description at startup; full skill + `reference/` + `scripts/` on
demand, "progressive disclosure"); (c) formally-verifiable rules enforced by the
deterministic layer (our conformance gates), not in the prompt at all.

**MCP is the de-facto way to make a CLI agent-operable.** Wrapping each CLI leaf
as an MCP tool with `inputSchema`/`outputSchema` gives schema-validated
arguments, structured `isError: true` execution errors with instructive text,
capability discovery via `tools/list`, and `ToolAnnotations` (`readOnly`,
`destructive`, `idempotent`) that clients use to decide when to ask for human
confirmation. Anthropic tool-design guidance maps cleanly onto our surface:
unambiguous names (`filing_year` not `year`), namespacing (`aeat_calculate`,
`aeat_verify`, `aeat_export`), describing specialised terms (`casilla`), and
returning only high-signal output.

**The Claude Agent SDK supplies the primitives.** `AgentDefinition` subagents
with isolated context and scoped tools; `PreToolUse`/`PostToolUse`/`Stop` hooks
for validation and audit logging; resumable/forkable sessions; filesystem config
(`CLAUDE.md`, `.claude/skills/*/SKILL.md`, programmatic `mcp_servers`). A
sequential subagent pipeline (spec → calculate → verify → export) where the
verifier does not share the implementer's context avoids the rationalisation
problem.

**Evals: trajectory + faithfulness + determinism.** The field evaluates full
trajectories (tool choice, argument validity, step count, policy compliance),
not just final outputs. Documented failure modes for financial MCP agents: wrong
tool selection, data-interpretation mistakes, context mismanagement, and
**hallucinated tool outputs** (fabricating plausible results when uncertain). A
determinism-replay approach (capture golden tool call/response pairs, replay,
assert identical output) catches both harness regressions and the
non-determinism that is an assurance failure in regulated work. Our existing
round-30 testimonial pattern that surfaced the M200 silent-under-declaration is
precisely the scenario-based golden-task methodology the literature endorses.

## Proposed framework shape (input to the ADR)

A layered harness, authored in the project's existing artifact shapes plus an
MCP exposure layer:

- **Layer 0 — Capability manifest (enabling work).** Expose
  `OperatorSurfaceContract` + `SCHEMA_REGISTRY` schemas through a CLI command and
  feed it to MCP `tools/list`. Lowest cost, highest leverage; unblocks
  everything else.
- **Layer 1 — Operator rules** (the agent's CLAUDE.md/AGENTS.md): the operating
  contract — never compute a tax value; relay CLI JSON verbatim with provenance;
  never assert a local export is official; never submit live; act on `warning`
  notices; treat positive-income/zero-tax as suspect; resolve revision by law not
  injection. These are the *operator* analogues of the existing safety rules,
  re-cast for the agent that *uses* the tool rather than the engineer who builds
  it.
- **Layer 2 — Tax-advisor personas** (`AgentDefinition` subagents): a coordinator
  plus task-scoped roles (onboarding/profile, bookkeeper/ledger-groomer,
  classifier, modelo-preparer, verifier, filing-handoff/reconciler) with
  tool access scoped to each role's mutability tier.
- **Layer 3 — Workflow skills** (`SKILL.md` per flow): the canonical workflows
  from Finding 4 as executable playbooks with preconditions, command sequence,
  and JSON success assertions, using progressive disclosure for per-modelo
  reference material.
- **MCP server** wrapping CLI leaves as typed tools with mutability annotations,
  driving HITL via `PreToolUse` confirmation hooks (auto-approve read-only/dry-run;
  confirm verify/export; block live-write attempts) and a `PostToolUse`
  faithfulness hook that flags any numeric casilla value in agent text not
  present in the preceding tool-result JSON.
- **Eval / testimonial gate**: golden scenarios grounded in AEAT-authoritative
  worked examples (expected tool sequence, expected casilla values, provenance
  present), run on every harness change — the operator-side counterpart of the
  persona testimonial gate, and bound by the same `no-tautological-calculation-tests`
  and `no-silent-under-declaration` disciplines.

**Packaging.** Follow the accepted product-packaging model
(`2026-06-28-product-packaging-adr`): ship the harness behind a capability extra
(e.g. `aeat[mcp]` / `aeat[agent]`) or a sibling entry point, lean on
`aeat config check` for provisioning readiness, and never bundle model weights or
credentials. Co-commit every harness rule/skill that references a CLI verb or
JSON field with the CLI surface it couples to — the `aeat-cli-pull-and-file-standard`
rule is the template (it exists because verb drift orphaned operator
instructions).

## Open questions for the ADR

1. **MCP server vs. raw-Bash harness vs. both.** Recommendation leans MCP
   (typed args, capability discovery, annotation-driven HITL), but a thin
   rules+skills bundle over raw `aeat --format json` is a faster first cut. Decide
   the sequencing.
2. **Where the harness artifacts live and how they distribute.** A new extra /
   entry point? A separate installable bundle? In-repo `.claude/` operator
   directory distinct from the dev `.claude/`? This must not collide with the
   vaultspec dev harness that already owns `.claude/`.
3. **HITL policy tiers.** The exact mutability→confirmation mapping, and whether
   the gate lives in the MCP layer, the CLI (`--yes` already exists), or both.
4. **Faithfulness enforcement.** Advisory `PostToolUse` flag vs. hard block on a
   suspected hallucinated numeric.
5. **Eval substrate.** Reuse/extend the persona-testimonial machinery, or stand
   up a separate golden-task replay harness; how AEAT worked-example oracles are
   sourced.
6. **Naming / Spanish-stem discipline.** Operator personas/skills/tools naming
   under `aeat-spanish-stem-naming` (e.g. `casilla`, `modelo`, `declaracion`).

## Recommendation

Proceed to an ADR. Sequence the build so **Layer 0 (expose the contract
manifest)** lands first — it is small, unblocks both the MCP server and the
skills, and is independently valuable. Then author **Layer 1 operator rules** and
a minimal **Layer 2/3** vertical slice for one modelo workflow (130 or 303) over
raw `aeat --format json`, prove it against an AEAT worked-example golden eval, and
only then invest in the MCP server and the full persona/skill matrix. This keeps
the first increment cheap and falsifiable while committing to the validated
end-state (MCP + three-layer harness + HITL hooks + golden/replay evals).

## Sources

Internal (by stem): `operator_surface/_contract.py`, `operator_surface/_help.py`,
`core/json_contract.py`, `core/errors/_registry.py`, `entrypoints/cli/_exit_codes.py`,
`entrypoints/cli/__init__.py`; vault `2026-05-20-cli-persona-task-catalogue-reference`,
`2026-06-30-cli-persona-testimonials-plan`, `2026-06-28-product-packaging-adr`,
the `docs/how-to/` set; rules `cli-notices-are-the-only-diagnostic-channel`,
`aeat-calculation-grounding`, `no-silent-under-declaration`, `aeat-safety-legal-gates`,
`aeat-cli-pull-and-file-standard`, `aeat-architecture-boundaries`.

External (web, mid-2026; URLs as plain text):
- anthropic.com/engineering/writing-tools-for-agents
- anthropic.com/engineering/code-execution-with-mcp
- anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- code.claude.com/docs/en/agent-sdk/overview
- platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- modelcontextprotocol.io/specification/2025-11-25/server/tools
- tax.thomsonreuters.com/blog/agentic-ai-use-cases-for-the-tax-industry/
- thomsonreuters.com/en/press-releases/2025/july (agentic AI launch)
- wolterskluwer.com/en/expert-insights/ai-tax-audit-workflow-effectiveness
- galileo.ai/blog/ai-agent-compliance-governance-audit-trails-risk-management
- blog.auditoria.ai/finance-ai-2026-governed-autonomy
- digitalapplied.com/blog/ai-agent-eval-frameworks-testing-guide-2026
- accountingtoday.com/news/pilot-launches-fully-autonomous-ai-bookkeeper
- github.com/Piebald-AI/claude-code-system-prompts
- FinMCP-Bench (arxiv 2603.24943) and Replayable Financial Agents (arxiv 2601.15322)
  — preprints, preliminary, cited for failure-mode taxonomy only.
