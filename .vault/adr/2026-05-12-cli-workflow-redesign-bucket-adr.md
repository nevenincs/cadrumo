---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace cli-workflow-redesign with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#cli-workflow-redesign'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-12'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-12-cli-design-research]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-workflow-redesign` adr: `Profile-scoped bucket storage invariant` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The current `archive` term is misleading for the product data model. The
implemented subsystem exports and restores selected secure-object namespaces as
a portable bundle. That is useful infrastructure, but it does not express the
product concept the CLI needs: a profile-scoped data bucket that owns the active
profile's operational data and calculation history.

This ADR records only the bucket decision. Other CLI workflow redesign decisions
must be recorded in separate ADRs as they are approved.

## Considerations

- Domain ownership by bucket-backed system:
  - `ledger` owns incoming/expense transaction history, enrichments,
    classification, attachments, VAT/IRPF inputs, and proportionality inputs.
  - `profile` owns current profile identity/legal/tax/address context, active
    bucket selection, and calculation-context profile facts.
  - `modelo` owns calculation work units, calculation engine execution,
    verification, internal filing, filing-record ownership, and local
    filing/export status transitions.
  - `bucket` owns storage identity and persistence/lifecycle concerns; it is
    not normal operator workflow UX.
- `aeat app` domains consume the active bucket and execute workflow, while
  bucket-level operations remain storage maintenance surfaces.
- A bucket is the profile-scoped storage slice. It is not a backup archive and
  not a loose namespace bundle.
- Bucket management is a `config` responsibility. The approved command surface
  is `aeat config bucket`, not `aeat app bucket`.
- `aeat config bucket` is a storage modification, recovery, and inspection
  surface. It is not the normal operational UX for ledger or modelo work.
- Normal UX should not require users to touch buckets directly; `app` domains
  drive the contents of the active bucket through backend services.
- Profile data itself must live inside the profile's bucket.
- Live AEAT submission remains disabled. Bucket-backed internal filing state
  must not imply live submission.

## Constraints

- Profile data itself must be stored inside the profile's bucket.
- A bucket must be created atomically when a profile is created.
- Application data writes must resolve through the active profile's bucket.
- Persisted operational records must be bucket-linked where applicable.
- Bucket display names may change; bucket identity must remain stable for data
  links and audit trails.
- The secure storage backend and SQL schemas must be hardened so linked data is
  protected by explicit relationships, not accidental namespace grouping.
- Existing `archive` code must not remain in operator CLI registration,
  command discovery, or public help. Any storage migration is backend/internal
  only and does not create a compatibility surface.

## Implementation

The `archive` product surface is rejected for profile-scoped data management.
Its replacement is:

- `aeat config bucket`

`aeat config bucket` owns profile-scoped storage management. These are
storage-level operations for inspection, portability, recovery, and explicit
maintenance, not day-to-day ledger or modelo workflow commands:

- browse bucket contents
- search bucket contents
- export bucket data
- import bucket data
- rename bucket display metadata
- delete bucket data subject to explicit destructive safeguards

Bucket semantics:

- `bucket_id` is the stable storage identity.
- profile name and bucket name are editable labels.
- profile creation creates the bucket and writes the profile record into it.
- active profile selection selects the active bucket.
- normal app workflows create and modify bucket contents without requiring
  direct bucket commands.
- ledger financial transaction, payable invoice, collectible invoice, purchase
  invoice evidence, modelo, calculation, bucket-event, and generated-artifact
  records must be associated with a bucket before they are considered product
  data.

Modelo semantics reflected by follow-up ADRs:

- modelo work units are keyed by bucket, year, period, modelo, and modelo
  revision.
- internal "filed" state means a complete verified modelo revision is marked as
  current inside the local bucket.
- this state is not live submission.
- live-compatible export is separate from internal filing state and must not
  imply live AEAT submission.

`aeat app` and `aeat config` are the only top-level redesigned roots for
operator use:

- `aeat config`: profile lifecycle, bucket lifecycle (`aeat config bucket`),
  first-run/setup/init migration, and other durable environment/configuration
  state.
- `aeat app`: operational tax workflows such as ledger financial transaction,
  payable invoice, collectible invoice, purchase invoice evidence, modelo,
  status, and list views over the active bucket.
- `aeat app` must not introduce `bucket`, `setup`, `archive`, or other
  storage-maintenance verbs.

## Rationale

The bucket abstraction is necessary because the product's real data boundary is
not the command name and not the current secure-object namespace. It is the
active profile's complete data slice. Ledger financial transaction history,
purchase invoice evidence links, payable invoices, collectible invoices, profile
values, modelo calculations, and internal filing decisions must be recoverable
and auditable as one coherent scoped dataset.

Rejecting `archive` as a user-facing term prevents backup/import/export
infrastructure from defining the product workflow. Users should not need to
understand secure-object namespaces to understand which profile's data they are
moving, browsing, or deleting.

## Bucket-link migration scope

Bucket-linkage is universal. The following persistence layers gain bucket
scoping (column, foreign key, and bucket-resolution lookup) before any
operator-facing `app` verb consumes them through the redesigned tree:

- secure-object repository (the foundation for all encrypted persistence)
- workflow-state repository (active profile, profile facts, calculation-context
  cache)
- transaction catalogue repository (`ledger_transaction` records)
- invoices catalogue repository, split into `payable_invoice`,
  `collectible_invoice`, and `purchase_invoice_evidence` repositories per the
  invoice-domain-decoupling decision)
- filing-draft repository
- filing-history repository
- submission repository
- rental-finca / rental-contract / amortization-ledger repositories
- assets-ledger repository, inventory-ledger repository

Implementation order is: secure-object foundation first; workflow-state and
ledger together; invoice/evidence split per the source-kind taxonomy; modelo
filing and submission repositories; rental and assets ledgers last. Each step
lands its own plan + exec record; this ADR fixes the scope.

## Consequences

- root `aeat archive` is removed in favor of `aeat config bucket`.
- archive bundle behavior moves under `aeat config bucket`; old archive
  entrypoints do not remain executable.
- storage migrations are required for each persistence layer named in the
  bucket-link migration scope above; the redesigned operator tree must not
  consume a non-bucket-linked repository.
- SQL schemas and secure-object repositories must be audited for bucket
  relationship integrity.
- CLI copy must reserve "submission" and live-filing language for live AEAT
  interactions, which remain disabled.
- Product UX must keep direct bucket operations out of the normal operator path
  unless the user is inspecting, moving, recovering, renaming, or deleting
  storage.
- Root exposure is decided in this ADR: redesigned operator UX remains at
  `aeat config` and `aeat app`.
- Legacy entrypoints `aeat setup*`, `aeat archive*`, and equivalent legacy
  roots or aliases must be removed from operator CLI registration, command
  discovery, and supported public help. Backend/internal data migrations may
  exist only outside user-facing CLI surfaces.
- The exact `config` tree is locked by the config-init-shape, config-auth-
  shape, config-doctor-shape, and config-cli-profile-surface ADRs. The exact
  `app` command tree is locked by the app-modelo-shape, app-modelo-bindings-
  shape, app-overview-shape, app-ledger-ratios-shape, app-live-shape, app-
  registry-boundary, and app-review-queue-execution ADRs. Bucket schema
  migration and ledger-to-modelo calculation data flow are tracked in the
  execution plan, not in additional ADRs.

## 2026-05-15 amendment - bucket maintenance verbs

The 2026-05-15 ground-truth audit found `BucketMaintenanceService` and
the prescribed maintenance verbs entirely absent from the codebase
despite the W77 closure claim. This amendment locks the maintenance
surface so the gap is closed in a follow-up wave.

Required application-layer surface: a `BucketMaintenanceService` under
`src/aeat/application/bucket_maintenance/` exposing six lifecycle-state
methods on the active profile bucket:

- `browse(bucket_id, namespace_filter=None, cursor=None)` - paginated
  listing of bucket contents grouped by namespace; respects
  `SensitivityClass` redaction policy.
- `search(query, scope=None)` - attribute / payload search; returns
  ranked rows with match metadata.
- `export(bucket_id, output_path)` - portable encrypted archive with
  manifest + checksums; emits `bucket.exported` bucket event.
- `import(source_path, force_replace=False)` - validates manifest +
  checksums; refuses identity collision unless `force_replace`; emits
  `bucket.imported`.
- `rename(bucket_id, new_display_name)` - mutates display name only;
  bucket id is stable; emits `bucket.renamed` with old / new payload.
- `delete(bucket_id, confirmed=False)` - destructive erase; refuses
  unless `confirmed=True`; emits `bucket.deleted` event before erase.

Required CLI surface: `aeat config bucket {browse, search, export,
import, rename, delete}` as thin handlers under the existing
`bucket_app` Typer group. All handlers MUST delegate to the service,
render via `_emit`, route errors through `command_error_boundary`.

Required `BucketEventType` additions: `BUCKET_EXPORTED`,
`BUCKET_IMPORTED`, `BUCKET_RENAMED`, `BUCKET_DELETED`. The maintenance
verbs are documented as **lifecycle-state operations** under W71's
contract, not CRUD verbs (browse / search are key-value queries on
container contents; export / import / rename / delete operate on the
container itself).

Destructive-action protocol: `delete` requires explicit `--yes` flag at
the CLI boundary; the service refuses without `confirmed=True`. Active
profile bucket cannot be deleted until the operator switches profiles
first.
