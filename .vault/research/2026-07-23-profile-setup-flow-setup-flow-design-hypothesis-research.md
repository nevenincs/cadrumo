---
tags:
  - '#research'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:f14d38203f53871a61d283864fafa9487b0c91439348abdbe90d3790748d8f2b'
related: []
---

# `profile-setup-flow` research: `setup flow design hypothesis`

How should the interactive profile setup flow behind `aeat config profile
create` / `modify` be structured so it is one coherent, ordered, paged
experience — and how should it cross-reference, reconcile, and apply AEAT
censo facts? The current interactive mode is line-by-line, informationally
light, scattered across several CLI surfaces (create, modify, repair,
apoderado, descendiente), does not follow a required step order, and never
offers to reconcile against the taxpayer's censo. This document frames a
complete design hypothesis for the flow — the phase sequence, the
question-page contract expressed against the Stream-1 TUI substrate, the
censo reconciliation step, modify/resume semantics, and the option space the
ADR must settle. Codebase grounding is deliberately deferred: the RAG service
was unavailable at authoring time, so every claim about existing modules is
marked as an assumption to be verified in a follow-up grounding pass before
the ADR is finalized.

## Findings

### F1 — Problem statement, decoded

The operator's complaint decomposes into six deficits: (1) no canonical step
ORDER — questions arrive in an ad-hoc sequence that does not mirror how a
taxpayer profile is actually constituted (identity before domicile before
régimen before family before income categories); (2) fragmentation — profile
completion is spread across `create`, `modify`, and satellite verbs
(`repair`, `apoderado`, `descendiente` sub-flows), each with its own
prompting style; (3) informational poverty — a bare one-line prompt with no
explanation of what the question means, which values are accepted, what
format is expected, or what happens on failure; (4) weak navigation — no
back/forward/edit/reset/restart, no way to review answers given so far; (5)
no checkpoint/resume — an interrupted setup loses everything; (6) no AEAT
cross-reference — the wizard never offers to reconcile operator input
against the taxpayer's censal facts (Mis Datos Censales / M036 surface),
even though censo snapshot machinery exists in the application layer.

### F2 — Hypothesis: a canonical eight-phase flow

The flow is a linear spine of phases, each a group of question pages, with
conditional branches hanging off phase-local answers. Hypothesized order,
chosen so that every later phase's question set is determined by earlier
answers (identity type gates document formats; domicile gates CCAA axes;
economic-activity gates régimen pages; family situation gates descendiente /
ascendiente sub-flows):

1. **Entrada** — mode selection: fresh create, modify existing, or resume a
   checkpointed in-progress setup. Not a data phase; routes only.
2. **Identidad** — entity kind (persona física / jurídica / entidad en
   atribución), identifying document (NIF / DNI / NIE / CIF-style NIF for
   jurídicas / NII), name fields. Document format validation is per-kind.
3. **Domicilio fiscal** — address, municipio, provincia, and the derived
   comunidad autónoma (CCAA), which parameterizes autonomic tax axes
   downstream.
4. **Actividad y censo** — does the taxpayer carry an economic activity;
   if so: IAE epígrafe(s), régimen de estimación (directa normal /
   directa simplificada / objetiva), IVA regime (general / simplificado /
   recargo de equivalencia / exento), alta censal facts.
5. **Situación familiar** — estado civil, descendientes (repeating
   sub-flow, one page-group per descendiente), ascendientes, discapacidad
   grades. This absorbs the current standalone `descendiente` surface.
6. **Categorías de renta IRPF** — which IRPF income categories apply
   (trabajo, capital, actividades económicas, ganancias). Feeds the
   cross-period applicability machinery (`taxpayer_files_economic_activity`).
7. **Apoderamiento / representación** — optional representative or
   apoderado enrolment. Absorbs the standalone `apoderado` surface.
8. **Cotejo censal + revisión** — the AEAT censo cross-reference step (F5),
   followed by a full review page (every answer, grouped by phase, each
   jump-editable) and the final atomic commit to the encrypted profile
   store.

Alternative considered: a free-form hub-and-spoke model (a menu of sections
the operator visits in any order). Rejected as the primary model because the
operator explicitly wants "required setup steps" honored and because later
phases depend on earlier answers; however, MODIFY mode (F6) reuses the same
phase spine in hub mode, so the spine must be authored order-independent at
the data level even though CREATE walks it linearly.

### F3 — Question-page contract (consumed from the Stream-1 substrate)

Every question is one full grounded page. The hypothesis expresses each page
as a declarative, typed definition the substrate renders; the flow stream
authors CONTENT, the substrate owns RENDERING and key handling. Required
per-page fields:

- **id** — stable kebab-case identifier, Spanish stem where the concept is
  an AEAT surface (`identidad.nif`, `censo.regimen-estimacion`).
- **title + explicación** — what is being asked and why the app needs it,
  in taxpayer-general terminology; where the question mirrors a censal or
  legal concept, `legal_refs` / `source_refs` provenance rides along and is
  displayed as grounding.
- **answer type** — one of a closed set of page kinds: free text with
  format mask, single choice (closed StrEnum), multi choice, decimal,
  date, repeating group (descendientes), confirmation. Closed value sets are
  core StrEnums per the architecture-boundaries rule; the page shows the
  full accepted-value list with per-value one-line descriptions, never a
  bare prompt.
- **format contract** — for formatted answers (NIF/DNI/NIE/NII, IBAN,
  postal code): the expected pattern, a worked example, and normalization
  rules (case folding, whitespace). Validation failure re-renders the page
  with the specific violated constraint named — never a bare "invalid".
- **optionality + default + prefill** — whether skippable, the default
  shown, and the prefill source (existing profile value in modify; censo
  fact where one is enrolled; nothing on fresh create).
- **validator hook** — a callable contract the substrate invokes
  synchronously per answer (format/checksum, e.g. NIF control letter) plus
  a phase-exit validator for cross-field invariants (e.g. régimen objetiva
  requires an eligible IAE epígrafe).
- **navigation affordances** — back / forward / jump-to-page-from-review /
  reset-answer / restart-flow / save-and-exit (checkpoint). These are
  substrate primitives; the flow only declares which are legal on each page
  (e.g. no "back" past the commit page).

Substrate capabilities this stream REQUIRES from `tui-wizard-substrate`:
(a) a conditional-branch primitive (page visibility predicated on earlier
typed answers); (b) a repeating-group primitive (N descendientes); (c) a
synchronous validator hook returning a typed error the page renders; (d) a
review-page primitive that enumerates answered pages with jump-edit; (e) a
checkpoint field on the flow state (opaque encrypted blob handled by the
flow, not the substrate); (f) a three-way diff/choice page kind for censo
reconciliation (F5) — per-fact "keep mine / take censo / decide later".

### F4 — Question catalogue as typed data, single authority

The catalogue of profile questions is data, not imperative prompt code: a
tuple of typed page definitions (pydantic v2, strict) grouped into the
phases of F2, declared once and consumed by BOTH create and modify. The
existing wizard package (assumed at `src/cadrumo/application/wizard/`, with
`_catalogue.py`, `_compiler.py`, `_models.py`, `_prompter.py`, `_runner.py`
— unverified, RAG down) already carries a catalogue/compiler split and a
canonical prompter with exactly two implementations; the hypothesis is to
EXTEND that catalogue into the paged contract rather than author a parallel
one. Hard constraint carried forward: no third prompter copy — a past
incident shipped a drifted hand-copy of the canonical prompter, so the flow
must consume the substrate's prompting surface exclusively. Whether the
existing catalogue model can express F3's page contract or needs a
superseding model is a grounding question for the follow-up pass; the ADR
must settle extend-vs-supersede.

### F5 — Cotejo censal: cross-reference, reconcile, apply

The step the wizard has never offered. Constraint frame: the live censo
scrape was retired by `2026-07-11-censo-operator-manual-enrolment-adr` —
censal facts are operator-manual today, and the former `aeat config profile
censo pull` verb is gone; any future fetch-from-AEAT verb MUST be named
`pull` and any single-file input MUST be `--file` per the CLI standard.
Three coexistence options for where reconciliation source data comes from:

- **O1 — reconcile against the enrolled censo snapshot only.** The wizard's
  cotejo phase reads the already-enrolled censo facts (CensoSnapshot
  machinery, operator-manual enrolment) and three-way compares them with
  the operator's in-flow answers. No transport question arises. Weakness:
  a fresh taxpayer has no enrolled snapshot, so the phase degrades to a
  skip with an advisory pointing at the manual enrolment surface.
- **O2 — O1 plus in-flow file ingestion.** The cotejo phase additionally
  offers to ingest an AEAT censal artefact the operator downloaded
  themselves (Mis Datos Censales PDF / M036 justificante) via a
  `file --file PATH` sub-step, parse it into censo facts, enroll, then
  reconcile as O1. Honors the retirement ADR (no live scrape) while still
  delivering "cross-reference against the remote surface" value — the
  remote hop is the operator's browser, not the app.
- **O3 — reinstate a live `pull` transport.** Requires superseding the
  retirement ADR; out of this stream's authority to decide alone, but the
  flow design must leave the cotejo phase transport-pluggable so a future
  `pull` slot drops in without reshaping the flow. Evidence favors O2 now
  with the O3 socket declared: the operator's ask ("offer to
  cross-reference, sync and PULL") is fully served at the reconciliation
  level by O2, and the verb-naming rule reserves `pull` for the day the
  transport returns.

Reconciliation semantics hypothesis: per censal fact, a three-state page —
operator answer, censo fact, and a decision (keep operator value / adopt
censo value / mark unresolved). Adopting emits the same apply path the censo
machinery already owns (assumed `CENSO_APPLIED` bucket event; unverified).
Unresolved facts persist as a typed divergence list on the profile,
surfaced as `Notice`s on later profile reads — never silently dropped, per
the no-silent-under-declaration discipline transplanted to censal identity.
Direction of authority: the censo is EVIDENCE, the operator is the
AUTHORITY — the wizard never auto-overwrites an operator answer from a
censo fact without an explicit per-fact adoption.

### F6 — Modify mode: same spine, hub navigation, diff commit

`modify` enters the identical phase spine seeded with the existing profile's
values, but in hub mode: a section menu (the F2 phases with per-phase
completeness/divergence badges) from which the operator jumps into any
phase; pages render prefilled with current values; phase-exit validators
re-run on any touched phase. The commit page renders a field-level DIFF
(old → new) rather than a plain summary, and the write is one atomic
mutation of the profile record — reusing the existing single-writer profile
mutation path (composition rule: never a parallel write path). The satellite
verbs (`repair`, `apoderado`, `descendiente`) become entry-point aliases
that open the same flow deep-linked at the owning phase, retiring their
bespoke prompt loops; whether the verbs themselves survive as aliases or are
folded away entirely is an ADR decision (the no-shims rule pushes toward
folding, but the verbs are operator muscle-memory surfaces — the ADR should
weigh discoverability against surface count).

### F7 — Checkpoint / resume

An interrupted setup persists as an encrypted checkpoint object in the
active bucket's secure-object repository — NEVER a plaintext temp file: the
answers include NIF, domicile, family and income facts, squarely inside the
sensitive-financial-data-secure-storage-only perimeter. Checkpoint content:
the typed answer set so far, the current page id, the catalogue revision it
was authored against, and a created/modified stamp. Resume semantics: on
next `create`/`modify` invocation for the same bucket, offer resume /
discard; a checkpoint authored against an OLDER catalogue revision is
re-validated page-by-page on resume, and any answer whose question changed
shape is re-asked, not silently coerced (no-legacy-compatibility: the
checkpoint is short-lived working state, so the cheap posture is re-ask, not
upgrade machinery). Exactly one checkpoint per bucket per flow kind
(create/modify), idempotent-guarded overwrite.

### F8 — Failure and diagnostic surfaces

Three tiers: (1) per-answer validation errors render inline on the page
(substrate-owned rendering of the typed validator error) — these are
interactive-loop feedback, not envelope traffic; (2) flow-level advisories
(censo divergence retained, checkpoint discarded, censo snapshot absent)
are typed `Notice`s on the command's final envelope, per the
notices-only-diagnostic-channel rule; (3) hard failures (storage write
refusal, catalogue/registry load error) abort the flow AFTER writing a
checkpoint where the state is coherent, and surface through the standard
stderr error envelope. The non-interactive (flag-driven) create/modify path
is untouched by this redesign except that it shares the same validators —
one validation contract for both entry modes, or the interactive flow's
richer validation silently diverges from the scripted one.

### Not investigated / deferred to the grounding pass

Everything filesystem-factual: the actual wizard module inventory and its
catalogue model shape; the profile CLI verb surfaces and their current
prompt loops; the censo machinery's real types, event names, and whether a
file-ingestion parser for censal artefacts exists at all (O2 may need net-new
parsing work — sizeable); the profile record's field inventory versus the F2
phase axes; the existing checkpoint/idempotency primitives. Additionally,
external research is needed on the exact Mis Datos Censales (G313) / M036
fact surface and which censal fields map onto which profile axes, and on
the authoritative format/checksum rules for NIF/DNI/NIE/CIF-form/NII — both
are scoped research requests for the coordinator's researchers, not
assumptions this document makes.

## Grounding pass (2026-07-23, direct reads; RAG still warming)

The UNVERIFIED flags above are now resolved by direct file reads. Facts that
supersede the hypothesis's assumptions:

### G1 — The real catalogue is richer and already declarative

`src/cadrumo/application/wizard/_catalogue.py` declares one `WizardFlow`
(`SETUP_FLOW`, id `setup`) of ELEVEN sections in this order: `taxpayer-type`,
`profile`, `taxpayer`, `spouse`, `family`, `iva`, `enrollment`,
`obligations`, `residence`, `capabilities`, `notes` — ~70 questions, each a
frozen `WizardQuestion` with `profile_key`, widget StrEnum, `Translatable`
prompt/help keys (`wizard.setup.<section>.<question>.*`), closed choices
built from core/domain StrEnums (`EntityType`, `IVARegime`, `CCAA`,
`IrpfIncomeCategory`, `SituacionFamiliar`, …), and declarative
`visible_when` conditions (`equals`/`contains`, OR via `WizardVisibility`).
The F2 "catalogue as typed data" hypothesis is ALREADY the architecture; the
deficit is ORDER (identity `tax-id` buried mid-flow in section 2;
`residence`/CCAA ninth), NAVIGATION, and page richness — not data modelling.
F4's extend-vs-supersede question resolves to EXTEND.

### G2 — The runner is strictly forward-only

`src/cadrumo/application/wizard/_runner.py:122` (`run_flow`) walks sections
in order, evaluates visibility incrementally, asks, validates
(`_widgets.py`), accumulates canonical tokens, returns the typed
`answers_model`. No back, no jump, no review, no checkpoint — the operator's
navigation complaint is structural, and the substrate's `FlowEngine` is the
correct evolution seam.

### G3 — Create/edit already share the flow; edit seeds defaults

`src/cadrumo/entrypoints/cli/_config/__init__.py:55` builds `create` and
`edit` as two closures over the SAME flow via `build_wizard_command(...,
mode=...)`; edit mode seeds canonical defaults from the existing profile and
`--quiet` / `--accept-defaults` drive the non-interactive path through the
same descriptor (`src/cadrumo/application/wizard/_commands.py:807-923`).
Satellite surfaces remain separate: `_config/_apoderado.py`,
`_config/_descendiente.py`, `_config/_repair_profile.py`.

### G4 — Copy is already keyed; failure copy is typed

`src/cadrumo/locales/en.yml` carries 318 `wizard.*` keys — 81 `prompt`, 96
`help`, 72 choice `label`, 13 `description`, plus typed widget-failure keys
(`wizard.errors.invalid_tax_id`, `.invalid_postcode`, `.blank_text`, …) and
cross-field verifier keys (`wizard.verifier.*`, produced by
`application/wizard/_verifier.py`). Four locales (en/es/ca/hu) under parity
+ honesty gates. The substrate's "references only, no literals" contract is
CONFIRMED as continuity, not migration.

### G5 — Per-question legal grounding is derivable from the registry

101 registry binding files declare `source = "profile"` with
`selector = { profile_key = "..." }` plus `legal_refs` / `source_refs`
(e.g. `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/bindings/0001-profile-censo-status.toml`
binds `censo.status` with RD 1065/2007 arts. 9-11). A reverse index
profile_key → consuming bindings → legal_refs yields each question's legal
grounding and "feeds modelo X" provenance from the compiled registry
snapshot — no hand-authored grounding copy needed.

### G6 — Terminology Handbook is the concept-help source

`src/cadrumo/_data/terminology/concepts/` holds 117 concept fragments with
multilingual `short_description` / `definition` / `legal_refs` / sources
(e.g. `censo.toml`, lifecycle `approved`). Taxpayer-facing approved concepts
are the ready-made "understand this question" copy layer.

### G7 — Censo reality

Censal facts are operator-manual (live scrape retired). Existing machinery:
`application/user_profile/_censo_sync.py` (`CensoSyncService`; censo-derived
facts carry a distinct `UserProfileFact.source` and a
`censo.enrolment_unverified` status), `application/modelo/_m036_lifecycle.py`,
`domain/calculations/registry/_censo_modelos.py`, `BucketEventType.CENSO_*`
(`domain/buckets/_event.py`), and profile keys under `censo.*`
(`censo.status`, `censo.activity_start_date`, `censo.large_company`, …).
There is no censo pull verb on the live surface. F5's option O2 (reconcile
against enrolled facts + operator-downloaded artefact ingest) remains the
evidence-favored shape; the artefact parser is net-new work.

### G8 — AEAT censal fact surface (delivered research, 2026-07-23)

Coordinator-relayed research on Mis Datos Censales / Modelo 036. M036 field
inventory: identificación (NIF, nombre/razón social, tipo declarante);
domicilios (fiscal/social/notificaciones); actividades económicas + locales
(IAE epígrafes with alta/baja); régimen IVA (general / recargo /
simplificado / REDEME / especiales); régimen IRPF/IS (estimación directa
normal/simplificada, objetiva); obligaciones/periodicidad (retenciones,
pagos fraccionados); representación; situación censal. Profile-axis map:
identificación→identity, domicilio→fiscal domicile/CCAA, IAE→activity,
IVA/IRPF regímenes→their axes, obligaciones/periodicidad→DERIVED deadline
schedule (not static profile facts), situación→lifecycle. The **Certificado
de Situación Censal (procedure G313)** is operator-downloadable
(Clave/certificado/DNIe, PDF + CSV code) and plausibly covers identity,
domicilio, IAE epígrafes, IVA régimen — the natural `file --file`
reconciliation artefact; IRPF régimen and representation are NOT confirmed
on it and stay operator-entry. M037 was SUPPRESSED 2025-02-03 (Orden
HAC/1526/2024, BOE-A-2025-410): M036 is the single census vehicle — which
matches the repo's registry revision id `2025-02-03-y-siguientes` for M036
and the retired `Modelo.M037` in `NON_REGISTRY_MODELOS`. UNVERIFIED flags
carried: exact M036 casilla numbers (122-124/127/131-133) and the exact
G313 certificate field list are from secondary summaries — pull the
post-2025 M036 PDF and the official G313 page before pinning ids.

### G9 — Canonical identity validator already ships

`cadrumo.core.identity` is the single validation authority:
`validate_spanish_tax_id` (`core/identity/_tax_id.py:34`),
`validate_identity` returning the `IdentityDocument` StrEnum
(`core/identity/_documents.py:257`), `nif_check_letter` (the sanctioned
mod-23 `TRWAGMYFPDXBNJZSQVHLCKE` table), with NIF / prefixed-NIF (NIE-style
K/L/M) / NIE / CIF branches. The identity pages REUSE this authority; the
coordinator-supplied algorithm spec (DNI mod-23; NIE prefix-substitution;
CIF even/odd-digit checksum with per-org-letter digit-vs-letter control;
NII = `ES` + NIF for VIES) serves as format-hint/failure-mode COPY content,
with the CIF letter-class split and org-letter set flagged design-level
pending a primary-source pass (RD 1065/2007 arts. 18-20; RD 1553/2005).
Observation for the audit backlog: `_tax_id.py` and `_documents.py` each
carry private `_validate_nif/_validate_nie/_validate_cif` implementations —
a possible internal duplication inside the same core package (not blocking
this stream; both are behind the one public facade).

### G10 — Swarm grounding map + direct censo verification (2026-07-23)

The 96-agent profile-integration map (coordinator scratchpad artefacts
`profile_shape_map.md` / `profile_domain_maps.md`) plus this stream's own
mandated direct reads yield the reconciliation facts:

- **Censo reality (verified directly, superseding G7's assumption):**
  `CensoSnapshot` / `CensoSnapshotService` / `CensoFactSet` DO NOT EXIST in
  `src/cadrumo` (rg: zero matches) — the whole snapshot substrate was
  deleted outright by the Update section of
  `2026-07-11-censo-operator-manual-enrolment-adr` (read in full this
  pass), which also retired the entire `censo pull/compare/apply` verb
  family onto `config profile edit`, re-seated
  `CensoSyncService.bound_raw_afectacion_ratio` onto operator-declared
  `vivienda_office` m² profile facts, and deleted the
  `CENSO_CORROBORATED` provenance member. That ADR explicitly leaves one
  door open: "re-seat compare/apply over an operator-entered fact set only
  if a real workflow needs the diff". Operator-entered censal facts are a
  NON-OFFICIAL evidence tier, never stamped AEAT-verified; the calendar
  keeps its `censo.enrolment_unverified` posture. `CENSO_REFRESHED` /
  `CENSO_APPLIED` exist only as enum members (`domain/buckets/_event.py:103`,
  zero emission sites) — dormant leftovers subject to
  `retired-enum-members-need-consumer-reconciliation`.
- **Profile persistence boundary (map §1/§5):** sole writer is
  `ProfileLifecycleService` (sequenced by `ProfileRepository`, PROFILE_*
  event co-emission pinned by `test_event_emission_contract.py`); partial
  writes go through `set_active_fields`/`persist_patch` onto live
  effective-dated `UserProfileFact` rows — there is NO draft/staging store.
  `TaxpayerProfile` cross-field legal validators fire at CONSTRUCTION
  (`taxpayer_profile_from_mapping`), so intermediate/incomplete state must
  never be promoted through it; `ProfileRepository._refuse_duplicate_tax_id`
  binds at profile mint. `ApoderadoService` representation is a SEPARATE
  encrypted namespace (`represented_nif`), not a profile fact.
- **Derived-fact injectors (map §4.2):** `resolve_profile_sourced_bindings`
  (`application/modelo/_profile_binding.py`) derives six classes of
  legally-mandated synthetic facts (`_inject_derived_marriage_facts`,
  `_family_facts`, `_minimo_descendientes_facts`,
  `_anualidades_eligibility_facts`, `_autonomic_deduccion_facts`,
  `_state_attribution_facts`; LIRPF arts. 58/61/64/75/81/81bis/82, Madrid
  DL 1/2010, M303 state attribution) from RAW fact shapes; descendant facts
  round-trip through `descendant_facts_from_list`/`descendant_list_from_facts`
  (`domain/contribuyente/_descendant_facts.py`).
- **Copy-assembly correction (map §5):** the schema↔locale leg is real
  (schema.toml fields carry `legal_refs`/`model_selectors`; locale parity
  gates enforce the four catalogues), but NO mechanism renders BOE corpus
  prose into wizard copy — the corpus grounds registry calculation values
  only. `tema-profile.toml` is `draft`, so no taxpayer-facing profile
  glossary concept ships yet.
- **Rename discipline (map §4.1/§4.4):** field paths are load-bearing
  string contracts across the 4-way binding (wizard `profile_key` ↔
  `schema.toml` path ↔ four locale catalogues ↔ registry binding
  selectors, 100-150+ TOMLs) plus the MCP harness `TAX_ID_FACT_PATH`
  constant; RE-SEQUENCING is safe, renames need one atomic sweep verified
  by `python -m cadrumo.locales scaffold --check` and
  `validate_user_profile_registry_contract`
  (`domain/user_profile/_registry_contract.py`).
- **Applicability:** `derive_modelo_applicability` already has two call
  sites (`_work_create_policy.py`, `_profile_readiness_gate.py`) whose
  relationship is unresolved — no third may be added.
- **Process:** the map and this pass are rg/direct-read only; the
  `vaultspec-rag` confirmation pass is still outstanding (service
  unreachable at verification time) and remains a pre-finalization gate.

### G11 — Raw handover reconciliation (2026-07-23, second delta)

Coordinator handed over the raw swarm corpus (scratchpad
`profile_shape_map.md`, `profile_domain_maps.md`,
`profile_raw_discovery_sites.md`, `censo_research.md`, plus the workflow
journal `wf_0d15a538-7d0/journal.jsonl` as the raw source of record; the
map was also persisted as vault audit
`2026-07-23-profile-setup-flow-integration-shape-audit`). New facts binding
the flow design:

- **Descendant gap:** `SETUP_FLOW` collects NO descendants today — they
  ride only the standalone `descendiente` CLI verb. Wizard descendant
  collection is therefore net-new scope. The exact persisted shape
  (verified directly, `domain/contribuyente/_descendant_facts.py:8-20`):
  `renta_family.descendiente.{n}.{birth_date, adoption_date, discapacidad,
  convivencia, custodia_compartida, meses_madre_trabajo, gastos_guarderia,
  nif}` (n 0-based) plus aggregates `renta_family.descendientes_count` and
  `renta_family.gastos_guarderia_reales_2024`, produced by
  `descendant_facts_from_list` / reloaded by `descendant_list_from_facts`.
- **Map correction:** `save_answers_to_profile` does not exist; the real
  wizard answer writers are `persist_answers` and `persist_patch`
  (`application/wizard/_persistence.py`).
- **Substrate D4 final form — "facts ARE the checkpoint":** the substrate
  defines a checkpoint PORT; the domain flow implements it by routing
  through `ProfileLifecycleService`/`set_active_fields` onto
  effective-dated `UserProfileFact` rows; cursor/staleness/deferred are
  DERIVED on resume (facts re-project to answers against the current
  definition; cursor = first unanswered visible question). No bespoke
  store, no stored fingerprint; cold-start create = early registration in
  an explicit setup-incomplete state with tax-id uniqueness at minting;
  discard erases via the lifecycle authority. Supersedes the earlier
  opaque-extension-payload checkpoint slot.

### G12 — Substrate raw-pass additions (2026-07-23, third delta)

Relayed from the substrate stream's full wizard-module read: the wizard
feeds two CORE registration slots — `register_wizard_catalogue`
(`application/wizard/_catalogue.py:1050`) and `register_project_answers`
(reverse answers projection) — that domain consumers read to avoid upward
imports; both must keep being fed across the re-sequence.
`verify_setup_answers` (`application/wizard/_verifier.py`) is a separate
cross-field gate (spouse / joint-taxation / monoparental, LIRPF art. 82)
from the ProfileKey requirement registry and re-homes into the substrate's
flow-scope validator slot. TWO `TaxpayerProfile` derivation paths already
coexist (`load_active_taxpayer_profile` vs `taxpayer_profile_from_mapping`)
— consolidation is plan scope; no third path. The `profile` namespace is a
dynamic translation root invisible to static locale scanning, so the
locales scaffold/parity gates must run on ANY question-set change.
`ProfileValidationService` schema-validates facts pre-persistence and
soft-tombstone delete semantics ride the lifecycle authority (consistent
with the route-through-`ProfileLifecycleService` ruling).

### G13 — G313/M036 primary-source pass (2026-07-23, supersedes G8's coverage claims)

Primary-source research (coordinator scratchpad `g313_research.md`; no
secondary sources behind any confirmed number):

- **G313 certificate — official field list** (AEAT "¿Qué certifica?" page,
  verbatim): domicilio fiscal; condición de residencia; NIF de los
  representantes; situación tributaria; actividades y locales; obligaciones
  periódicas. CORRECTION to G8: **representación IS certified** (the
  representative NIF is an explicit certificate field), so the cotejo can
  reconcile the representación axis from the artefact. **IRPF régimen stays
  UNVERIFIED**: plausibly inside the "situación tributaria" bucket, but no
  primary source decomposes that bucket per tax and no issued-certificate
  specimen was reachable — keep it operator-entry, assumption labelled. CSV
  verification mechanics also unverified.
- **M036 casillas — layer distinction** (read directly from BOE-A-2025-410,
  Orden HAC/1526/2024, Anexo I, pp. 4125-4142): the 122-124 / 127 / 131 /
  132-133 numbers from G8 are the page-1 "Causas de presentación"
  SECTION-SELECTOR checkboxes, not data fields. The DATA fields: domicilio
  A11-A25 (físicas) / B11-B25 (jurídicas) / C11-C25 (EP no residentes);
  actividades 400 descripción, 402 grupo/epígrafe IAE, 403 tipo, 404
  código, locales 405-499; IVA 500-599 with regímenes 510-576 (510
  general, 514-516 recargo, 550-568 simplificado, 534-572 agricultura,
  518-528 usados/agencias, 517-569 criterio de caja, 574-576 oro);
  IRPF 604-612 (604 objetiva, 605 renuncia, 606 revocación, 607 exclusión,
  608 directa normal, 609 directa simplificada); IS 620-654; IRNR 630-638;
  representantes checkbox 126 + data 300-334 / 350-384. NEW página 10
  "Titulares reales" (checkbox 145, codes 000-023; RD 117/2024 / Ley
  13/2023, LGT art. 93) — a censal axis with no current profile
  counterpart; enrolment is a follow-up ADR question, not silently
  droppable. M037 suppression and the 2025-02-03 entry into force
  re-confirmed against the BOE text.
- **Substrate `registered_values` handle** (relayed): `run_flow_tui`
  accepts a `Mapping[page_key, str]` rendered as a registered-value column
  on the review DataTable — the modify-mode projection of the active
  record's facts to page keys supplies it, giving staged-vs-on-record side
  by side.

## Sources

- Operator brief for the profile-setup epic (this stream's dispatch),
  2026-07-23 — the deficit list in F1 and the pull/cross-reference ask.
- `2026-07-11-censo-operator-manual-enrolment-adr` — live censo scrape
  retired; censal facts operator-manual (cited from the CLI-standard rule's
  worked example; the ADR body itself not re-read this pass).
- Project rules relied on: `aeat-cli-pull-and-file-standard`,
  `sensitive-financial-data-secure-storage-only`,
  `cli-notices-are-the-only-diagnostic-channel`, `no-legacy-compatibility`,
  `composition-service-no-parallel-write-path`,
  `aeat-architecture-boundaries`, `aeat-spanish-stem-naming`,
  `single-subject-mutation-is-idempotent-guarded`.
- UNVERIFIED (RAG unavailable; flagged inline): the wizard package layout
  under `src/cadrumo/application/wizard/`, the two-prompter canonical
  claim, `CensoSnapshot` / `CensoSnapshotService` / `CENSO_APPLIED`
  identifiers, and the satellite profile verb inventory. All from the
  dispatch brief and prior-session knowledge; must be confirmed by `rg` +
  RAG before the ADR is finalized.
