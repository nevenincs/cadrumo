---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace modelo-036-census-sync with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#modelo-036-census-sync'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-16'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]"
  - "[[2026-05-16-modelo-036-census-sync-research]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - The related: field carries the AUTHORISING documents (ADR, research,
       reference, prior plan) for every Step in this plan. Steps inherit this
       chain; per-row reference footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artefact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULT PLAN CLI:
     The `vault plan` CLI (vaultspec-core) is the canonical surface
     for structural manipulation of this plan document. Writers and
     executors MUST use `vault plan step add/insert/move/remove/
     check/uncheck/toggle/edit`, `vault plan phase add/move/remove/
     edit`, `vault plan wave add/move/remove/edit`, `vault plan epic
     intent`, and `vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `modelo-036-census-sync` plan

Land the live-synced census-data store for Modelo 036 against the
authorising ADR's 2026-05-16 amendment. AEAT is the binding legal
source of truth; the local profile is a cache that must be kept
honest. `aeat config profile census {refresh, show, compare, apply}`
gives operators a four-verb surface; `apply` cross-validates every
dependent calculation and stamps `CENSUS_STALE` on work units,
calculation revisions, filing drafts, and filing records that
referenced the prior census facts. The six downstream services
refuse with a typed `CensusStaleRefusedError` until the operator
re-runs `calculate` against the new census.

## Proposed Changes

Phases land in dependency order. Phase `P01` extends the
`user_profile/schema.toml` with the comprehensive census-field
delta, every field grounded in a primary BOE / LIRPF / LIVA /
RIRPF / RIVA citation. Phase `P02` mints the `CensusSnapshot`
domain model and the `CensusSnapshotService` mirroring the
existing `Borrador100SnapshotService` pattern. Phase `P03` lands
the sede G313 adapter that pulls the census through the existing
`_active_verified_session()` live-read gate. Phase `P04` mints
the `CensusSyncService` exposing the four operator verbs, plus
the new `BucketEventType` members and the `CensusSyncError`
hierarchy. Phase `P05` extends the six downstream services
(`calculate_modelo_revision`, `verify_modelo_revision`,
`file_modelo_revision`, `build_draft`, `approve_draft`,
`export_draft`) with the `CENSUS_STALE` refusal contract and the
cross-validation walker that stamps dependents. Phase `P06`
mounts the CLI verbs, scaffolds and translates the four-locale
help strings, and lands the surface tests. Phase `P07` ships the
legal-binding registry validator and the backend-boundary
regression that locks both invariants.

## Steps

### Phase `P01` - extend schema with legally-bound census fields

Land the comprehensive census-field delta with primary-source legal grounding for every new field.

- [ ] `P01.S01` - add fiscal-address cadastral reference and habitual-vivienda flag with TR Ley Catastro Art. 50 grounding; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S02` - add census section with activity_start_date and activity_end_date and RGAT grounding; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S03` - add census.establecimiento_type enum with Art. 28 and Art. 30 LIRPF grounding; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S04` - add census.elected_withholding_pct enum with LIRPF Art. 101.5 and RIRPF Art. 95.1 and Art. 95.2 grounding (BOE-A-2007-6820); `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S05` - add vivienda_office section with total_m2 and office_m2 and LIRPF Art. 30.2 rule 5 grounding (Ley 6/2017 BOE-A-2017-12544); `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S06` - wire activities.iae_epigraph into model_selectors so the field reaches AutonomoProfile; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S07` - add schema parser validation that every census field declares a legal_refs entry; `src/aeat/application/user_profile/_schema_loader.py`.
- [ ] `P01.S08` - extend autonomo_profile_from_mapping to surface the new census fields on AutonomoProfile; `src/aeat/domain/deadlines/_profiles.py`.
- [ ] `P01.S09` - add statutory_multiplier field to ProportionalityKind metadata so the legal arithmetic attaches to the Kind rather than per-category; `src/aeat/domain/categories/_proportionality.py`.
- [ ] `P01.S10` - split HOME_OFFICE category family into SUMINISTROS subkind (statutory_multiplier 0.30 LIRPF Art. 30.2 rule 5) and OWNERSHIP subkind (multiplier 1.0 raw afectacion); `src/aeat/domain/categories/_spending_category.py`.
- [ ] `P01.S11` - move SUMINISTROS_HOME_OFFICE_LUZ AGUA GAS INTERNET to USAGE_RATIO_HOME_AREA_SUMINISTROS kind; `src/aeat/domain/categories/_spending_category.py`.
- [ ] `P01.S12` - introduce AMORTIZACION_VIVIENDA_AFECTO IBI_VIVIENDA_AFECTO COMUNIDAD_VIVIENDA_AFECTO categories under USAGE_RATIO_HOME_AREA_OWNERSHIP kind; `src/aeat/domain/categories/_spending_category.py`.
- [ ] `P01.S13` - derive UsageRatioProfile entries for HOME_OFFICE categories from census vivienda_office raw ratio times the kind statutory_multiplier; `src/aeat/domain/usage_ratios/_service.py`.
- [ ] `P01.S14` - emit strong-warning event when a per-category ratios set override deviates from the census-derived value (the census is the binding legal source per the ADR amendment); `src/aeat/application/ledger/_ratios.py`.
- [ ] `P01.S15` - clean-break refuse-load: refuse to load any pre-existing UsageRatioProfile entry for a HOME_OFFICE category if vivienda_office is unset or if the stored value disagrees with the census-derived value; no shim no auto-migration; `src/aeat/domain/usage_ratios/_service.py`.
- [ ] `P01.S16` - apply the census-derived ratio at ledger classify and allocate transaction-classification time so business_pct on each Transaction carries the legally-correct value; `src/aeat/application/ledger/_actions.py`.
- [ ] `P01.S17` - schema-shape boundary tests for every new field; `src/aeat/application/user_profile/test_schema_census_fields.py`.
- [ ] `P01.S18` - real-behavior tests covering census-derived ratio per Kind override-warning emission and refuse-load clean-break; `src/aeat/domain/usage_ratios/test_census_derivation.py`.

### Phase `P02` - CensusSnapshot domain model and snapshot service

Mirror the Borrador100 snapshot pattern as the census-data persistence layer.

- [ ] `P02.S19` - add CensusSnapshot pydantic v2 model with content-addressed snapshot_id and state machine; `src/aeat/application/live/_census.py`.
- [ ] `P02.S20` - add CensusSnapshotState closed StrEnum with ACTIVE SUPERSEDED DISCARDED members; `src/aeat/application/live/_census.py`.
- [ ] `P02.S21` - add derive_census_snapshot_id helper hashing profile_id captured_at source_url and canonical-json census_facts; `src/aeat/application/live/_census.py`.
- [ ] `P02.S22` - add CensusSnapshotRepository over SecureObjectRepository under namespace aeat.application.live.census_snapshot; `src/aeat/application/live/_census.py`.
- [ ] `P02.S23` - add CensusSnapshotService.capture with auto-supersession of any prior ACTIVE for the same profile; `src/aeat/application/live/_census.py`.
- [ ] `P02.S24` - add CensusSnapshotService.latest_active and discard; `src/aeat/application/live/_census.py`.
- [ ] `P02.S25` - real-behavior tests for id derivation supersession and encrypted round-trip; `src/aeat/application/live/test_census_snapshot.py`.

### Phase `P03` - sede G313 adapter and provenance wiring

Land the live-gated census read against the Mis Datos Censales endpoint.

- [ ] `P03.S26` - add CensusFactSet strict pydantic envelope carrying every census field from the schema delta; `src/aeat/adapters/outbound/aeat/sede/_census.py`.
- [ ] `P03.S27` - add CensusSedeDriver mirroring the _renta_web_open driver structure; `src/aeat/adapters/outbound/aeat/sede/_census.py`.
- [ ] `P03.S28` - parse the G313 result page into a CensusFactSet refusing on unknown fields; `src/aeat/adapters/outbound/aeat/sede/_census.py`.
- [ ] `P03.S29` - persist the raw G313 HTML to the observation store for the audit trail; `src/aeat/adapters/outbound/aeat/sede/_census.py`.
- [ ] `P03.S30` - wire UserProfileFact.source aeat_census_read as the provenance tag for captured facts; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P03.S31` - real-behavior adapter test against a saved-HTML G313 fixture; `src/aeat/adapters/outbound/aeat/sede/test_census_driver.py`.

### Phase `P04` - CensusSyncService, new events, error hierarchy

Mint the operator-facing service plus the bucket-event and error machinery.

- [ ] `P04.S32` - add CENSUS_REFRESHED profile.census.refreshed to BucketEventType; `src/aeat/domain/buckets/_event.py`.
- [ ] `P04.S33` - add CENSUS_APPLIED profile.census.applied to BucketEventType; `src/aeat/domain/buckets/_event.py`.
- [ ] `P04.S34` - add CENSUS_DEPENDENT_STAMPED_STALE modelo.census.dependent_stamped_stale to BucketEventType; `src/aeat/domain/buckets/_event.py`.
- [ ] `P04.S35` - add CensusSyncError base plus CensusNotAvailableError CensusFieldValidationError CensusApplyConflictError; `src/aeat/application/profile/_census_errors.py`.
- [ ] `P04.S36` - register every new error in the application error registry; `src/aeat/core/errors/registry/_application.py`.
- [ ] `P04.S37` - add CensusProfileComparison pydantic envelope carrying the field-by-field comparison in operator-readable form; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P04.S38` - add CensusSyncService.refresh_census; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P04.S39` - add CensusSyncService.show_census; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P04.S40` - add CensusSyncService.compare_census_with_profile; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P04.S41` - add CensusSyncService.apply_census_to_profile that overwrites profile walks dependents stamps stale emits events; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P04.S42` - real-behavior service tests for each verb; `src/aeat/application/profile/test_census_sync.py`.

### Phase `P05` - stale-cascade refusals across six downstream services

Wire the CENSUS_STALE flag and refusal contract through every service that consumes census-derived facts.

- [ ] `P05.S43` - add census_stamped_stale_at and census_stale_reason fields to WorkUnit; `src/aeat/domain/modelos/_work_unit.py`.
- [ ] `P05.S44` - add the same fields to CalculationRevision; `src/aeat/domain/modelos/_calculation_revision.py`.
- [ ] `P05.S45` - add the same fields to FilingDraft; `src/aeat/domain/filing/_draft.py`.
- [ ] `P05.S46` - add the same fields to FilingRecord; `src/aeat/domain/modelos/_filing_record.py`.
- [ ] `P05.S47` - add CensusStaleRefusedError and register it in the domain error registry; `src/aeat/domain/modelos/_errors.py`.
- [ ] `P05.S48` - refuse on stale in calculate_modelo_revision; `src/aeat/application/modelo/_actions.py`.
- [ ] `P05.S49` - refuse on stale in verify_modelo_revision; `src/aeat/application/modelo/_actions.py`.
- [ ] `P05.S50` - refuse on stale in file_modelo_revision; `src/aeat/application/modelo/_actions.py`.
- [ ] `P05.S51` - refuse on stale in build_draft; `src/aeat/application/filing/__init__.py`.
- [ ] `P05.S52` - refuse on stale in approve_draft; `src/aeat/application/filing/_review.py`.
- [ ] `P05.S53` - refuse on stale in export_draft; `src/aeat/application/filing/_export.py`.
- [ ] `P05.S54` - add the cross-validation walker that apply_census_to_profile uses to enumerate every affected dependent; `src/aeat/application/profile/_census_sync.py`.
- [ ] `P05.S55` - real-behavior tests covering every refusal path; `src/aeat/application/modelo/test_census_stale_refusal.py`.

### Phase `P06` - mount CLI verbs, locales, surface tests

Operator-facing CLI surface in plain English with no programmer jargon.

- [ ] `P06.S56` - mount the aeat config profile census refresh verb; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [ ] `P06.S57` - mount the aeat config profile census show verb; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [ ] `P06.S58` - mount the aeat config profile census compare verb; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [ ] `P06.S59` - mount the aeat config profile census apply verb; `src/aeat/entrypoints/cli/_config/_profile_census.py`.
- [ ] `P06.S60` - scaffold locale entries via python -m aeat.locales scaffold; `src/aeat/locales/`.
- [ ] `P06.S61` - translate English help strings into operator-readable prose; `src/aeat/locales/en.yml`.
- [ ] `P06.S62` - translate the four sets into Spanish; `src/aeat/locales/es.yml`.
- [ ] `P06.S63` - translate the four sets into Catalan; `src/aeat/locales/ca.yml`.
- [ ] `P06.S64` - translate the four sets into Hungarian; `src/aeat/locales/hu.yml`.
- [ ] `P06.S65` - CLI surface tests for the refresh verb; `src/aeat/entrypoints/cli/test_profile_census_refresh_verb.py`.
- [ ] `P06.S66` - CLI surface tests for the show verb; `src/aeat/entrypoints/cli/test_profile_census_show_verb.py`.
- [ ] `P06.S67` - CLI surface tests for the compare verb; `src/aeat/entrypoints/cli/test_profile_census_compare_verb.py`.
- [ ] `P06.S68` - CLI surface tests for the apply verb covering walker stale events and refusal cascade; `src/aeat/entrypoints/cli/test_profile_census_apply_verb.py`.

### Phase `P07` - boundary regression and legal-binding validator

Lock the invariants the ADR amendment declares.

- [ ] `P07.S69` - registry validator unit test asserting every census field carries legal_refs; `src/aeat/_data/registry/aeat/user_profile/test_legal_grounding.py`.
- [ ] `P07.S70` - backend-boundary regression asserting CensusModeloFoundationCommand stays unimported by the CLI; `src/aeat/entrypoints/cli/test_backend_boundary.py`.
- [ ] `P07.S71` - boundary regression asserting CensusSyncService is the only CLI-facing census surface; `src/aeat/entrypoints/cli/test_backend_boundary.py`.
- [ ] `P07.S72` - CENSUS_STALE bypass regression attempting every refusal path; `src/aeat/application/modelo/test_census_stale_bypass_regression.py`.
- [ ] `P07.S73` - walker-coverage regression seeding every dependent catalogue and asserting every entry is stamped; `src/aeat/application/profile/test_census_apply_walker_coverage.py`.

## Parallelization

State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency.

## Verification

State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.
