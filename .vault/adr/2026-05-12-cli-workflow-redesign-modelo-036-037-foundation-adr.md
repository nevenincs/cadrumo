---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-research]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr]]"
---

# `cli-workflow-redesign` adr: `Modelo 036 and 037 foundation` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Census workflows are foundational for autónomos, but 036/037 registry files are
missing. The design must add a current Modelo 036 foundation while preserving
Modelo 037 only as historical, inactive metadata.

## Considerations

Modelo 036 is event-triggered rather than periodic: alta, modificación, and
baja happen when census state changes. Modelo 037 was suppressed from
2025-02-03 and must not remain an active workflow.

## Constraints

No portal-only support, setup wizard substitute, integer modelo codes, live
submission, or Modelo 037 active shim is allowed. Modelo codes remain strings
so leading-zero codes are preserved.

## Implementation

Add a Modelo 036 registry foundation with sectional decomposition, profile
bindings, and event-triggered work-unit lifecycle for `alta`, `modificacion`,
and `baja`.

Keep Modelo 037 as historical source metadata only, inactive and superseded by
036. Portal discovery may list historical 037 metadata, but `app modelo`
refuses new active 037 work units.

## Rationale

Census state belongs in the modelo/workflow system, not as a setup wizard
substitute. Treating 036 as registry-backed preserves traceability and lets
profile state derive from explicit census history.

## Consequences

The project gains a filing-grade foundation for census workflows without
reviving Modelo 037. Tests must cover string modelo codes, event-triggered
period semantics, and inactive 037 refusal.

## 2026-05-16 amendment — live-sync, stale-cascade, and legal-grounding contract

The original implementation framed 036 as a filing-lifecycle modelo whose
alta / modificación / baja states would be calculated, verified, and filed
through the existing modelo verb spine. Operator review during W85
discovery overturned that framing: 036 is a census-data record AEAT holds
about the operator, not a calculation the operator performs. The legally
correct mental model is that AEAT's census state is the binding source of
truth and the local profile must mirror it. This amendment locks that
shape.

### Locked decisions

- **036 is a live-synced census-data store, not a filing-lifecycle modelo.**
  The alta / modificación / baja periods in `036.toml` are AEAT-side event
  kinds, not local filing states. The local app never files a 036; the
  operator files it themselves at sede.agenciatributaria.gob.es and the
  local app reads the resulting census back from AEAT.

- **AEAT is the binding legal source of truth.** Any divergence between
  AEAT's census record and the local profile is resolved in AEAT's
  direction. The local profile is treated as a cache that must be kept
  honest against the upstream record.

- **CLI surface lives under `aeat config profile census`.** Four verbs:
  - `refresh` — pulls the current census from AEAT, persists a
    content-addressed snapshot, auto-supersedes any prior ACTIVE snapshot
    for the same profile, emits `CENSUS_REFRESHED`.
  - `show` — renders the latest ACTIVE snapshot in operator-readable
    form (every field labelled in plain language, no JSON-only output).
  - `compare` — renders the field-by-field comparison between the
    latest snapshot and the active local profile in plain operator
    language (no "diff" jargon).
  - `apply` — overwrites the local profile with the snapshot's values,
    cross-validates every dependent calculation, stamps the affected
    work units / calculation revisions / filing drafts / filing records
    as `CENSUS_STALE`, emits `CENSUS_APPLIED` plus per-dependent
    `CENSUS_DEPENDENT_STAMPED_STALE`.

- **Backend-boundary stays intact.** `CensusModeloFoundationCommand` and
  the rest of `src/aeat/domain/calculations/registry/_census_modelos.py`
  remain backend-owned (the existing
  `test_census_modelo_foundation_stays_backend_owned` regression keeps
  passing). The new `CensusSyncService` is the only CLI-accessible
  surface, layered on top of the foundation.

- **Snapshot lifecycle mirrors Borrador100.** `CensusSnapshot` is
  content-addressed (SHA-256 over profile_id + captured_at + source_url
  + census_facts), stored in encrypted SQLite under namespace
  `aeat.application.live.census_snapshot` with sensitivity `PII`, with
  a closed `ACTIVE` / `SUPERSEDED` / `DISCARDED` state machine.
  Re-fetch auto-supersedes the prior ACTIVE snapshot for the same
  profile. Caller emits the bucket event.

- **Stale-cascade contract on `apply`.** The service walks every
  active work unit, calculation revision, filing draft, and filing
  record in the active profile bucket. Every entry whose calculation
  snapshot referenced a now-superseded census fact is stamped with a
  `census_stamped_stale_at` timestamp plus a `census_stale_reason`
  string identifying which census fact changed. The six downstream
  services — `calculate_modelo_revision`, `verify_modelo_revision`,
  `file_modelo_revision`, `build_draft` (filing), `approve_draft`
  (filing), `export_draft` (filing) — refuse with a typed
  `CensusStaleRefusedError` until the operator re-runs `calculate`
  against the new census. The refusal message names the exact
  `aeat app modelo work calculate <id>` recovery command.

- **AEAT live-read surface.** The sede adapter targets G313
  (`/Sede/procedimientoini/G313.shtml`, Mis Datos Censales, CONSULTATION
  category — read-only). Authentication is gated through
  `_active_verified_session()` and uses the existing certificate or
  Cl@ve PIN / Cl@ve Permanente / DNIe paths (G313 does not accept
  Cl@ve Móvil per the portal entry). G322 (036 procedure, declaration)
  is out of scope for this wave because live writes are permanently
  forbidden by the safety-legal-gates rule. The `UserProfileFact.source`
  enum value `aeat_census_read` is now consumed (it had been reserved
  as a forward-declaration).

- **Comprehensive schema delta in one wave.** Every census field 036
  carries lands in `user_profile/schema.toml` in one wave, not iteratively.
  New fields include:
  - `contact.fiscal_address_cadastral_reference`
  - `contact.fiscal_address_is_habitual_vivienda` (bool flag)
  - new section `census`: `activity_start_date`, `activity_end_date`,
    `establecimiento_type` enum (own / rented / free local),
    `elected_withholding_pct` enum (1 / 7 / 15)
  - new section `vivienda_office`: `total_m2`, `office_m2` (the
    raw inputs that derive the `business_ratio` for the home-office
    category family)
  - `activities.iae_epigraph` is wired into `model_selectors` so the
    field actually reaches `AutonomoProfile` and the 036 binding layer
    (closes the existing dead-field bug discovered in W85 mapping).

- **Legal-grounding requirement.** Every census field that drives a
  downstream calculation MUST declare `legal_refs` in its schema entry
  pointing to the primary BOE / LIRPF / LIVA / RIRPF / RIVA / Ley
  General Tributaria source that fixes any cap, threshold, or
  applicability rule. Confirmed primary citations from the W85
  research doc:
  - `vivienda_office.office_m2 / total_m2` is the raw afectacion
    proportion. LIRPF Art. 30.2 rule 5 (Ley 6/2017 effective
    2018-01-01, BOE-A-2017-12544) governs how this ratio is applied:
    the raw ratio is used directly for ownership and amortization
    costs of the home, and is multiplied by 0.30 (a statutory factor,
    NOT a ceiling on the proportion) when deducting suministros
    (utilities). The engine MUST compute these two variants at
    calculation time; the schema stores the raw m2 inputs and the
    derived raw ratio only. There is no statutory cap on the raw
    ratio itself; the AEAT 2022 IRPF manual confirms this reading.
  - `census.elected_withholding_pct` enum values cite LIRPF Art.
    101.5 plus RIRPF Art. 95.1 and Art. 95.2 (BOE-A-2007-6820 as
    amended by BOE-A-2023-2023). The 15 % is the standard
    professional retention; the 7 % is the nuevos-profesionales rate
    for the year of alta plus the two following calendar years;
    the 1 % is the modulos transport carve-out per the annual
    Orden de Modulos (Orden HAC/1425/2025 for fiscal year 2026,
    BOE-A-2025-25272).
  - `iva.roi_enrolled` cites LIVA Art. 25 plus RIVA Art. 3
    (BOE-A-1992-28740 as amended).
  - `iva.oss_enrolled` cites LIVA Art. 163 unvicies (BOE-A-1992-28740
    as amended by Ley 4/2020).
  - `census.activity_start_date` and `census.activity_end_date`
    cite RGAT Arts. 9 and 11 (BOE-A-2007-15984).
  - `census.establecimiento_type` cites LIRPF Arts. 28 through 30
    (BOE-A-2006-20764).
  - `irpf.uses_objective_estimation` cites LIRPF Art. 31
    (BOE-A-2006-20764) plus the annual Orden de Modulos
    (Orden HAC/1425/2025 for fiscal year 2026, BOE-A-2025-25272).
  - `contact.fiscal_address_cadastral_reference` cites RDLeg 1/2004
    (BOE-A-2004-4163).
  - `contact.fiscal_address_is_habitual_vivienda` cites LIRPF Art.
    68.1.3 (BOE-A-2006-20764). The deduction itself is suppressed
    for vivienda acquisitions from 2013 onward but the habitual-
    residence concept remains operative for afectacion parcial.

  A registry validator added in this wave fails CI if a new census
  field lands without a `legal_refs` entry. The legally-grounded
  computation rules (the suministros 0.30 multiplier, the
  nuevos-profesionales three-year window for the 7 % withholding
  rate, the annual Orden de Modulos for modulos eligibility, etc.)
  are ENFORCED by the engine at calculation time; the schema carries
  the raw inputs and the engine applies the statutory arithmetic.

### New BucketEventType members

- `CENSUS_REFRESHED` (`profile.census.refreshed`) — emitted by `refresh`,
  payload carries the snapshot id and the AEAT source url.
- `CENSUS_APPLIED` (`profile.census.applied`) — emitted by `apply`,
  payload lists the count of stamped dependents by kind.
- `CENSUS_DEPENDENT_STAMPED_STALE`
  (`modelo.census.dependent_stamped_stale`) — emitted once per stamped
  dependent, scoped to the dependent's object id, payload names the
  census fact that changed.

### New error hierarchy

Under `src/aeat/application/profile/_census_errors.py`:

- `CensusSyncError` — base.
- `CensusNotAvailableError` — sede returned no parseable census
  (operator likely not enrolled in IAE yet, or G313 authentication
  failed at AEAT side).
- `CensusFieldValidationError` — sede returned a value the schema
  cannot accept (out-of-range withholding %, unknown establecimiento
  type, etc.).
- `CensusApplyConflictError` — `apply` aborted because a dependent's
  state cannot be safely stamped (e.g. an in-flight workflow run on the
  dependent).

Plus `CensusStaleRefusedError` under the modelo error family (raised by
the six downstream services).

### 037 stays inert

This amendment reaffirms that 037 carries no live surface, no CLI
verb, and no sync path. It remains historical-metadata-only per the
original ADR, superseded by 036 from 2025-02-03 (Orden HAC/1526/2024,
BOE-A-2025-410).
