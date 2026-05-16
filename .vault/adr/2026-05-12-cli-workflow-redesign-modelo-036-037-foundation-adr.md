---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
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
  applicability rule. Examples:
  - `vivienda_office.office_m2 / total_m2` ratio cap (the home-office
    deduction has a hard ceiling per Art. 22 RIRPF / Art. 30.2.5
    LIRPF — verify the exact 30 % default in the W85 research doc).
  - `census.elected_withholding_pct` enum values (1 % / 7 % / 15 %)
    each cite the LIRPF article that defines them (Art. 95 LIRPF +
    Art. 101 RIRPF for the standard 15 % retention, the 7 % new-
    autónomo reduction, and the 1 % módulos transport carve-out).
  - `iva.roi_enrolled` cites Art. 25 LIVA + RIVA Art. 3.
  A registry validator added in this wave fails CI if a new census
  field lands without a `legal_refs` entry. Caps and thresholds are
  ENFORCED by the engine, not merely documented; the
  `business_ratio` for HOME_OFFICE categories is clamped to the
  legally-derived ceiling.

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
