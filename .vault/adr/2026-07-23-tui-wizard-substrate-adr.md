---
tags:
  - '#adr'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:566e3945ba5337550fe1ffdd5752e953e8b33f17001fe0e73bdbf3f30b017b3f'
related:
  - "[[2026-07-23-tui-wizard-substrate-research]]"
---

# `tui-wizard-substrate` adr: `paged TUI wizard substrate` | (**status:** `accepted`)

## Problem Statement

The interactive setup experience is a line-by-line, forward-only,
single-pass walk with no back-navigation, no review, no reset, no restart,
and no checkpoint; per-question understanding aids (grounding help, accepted
values, format hints, failure modes, live validation) have no descriptor
slots or rendering surface (`2026-07-23-tui-wizard-substrate-research`). The
operator has mandated a rich paged TUI where every question is a full page
and the flow is fully navigable, reviewable, and resumable. A second stream
(`profile-setup-flow`) will build the profile-setup flow on whatever
substrate this record defines, and future application flows (modelo work,
reconciliation walkthroughs) are expected to compose on the same substrate —
so the substrate's architecture and public contract must be decided now,
explicitly and once.

## Considerations

- The one-shot `Prompter` architecture is a structural ceiling: paging,
  back-navigation, jump, and review need a screen-owning event loop, not a
  sequence of independent prompts (research, "one-shot and line-oriented").
- A third drifted prompter copy once shipped; single-canonical-authority for
  flow semantics is a hard requirement, not a preference
  (`aeat-rag-discovery-mandatory` narrative; research).
- The non-interactive flag path, the headless test drive, and the future TUI
  must share one branching/validation authority or they drift
  (disconnected-surface class; cf. `one-aggregation-path-pull-equals-calculate`).
- Hexagonal boundaries: flow semantics belong in the application layer; the
  CLI and any TUI framework are adapters. Typed pydantic v2 models
  throughout; closed sets as StrEnum in `core/`
  (`aeat-architecture-boundaries`).
- In-progress answers contain NIF/NIE and family/financial facts; any
  checkpoint is sensitive data
  (`sensitive-financial-data-secure-storage-only`; research, "Checkpoint
  state is sensitive data").
- Windows console degradation (`NoConsoleScreenBufferError` class) is an
  existing, handled reality that the substrate must keep handling (research).
- The substrate is generic computing vocabulary — English naming is correct;
  domain flows layered on it use Spanish stems where they touch AEAT
  concepts (`aeat-spanish-stem-naming`).
- The existing descriptor discipline (frozen declarative flow records,
  canonical-token answer plane, i18n-key validators, redacted diagnostics,
  create-vs-edit patch split) is load-bearing and must carry forward
  (research, "What the current stack does well").
- Localized contract/help/hint/description copy already ships in the
  codebase and must be resolved at render time, never hardcoded or
  invented (operator directive, 2026-07-23). The grounding map narrowed
  the *supported* sources: the schema↔locale leg is real and
  gate-enforced (schema field definitions + the four locale catalogues),
  but no site assembles wizard question copy from the BOE/AEAT legal
  corpus — that corpus grounds registry calculation `legal_refs`, not
  question text (research, "Reconciliation against the
  profile-integration grounding map").

## Considered options

1. **Frontend-owned flow** — build the wizard directly as a TUI application;
   screens own the logic. Rejected: welds flow semantics to one rendering
   library, forces the non-interactive and test paths to re-implement
   branching/validation (drift class), and puts application logic in an
   adapter.
2. **Incremental extension of the one-shot prompter** — add back/review as
   special prompt answers (e.g. typing `:back`). Rejected: cannot deliver
   full-page rendering, live validation, jump, or review; grows a
   pseudo-command-language inside answers; the ceiling is architectural.
3. **Renderer-agnostic flow engine + thin frontends** (chosen) — a pure
   state machine in the application layer owns all flow semantics; the
   full-screen TUI, the plain line-mode fallback, and the non-interactive
   driver are thin projections dispatching typed intents.

For the rendering layer of the full-screen frontend: **Textual**
(application framework, headless test driver; new dependency),
**prompt_toolkit full-screen** (already a transitive dependency; layout and
widget layer hand-built), **urwid** (weaker Windows story), **Rich alone**
(no input/event loop; insufficient). Chosen: Textual, on the dependency
verdict and application-model comparison (research, "Dependency verdict
for the rendering candidates"); ruling in D5.

## Constraints

- The rendering library (D5) introduces one new direct dependency
  (`textual`, MIT, verified conflict-free against the existing
  rich/questionary/prompt_toolkit pins). The engine architecture (D1–D4)
  is deliberately insulated from the rendering layer: no engine or
  contract type may import from the rendering library, so a rendering
  pivot stays an adapter swap. Textual's Windows-terminal behaviour under
  degraded hosts (conhost, git-bash) was not exhaustively surveyed; the
  line-mode fallback and translated refusal are the safety net.
- A `create` flow's cold start precedes a usable profile; under the D4
  incremental-facts model the profile is registered early through the
  lifecycle authority in an explicitly setup-incomplete state, so the
  readiness gates — not storage location — are what keep it non-usable
  until review-submit completes it.
- The substrate must keep the translated non-TTY/no-console refusal and the
  IO-injection headless-drive contract working; a host that cannot run the
  full-screen frontend degrades to the line-mode frontend, and a host that
  can run neither receives the existing translated refusal.
- Grounding combines full-file reads of the entire wizard package with the
  profile-integration discovery audit. The single-flow-authority claim is
  keyword-confirmed; a `vaultspec-rag` semantic sweep per coding site (per
  the RAG-discovery rule) remains the guard against a
  same-concept-different-name site the keyword pass could miss.

## Implementation

The decision is five rulings, D1–D5.

**D1 — Renderer-agnostic FlowEngine, the single flow authority.** A pure
state machine in the application layer (substrate package under
`src/cadrumo/application/`, e.g. `application/flows/`) owns all flow
semantics. Its state is an immutable, strict pydantic v2 `FlowState`:
canonical-token answer map, cursor (current page id), visit history,
per-question validation results, and staleness marks. It exposes typed
transitions — `answer(page_id, raw)`, `next()`, `back()`, `jump(page_id)`,
`reset(page_id)`, `restart()`, `checkpoint()` — each returning a new
`FlowState`. Visibility/branching is recomputed from the answer map on
every transition. Exactly one engine ships; frontends contain zero flow
logic. The existing `run_flow` forward-only walk and the `Prompter`-driven
interaction model are absorbed and retired with their consumers moved to
the engine (`no-legacy-compatibility`: no bridge, no parallel authority).
The scripted `CanonicalAnswerPrompter` role becomes a scripted intent
driver over the same engine, preserving underflow/overflow drift detection.

**D2 — Full-page question model.** The flow descriptor generalises the
existing frozen records: each question page declares, beyond the current
id/widget/prompt/choices/required/default/visibility, three new descriptor
slots — grounding help prose, format/structure hint, and failure-mode
descriptions. Every copy slot is a *reference*, never a literal string: an
i18n key under the established `wizard.<flow-id>.` prefix discipline, or a
typed reference into the sources that actually serve wizard copy today —
the profile/modelo schema definitions and the four locale catalogues
under `_data` (plus approved terminology concepts where a glossary entry
exists). The substrate is a **dynamic copy assembler**: at render time it
resolves each reference against those existing sources and composes the
page; it carries no prose of its own and invents none — schema-derived
facts (accepted values, casilla labels, per-choice descriptions) are
pulled from the schema/locale authority they already live in, so page
copy can never drift from the bundled contract text. The BOE/AEAT legal
corpus is explicitly NOT a v1 copy source: no mechanism assembles
question text from it today, so a per-question corpus-excerpt reference
type would be new design — deliberately out of scope here, and if wanted
later it must arrive with its own legal-grounding discipline, not as an
assumed capability. The page renders fixed zones:
header (flow title, section and step position, progress), body (prompt,
help, required/optional badge, format hint, input widget — closed sets
render as selectable choice lists with per-choice descriptions, never free
text — live validation line, current-answer echo when revisiting), footer
(key bindings). Validation is three-tier: non-blocking keystroke-level
format feedback; blocking commit-time field validation (the existing
widget validators, retained, with their i18n message keys and redacted
diagnostics); and cross-field validation declared at either **section
scope** (run when the operator leaves the section, blocking forward
navigation with a typed, rendered result) or **flow scope** (run at the
review surface). Widget kinds remain a closed StrEnum in `core/`; the set
grows by two substrate-generic kinds: a **repeating group** — a sub-page
group instantiated N times (count driven by an earlier answer or by
add/remove from the review surface), whose instances key the answer map
with an instance index and participate individually in staleness and
review — and a **compare-select** page kind presenting N labelled
candidate values (each carrying a provenance/description reference) plus
an explicit defer option; choosing defer marks the question *deferred*, a
distinct review status that never silently resolves. Candidate labels and
provenance are domain-supplied references; the substrate knows nothing of
what is being compared.

**D3 — Navigation, review, staleness.** `next`/`back` move over the
currently-visible page sequence. Changing an earlier answer whose value
gates later questions marks dependent answers **stale** — never silently
deletes them. A review/summary surface lists every section and question
with status (answered / optional-skipped / invalid / stale) and supports
jump-to-page; it is reachable at any time. Completion (handing the typed
answers model to the domain flow's persistence hook) is possible only from
review and only when every required visible question is valid and no
staleness remains. `reset(page_id)` restores one question to its default;
`restart()` clears the whole `FlowState` behind an explicit confirmation.

**D4 — Checkpoint = incremental facts through the domain's existing
encrypted persistence authority; no bespoke store.** Grounded against
discovered reality (research, "Reconciliation against the
profile-integration grounding map"): no canonical partial-state
checkpoint object exists today, and inventing one would add a second
persistence surface beside the one that already works. The ruling is
therefore the *incremental-facts* model, not a separate draft store:

- The substrate defines a **checkpoint port** (save/load/discard over the
  canonical answer map); the domain flow supplies the implementation, and
  every implementation MUST route through the owning domain's existing
  encrypted persistence authority. For profile setup that is
  effective-dated `UserProfileFact` writes via `ProfileLifecycleService`
  (`set_active_fields` path — already encrypted, already event-emitting,
  already existing) — never a direct `UserProfileRecord`/`BucketManifest`
  write, never a new store, never flow-owned crypto (a flow-run
  encryption layer would be a second, parallel crypto authority).
- **The facts are the checkpoint.** Substrate-level state that is not a
  domain fact (cursor, visit history, staleness/deferred marks) is
  derived and ephemeral: resume projects the persisted facts back into
  canonical answers, recomputes visibility and validation from the
  *current* flow definition, and places the cursor at the first
  unanswered visible question. Re-validation on resume is thereby
  inherent — a fact that no longer validates or no longer fits the
  definition lands stale in review; a checkpoint is never blindly
  rehydrated and never blocks with an opaque failure. No definition
  fingerprint needs storing.
- **Partial state is never promoted.** Incomplete fact sets MUST NOT be
  passed through the full-model constructor
  (`taxpayer_profile_from_mapping`) whose cross-field legal validators
  (impatriado start date, non-resident country, representante fiscal)
  assume a complete profile, and those validators MUST NOT be relaxed to
  accommodate incremental entry. The existing readiness gates
  (`build_wizard_status`, the modelo-work readiness gate) remain what
  keeps a mid-setup profile non-usable downstream; the substrate's
  submit-from-review gate (D3) is when the domain flow may first treat
  the fact set as complete.
- For a `create` cold start the profile is registered early through the
  lifecycle authority in an explicitly setup-incomplete state so
  incremental fact writes have a home; cross-profile tax-id uniqueness is
  still enforced at the point the profile is minted. On launch with an
  in-progress setup the frontend offers resume-or-discard; discard erases
  through the same lifecycle authority. Checkpoint diagnostics carry
  counts, never answer values.
- **Checkpoint lifecycle ownership.** Save is frontend-owned (the
  affordance lives where the operator acts); **completion-discard is
  domain-owned**: the domain flow erases the in-progress run through
  `discard_checkpoint` only AFTER its `on_complete` persistence
  succeeds — under the incremental-facts model this is the same
  lifecycle transition that clears the setup-incomplete state. A
  frontend MUST NOT discard at submit: the frontend cannot observe
  domain persistence success, and a discard-before-persist failure
  window would destroy the operator's only copy. Frontend-initiated
  discard exists solely for explicit operator intents (declining the
  resume offer). A crash between domain persistence and discard leaves
  at worst a stale checkpoint that resume re-validates against the
  completed record.
- **Per-mode checkpoint ruling.** The checkpoint port is chosen
  *per flow mode* by the domain; facts-as-checkpoint does NOT mandate
  incremental persistence for every mode. The distinction is the safety
  shield: a `create` flow's incremental writes land behind an explicit
  setup-incomplete state that keeps every consumer (readiness gates, the
  full-model constructor) away from a half-entered fact set, whereas a
  `modify` flow edits a LIVE, valid profile with no such shield —
  incremental writes there would expose concurrent readers to a
  half-applied edit set. A modify-mode flow therefore stages edits in
  the in-memory `FlowState` and commits ONCE from review as an atomic
  patch through the same mutation authority (one write, one co-emitted
  lifecycle event); its checkpoint-port implementation is a declared
  no-op. Two honesty constraints bind the no-op choice: the frontend
  MUST surface that mid-flow save/resume is unavailable in that mode
  (the save-and-exit affordance is disabled with an explicit message —
  an interrupted modify discards staged edits loudly, never silently),
  and the no-op is a per-mode declaration on the flow definition, not a
  silent implementation detail. Navigation, staleness, validation, and
  submit-only-from-review semantics are identical in both modes.

**D5 — Rendering: full-screen frontend on Textual (ruled); line-mode
fallback retained.** The full-screen frontend is an adapter over the
engine, built on Textual (`textual@8.2.8` line at decision time). The
dependency verdict (research, "Dependency verdict for the rendering
candidates") shows Textual adds cleanly — MIT, no version conflict with
the existing rich/questionary/prompt_toolkit set, no prompt_toolkit
coupling — so the choice reduces to Textual's application model (screens,
focus management, reactive widgets, headless `Pilot` test driver) versus
hand-building an equivalent widget/layout/focus layer on raw
prompt_toolkit full-screen. Hand-building that layer would create a
bespoke in-house UI framework this project would then own — the
duplicate-infrastructure shape the codebase consistently refuses — and
its testing story would be pipe-driven rather than a first-class headless
driver, against the real-behavior test discipline. Textual is therefore
ruled, not provisional. The engine/contract insulation stands regardless:
no engine or contract type imports the rendering library, so a future
rendering pivot remains an adapter swap. A
plain line-mode frontend (sequential paging without full-screen control)
remains for hosts that cannot run the full-screen application, and the
existing translated unsupported-console refusal remains for hosts that can
run neither. The non-interactive flag path drives the engine directly with
no frontend, so `--quiet`/flags, TUI, and line mode share identical
branching and validation by construction.

**Substrate public contract** (what `profile-setup-flow` and future flows
consume): a `FlowDefinition` family of strict frozen pydantic v2 records
(sections → pages; per-page widget kind, copy *references* for
prompt/help/format hint/failure modes — i18n keys or typed
corpus/schema/locale references per D2, never literal strings — choices
with description references, required, default,
declarative branching predicates over earlier answers, repeating groups,
and the compare-select page kind); pure per-question
validators plus section-exit and flow-scope cross-field validators returning typed
results with i18n message keys; and two ports the domain flow supplies — an
`on_complete(typed_answers)` persistence hook and a checkpoint-port
implementation that routes through the domain's existing encrypted
persistence authority (per the D4 incremental-facts ruling; for profile
setup, lifecycle-service fact writes). The review surface is a substrate primitive the domain
flow receives for free, never composes itself. The substrate is domain-blind: no
profile, censo, or AEAT vocabulary. Continuity with today's descriptor
vocabulary (question ids, canonical tokens, translation-key prefixes,
choice records) is intentional so the profile flow migrates by extension,
not rewrite — including the descriptor→`ProfileKey` compile projection
(`compile_profile_keys`, with its duplicate-key rejection and
`required_when_*` conditional-requirement derivation) AND the two core
registration slots the wizard feeds today (`register_wizard_catalogue`
for the flow descriptors, `register_project_answers` for the reverse
answers projection) — lower layers consume both without upward imports,
so the engine's definition model must keep feeding all three unchanged.
Existing flow-level consistency checks (the `verify_setup_answers`
cross-field gate) re-home into the substrate's flow-scope validator slot
— preserved and migrated, never dropped in consolidation.

**Completeness-by-construction (typed-answers enforcement).** The
substrate never runs `answers_model` validation itself: a raw model
error is library prose (the localization-leak class) and mapping it to
operator copy is domain knowledge. Instead, every model-boundary
cross-field invariant the domain's typed answers model enforces at
construction MUST also be registered as a flow-scope validator, so the
review surface is the complete gate and post-review model construction
cannot fail except as a domain defect. A domain flow whose typed model
carries construction-time validators (the taxpayer profile's
impatriado-date, non-resident-country, and representante checks) may
not wire its commit path until those checks are registered flow-scope.
The preferred implementation is a single flow-scope validator that
RE-RUNS the real domain construction over the staged answers and maps
the per-field failures through the domain's error-to-key mapping into
typed verdicts: the model validators stay the single authority and no
invariant is ever restated, so drift is structurally impossible.
Mapped verdicts carry catalogue keys and redacted context only — the
raw model message never rides through.
`answers_model` remains the typed hand-off shape and the definition
fingerprint component, nothing more.

**Route-through constraints** (binding on every domain flow consuming the
substrate, confirmed by the grounding map): `on_complete` and every
checkpoint-port implementation write exclusively through the owning
domain's mutation authority — for profiles, `ProfileLifecycleService`
(sole writer, `BucketEventType.PROFILE_*` co-emission pinned by its
event-contract gate) — never directly to the persisted record or
manifest; the persisted profile shape is effective-dated
`UserProfileFact` rows under the `schema.toml` authority; representation
(apoderamiento) is a separate encrypted namespace, never modelled as a
profile fact or wizard-written field; profile selection goes through the
single transacted active-profile pointer writer; and identity-bearing
answers validate through the one `core.identity` checksum authority,
never a widget-local reimplementation. All substrate symbols are consumed through the owning
package's public top-level facade (`service-imports-via-top-level-reexports`).

## Rationale

Option 3 wins on a knockout: every operator-mandated capability (paging,
back, jump, review, reset, restart, checkpoint) is flow *state*, and the
codebase's repeated failure mode is duplicated or drifted authorities over
shared semantics. Centralising flow state in one pure engine makes the
TUI, line-mode, non-interactive, and test surfaces provably consistent —
the same cure the pull-equals-calculate parity rule applies to
calculation transports — and makes the third-prompter incident class
structurally unrepresentable (a frontend without flow logic has nothing to
drift). The hexagonal split falls out for free: the engine and contract
are application-layer, typed, and import no rendering library, so the D5
rendering decision is a swappable adapter concern rather than an
architectural commitment. Preserving the descriptor/canonical-token/i18n
discipline (research, "What the current stack does well") minimises
migration risk for the consuming profile stream while deleting, not
bridging, the superseded one-shot walk (`no-legacy-compatibility`).

## Consequences

- **Gains.** One flow authority for all interaction surfaces; the operator
  gets the full paged experience; future flows (modelo work wizard,
  reconciliation walkthroughs) compose on the same substrate; headless
  testing of complete navigation scenarios (back/jump/reset/resume)
  becomes ordinary unit testing of engine transitions.
- **Costs.** A full-screen TUI frontend is a significant new adapter;
  Textual is a new direct dependency with its own release
  cadence; the line-mode fallback must be maintained alongside it; the
  existing prompter/runner surface and its tests are retired and rebuilt
  on the engine — a real migration for the CLI wiring and the modelo work
  wizard consumer.
- **Risks / pitfalls.** Staleness semantics (D3) are the subtle part —
  silent deletion or silent retention of gated answers would each recreate
  an under-declaration-shaped hazard at the profile layer; the review
  surface must make staleness impossible to miss. The D4
  incremental-facts model means a mid-setup profile exists as a live
  record — the setup-incomplete state, its readiness-gate coverage, the
  never-promote-partial-state rule, and discard-through-lifecycle each
  need explicit tests, and resume-across-definition-change with them.
  Textual's behaviour on degraded Windows hosts was not exhaustively
  surveyed, so the line-mode degradation path must be exercised early; the
  insulation boundary (no engine/contract import of the rendering library)
  keeps any future rendering pivot cheap and must be gate-enforced in
  review.
- **Follow-ups.**
  `profile-setup-flow` authors its `FlowDefinition` against the contract
  above; a plan document sequences engine → contracts → line-mode frontend
  → full-screen frontend → checkpoint store → CLI migration.
