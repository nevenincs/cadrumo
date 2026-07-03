---
tags:
  - '#research'
  - '#agent-harness'
date: '2026-07-01'
modified: '2026-07-01'
related: []
---

# `agent-harness` research: `harness elements design mapping`

Living design-research capture for the CONTENT design of the agent-harness
(the LLM operating layer over the deterministic `aeat` CLI). The accepted
2026-06-30 research and ADR settled the harness SHAPE (Q1-Q6: tool exposure,
artifact home, HITL tiers, faithfulness, eval substrate, naming); this document
captures the ongoing design of what actually goes inside each layer -
personality/personas, rules, and skills. It is appended to continuously and
feeds the binding research and ADRs authored later in the vaultspec pipeline.
Sources include the design owner's stream-of-consciousness input and the
collaborating thinking-agent design maps, both recorded here as a trail.

## Target capability (DAE-80) - what the harness must deliver

The harness exists so a non-expert user can ask a large language model to assist
them in filing their tax return, in natural language, and the agent:

- has the right knowledge context to look up ON DEMAND the required legal,
  branding, calculation, and regulatory references (never inventing them);
- reasons about the user's circumstances, stated requirements, and prior filing
  history;
- drives the deterministic CLI to produce a FILEABLE ARTEFACT (the export /
  fichero) that the user uploads themselves - live submission stays permanently
  forbidden.

End-to-end journey the harness must support (natural-language driven, each step
over `--format json`): onboard taxpayer -> establish AEAT read access ->
determine obligations -> build and groom the ledger -> classify and apportion ->
attach evidence -> prepare a modelo -> calculate -> verify and resolve findings
-> export and hand off -> record the filing marker -> reconcile against the
justificante. The agent orchestrates; the CLI computes; the human files.

## How the layers compose to deliver it

- The **manifest** (Layer 0) is the agent's live map of what the CLI can do; the
  agent's tool catalogue and the on-demand lookup index.
- **Rules** (Layer 1) are the always-on operating contract: safety invariants +
  where-to-look orientation + workflow ordering.
- **Personas** (Layer 2) are the roles that carry the journey: a coordinator that
  routes, plus task-scoped specialists (onboarding, ledger, classifier, preparer,
  verifier, filing / reconcile), each tool-scoped to its mutability tier.
- **Skills** (Layer 3) are the lazy-loaded playbooks the personas execute for each
  concrete workflow, pulling legal / calculation reference on demand via
  progressive disclosure.
- The **on-demand knowledge** requirement (legal / calc / branding references) is
  met by reading provenance (`legal_refs` / `source_refs`) off the CLI JSON and
  the manifest / legal surfaces - never by embedding a static knowledge dump (D2).

## Firm decisions (locked)

- **D1 - Black box / CLI-only.** The aeat package internals are a black box. The
  CLI (`aeat config` / `aeat app`, `--format json`) is the ONLY interface the
  agent harness may operate. The user and the operator agent are never exposed
  to any development, technical, or internal interface. Aligns with the
  two-root CLI boundary and the harness ADR (consume the contract, never reach
  past it). Candidate to codify as a rule once the harness lands.
- **D2 - Reference the manifest, do not hardcode internals.** Any "summary of
  what the backend does" inside a persona or rule must REFERENCE the live
  Layer-0 capability manifest (the `OperatorSurfaceContract`, exposed as
  `aeat app contract --format json`), not hardcode a snapshot of the backend.
  A hardcoded summary rots as the CLI changes; the `operator-harness-cites-live
  -cli-surface` rule co-commits any surface-citing artifact with the surface.

## Structure - the harness elements

The design owner frames the harness content as separable aspects; mapped onto
the ADR layers:

- **Agent personality / personas** (ADR Layer 2). A helpful agent equipped with
  the CLI tool, a rich context set, knowing where to find legal references, able
  to triage issues and fulfil + write requests. It is an abstraction /
  distillation of the toolset + rules + information - a summarised "what needs to
  be done" that also summarises what the backend can do (subject to D2).
- **Rules** (ADR Layer 1). Rules that orient the agent to WHERE INFORMATION IS
  and describe the tool's shape. Open interpretation resolved toward: rules
  orient over the CLI / manifest / legal-reference surfaces, NOT the Python
  package layout (D1). Any package-layout knowledge stays in this design doc for
  the builders and is never shipped to the operator agent.
- **Skills** (ADR Layer 3). Executable workflow playbooks. Organisation is an
  open question - three candidate axes below.

## Skills organisation - open question (three candidate axes)

1. **By tax category** - personal income, IVA, retenciones, etc.
2. **By modelo** - a skill for completing each modelo.
3. **By tax domain / taxpayer persona** - e.g. freelance autonomo, media /
   audiovisual worker, intra-community operator; roughly maps skills to
   real taxpayer personas.

A hybrid is plausible (per-modelo completion skills as the executable core,
composed by persona-oriented entry skills, with tax-category material as shared
progressive-disclosure fragments) - to be assessed by the skills design map.

## Open tensions

- **T1 - "rules describe the source packages" vs black box.** Resolved toward:
  rules describe the CLI/manifest SHAPE (command families, domains, where to look
  for legal refs), not Python internals. Confirm level with the design owner if
  it recurs.
- **T2 - personality as a distilled summary of "what is implemented".** Must
  reference the manifest (D2), not embed a rotting snapshot. The degree of
  distillation vs live reference is a core design question for the persona map.

## Design methodology (recommended approach)

- **Ground empirically before authoring.** Run the positive-inverse experiment
  (give an agent the JSON contract + knowledge, have it attempt one real
  workflow, observe where it stumbles even WITH knowledge) and mine the
  cli-persona-testimonials corpus, to build a failure taxonomy that grounds the
  rules/personas/skills rather than speculating them.
- **Slice-first, not matrix-first.** Design one vertical slice (one anchor
  modelo) deeply and prove it coheres before designing the full persona/skill
  matrix.
- **Split by surface-stability.** Design the surface-INDEPENDENT parts now
  (rule invariants, persona/scoping model, HITL policy, eval methodology);
  DEFER surface-citing artifacts (concrete skill playbooks, the MCP tool table)
  until the in-flight hardening briefs settle the CLI surface.
- **Lead with the assurance crux.** Hallucinated numerics are the load-bearing
  risk in regulated work; design the faithfulness hook + golden/determinism-replay
  eval early, in lockstep with the deterministic-output-replay-substrate work.

## Collaborating thinking-agent design maps

Three design-mapping agents were dispatched to map the shape of the harness
elements (persona layer, rules layer, skills organisation), each grounded in
the CLI surface, the accepted ADR, and decisions D1/D2. Their maps are appended
below as they complete.

Status: persona PENDING, rules DONE (below), skills PENDING.

### Grounding meta-finding - the harness is partly built at HEAD

The rules map surfaced that significant harness infrastructure already exists
and must be treated as the baseline (this is a restructure/completion, not
greenfield): the Layer-0 manifest builder (`build_operator_surface_manifest`);
four theme-clustered Layer-1 operator rule files shipped as wheel data under the
agent data tree and read via `aeat.agent.iter_operator_rules()`
(`operator-operating-rules`, `operator-envelope-reading`, `operator-grounding`,
`operator-safety-handoff`); a live drift gate (`test_rule_surface_conformance`)
that parses every backticked `aeat ...` span and envelope/notice field in those
rules and resolves them against the live manifest and the real `SchemaEnvelope` /
`Notice` models; and an end-user workspace materialiser (`aeat app agent`),
distinct from the dev `.claude/`. The dev rule `operator-harness-cites-live-cli
-surface` codifies the gate. Implication: the design owner's rule categories are
a RESTRUCTURE of an existing set, and the manifest/materialiser Layer-0 work is
further along than the plan implied.

### Operator rules layer map (Layer 1)

**Three orthogonal categories of operator rule** (the current four files each mix
all three; making the axes explicit is the restructure):

- **A - Behavioural / safety invariants** (the never/always contract): never
  compute/estimate/round/invent a value; relay JSON verbatim with `legal_refs` /
  `source_refs`; never fabricate a tool result; never submit live; local export
  is never official evidence; act on `warning` notices; verified-complete + zero
  findings on positive income is suspect; resolve revision by law; respect
  mutability (never auto-`--yes`); sensitive data stays in the encrypted bucket.
  Value/provenance-shaped, name no verbs - the most black-box-safe category.
- **B - Orientation / "where to look"** (the routing table): maps an operator
  question to the command / manifest section / legal surface that answers it
  (catalogue -> `aeat app contract`; what's due -> `overview`; casilla value +
  basis -> `modelo work calculate`; did it land -> `reconcile pull`; how to read
  the outcome -> envelope `status` / `notices` / `error.suggestion`; the exit-code
  table). Most exposed to CLI drift; MUST be manifest-derived.
- **C - Workflow-ordering** (the lifecycle): `CALCULATE -> VERIFY -> FILE` and the
  broader happy path, as an INVARIANT (never verify before calculate; never
  export before a clean verify; never claim filed/reconciled before a human
  files). Currently expressed only in skills + the manifest lifecycle contract -
  NO Layer-1 rule states the ordering. Clearest structural gap.

**Recommended restructure (Option 3, hybrid):** keep the behavioural files
theme-clustered (A reads well by theme); extract orientation into one
manifest-derived `operator-orientation-routing` rule + the stable
`operator-envelope-reading` rule (B); add one `operator-lifecycle-ordering` rule
(C); optionally split an `operator-honest-declaration` invariant out of the
grounding/safety files (promotes `no-silent-under-declaration` to first-class).
Net ~4 -> ~7 files, each dominated by one axis, so drift blast-radius per rename
is one file.

**Keeping orientation black-box-safe (the mechanism):** the existing gate is a
POSITIVE gate (a rule may only name a verb/field the manifest exposes; a rename
reddens it). The gap is no NEGATIVE gate - nothing forbids naming an internal
(`aeat.<pkg>...`, a `src/aeat/...` path, a private/`_` module, a `test_*` name).
Recommendation: add a negative conformance assertion so "orient over the CLI /
manifest / legal surface, never the package layout" is mechanically enforced.
Consider two-tier orientation by volatility (stable envelope-shape prose vs
drift-prone command routing table), and possibly GENERATING the routing table's
verb column from the manifest `operator_question` field so zero verb strings are
hand-maintained.

**Operator vs dev/vaultspec rules - keep separate, never merge:** different
audience (agent USING the tool vs engineer BUILDING it), home (`_data/agent/`
materialised to an end-user workspace vs `.claude/` synced by vaultspec),
surface-it-may-name (CLI/manifest/legal only vs the whole package), and
enforcement (drift gate + golden eval vs vaultspec/AST/full-tree gates). The
operator rules are the positive re-cast of specific dev safety rules
(`aeat-calculation-grounding`, `aeat-safety-legal-gates`,
`local-filed-observations-are-non-official-evidence`, `no-silent-under-declaration`,
`revision-resolution-is-law-determined`, `cli-notices-are-the-only-diagnostic-channel`,
`aeat-architecture-boundaries`, `sensitive-financial-data-secure-storage-only`).
The dev rule `operator-harness-cites-live-cli-surface` is the BRIDGE and stays
dev-side.

**Open questions (rules):** reorg vs internal tagging; generate the routing verb
column from the manifest; the exact negative-gate regex boundary (must not read
the manifest's own `service_owner` internal names into a rule); whether
lifecycle-ordering is a Layer-1 rule sourcing step names from the manifest
`LifecycleContract`; whether honest-declaration is its own rule; persona->rule
binding by-reference vs by-inclusion; whether a verb surfaces the legal catalogue
for a casilla or provenance is only ever inline on the calculate payload.

### Persona / personality layer map (Layer 2)

**Already built:** seven personas ship under `src/aeat/_data/agent/personas/`
(`coordinator`, `onboarding`, `ledger-groomer`, `classifier`, `modelo-preparer`,
`verifier`, `reconciler`), covered by the same drift gate. Mutability vocabulary
is the closed `OperatorMutability` enum (`READ_ONLY`, `LOCAL_STATE_MUTATING`,
`LIVE_READ`); each command family carries one tier.

**Recommended roster + boundary form:** keep the seven roles. Express each
persona's tool boundary in the manifest's OWN vocabulary - the family `child`
token + the `OperatorMutability` ceiling ("`modelo` family, up to
`LOCAL_STATE_MUTATING`, never `LIVE_READ`") - not a hand-copied verb list. The
coordinator is READ_ONLY + delegation and issues no mutating verb directly; every
mutation flows through the role that owns that family's tier. The
verifier/preparer context split is a roster invariant (independent dispatch, no
shared preparer context), not a suggestion.

**The central drift question (T2), resolved:** a persona carries durable role
identity + boundary-in-manifest-vocabulary + a POINTER to read
`aeat app contract --format json` at session start - never an inline snapshot of
backend capability (that rots under the black box). The few verbs a persona names
for readability are safe only because the drift gate fails the build when one
orphans. The MACHINE-ENFORCED per-persona tool allowlist (the MCP `PreToolUse`
gate) should be GENERATED from the contract's `(family, mutability)` records at
build time, so the enforced boundary cannot diverge from the prose. Pattern:
author prose as pointer+scope; generate the enforced allowlist.

**No duplication across layers:** a persona REFERENCES rules (never restates an
invariant) and DISPATCHES/EXECUTES skills (never inlines a command sequence); it
carries only role identity, the manifest-scoped boundary, and pointers. Naming:
personas use English generic role nouns (coordinator, verifier); skills use
Spanish domain stems (`preparar-modelo-130`, `reconciliar`).

**Key persona open questions:** (1) enforced allowlist = build-time codegen from
the contract vs runtime read; (2) the `live` family is annotated
`LOCAL_STATE_MUTATING` while `LIVE_READ` is declared-but-unused - resolve the
taxonomy so personas can state "live is read-only observation, never write";
(3) how the verifier/preparer isolation degrades when running over raw
`--format json` with no SDK (prose-only vs hard-isolated); (4) coordinator =
dispatched subagent vs top-level session identity, and persona-owns-routing vs
coordinator-owns-routing for skill selection; (5) keep ONE parameterised
`modelo-preparer` and push per-form detail into skills, rather than per-modelo
preparers; (6) EXPORT/handoff persona ownership is currently unassigned (preparer
"does not export", reconciler acts "after the human files") - the irreversible
faithfulness hard-block boundary has no owner; (7) mandate a per-session manifest
read as a precondition.

### Skills organisation map (Layer 3)

**Grounding:** the executable core is ~20 registry-modelled forms (a typical
taxpayer touches 4-8), not the full `Modelo` enum. Three real typed axes already
exist: `domain` per modelo (iva/irpf/is/censo/informative/cross_tax/irnr/...),
IVA classification (R01-R30 -> 15 `IvaCategory`), IRPF `SpendingCategory` (~40
leaves). The 28 how-to guides are organised by WORKFLOW STAGE (the
`CALCULATE -> VERIFY -> FILE` spine), not by modelo or category - a fourth,
implicit axis the three proposed axes omit and the project already uses.

**Axis analysis:** by-tax-category = best REFERENCE unit but a bad executable unit
(a category's "procedure" is really N modelo procedures; high lifecycle
duplication). By-modelo = best EXECUTABLE/testable/co-commit unit (1:1 with the
command sequence, one golden-eval scenario, contained co-commit blast radius) but
~20 skills sharing ~80% spine, and not how a user thinks. By-persona = best ENTRY
unit (matches how a user arrives) but open-ended/subjective/unbacked and, if used
as the executable layer, the worst duplication.

**Recommendation - three-tier HYBRID with the workflow spine as shared backbone:**
- **Tier A - persona ENTRY skills** (thin, routing-only): a small bounded set of
  obligation-itinerary skills keyed to profile facts (`autonomo-estimacion
  -directa`, `autonomo-modulos`, `intra-community-operator`, `retenedor
  -empleador`, `pyme-sociedad`, `arrendador`). Each calls `overview explain` /
  `agenda` to DERIVE which modelos apply (never hard-codes them), sequences by
  cadence + cross-form carry, and delegates each filing to Tier B. Cites only
  stable orchestration verbs - low co-commit churn.
- **Tier B - per-modelo COMPLETION skills** (the executable core): one playbook
  per registry-modelled form over the invariant spine (`work create -> calculate
  -> verify -> revision review -> export -> record marker -> reconcile`), with a
  per-form `reference/` fragment (casillas, bindings, period tokens, prior-period
  carries, verification predicates). The golden-eval unit and the co-commit unit.
  Author the spine ONCE as a shared lifecycle fragment; each per-modelo skill
  carries only its form-specific delta. Start with ONE slice (130 or 303); defer
  the rest's casilla-level reference until the surface settles.
- **Tier C - tax-category + workflow REFERENCE fragments** (shared progressive
  -disclosure library): the IVA R01-R30 decision table, the SpendingCategory
  families, exemption articles, the classify/allocate/prorrata procedure, the
  import/dedup/evidence procedure, the auth/censo procedure - authored once,
  pulled on demand. Where category material belongs (as knowledge, not a
  top-level skill), and where the cross-cutting non-modelo stages live.

**Key skill open questions:** the spine as a first-class skill vs a reference
fragment; how the Tier-A persona set is bounded (pin each to a profile-fact
predicate so personas are DERIVED not enumerated); per-form vs per-form-FAMILY
granularity for near-identical pairs (130/131, 111/115/123, 180/190/193,
303/390); long-tail coverage policy (210/714/720/349/369); classification in
Tier B vs Tier C (-> Tier C); where cross-form carry orchestration lives (Tier-A
itinerary vs Tier-B precondition); one golden-eval per Tier-B skill + composed
evals for Tier-A itineraries; the co-commit seam per tier.

## Consolidated concrete proposals (DAE-80)

Synthesised from the three design maps. Ideation only - the ADR ratifies; no code
here.

**P0 - Reframe: this is restructure/completion, not greenfield.** The first cut
has landed (manifest builder, 4 rules, 7 personas, >=1 skill, drift gate,
workspace materialiser). Every proposal below rationalises or completes an
existing artifact. The design phase's job is to ratify the taxonomy, close the
structural gaps, and decide the enforced-boundary mechanism - not to invent the
layers.

**P1 - Rules (Layer 1): 3 explicit categories, ~4->~7 files, + a negative gate.**
Keep behavioural invariants theme-clustered (Category A); extract orientation into
one manifest-derived `operator-orientation-routing` rule + the stable
`operator-envelope-reading` (Category B); ADD `operator-lifecycle-ordering`
(Category C - the missing `CALCULATE->VERIFY->FILE` invariant); optionally split
`operator-honest-declaration` (promote `no-silent-under-declaration`). Complete
the enforcement with a NEGATIVE gate that fails any operator rule naming an
internal (`aeat.<pkg>`, `src/aeat/...`, `_private`, `test_*`) so black-box is
mechanical. Consider generating the routing table's verb column from the manifest
`operator_question` field.

**P2 - Personas (Layer 2): keep 7 roles, boundary in manifest vocabulary,
generate the enforced allowlist.** Author personas as role identity + boundary
(family child + mutability tier) + manifest pointer; never snapshot capability.
Generate the machine-enforced per-persona tool allowlist from the contract's
`(family, mutability)` records so prose and enforcement can't drift. Close the
EXPORT/handoff persona-ownership gap. Resolve the `live` mutability taxonomy
(`LIVE_READ` declared-but-unused).

**P3 - Skills (Layer 3): three-tier hybrid.** Persona entry skills (thin,
profile-derived itineraries) over per-modelo completion skills (the executable,
co-committed, golden-eval core) over a shared category+spine reference library.
Author the lifecycle spine once; defer per-form casilla reference behind the
hardening surface; prove one slice first.

**P4 - Cross-cutting invariant to ratify:** each layer has one job and references
the others - rules state invariants, personas carry role+scope+pointers, skills
execute procedures, the manifest is the single capability source. No layer
snapshots another; the drift gate (positive) + a new negative gate keep every
citation black-box-safe and live.

**The load-bearing decisions the ADR must settle:** (1) enforced per-persona
boundary = build-time codegen from the contract vs runtime manifest read; (2) the
`live`/`LIVE_READ` mutability taxonomy; (3) who owns the irreversible export/
record-marker faithfulness hard-block; (4) rules reorg (Option 3) vs internal
tagging, and the negative-gate regex boundary; (5) the Tier-A persona-set closure
rule (profile-fact predicates, derived not enumerated); (6) per-form vs
per-form-family skill granularity; (7) how verifier/preparer isolation degrades
without the SDK.

## Completion sequence (roadmap to drive all work to done)

Two concurrent tracks converge. **Track 1 - backend hardening** (already in
flight): custody + the eight gap briefs (#1 manifest completeness, #2 ledger-add
idempotency, #3 modelo verify guards, #4 determinism substrate, #6 review
actionability, #7 obligation coverage, #8 reconcile depth, #9 fichero parity).
**Track 2 - harness design->build** (this document). Surface-INDEPENDENT harness
work runs in parallel with Track 1; surface-CITING work is gated on Track 1
landing.

- **Phase 0 - Ground empirically + close design research (NOW).** Run the
  positive-inverse experiment on one anchor modelo + mine the persona-testimonial
  corpus -> a failure taxonomy; consolidate the three maps + taxonomy into the
  binding research. Surface-independent; do now. Turn the 7 load-bearing
  decisions into the ADR agenda.
- **Phase 1 - Ratify via ADR(s).** One cohesive harness-content ADR (or three:
  rules / personas / skills) settling the 7 decisions. Gate: owner approval.
- **Phase 2 - Restructure the surface-independent layers** (parallel with Track
  1): rules A/B/C reorg + `operator-lifecycle-ordering` + `operator-honest
  -declaration` + the negative gate; persona boundaries in manifest vocabulary +
  generated per-persona allowlist + export/handoff owner + `live`/`LIVE_READ`
  taxonomy fix. Prereq: #1 manifest completeness (Track 1).
- **Phase 3 - Converge: Track 1 lands.** The eight briefs + custody complete;
  this is the gate for all surface-citing harness work. Watch the critical
  prereqs: #1 (manifest -> rules/personas), #4 (determinism -> eval).
- **Phase 4 - Build the assurance spine.** Faithfulness hook + golden/
  determinism-replay eval with AEAT-worked-example oracles, in lockstep with #4.
  The regulated-work crux; must exist before the agent is trusted.
- **Phase 5 - Prove the vertical slice.** Author the anchor modelo's Tier-B
  completion skill + the shared lifecycle spine + the Tier-C fragments it needs,
  over raw `--format json`; run the golden eval end-to-end. Gate: the slice
  passes with provenance intact. Depends on Phase 2 + Phase 4 + the anchor
  modelo's surface being settled.
- **Phase 6 - MCP server + HITL.** `aeat-mcp` server sourcing schemas + mutability
  from the manifest; `PreToolUse` HITL tiers (the generated per-persona allowlist);
  `PostToolUse` faithfulness (advisory, hard-block at the export/marker boundary).
- **Phase 7 - Generalize the matrix.** Remaining Tier-B per-modelo skills (each as
  its surface settles), Tier-A persona entry skills, the Tier-C reference library;
  one golden scenario per skill; bind golden + replay as a standing harness-change
  gate.
- **Phase 8 - Close.** Full harness eval green; fresh-context honesty review
  (`aeat-campaign-close-honesty-review`); codify durable lessons (D1 black-box,
  layer-separation invariant) as rules; user docs.

Critical path: 0 -> 1 -> (2 || Track 1) -> 4 -> 5 -> 6 -> 7 -> 8. Track 1 runs
concurrently and must be done before Phase 5 (anchor modelo) and Phase 7 (full
matrix). Each phase is a vaultspec pipeline pass (research/ADR -> plan -> execute
-> verify), not a single commit.

## Empirical failure taxonomy (Phase 0 grounding)

From mining the persona-testimonial lineage. Categories 1-6 have concrete
AEAT-specific reproductions (repurposable as golden scenarios); categories 7-9
have NO AEAT persona evidence and rest on external-literature + design reasoning
(they need NEW golden scenarios) - an asymmetry the ADR must name.

1. **Missed under-declaration (highest severity).** M200 140k-profit -> zero tax,
   verify returned verified_complete + 0 findings (manual base casilla, no
   formula). Justifies a golden-eval class asserting advisories FIRE. Already
   codified in operator-grounding / safety-handoff + no-silent-under-declaration.
2. **Obligation under/over-scoping.** Landlord told M130 applies (he has no
   economic activity); Renta annual window absent from every calendar.
   Corroborates the in-flight #7 obligation-coverage brief. The operator must not
   read "the tool did not mention X" as "X does not apply".
3. **Dropped provenance.** A real M130 calculate returned correct values but no
   `legal_refs` / formula_ids at the CLI layer (graded Major). The CLI itself can
   omit provenance -> the rule alone is insufficient; needs the Q4 faithfulness
   hook.
4. **Wrong lifecycle sequencing / cross-surface contradiction.** `work create`
   accepted an out-of-window period silently; `modelo readiness: True` vs verify
   `NO_PENDING_OBLIGATION` (4 reporters). A lifecycle skill must reconcile
   readiness against deadline / calendar and treat disagreement as
   stop-and-report, not retry-past.
5. **Auth / profile / state confusion.** Self-referential recovery deadlock;
   wrong active profile silently shows another taxpayer's data; shallow
   `auth test` / `auth status`. Onboarding persona needs "confirm active profile
   before every mutating sequence".
6. **Wrong tool / grammar choice.** `--help` vs runtime flag mismatch (retention
   vs retencion); BOE numbers rejected where dot-path ids are required;
   period-token hints disagree across surfaces. The evidence base for WHY the
   Layer-0 manifest (real accepted values, not `--help` prose) is the right fix.
7. **Exit-code / status misread as crash** - LLM-operator-specific; no persona
   repro; codified in operator-envelope-reading; needs a purpose-built golden.
8. **HITL / confirmation bypass** - an autonomous agent optimising for completion
   may pass `--yes`; no persona repro (humans had no reason to); justifies the Q3
   defense-in-depth.
9. **Hallucinated casilla / number** - documented financial-MCP failure mode; no
   AEAT repro; the reason operator-operating-rules leads with "never invent a
   value" plus the Q4 faithfulness backstop.

**ADR-grounding implication:** categories 1-6 seed golden scenarios directly from
existing repros; 7-9 require net-new scenarios and must be flagged as
design-reasoned, not testimonial-proven - the eval plan should PRIORITISE 7-9
because no repro can be repurposed.

## ADR decision agenda (Phase 1) - recommended resolutions

Structure: ONE cohesive harness-content ADR (the three layers are
cross-referential at HEAD; splitting forces forward-references). Further HEAD
discovery: the MCP server + HITL scaffolding already exist
(`entrypoints/mcp/_server.py`, `_hitl.py` with a GLOBAL verb-shaped confirmation
policy, not yet persona-scoped), and an `exportar-declaracion` skill exists but
no persona owns it.

Recommended resolutions (for owner ratification):

- **D1 persona boundary:** runtime manifest read filtered by active persona, with
  a build-time-verified TEST pinning each persona to its (family, mutability)
  ceiling - codegen the ASSERTION, not a second allowlist artifact (avoids a new
  drift surface; matches aeat-registry-authority-flow).
- **D2 live/LIVE_READ:** retire the unused `LIVE_READ` member; `live` =
  LOCAL_STATE_MUTATING is CORRECT (a pull writes derived local state - censo
  snapshot, participation index). Track-1-adjacent enum cleanup with a
  zero-consumer check (retired-enum-members rule).
- **D3 export owner:** extend the VERIFIER to own export/record-marker - the same
  independent actor that found the work clean produces the irreversible artefact
  (no rationalisation reintroduced, unlike folding export into the preparer).
  Alternative flagged: a distinct `exportador` (Spanish-stem) role for audit
  separation. This clarifies an underspecified roster boundary in the accepted
  ADR (an addition, not a reversal).
- **D4 rules reorg:** Option 3 hybrid; ADD `operator-lifecycle-ordering`
  (confirmed the CALCULATE->VERIFY->FILE order lives ONLY in coordinator.md prose
  today - a real undeclared-invariant gap). The negative gate sources its
  blocklist from the manifest's own `service_owner` STRING VALUES (not a hand
  regex), so a new backend module cannot leak into rule prose and legit
  CLI-domain nouns (ledger, modelo) are not false-positived.
- **D5 Tier-A closure:** ratify the PRINCIPLE now - each entry skill gated on an
  explicit TaxpayerProfile fact predicate (derived, not enumerated; mirrors
  cross-period-suppression-grounded-in-registry-classification). Enumerate the set
  in Phase 7 after #7 obligation-coverage settles.
- **D6 skill granularity:** strict per-modelo (one skill = one modelo = one
  golden-eval unit = one co-commit unit); author sibling forms (131 vs 130) by
  DIFF, and the CALCULATE->VERIFY->FILE spine ONCE as a shared fragment so
  per-modelo skills carry only form-specific deltas.
- **D7 verifier isolation:** state the invariant testable + runtime-agnostic -
  "the verifier's context MUST be constructible from tool-result JSON alone, never
  from the preparer's transcript"; enforce structurally (separate invocation
  seeded only by work-unit id + revision JSON) even without the SDK;
  degraded-trust self-report only if a runtime truly cannot isolate.

**Reconciliation for the ADR:** (1) D3 is a clarification/addition to the accepted
ADR's roster, not an amendment; (2) D2 touches the `OperatorMutability` core enum
- confirm zero consumers per retired-enum-members before deletion.

**Surface split:** independent now (D2, D4, and the principles of D3/D6/D7);
gated on Track 1 (D1 weakly on manifest; D5 on #7; D6-authoring on per-form
surfaces).

## HEAD re-baseline - the harness is ~80% built

Four independent Sonnet-5 grounding passes (rules map, persona map, skills map,
eval catalogue) converge on one conclusion: the DAE-80 harness is FAR more
complete than the roadmap assumed. What exists at HEAD: the Layer-0 manifest
builder + `aeat app contract`; four Layer-1 operator rule files + a live positive
drift gate; seven Layer-2 personas; Layer-3 skills incl. `exportar-declaracion`;
the MCP server + `PreToolUse`/HITL + a faithfulness check (all with unit tests);
the `aeat app agent` workspace materialiser; and a golden-eval subsystem
(`src/aeat/agent/eval/`) with GoldenScenario/GoldenResult models, a runner,
determinism-replay, two passing scenarios (M130, M303) with anti-tautology
proofs, an M130 AEAT numeric value-oracle, and an M100 live-oracle-replay corpus.

The TRUE remaining epic is therefore targeted gap-closure, not a build:
(1) the 7 ADR restructure decisions; (2) the eval-wiring gaps below; (3) the
Track-1 dependencies (#1 manifest, #4 determinism, #7 obligations).

## Golden-eval catalogue (P4 build spec)

The eval substrate exists but has specific integration gaps. Key finding: the
runner today statically inspects trajectory strings + the registry snapshot; it
does NOT dispatch a live CLI call to inspect the JSON RESPONSE payload, and the
faithfulness/HITL pure functions are unit-tested but NOT wired into an
end-to-end golden run.

Per-category status (1-6 repurposable from persona repros; 7-9 net-new, priority):

1. **Under-declaration** - structural assertion: verify MUST NOT return
   verified_complete+0-findings on positive input/zero base (M200 140k repro).
   Needs a new GoldenScenario finding-severity field + a first `modelo_200.toml`.
2. **Obligation under/over-scoping** - narration-level: operator must not read
   "tool didn't mention X" as "X not applicable". Gated on Track-1 #7.
3. **Dropped provenance** - extend the runner to dispatch a real
   `modelo.work.calculate` and assert legal_refs/source_refs on the RESPONSE
   payload (not just the registry). Highest-value near-term close.
4. **Lifecycle / cross-surface contradiction** - readiness:True vs verify
   NO_PENDING_OBLIGATION -> stop-and-report; needs a must-halt scenario shape.
5. **Auth/profile confusion** - require an active-profile confirm before the
   first mutating verb (expressible with the current model).
6. **Wrong tool/grammar** - instructive-refusal-then-corrected-retry; needs a
   recovery-trajectory field. Largely a Layer-0/Track-1 concern.
7. **Exit-code misread as crash** (NET-NEW, HIGH) - exit 1 = verdict; assert
   well-formed JSON + a continuation verb, not an abort. New ExitCodeScenario.
8. **HITL bypass** (NET-NEW) - wire confirmation_for_tool into a golden run so a
   CONFIRM-tier step is not auto-approved even with an auto-yes flag.
9. **Hallucinated number** (NET-NEW, HIGH) - wire faithfulness_check against a
   REAL captured calculate JSON: advisory off-handoff, hard-block at export; the
   grounded counter-case quotes the M130 oracle figure (1.600,00) to avoid
   false positives.

**Minimal first slice (against the existing M130 anchor):** (3) response-payload
provenance -> (9) faithfulness wired end-to-end -> (7) exit-code-as-verdict ->
(1) under-declaration advisory (needs new M200 scenario) -> (8) HITL wired on the
existing export step. Categories 2/4/5/6 follow Track 1 (#7, #1).

**Determinism-replay pinning (lockstep with #4):** filing year/period explicit;
revision via select_revision (law-determined, never injected); work_unit_id
scenario-declared or excluded from byte-identical compare; oracle Decimals are
the scenario's own fixture data; faithfulness/HITL deterministic by construction.
