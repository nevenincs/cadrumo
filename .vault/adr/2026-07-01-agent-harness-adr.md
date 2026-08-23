---
tags:
  - '#adr'
  - '#agent-harness'
date: '2026-07-01'
modified: '2026-07-10'
body_hash: 'sha256:73bebaf19a623c32a2919a94fa9cf2407f32f9106ec4c90f3b9752e12a6dfc6d'
related:
  - "[[2026-07-01-agent-harness-research]]"
  - "[[2026-06-30-agent-harness-adr]]"
---

# `agent-harness` adr: `harness content: rules, personas, skills` | (**status:** `accepted`)

## Problem Statement

The accepted `2026-06-30-agent-harness-adr` settled the harness's SHAPE: four
layers (manifest, rules, personas, skills) plus an MCP tool-exposure surface,
resolving six cross-cutting questions (tool exposure, artifact home, HITL
tiers, faithfulness, eval substrate, naming). It left the CONTENT of Layers
1-3 - what the rules actually say, what the personas actually cover, how the
skills are actually organised - for a follow-on decision, because the content
questions could not be answered without first grounding them against the real
CLI surface and real operator-failure evidence.

That grounding is now done. The harness first cut is **substantially built at
HEAD**, not greenfield: the Layer-0 manifest builder
(`build_operator_surface_manifest`), four theme-clustered Layer-1 operator
rule files shipped as wheel data (`operator-operating-rules`,
`operator-envelope-reading`, `operator-grounding`, `operator-safety-handoff`),
a live drift gate (`test_rule_surface_conformance`) that resolves every
backticked verb and envelope field in those rules against the live manifest
and the real `SchemaEnvelope`/`Notice` models, seven personas under
`src/aeat/_data/agent/personas/`, at least one skill
(`exportar-declaracion`), an MCP server plus `PreToolUse`/HITL scaffolding
under `entrypoints/mcp/`, and the end-user workspace materialiser
(`aeat app agent`). This ADR is therefore a **restructure/completion**
decision, not an invention of the layers: it ratifies the taxonomy the three
design-mapping passes converged on, closes the structural gaps they found
(a missing lifecycle-ordering rule, an unowned export boundary, an unenforced
black-box negative gate, a dormant enum member), and settles the seven
load-bearing decisions the `2026-07-01-agent-harness-research` document's ADR
agenda identified. It introduces no code; it records the decided content
shape and the rationale for each resolution.

## Considerations

**The manifest is the single capability authority; nothing else may snapshot
it.** Per D2 in the accepted parent ADR, any rule, persona, or skill that
names "what the backend can do" must reference the live
`OperatorSurfaceContract` (`aeat app contract --format json`), never hardcode
a summary. This governs every one of the seven decisions below: a rule
naming a verb, a persona naming a family boundary, and a skill naming a
lifecycle step are all reads of the manifest, not restatements of it, and the
existing positive drift gate (a rule may only name a verb/field the manifest
exposes) is the mechanism that keeps that discipline live.

**The operator/dev rule boundary is absolute and must not blur.** Operator
rules (`_data/agent/`, materialised to the end-user workspace) and dev/
vaultspec rules (`.claude/`, synced by `vaultspec-core sync`) differ in
audience, home, citable surface, and enforcement gate. Operator rules may
name only the CLI/manifest/legal surface; dev rules may name the whole
package. `operator-harness-cites-live-cli-surface` is the dev-side bridge
rule and stays dev-side. No decision below moves content across that
boundary.

**Naming discipline carries over from the accepted ADR (Q6).** Personas keep
English generic role nouns (`coordinator`, `verifier`, `classifier`); skills
keep Spanish domain stems (`preparar-modelo-130`, `reconciliar`,
`exportar-declaracion`) per `aeat-spanish-stem-naming`.

**Empirical grounding, not speculation.** The failure taxonomy mined from the
`cli-persona-testimonials` lineage (missed under-declaration, obligation
scoping, dropped provenance, lifecycle-sequencing contradictions, profile
confusion, wrong tool/grammar choice) grounds six of the nine identified
failure categories in real reproductions; three (exit-code misread, HITL
bypass, hallucinated numerics) have no AEAT persona repro and rest on
external-literature reasoning. Every decision below is traceable either to a
concrete repro or to an explicitly-flagged design-reasoned gap, never to
unmotivated preference.

## Considered options

Each of the seven load-bearing decisions the research's ADR agenda raised is
recorded below as a titled subsection: the decision, the options weighed, and
the resolution.

### D1 - Per-persona tool-boundary enforcement mechanism

**Decision:** how is a persona's manifest-scoped tool boundary (`family` child
token + `OperatorMutability` ceiling) mechanically enforced so prose and
runtime behaviour cannot diverge?

**Options considered:**
- *Build-time codegen of a second allowlist artifact* (a generated file
  listing each persona's permitted tools, checked into the harness data
  tree): gives a fast `PreToolUse` lookup, but creates a second copy of the
  contract's `(family, mutability)` data that can itself drift from the
  manifest between builds - a new drift surface competing with the manifest's
  own authority, contrary to `aeat-registry-authority-flow`'s single-authority
  discipline.
- *Prose-only persona boundary* (the persona document states its scope in
  words, no runtime check): cheapest, but unenforceable - a misbehaving or
  updated persona could silently claim a wider boundary with nothing to catch
  it.
- **Chosen - runtime manifest read filtered by active persona, backed by a
  build-time-verified pinning test.** The `PreToolUse` gate reads
  `aeat app contract --format json` at session start and filters the tool
  set live by the active persona's declared `(family, mutability)` ceiling;
  a test asserts each persona's declared ceiling still resolves against the
  live contract (codegen the ASSERTION, not a second allowlist). This keeps
  exactly one authoritative source (the manifest) and makes a manifest change
  fail the pinning test loudly rather than silently widening or narrowing a
  stale copy.

### D2 - Retire the unused `LIVE_READ` mutability member

**Decision:** does the `live` command family's `OperatorMutability` annotation
stay `LOCAL_STATE_MUTATING`, or does the harness introduce/adopt the
currently-declared-but-unused `LIVE_READ` member?

**Options considered:**
- *Adopt `LIVE_READ` for the `live` family* (framing a live pull as a pure
  read with no local side effect): matches the intuitive "pull is read-only"
  mental model, but is factually wrong - a `live` pull writes derived local
  state (the censo snapshot, the participation index), so labelling it
  `LIVE_READ` would misrepresent its mutability to every consumer of the
  contract, including the `PreToolUse` HITL gate.
- **Chosen - `live` stays `LOCAL_STATE_MUTATING`; `LIVE_READ` is retired.**
  The member is dormant (declared, zero production consumers) and its
  intended meaning does not describe any real command family. Retiring it
  removes a taxonomy fork that would otherwise invite a future persona
  document to reach for the wrong member. Per
  `retired-enum-members-need-consumer-reconciliation`, deletion is gated on a
  zero-consumer check across production and test code before the member is
  removed from `OperatorMutability`; this decision authorises that check as a
  Track-1-adjacent cleanup, not a live-now code change.

### D3 - Ownership of the export / record-marker handoff boundary

**Decision:** the accepted parent ADR's Layer-2 roster left the irreversible
export-and-record-marker step (the faithfulness hard-block boundary from Q4)
without an explicit owning persona - the preparer "does not export" and the
reconciler acts "after the human files". Who owns it?

**Options considered:**
- *Fold export into the modelo-preparer*: keeps the roster at its current
  size, but reintroduces the exact rationalisation risk the verifier/preparer
  context split exists to prevent - the actor that built the filing would
  also be the actor that produces its irreversible artefact, with no
  independent check in between.
- *A distinct `exportador` role* (Spanish-stem, per `aeat-spanish-stem-naming`):
  gives the strongest audit separation (a fourth, dedicated actor whose only
  job is the irreversible handoff), flagged as a live alternative for a future
  hardening pass if export-specific audit requirements grow.
- **Chosen - extend the verifier to own export and the record-marker.** The
  verifier is already the independent actor that certifies the filing clean;
  extending its mandate to producing the irreversible artefact keeps one
  independent, non-rationalising actor at the hard-block boundary without
  growing the roster. This is a **clarification of an underspecified roster
  boundary in the accepted ADR, not a reversal** - the accepted ADR named the
  seven roles and the isolation principle but left this one ownership
  question open.

### D4 - Rules-layer reorganisation and the black-box negative gate

**Decision:** how do the four existing theme-clustered operator rule files
restructure to make the three orthogonal rule axes (behavioural invariants,
orientation/routing, workflow-ordering) explicit, and how is "never name a
package internal" mechanically enforced rather than merely intended?

**Options considered:**
- *Leave the four files as-is*: cheapest, but confirmed to hide a real
  structural gap - the `CALCULATE -> VERIFY -> FILE` lifecycle invariant
  currently lives only in `coordinator.md` prose, in no Layer-1 rule, and the
  three axes (safety invariants, routing, ordering) are mixed within each
  file so a rename's drift blast-radius is unpredictable.
- *Full flat re-split into one file per fine-grained topic* (~15 files):
  makes every axis maximally separable, but over-fragments a corpus an agent
  must load per session and adds file-count churn disproportionate to the
  gap found.
- **Chosen - Option 3 hybrid.** Keep the behavioural-invariant files
  theme-clustered (Category A reads well by theme and changes rarely).
  Extract orientation/routing into one manifest-derived
  `operator-orientation-routing` rule alongside the stable
  `operator-envelope-reading` rule (Category B). Add one new
  `operator-lifecycle-ordering` rule stating the
  `CALCULATE -> VERIFY -> FILE` invariant explicitly (Category C - the
  confirmed missing rule). Optionally extract an `operator-honest-declaration`
  invariant (promoting `no-silent-under-declaration` to first-class) if it
  does not fit cleanly inside the grounding/safety files during authoring.
  Net effect ~4 -> ~7 files, each dominated by one axis. Pair this with a new
  **negative conformance gate**: it forbids an operator rule from naming an
  internal (`aeat.<pkg>...`, a `src/aeat/...` path, a private `_module`, a
  `test_*` name), and its blocklist is **sourced from the manifest's own
  `service_owner` string values**, not a hand-written regex - so a new backend
  module cannot leak into rule prose by omission, and legitimate CLI-domain
  nouns (`ledger`, `modelo`, `casilla`) are never false-positived because they
  are not `service_owner` values.

### D5 - Tier-A persona-entry-skill closure rule

**Decision:** how is the bounded set of persona-entry itinerary skills (the
research's Tier A - `autonomo-estimacion-directa`, `intra-community-operator`,
etc.) determined, so the set does not become an open-ended, subjectively
curated list?

**Options considered:**
- *Enumerate the full itinerary set now*: gives a concrete, reviewable list
  immediately, but is premature - the in-flight `#7 obligation-coverage`
  hardening brief has not yet settled which profile facts reliably determine
  which obligations apply, so an enumeration authored now risks encoding a
  wrong or incomplete mapping that later needs correction anyway.
- **Chosen - ratify the closure PRINCIPLE now; enumerate later.** Each Tier-A
  entry skill is gated on an explicit `TaxpayerProfile` fact predicate -
  the itinerary set is DERIVED from profile facts, never a hand-enumerated
  list - mirroring the same derivation discipline
  `cross-period-suppression-grounded-in-registry-classification` applies to
  cross-period dependency suppression. The concrete predicate set is deferred
  to Phase 7 of the completion roadmap, once `#7 obligation-coverage` settles
  what profile facts are reliably available.

### D6 - Skill granularity: per-modelo vs per-category vs per-persona as the executable unit

**Decision:** which of the three candidate organising axes (tax category,
modelo, taxpayer persona) is the EXECUTABLE unit - the thing a golden-eval
scenario and a co-commit both bind to?

**Options considered:**
- *Tax-category as the executable unit* (one skill per IVA/IRPF/retenciones
  category): the best REFERENCE granularity, but a poor executable unit - a
  category's real "procedure" is actually N distinct modelo procedures, so
  using it as the executable layer produces high lifecycle duplication inside
  each category skill.
- *Persona as the executable unit* (one skill per taxpayer archetype): matches
  how a user arrives, but is open-ended, subjective, and unbacked as an
  executable contract, and produces the worst duplication of all three axes
  if used as the executable layer rather than as an entry point.
- **Chosen - strict per-modelo granularity as the executable core (Tier B).**
  One skill = one registry-modelled modelo = one golden-eval scenario = one
  co-commit unit, over the invariant
  `work create -> calculate -> verify -> revision review -> export -> record
  marker -> reconcile` spine. The spine is authored ONCE as a shared
  lifecycle fragment; near-identical sibling forms (130/131, 111/115/123,
  180/190/193, 303/390) are authored BY DIFF against that shared spine, so
  each per-modelo skill carries only its form-specific delta (casillas,
  bindings, period tokens, prior-period carries, verification predicates).
  Tax-category material becomes a Tier-C shared reference fragment pulled on
  demand, not a top-level skill; persona itineraries become the thin Tier-A
  entry layer (D5) that sequences and delegates to Tier-B skills, never
  duplicating their procedure.

### D7 - Verifier/preparer context isolation without the Agent SDK

**Decision:** the roster invariant requires the verifier to run in isolated
context from the preparer to avoid the rationalisation problem. How does that
isolation degrade when a runtime has no SDK subagent-isolation primitive and
the harness operates over raw `--format json`?

**Options considered:**
- *Prose-only instruction* ("act as if you have not seen the preparer's
  reasoning"): works when a real SDK isolation boundary backs it up as a
  defence-in-depth restatement, but as the SOLE mechanism on a bare-CLI
  runtime it is unenforceable and reintroduces exactly the rationalisation
  risk the split exists to prevent - a single-context agent that "pretends"
  not to have seen its own prior reasoning still has.
- **Chosen - state the invariant testably and runtime-agnostically, enforce
  structurally wherever possible.** The invariant: "the verifier's context
  MUST be constructible from tool-result JSON alone, never from the
  preparer's transcript." Where the runtime supports it, this is enforced
  structurally - a separate invocation seeded only by the work-unit id and
  the revision JSON, with no access to the preparer's conversation. A
  degraded self-report mode (the agent asserts it constructed context from
  JSON only) is the fallback ONLY when a runtime genuinely cannot isolate
  invocations, and is explicitly named as degraded trust, not treated as
  equivalent to structural isolation.

### Reconciliation with the accepted 2026-06-30 ADR

None of the seven decisions above contradict the accepted parent ADR's
Q1-Q6. D1 is the concrete enforcement mechanism for the Q3 HITL defense-in-
depth the parent ADR already chose. D2 is a taxonomy cleanup inside the
`OperatorMutability` enum the parent ADR introduced, not a change to its
`READ_ONLY`/`LOCAL_STATE_MUTATING` split. D4's rules reorg and negative gate
implement Layer 1 as already described; no rule category is added that the
parent ADR's Layer-1 description forecloses. D5 and D6 implement Layer 3 as
already described (workflow skills, progressive disclosure, one vertical
slice first). D7 implements the "verifier runs in isolated context" sentence
in the parent ADR's Layer-2 description, made testable.

**D3 is the one decision that is an addition rather than a pure
implementation of an already-stated line**: the accepted ADR named the seven
personas and the isolation principle but left the export/record-marker
ownership question genuinely open (the research explicitly surfaced it as
"currently unassigned"). This ADR closes that gap by extending the verifier's
mandate; it does not reverse or contradict any roster decision the parent ADR
made, because the parent ADR made none on this specific point.

**D2 carries a follow-on obligation, not an immediate code change**: per
`retired-enum-members-need-consumer-reconciliation`, retiring `LIVE_READ`
requires a zero-consumer sweep across validation, schema, fixture, and test
call sites before the member is deleted from `OperatorMutability`. This ADR
authorises the direction; the reconciliation sweep is implementation-plan
work, not a claim that the member is already gone.

## Constraints

**Every decision remains bound by the accepted parent ADR's constraints.**
The CLI root surface stays pinned to `config`/`app`; the operator/dev rule
boundary (Considerations, above) is absolute; live submission stays
permanently forbidden and no decision here touches that rail; the MCP runtime
and Agent-SDK hook contracts remain evolving frontier surfaces the harness
must degrade gracefully against (D7's fallback mode is exactly that
degradation, made explicit rather than left implicit).

**Two concurrent tracks gate different decisions differently.** Track 1 -
backend hardening already in flight (the eight gap briefs: `#1` manifest
completeness, `#2` ledger-add idempotency, `#3` modelo verify guards, `#4`
determinism substrate, `#6` review actionability, `#7` obligation coverage,
`#8` reconcile depth, `#9` fichero parity) - and Track 2, this harness-content
work. Some of the seven decisions are **surface-independent** (their
principle and, largely, their authoring can proceed now, in parallel with
Track 1); others are **surface-citing** (concrete authoring must wait on a
specific Track-1 brief landing so the artifact does not orphan the moment
that brief lands). The classification is recorded in the Consequences
section below, since it determines what can be scheduled immediately versus
what must wait.

**The negative gate (D4) must not misfire on legitimate CLI-domain nouns.**
Because its blocklist is sourced from the manifest's `service_owner` values
rather than a hand-authored regex, a false positive would require a
`service_owner` value that coincides with an operator-facing noun - an
authoring-time check the implementation plan must verify empirically before
the gate ships, not merely assert.

## Implementation

The seven decisions above compose into concrete restructuring work across
Layers 1-3, staged as Phase 2 of the completion roadmap the research
document lays out (parallel with Track 1, gated where noted):

- **Layer 1 (rules).** Reorganise the four existing operator rule files per
  D4's Option 3: theme-clustered behavioural files stay; one
  `operator-orientation-routing` rule is extracted (manifest-derived); one
  new `operator-lifecycle-ordering` rule is authored (the confirmed gap); an
  optional `operator-honest-declaration` extraction is assessed during
  authoring. The negative-gate conformance test is added alongside the
  existing positive drift gate, sourcing its blocklist from
  `service_owner` values.
- **Layer 2 (personas).** The seven-role roster is retained. Each persona's
  boundary is re-expressed as `(family, mutability)` read from the manifest
  at session start (D1), backed by a pinning test. The verifier's mandate is
  extended to cover export and the record-marker (D3). The
  `OperatorMutability` taxonomy is cleaned up per D2, gated on the
  zero-consumer sweep. The verifier/preparer isolation invariant is stated
  testably and enforced structurally where the runtime allows (D7).
- **Layer 3 (skills).** The three-tier hybrid from the research is adopted:
  Tier-A persona-entry skills gated by profile-fact predicates (D5,
  principle now, enumeration in Phase 7); Tier-B per-modelo completion
  skills as the executable/golden-eval/co-commit unit, built one vertical
  slice first (D6); Tier-C shared category and lifecycle-spine reference
  fragments authored once and pulled on demand.

No source code changes accompany this ADR; the above is the shape the
subsequent implementation plan will structure into waves, phases, and steps.

## Rationale

Every resolution above is grounded either in a concrete operator-testimonial
reproduction, in an explicit HEAD-state finding from the three design-mapping
passes, or in an existing project rule the research cross-referenced (never
in unmotivated preference). D1 avoids introducing a second drift-prone
allowlist artifact, consistent with the single-authority discipline
`aeat-registry-authority-flow` establishes for the registry and extended here
to the manifest. D2 corrects a factually wrong mutability label before it
ever ships to a persona document. D3 closes a roster gap the research found
literally unassigned, choosing the option that preserves the
rationalisation-avoidance property the isolation principle exists for. D4
responds directly to the confirmed missing lifecycle-ordering rule and turns
"never name an internal" from an aspiration into a sourced, empirically
groundable gate. D5 and D6 both follow the research's axis analysis: category
is the best reference unit but the worst executable unit; modelo is the best
executable unit; persona is the best entry unit; the three-tier hybrid uses
each axis for the job it is actually good at, rather than forcing one axis to
do all three jobs. D7 states an isolation invariant that is testable and
runtime-agnostic instead of leaving it as an unverifiable prose aspiration,
matching the project's general preference for structural enforcement over
self-report (`aeat-quality-gates`, `no-silent-under-declaration`).

## Consequences

**Gains.** The seven decisions close every structural gap the three
design-mapping passes found: the missing lifecycle-ordering rule, the
unenforced black-box negative gate, the unowned export boundary, the dormant
mutability member, and the open questions on persona-boundary enforcement,
skill granularity, and verifier isolation. Layers 1-3 now have a ratified,
gap-free content shape the implementation plan can execute against without
re-litigating any of the seven questions.

**Honest difficulties.** The negative gate's `service_owner`-sourced
blocklist must be empirically verified against the live manifest before it
ships, or a coincidental noun collision could false-positive a legitimate
rule. The D7 degraded self-report fallback is a real trust reduction versus
structural isolation and must be named as such in any persona document that
relies on it, never silently presented as equivalent. The D2 cleanup is
gated on a zero-consumer sweep that has not yet been run; this ADR
authorises the direction, not the deletion. D5's deferred enumeration means
Tier-A persona-entry skills cannot be fully authored until `#7`
obligation-coverage lands, so early Track-2 work is necessarily scoped to
the principle and to Tier B/C, not the full Tier-A set.

**Surface-independent vs surface-citing classification.** This determines
what can proceed now, in parallel with Track 1, versus what is gated on a
specific backend-hardening brief landing first:

| Decision | Classification | Track-1 dependency |
| --- | --- | --- |
| D1 (persona boundary mechanism) | Weakly surface-citing | `#1` manifest completeness - the runtime read and its pinning test need the manifest's `(family, mutability)` data to be complete and stable |
| D2 (retire `LIVE_READ`) | Surface-independent | None - pure core-enum cleanup, proceeds now |
| D3 (export/record-marker owner) | Surface-independent (the ownership decision itself) | None for the decision; the verifier's extended skill authoring will separately cite export/record-marker verbs once authored |
| D4 (rules reorg + negative gate) | Surface-independent | None - restructures existing rule files and sources the negative gate from manifest data already present |
| D5 (Tier-A closure principle) | Principle independent; enumeration surface-citing | `#7` obligation coverage - gates the concrete predicate/itinerary set, not the principle |
| D6 (per-modelo skill granularity) | Principle independent; authoring surface-citing | Track 1 generally, plus `#4` determinism substrate for each skill's golden-eval oracle |
| D7 (verifier isolation invariant) | Surface-independent (structural invariant, testable without the SDK) | None directly; its golden-eval proof benefits from `#4` determinism substrate landing |

**Pathways opened.** With the seven decisions settled, Phase 2 of the
completion roadmap (restructuring the surface-independent layers) can begin
immediately in parallel with Track 1, and Phase 5 (proving one vertical
Tier-B slice end-to-end) has an unambiguous target shape to build against
once Track 1 converges. The reconciliation confirms the accepted parent ADR
needs no amendment - only this one clarifying addition (D3) - keeping the
harness's decision trail linear rather than branching.

## Ratification

Ratified `proposed -> accepted` on 2026-07-02 by the driving agent on the basis
that every decision is implemented and gate-verified green at HEAD, so the ADR
now documents realised facts rather than proposals:

- **D1** (persona tool-boundary) - `is_tool_in_persona_scope`
  (`entrypoints/mcp/_persona_scope.py`) wired into `_server.py`
  `_call_tool`/`_list_tools`; family-granular by design (see D3 note).
- **D2** (`LIVE_READ` retired) - core-enum cleanup landed; the enum carries only
  `READ_ONLY` / `LOCAL_STATE_MUTATING`.
- **D3** (export/record-marker owner = verifier) - **accepted as documented
  persona-discipline, not gate-enforcement.** The persona-scope filter is
  family-granular (`modelo-preparer`/`verifier`/`reconciler` all resolve to
  `families={"modelo"}`), so the export-ownership boundary is a prose contract
  stated in both persona docs, not a runtime gate. This is the one owner-review
  judgment call: if per-verb gate-enforcement is later required, supersede this
  with a per-verb persona-scope ADR rather than amending here.
- **D4** (rules reorg + black-box negative gate) - 7 operator rules shipped; the
  negative drift gate refuses any operator doc that names a package internal.
- **D5** (Tier-A persona-entry closure) - 6 Tier-A itinerary skills shipped.
- **D6** (per-modelo skill granularity) - 17 Tier-B per-modelo skills shipped.
- **D7** (verifier/preparer context isolation invariant) - encoded and covered
  by the golden eval.

Verification at ratification: harness drift gate + golden eval `56 passed`;
operator-surface + json-schema + rule-surface conformance `115 passed`. The
parent `2026-06-30-agent-harness-adr` needs no amendment.
