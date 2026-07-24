---
tags:
  - '#adr'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - "[[2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research]]"
---

# `profile-setup-flow` adr: `paged profile setup flow with dynamic copy assembly and cotejo censal` | (**status:** `accepted`)

## Problem Statement

The interactive flow behind `aeat config profile create` / `edit` is a
forward-only, line-by-line walk of a well-typed but mis-ordered question
catalogue: identity arrives mid-flow, residence near the end, there is no
back/jump/review/checkpoint, each prompt is informationally thin, satellite
verbs (apoderado, descendiente, repair) run their own bespoke loops, and the
wizard never offers to cross-reference the profile against the taxpayer's
AEAT censo. The TUI substrate stream (feature `tui-wizard-substrate`)
supplies a renderer-agnostic `FlowEngine`/`FlowDefinition` contract with
full-page questions, navigation, validators, and encrypted checkpointing —
and (amended) requires every copy slot to be a REFERENCE resolved from the
bundled `_data` sources at render time. This record decides the profile
setup FLOW authored on that substrate: the canonical phase order, the
question-page copy-reference mapping, the censo cross-reference step, and
create/modify/resume semantics. Grounding:
`2026-07-23-profile-setup-flow-setup-flow-design-hypothesis-research`
(hypothesis F1-F8, grounding G1-G12).

## Considerations

- The catalogue is ALREADY declarative typed data with locale-key copy
  discipline and profile-key bindings (G1, G4); the deficits are order,
  navigation, page richness, and the missing censo step — not data modelling.
- The substrate contract is an intentional evolution of
  `WizardFlow`/`WizardQuestion`/`WizardCondition` with id and
  canonical-token continuity; one engine, no second authority.
- Per-question legal grounding is DERIVABLE: 101 registry bindings declare
  `source = "profile"` with `selector.profile_key` + `legal_refs` (G5); the
  Terminology Handbook carries 117 multilingual concept fragments (G6).
- The censo surface is smaller than first assumed (research G10, verified
  directly): the `CensoSnapshot` substrate was DELETED and the whole
  `censo pull/compare/apply` verb family retired onto `config profile edit`
  by `2026-07-11-censo-operator-manual-enrolment-adr`; operator-channel
  censal facts are a permanent non-official evidence tier;
  `CENSO_REFRESHED`/`CENSO_APPLIED` are dormant enum members with zero
  emission sites. The retirement ADR sanctions re-seating compare/apply
  over an OPERATOR-ENTERED fact set when a real workflow needs the diff.
- Persistence boundary (research G10): `ProfileLifecycleService` is the
  sole profile writer (event co-emission pinned by the emission-contract
  gate); there is NO draft store — `persist_patch`/`set_active_fields`
  write live effective-dated facts; `TaxpayerProfile` cross-field legal
  validators fire at CONSTRUCTION; `_refuse_duplicate_tax_id` binds at
  profile mint; `ApoderadoService` representation is a separate encrypted
  namespace, not a profile fact.
- Six derived-fact injector classes in `resolve_profile_sourced_bindings`
  compute legally-mandated synthetic facts (LIRPF arts. 58/61/64/75/81/
  81bis/82, Madrid DL 1/2010, M303 state attribution) from RAW fact
  shapes; descendant facts round-trip through
  `descendant_facts_from_list`/`descendant_list_from_facts` (research G10).
- Profile field paths are load-bearing string contracts across a 4-way
  binding (wizard profile_key ↔ schema.toml path ↔ four locale catalogues ↔
  registry selectors) plus the MCP harness `TAX_ID_FACT_PATH`; the two
  mechanical enforcement gates are `python -m cadrumo.locales scaffold
  --check` and `validate_user_profile_registry_contract` (research G10).
- No mechanism renders BOE corpus prose into wizard copy (the corpus
  grounds registry calculation values only); `tema-profile.toml` is still
  `draft` (research G10).
- `derive_modelo_applicability` already has two call sites whose
  relationship is unresolved; a third may not be added (research G10).
- `aeat-cli-pull-and-file-standard`: a future fetch-from-AEAT verb MUST be
  `pull`; a single-file input MUST be `--file`.
- `sensitive-financial-data-secure-storage-only`: answers (NIF, domicile,
  family, income facts) may persist only in the encrypted secure-object
  store; checkpoints included.
- `cli-notices-are-the-only-diagnostic-channel`, `no-legacy-compatibility`,
  `composition-service-no-parallel-write-path`,
  `aeat-spanish-stem-naming`, and the two-root CLI surface all bind.
- The non-interactive path (`--quiet`, `--accept-defaults`, explicit flags)
  walks the same descriptor today (G3) and must keep one validation
  contract with the interactive flow.
- The substrate contract (`2026-07-23-tui-wizard-substrate-adr`,
  D2/D4/public-contract) provides: declarative
  branching, a repeating-group primitive, per-answer + section-scope +
  flow-scope validators, a free review surface, and a generic
  compare-select page kind with an explicit defer status. D4's final form
  is the "facts ARE the checkpoint" model: the substrate defines a
  checkpoint PORT and the domain flow implements it over the existing
  effective-dated fact store — no bespoke checkpoint object (this
  supersedes the earlier opaque-extension-payload slot).
- `SETUP_FLOW` collects NO descendants today (they ride a standalone CLI
  verb + `descendant_facts_from_list`/`descendant_list_from_facts`); the
  wizard answer writers are `persist_answers`/`persist_patch`
  (research G11).
- The Certificado de Situación Censal (G313) is operator-downloadable and
  plausibly covers identity, domicilio, IAE, and IVA régimen; IRPF régimen
  and representation stay operator-entry; M036 is the single census vehicle
  since 2025-02-03 (research G8, with casilla-id and certificate-field
  UNVERIFIED flags carried).
- `cadrumo.core.identity` already ships the canonical NIF/NIE/CIF validator
  and `IdentityDocument` StrEnum (research G9); the flow reuses it, never a
  second identifier authority.

## Considered options

- **O-A: rewrite the catalogue as a new page model.** Rejected — the
  existing catalogue is sound typed data; a rewrite forks ids, locale keys,
  and profile keys for no structural gain (G1), and violates the
  no-parallel-authority discipline.
- **O-B (chosen): re-sequence and enrich the existing catalogue onto the
  substrate `FlowDefinition`,** adding copy-reference slots and the cotejo
  phase; ids, profile keys, and locale keys carry forward.
- **Censo C-1: reconcile only against existing profile facts.** Kept as
  the degradation and modify-mode baseline (a plain profile diff, no censo
  claim), but alone it gives a fresh taxpayer nothing to cross-reference.
- **Censo C-2 (chosen): in-flow ingestion of the operator-downloaded G313
  certificate** via `file --file`, then reconcile answers against the
  parsed artefact fact set. This is the retirement ADR's own sanctioned
  door — compare/apply re-seated over an OPERATOR-ENTERED fact set for a
  real workflow — and the remote hop is the operator's browser. There is
  no live surface to build on: the snapshot substrate is deleted (G10).
- **Censo C-3: reinstate a live `pull` transport.** Rejected — the
  retirement ADR's revival condition (a genuine AEAT consulta-only
  endpoint) is unmet and only a new accepted ADR can meet it; the flow
  keeps a transport-pluggable socket so `pull` can drop in then.
- **Satellite verbs: hard-delete vs deep-link.** Chosen: deep-link — the
  verbs survive as thin entry points that open the same flow at the owning
  phase; their bespoke prompt loops are deleted (no shim: one flow, several
  doors).

## Constraints

- Binds to the RESOLVED `tui-wizard-substrate` contract (renderer choice
  remains provisional and does not affect FlowDefinition-level authoring).
- The G313-certificate parser (C-2 ingestion) is net-new work of real size;
  the cotejo phase must degrade gracefully (C-1 + advisory) until it lands.
- The G313 certified field list and the M036 data-casilla layout are
  primary-sourced (research G13: AEAT "¿Qué certifica?" page;
  BOE-A-2025-410 Anexo I). Still UNVERIFIED and honestly labelled: the
  per-tax decomposition of the certificate's "situación tributaria"
  bucket (IRPF régimen stays operator-entry until an issued-certificate
  specimen proves otherwise), the CSV verification mechanics, and the
  CIF letter-class split (research G9) before extending identifier
  failure copy. The parser's fixture pass needs a real issued
  certificate specimen before its field extraction is pinned; no
  specimen or usable credentials exist today, so the parser ships as
  STRUCTURE ONLY — typed target shape and reconciliation mapping over
  the six certified fields, with the layout extractor unpinned and a
  loud, instructive refusal on any unrecognised document (never a
  silent mis-extraction). A specimen, when obtainable, enters through
  the encrypted evidence path, never a plaintext scratch location.
- Registry reverse-index (profile_key → bindings → legal_refs) must be
  computed from the compiled snapshot at flow-compile time, honoring
  `aeat-registry-authority-flow` (no fragment-path reads).
- Field-path stability: this record authorizes RE-SEQUENCING only. Any
  rename/restructure of a profile key or schema path is out of scope
  unless landed as one atomic 4-way sweep (wizard ↔ schema.toml ↔ four
  locale catalogues ↔ registry selectors, plus `TAX_ID_FACT_PATH`)
  verified by `python -m cadrumo.locales scaffold --check` and
  `validate_user_profile_registry_contract`.
- Any restructuring of descendant/marriage/residency/CCAA collection must
  preserve the exact raw fact shapes the six derived-fact injectors
  consume, or update the injectors atomically in the same change; a
  mismatch silently blanks a legally-mandated deduction. Descendant
  serialization reuses `descendant_facts_from_list`/`descendant_list_from_facts`.
- PLAN-SCOPE HANDOFF — dual `TaxpayerProfile` derivation paths:
  `load_active_taxpayer_profile` and `taxpayer_profile_from_mapping`
  already coexist, compounding the unreconciled
  `domain/contribuyente`-vs-`domain/deadlines` composition boundary. This
  flow adds NO third path; the implementation plan for this ADR must
  carry a reconciliation step (side-by-side read, consolidate or document
  the layering) before the flow's commit path is wired.

## Implementation

### 1. Canonical phase spine (decision)

The `setup` flow's eleven sections re-sequence into eight ordered phases;
existing question ids and profile keys are STABLE (checkpoint and
non-interactive flag continuity), sections regroup:

1. **entrada** — engine-level routing page: fresh create / modify / resume
   checkpoint. No profile data.
2. **identidad** — `output-language` FIRST (the operator must choose the
   language before anything else renders in it: the answer activates the
   chosen locale immediately for the remainder of the walk — a
   settings-scope override entered at the answer, cache-cleared so the
   next render resolves in the new language, honoring the
   activation-precedes-first-render constraint), then `entity-type`,
   `legal-entity-form` (from `taxpayer-type`), `tax-id`, `name`,
   `surnames`, `legal-name` (from `profile`). The entity-type axis gates
   the rest of the flow, and `tax-id` format validation is per-kind.
3. **residencia** — the current `residence` section moved up:
   `fiscal-residency`, `country-of-fiscal-residence`, representante fiscal,
   `tax-residence-ccaa`. CCAA and residency parameterize downstream phases.
4. **actividad y censo** — `irpf-income-categories`, `activity`,
   `activity-start-date`, `incn-prior-12-months`, the `iva` section
   (regime + enrolment confirms), the `enrollment` section, plus the
   activity-shaped `taxpayer-type` leaves (ley 49/2002 group,
   new-entity rate).
5. **familia** — `taxation-type` first (the individual-vs-joint
   declaration choice is a unidad-familiar decision, and the spouse
   block's visibility gates on it, so it MUST precede the spouse pages —
   seating it later would break the earlier-question gate invariant),
   then the `taxpayer`, `spouse`, and `family` sections
   (sex, marital status, situación familiar, marriage/birth/death dates,
   disability, spouse block), plus descendientes as an instance of the
   substrate's repeating-group primitive (instances keyed by index,
   individually reviewed and staleness-tracked). Descendant collection is
   a genuinely NEW wizard surface — today `SETUP_FLOW` collects no
   descendants at all; they ride only the standalone `descendiente` CLI
   verb — and the group MUST emit exactly the established fact shape:
   `renta_family.descendiente.{n}.{birth_date, adoption_date,
   discapacidad, convivencia, custodia_compartida, meses_madre_trabajo,
   gastos_guarderia, nif}` plus the derived aggregates
   (`renta_family.descendientes_count`,
   `renta_family.gastos_guarderia_reales_2024`), produced through
   `descendant_facts_from_list` — the shape the
   `_minimo_descendientes_facts` injector and the registry selectors
   consume. Descendant NIFs validate through `cadrumo.core.identity`.
6. **obligaciones** — the `obligations` section (withholdings, módulos,
   estimation/special regimes, informativas thresholds).
7. **preferencias** — `capabilities`, `notes` (`output-language` moved
   to the head of the flow — the language choice must precede every
   localized render).
8. **cotejo censal y revisión** — the censo cross-reference step (§3), then
   the substrate review screen (every answer, stale-marks surfaced,
   jump-edit), then the single atomic commit through the existing profile
   persistence path (`composition-service-no-parallel-write-path`).

Phase-order rationale: every later phase's gates are decidable from earlier
answers; the current catalogue's `visible_when` targets all resolve to
earlier questions under this order (the existing model validator enforces
it at flow-construction, so a mis-ordering fails at import).

### 2. Catalogue expressed on the substrate; copy is references only

`WizardFlow`/`WizardQuestion` evolve into the substrate `FlowDefinition`
page vocabulary (one canonical model set — the substrate's; no parallel
descriptor survives). Each page's copy slots are typed REFERENCES resolved
at render time by the substrate's copy assembler from three bundled
sources, in fixed zone order:

- **Prompt / choice labels / format hints / failure messages** — locale
  catalogue keys, continuing the `wizard.setup.*` namespace (318 keys
  exist; new pages add keys via the locales CLI only). Widget failure
  copy keeps the typed `wizard.errors.*` keys; cross-field verifier
  findings keep `wizard.verifier.*`.
- **Concept grounding ("understand this question")** — an optional
  `concept_id` per page referencing an `approved` Terminology Handbook
  fragment; the assembler renders the locale-matched `short_description`
  and `definition`. New profile-facing concepts are enrolled in the
  Handbook, never authored as flow literals.
- **Legal provenance ("why we ask / where it files")** — derived, not
  authored, and scoped to CITATIONS: the zone renders `legal_refs` from
  two existing sources — the field's own `schema.toml` definition (fields
  already carry `legal_refs`) and a flow-compile-time reverse index from
  the registry snapshot mapping each page's `profile_key` to the
  `source = "profile"` bindings that consume it (union of their
  `legal_refs`, resolved through the legal catalogue, plus the consuming
  modelos). It does NOT render BOE corpus prose — no such mechanism exists
  (the corpus grounds registry calculation values, research G10) and this
  record does not create one. Pages whose key carries no refs render no
  legal zone — nothing is invented. Concept references may name only
  `approved` Terminology Handbook fragments; profile-domain concepts still
  `draft` (e.g. `tema-profile`) are promoted through the Handbook
  lifecycle before a page may reference them.

A structural gate extends the existing Translatable-prefix validator: a
`FlowDefinition` page carrying a literal copy string (anything not a
key/reference) fails at construction.

Validators bind to the substrate's three scopes: per-answer typed
validators (tier 2) carry the existing widget checks plus, on the identity
pages, the canonical `cadrumo.core.identity` authority
(`validate_identity` / `validate_spanish_tax_id`; failure copy keyed per
`IdentityDocument` kind with format hints and worked examples as locale
references — never a second identifier implementation). The existing
`verify_setup_answers` cross-field checks (spouse consistency,
joint-taxation/situación-familiar, monoparental — LIRPF art. 82-grounded,
surfaced via `wizard.verifier.*` keys) are RE-HOMED into the substrate's
flow-scope validator slot — migrated intact, never dropped or
re-implemented; section-scope enrolment is used where a check's inputs
are complete at phase exit. This gate remains SEPARATE from the
ProfileKey requirement registry.

Two core registration slots the re-sequence MUST keep feeding unchanged:
`register_wizard_catalogue` (flow descriptors) and
`register_project_answers` (the reverse answers projection) — domain
consumers (`taxpayer_profile_from_mapping`, calc binding resolution) read
these core slots to avoid upward imports, and breaking either silently
breaks deadline/calc consumers.

Mechanical enforcement for ANY question-set change (not only renames):
the `profile` namespace is a DYNAMIC translation root invisible to static
locale scanning, so every catalogue edit runs
`python -m cadrumo.locales scaffold` / `scaffold --check` and the locale
parity/honesty gates.

### 3. Cotejo censal (decision — reconciled against the retirement ADR)

The phase-8 censo step is STRICTLY file-artefact reconciliation. There is
no live censo surface to build on: the `CensoSnapshot` substrate was
DELETED and the `censo pull/compare/apply` verb family retired onto
`config profile edit` by `2026-07-11-censo-operator-manual-enrolment-adr`
(research G10). That ADR's Implementation leaves exactly one door open —
"re-seat compare/apply over an operator-entered fact set only if a real
workflow needs the diff" — and this wizard phase IS that workflow. The
cotejo's second operand is therefore always an OPERATOR-SUPPLIED fact set,
never a live snapshot:

- **The artefact:** the Certificado de Situación Censal (G313) —
  operator-downloadable from Sede with Clave/certificado/DNIe as a PDF
  with CSV verification code — ingested through a `file --file PATH`
  sub-command surface. Parsed facts are an operator-supplied,
  NON-OFFICIAL-tier fact set (the retirement ADR's evidence-tier
  constraint: operator-channel censal facts are never stamped
  AEAT-verified; the calendar's `censo.enrolment_unverified` posture is
  unchanged by this feature). Provenance records the artefact origin (a
  distinct `UserProfileFact.source` token) without claiming official
  verification. Coverage (the six certified fields, primary-sourced per
  research G13): domicilio fiscal, condición de residencia, NIF de los
  representantes, situación tributaria, actividades y locales, and
  obligaciones periódicas — so identity/residence, domicilio, IAE, the
  obligation surface, AND the representación axis (representative NIF)
  reconcile from the artefact. IRPF régimen remains direct operator
  entry: it is not verified as a decomposed certificate field, and the
  page says so openly rather than implying coverage. M036 is the single
  census vehicle (M037 suppressed 2025-02-03). The parser grounds on the
  certified field list, never on M036 page-1 section-selector checkboxes
  (the 122-133 numbers are selectors, not data; the data casillas are
  the A/B/C domicilio rows, 400-404 actividades, 510-576 IVA regímenes,
  604-612 IRPF, 300-384 representantes — research G13). The M036
  "titulares reales" axis (página 10, RD 117/2024) has no profile
  counterpart today; its enrolment is an explicit follow-up decision,
  not silently dropped.
- **Reconciliation:** per fact present in both the flow's answers and the
  parsed artefact, an instance of the substrate's generic COMPARE-SELECT
  page kind: candidate values (operator answer, artefact fact) each with a
  provenance reference, plus the explicit DEFER option. Adopting writes
  through `ProfileLifecycleService` at commit like any other answer;
  deferring marks the question with the substrate's distinct "deferred"
  review status AND persists a typed divergence surfaced as a warning
  `Notice` on later profile reads — never silently resolved. The operator
  remains the authority; nothing auto-overwrites.
- **Degradation:** until the G313 parser ships, the phase renders an info
  `Notice` naming the `config profile edit` manual route and the
  certificate's Sede download path; in modify mode it still diffs in-flow
  answers against the EXISTING profile facts (a plain profile diff, no
  censo claim).
- **Events:** cotejo writes are ordinary profile mutations emitting the
  standard `PROFILE_*` lifecycle events. The dormant `CENSO_APPLIED`
  member (zero emission sites today, research G10) is RE-ENROLLED with a
  live emission site at cotejo artefact-apply — its semantics match
  exactly — while `CENSO_REFRESHED` (live-refresh semantics whose
  precondition is permanently false) is reconciled and deleted per
  `retired-enum-members-need-consumer-reconciliation`. No new event
  family.
- **Future `pull`:** the phase consumes a `CensoFactSource` port whose
  sole shipped implementation is the artefact parser; a live transport
  exists ONLY if a future ADR meets the retirement ADR's revival
  condition (a genuine AEAT consulta-only endpoint), enrolling as a
  second implementation under a `pull` verb. Nothing else changes.

### 4. Modify, satellites, checkpoint, failure surfaces (decisions)

- **Persistence model (binding — the substrate D4 "facts ARE the
  checkpoint" contract):** the substrate defines a checkpoint PORT; this
  flow supplies the implementation, and there is no bespoke checkpoint
  store, no stored cursor, no extension payload (the earlier
  opaque-payload design is superseded by the substrate amendment).
  - **Create:** the profile record is minted EARLY — at the first
    persistence event (a save-and-exit or the submit), whichever comes
    first — in an explicit SETUP-INCOMPLETE lifecycle state, with
    `_refuse_duplicate_tax_id` firing at that mint. Answers persist as
    effective-dated `UserProfileFact` rows through
    `ProfileLifecycleService` (`persist_answers` / `set_active_fields`).
    The facts themselves are the checkpoint: resume projects facts back
    to answers, recomputes visibility/validation against the current
    definition, and derives the cursor as the first unanswered visible
    question. Discard erases the incomplete profile via the lifecycle
    authority. The phase-8 commit is the transition OUT of
    setup-incomplete: flow-scope validators run, then the atomic
    `complete_setup` flips record AND manifest together — and only then
    may consumers construct a `TaxpayerProfile`; the readiness gate
    refuses modelo work on a setup-incomplete profile, so the
    cross-field legal validators never meet a half-entered fact set.
    Refinement path, explicitly conditioned: minting at `tax-id`
    validation (per-answer, before any save) requires the schema
    required-field check to defer while the record is SETUP-INCOMPLETE
    (completion re-enforces it); until that relaxation is designed, a
    partial mint would fail schema validation, so first-persistence
    minting is the honest boundary.
  - **Modify:** NO mid-flow persistence. A live, valid profile must never
    hold a half-applied edit set (consumers read it concurrently), so
    modify stages answers in `FlowState` only and commits ONCE at review
    as an atomic fact-level diff through `persist_patch`. Ratified by the
    substrate's per-mode checkpoint ruling (D4): the port is chosen per
    flow mode by the domain, discriminated by the safety shield —
    create's setup-incomplete state shields consumers; modify has no
    shield. Two binding honesty constraints ride the decision: (1) the
    frontend MUST surface that mid-flow save/resume is UNAVAILABLE in
    modify mode — save-and-exit disabled with an explicit message, and an
    interrupted modify discards staged edits LOUDLY, never silently;
    (2) the no-op checkpoint is a per-mode DECLARATION on the flow
    definition, never a silent implementation detail. Navigation,
    staleness, validation, and submit-only-from-review stay identical
    across both modes.
  The flow adds no new profile write path and no new applicability call
  site (two exist; their reconciliation is a separate concern). Cotejo
  deferrals persist as typed divergence facts at commit like any other
  answer — no side store.
- **Modify:** `edit` enters the same spine in the substrate's hub
  navigation, seeded from the existing profile (evolving today's
  edit-mode canonical seeding); the review screen renders a field-level
  old→new diff — concretely, the substrate review surface's
  registered-value column is fed by projecting the active record's facts
  to page keys through the projection authority, so the operator sees
  the staged in-flow answer and the on-record value side by side.
  Commit is one atomic mutation. Changed gating answers mark dependents
  STALE per the substrate contract — never silently dropped
  (`no-silent-under-declaration` transplanted to profile facts).
- **Satellites:** `descendiente` and profile `repair` become deep-link
  entry points into phase 5 and the review screen respectively; their
  bespoke prompt loops are deleted in the same change (no compatibility
  copies). The `apoderado` door deep-links into phase 7 but its writes
  route to `ApoderadoService`'s own encrypted namespace — representation
  is NOT a profile fact and the flow must not mint one; the flow merely
  hosts the pages and hands the typed answers to that service at commit.
- **Checkpoint/resume:** subsumed by the persistence model above — the
  encrypted profile facts ARE the create-mode checkpoint (already inside
  the secure-object store; no plaintext, no second crypto authority, no
  fingerprint to store). Resume is offered at `entrada` when a
  setup-incomplete profile exists for the bucket; definition drift is
  handled by recomputation (facts re-project against the CURRENT
  definition; answers whose question changed shape surface as
  stale-in-review, never silently coerced). Modify offers no resume by
  decision (see persistence model).
- **Failure tiers:** per-answer validator failures render in-page
  (substrate); flow-level advisories (censo divergence, checkpoint
  discarded, artefact parser unavailable) are typed `Notice`s on the final
  envelope; hard failures checkpoint-then-abort through the standard error
  envelope. The non-interactive path shares the same per-question and
  cross-field validators — one contract.

## Rationale

O-B wins on a knockout: the grounding pass (G1-G4) shows the assumed
"bare-bones wizard" is in fact a sound declarative catalogue with exactly
the copy-key discipline the substrate's reference-only amendment demands —
so the cheapest correct move is re-sequencing and enriching that data onto
the new engine, and every alternative that re-authors pages forks three
live authorities (ids, locale keys, profile keys) the rest of the system
already consumes. C-2 is the only censo option that both honors the
retirement ADR and gives a fresh taxpayer a working cross-reference story;
the derived legal-provenance zone (G5) turns "grounded page" from a copy
authoring project into a registry projection, which is why no grounding
prose is hand-written anywhere in the flow.

## Consequences

- The operator gets one ordered, resumable, fully-grounded setup surface;
  create, modify, apoderado, descendiente, and repair converge on one flow
  with several doors.
- Copy stays four-locale-complete by construction (locales CLI + parity
  gates); grounding stays law-true by construction (registry projection) —
  but the reverse index adds a flow-compile dependency on the registry
  snapshot, so registry load failures now surface at wizard start; the
  refusal must name the registry error, not a generic wizard failure.
- The censal-artefact parser is the long pole; until it lands the cotejo
  phase is honest but thin (enrolled-facts-only + advisory).
- Re-sequencing changes the interactive question ORDER while keeping ids:
  scripted `--quiet` flag runs are unaffected, but recorded operator
  transcripts and docs need regeneration (docs scaffolding + conformance
  gates cover this).
- Deleting the satellite prompt loops is a hard cut (no-legacy); any
  operator harness document citing the old loops must be swept in the same
  change (`operator-harness-cites-live-cli-surface`).
- Deferred-divergence Notices create a small standing surface on profile
  reads; the divergence facts must be covered by the roundtrip discipline.
- The SETUP-INCOMPLETE lifecycle state is a new, load-bearing profile
  surface: the readiness gate, profile listings, and the overview calendar
  must recognize it (an incomplete profile is visible but not workable);
  its lifecycle events ride the existing PROFILE_* taxonomy.
- Early minting means an abandoned create leaves an incomplete profile on
  disk until discarded — visible, erasable via the lifecycle authority,
  and honest (nothing hidden in a side store); tax-id uniqueness holds
  from mint, so a re-run create on the same NIF resolves to resume, not a
  duplicate.
- An interrupted MODIFY discards staged edits (no mid-flow persistence by
  decision); the operator-facing docs must say so plainly.
- Descendant collection in the wizard is net-new scope (today CLI-only):
  the familia phase's repeating group, its emission through
  `descendant_facts_from_list`, and the retirement of the standalone
  verb's bespoke loop land together.
