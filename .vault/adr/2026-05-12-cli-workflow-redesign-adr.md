---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-inventory-placement-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-actor-attribution-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-borrador-snapshot-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-profile-keys-discovery-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-ratios-eligible-and-validate-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-explain-legal-ref-convention-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-audit-research]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-audit]]"
  - "[[2026-05-14-cli-workflow-redesign-dev-environment-uv-windows-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-error-registry-exhaustiveness-invariant-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-list-vs-query-leaf-semantics-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr]]"
  - "[[2026-05-12-cli-design-research]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-04-30-inventory-management-cli-design-adr]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
---

> **Updated 2026-05-19**: Module-path mentions of domain/vat/_classification.py and domain/vat/_oss.py in the backend exit-cap inventory, plus the domain/vat legal prorrata substrate reference in the functional gap inventory, follow the Spanish-stem terminology authority: domain/vat migrates into domain/iva. The CLI verb tree, root-command contract, phantom-family adjudication, and backend exit-cap inventory shape are unaffected.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.




# `cli-workflow-redesign` adr: `Apex CLI design: root contract, mini-app requirements, per-modelo requirements, backend exit-cap inventory` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The `cli-workflow-redesign` feature has produced ten focused ADRs that lock
individual decisions (bucket, bucket event history, ledger transaction
management, invoice domain decoupling, modelo work units, modelo calculate
revisions, modelo verify, verified complete, modelo file, modelo filing
record). Each ADR is correct in isolation, but the team has no single document
that:

- Restates the root contract as a single enforced shape.
- Declares the complete mini-app requirements for every redesigned domain
  surface, not just bucket and modelo.
- Declares the per-modelo workflow requirements, including modelo-specific
  data flows, source-kind dependencies, and missing modelos.
- Inventories the backend capabilities that already exist but lack a CLI
  exit-cap (a user-visible verb).
- Adjudicates the phantom command families surfaced by the operator-journey
  audits (`status`, `compare`, `audit` evidence, `backlog`, `data
  require/readiness`).
- Tracks implementation mandates required by the accepted ADR decisions.

This apex ADR exists to be that single document. It is intentionally an
evolving artifact: as new child ADRs land, this apex must be updated to
reference them, surface their requirements into the affected mini-app or
per-modelo section, and shrink the list of open questions.

## Considerations

- The ten child ADRs already accepted define the **bucket + modelo + ledger**
  axis. They do not define the rest of the redesigned tree.
- The bucket ADR locks the root surface to exactly two roots: `aeat config`
  and `aeat app`. This apex enforces that contract uniformly and inventories
  every remaining domain against it.
- The ledger-transaction-management ADR removes the generic `invoice` family
  from operator UX, replaces it with canonical `app ledger` verbs, and routes
  purchase invoice evidence under ledger.
- The invoice-domain-decoupling ADR splits the historical generic `invoice`
  concept into four source kinds: `ledger_transaction`,
  `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`.
  Every mini-app and per-modelo section in this apex must honor that
  taxonomy.
- The bucket-event-history ADR mandates append-only event history for every
  material state transition, requires app status/list views to surface event
  context, and places history browsing at `aeat config profile history PROFILE`.
- Five accepted ADRs outside the redesign series are required pre-conditions
  for the redesign to land:
  - `config-cli-profile-surface` (2026-05-07) defines `aeat config profile`
    and removes `aeat setup profile`. Execution missing.
  - `inventory-management-cli-design` (2026-04-30) defines the inventory
    surface. Execution missing.
  - `unified-review-queue` (2026-04-18) defines a cross-domain review
    surface. Skeleton only.
  - `modelo-file` (2026-05-12) defines the internal-filing approval verb.
    Not yet registered in the modelo CLI.
  - The 2026-05-10 user CLI retirement plan removes the legacy
    `application/user_cli.py` boundary module. Draft.
- The Python backend already contains workflow, submission, reconciliation,
  filing history, complementaria, notifications, expedientes, NIF-IVA,
  datos-fiscales, GROI, and rental capabilities with zero user-visible CLI
  verbs. Every one of those exit-caps must be assigned a verb here or
  explicitly deferred to a follow-up ADR.
- The Python backend lacks: festivos / business-day deadline shift, IVA
  prorrata under arts. 101/103 LIVA, foreign-currency normalization,
  retenciones aggregation pipeline, 347 / 349 counterpart aggregation
  pipeline, BOE-format libro exporters, apoderamientos representation
  surface, DNI-e smart-card driver, modelos 036/037/145. These are
  functional gaps that the apex must surface but not design here.
- Vault dev-history audits surface phantom command families (`status`,
  `compare`, `audit`, `backlog`, `data require`) that are treated as
  canonical UX in roleplay audits but do not exist in code. Each phantom
  family must be adopted or retired by name.

## Constraints

- Live AEAT submission is permanently forbidden. No verb in this apex
  performs or implies live AEAT filing. No empty or fail-fast submitter support
  layer is permitted; live submission is absent from operator CLI
  registration, discovery, and help, and the access gate enforces refusal at
  backend boundaries.
- Root surfaces are exactly two: `aeat config` and `aeat app`. No third
  root may be introduced. Legacy roots (`setup`, `archive`, `deadlines`,
  `financial`, `filing`, `browser`, `data`, `sanitize`, `llm`) must be
  retired or folded under `config`/`app`.
- Bucket scoping is universal. Every persisted mutation must be bucket-
  linked and must emit a bucket event.
- Source kinds are restricted to `ledger_transaction`,
  `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`.
  CLI copy and event payloads must use these names.
- Modelo lifecycle is `calculate → verify → file`, with immutable verified
  and filed revisions and a paired filing record.
- `aeat app` must not introduce `bucket`, `setup`, `archive`, or other
  storage-maintenance verbs.
- CLI grammar is verb-noun. Every command supports `--format json`. Output
  rendering uses the `_emit` helper pattern (no Rich-only surfaces).
- Profile reads use workflow state only to identify the active profile
  pointer. `WorkflowState.profiles` stores pointer records such as
  `{ "bucket_id": profile_name }`; profile values themselves live only in
  `PROFILE_BUCKET_NAMESPACE = "aeat.application.profile.bucket"` as
  `Envelope[ProfileBucket]` with `SensitivityClass.IDENTITY`, loaded
  through `profile_bucket_repository().load(...)` from
  `state.active_profile_record()`.
- This apex is the complete CLI contract. The `related` frontmatter must be
  kept current as additional implementation records, audits, and execution
  plans land.

## Implementation

The body below is organised as the CLI design: root contract,
cross-cutting decisions, `config` mini-apps, `app` mini-apps, per-modelo
requirements, backend exit-cap inventory, phantom-family adjudication,
functional-gap inventory, and implementation mandates.

Sections marked "locked" reference the accepted child ADRs they restate.
ADR status is design status only: it records the interface and architecture the
project implements. Implementation tracking belongs in plans and execution
records, not in compatibility aliases or support surfaces.

### 1. Root tree contract (locked by bucket ADR)

- `aeat config`: profile lifecycle, first-run/init migration, durable
  environment/configuration state, and profile-named storage diagnostics.
  Storage lifecycle services remain backend/application surfaces unless a
  profile-named operator design is accepted.
- `aeat app`: operational tax workflow. Ledger transactions, payable and
  collectible invoices, purchase invoice evidence, modelo, status, and
  list views over the active bucket.
- No other root is permitted. Historical roots and misplaced app surfaces are
  removed from operator UX. Required migration is backend/internal data
  migration only and is never imported into user-facing CLI commands,
  discovery, or help.

**Fold-under map.** The retired roots resolve as:

- `aeat setup` → `aeat config` (profile, auth, init, status).
- `aeat archive` → retired. Export/import/browse are backend bucket-maintenance
  service operations until a profile-named operator surface is accepted.
- `aeat deadlines` → `aeat app overview` (calendar, agenda, explain).
- `aeat financial` → split across `aeat app ledger` (ingest, txs,
  classification, ratios) and hard removal of the old invoice surface.
- `aeat filing` → `aeat app modelo` (calculate, verify, file, amend,
  reconcile, export, import, filing-record, history). The unmounted
  `filing/__init__.py` becomes implementation harvest only.
- `aeat browser` → `aeat config repair connectivity` (health probe folded
  into the diagnostics surface).
- `aeat data` (ledgers/inventory) → `aeat app ledger inventory`. `data`
  is retired, not aliased. `app modelo` may consume inventory-derived
  readiness but does not own mutating inventory commands.
- `aeat sanitize`, `aeat llm` — empty packages, retired with no replacement.
  Their backing adapters (`adapters/inbound/sanitizer/`, `adapters/outbound/
  llm/`) retire with the operator surface unless explicitly refactored into
  a named application capability.
- `aeat app topic` — the topic module wired at root and under `app` is
  retired from operator UX. Topic/help content moves to inline
  command help and the `aeat app registry citations` / `manuals` surface.
  No `aeat help` or `aeat topic` root verb survives.

### 2. Cross-cutting decisions

- **Bucket scoping (locked).** Every persisted record is bucket-linked.
  Bucket identity is `bucket_id`. Profile creation creates the bucket.
  Active profile selection selects the active bucket.
- **Bucket event history (locked).** Every domain service emits append-only
  events with timestamp, event type, actor/source, command context, and
  affected object references. App status/list views render event summaries
  with at minimum: timestamp, type, object type, object id/revision,
  actor/source, outcome.
- **Source-kind taxonomy (locked).** Four kinds: `ledger_transaction`,
  `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`.
  Bare `invoice` is forbidden in CLI copy.
- **Live-AEAT charter (locked).** Submission is permanently forbidden. The
  operator CLI exposes no submitter support layer; the access-gate error class
  enforces refusal at backend boundaries.
- **Output rendering (locked).** Every retained command accepts
  `ctx: typer.Context` and renders via `_emit(ctx, payload, lines)`.
  Root `--format json|text` is the only output selector. Rich-only
  retained surfaces, command-local `--json`, bespoke JSON emitters, and
  NDJSON are rejected.
- **Profile read path (locked).** All command surfaces use workflow state
  only to identify the active profile pointer. `WorkflowState.profiles`
  stores pointer records such as `{ "bucket_id": profile_name }`; profile
  values live only in `PROFILE_BUCKET_NAMESPACE =
  "aeat.application.profile.bucket"` as `Envelope[ProfileBucket]` with
  `SensitivityClass.IDENTITY`, loaded through
  `profile_bucket_repository().load(...)` from
  `state.active_profile_record()`. `--profile PATH`,
  `AEAT_DEFAULT_PROFILE_PATH`, flat-file fallback reads, dual read paths,
  and profile-envelope compatibility surfaces are rejected.
- **CLI observability wrapping (locked).** `_observability.py` helpers are
  retired from the CLI redesign. Bucket event history owns material
  state-transition audit; evidence bundles own evidence-case replay.
  Generic run/replay ids are not root UX.
- **I18n contract (locked elsewhere).** Per the quadlingual-i18n ADR,
  command copy must be externalized and translatable. No bare strings in
  new command code.
- **Active-profile safety (locked, apex review 2026-05-12).** The active
  profile is the implicit identity for every `aeat app *` command. The
  redesigned tree treats cross-profile contamination as a P0 risk and
  enforces three guards:
  - Every `aeat app *` text-format output prints a header line containing
    the active profile's display name and NIF. The header is mandatory; it
    is not a verbosity-controlled detail.
  - Every `aeat app *` JSON-format output carries `active_profile` and
    `bucket_id` fields at the envelope level.
  - `aeat config profile set active NAME` emits a confirmation in both
    text and JSON output that includes the prior active profile, the new
    active profile, and the bucket id. When a recent switch (≤ 30 seconds,
    measured against the latest `profile.activated` bucket event) is
    followed by an `aeat app *` mutation, the mutation command prints a
    one-line "active profile was last switched at TIMESTAMP" notice on
    stderr before executing.
  - The convenience verb `aeat config profile use NAME` is the short form
    of `aeat config profile set active NAME` (the two are aliases). No
    `aeat switch`, `aeat use`, or other root-level shortcut is permitted;
    the HARD RULE restricts root to `config` + `app` only.
- **CLI source-kind aliases (locked, apex review 2026-05-12).** Where
  source-kind values appear as CLI flag inputs, short-form aliases are
  accepted at the parser boundary (`lt`/`pie`/`pi`/`ci` for
  `ledger_transaction` / `purchase_invoice_evidence` / `payable_invoice` /
  `collectible_invoice`). Help text, JSON output, event payloads, and
  storage columns always emit the canonical name. Aliases are not domain
  synonyms.
- **Active-profile per-command override (rejected, apex review
  2026-05-12).** A per-command `--profile PATH` or `--as PROFILE` override
  was considered for the gestoría use case and rejected. The risk surface
  (one command running against a non-active profile) is larger than the
  ergonomic gain. The convenience verb `config profile use NAME` plus
  mandatory active-profile header in `app` output is the alternative;
  gestoría workflows are expected to switch explicitly before each client
  batch and to confirm via the output header.

### 3. `aeat config` mini-app requirements

The `config` surface is a storage, identity, environment, and diagnostics
surface. Its sub-mini-apps are:

#### 3.1 `aeat config init` (locked by config-init-shape ADR)

First-run configuration and backend/internal setup-state migration entry point.

Canonical command:

```text
aeat config init [--profile NAME]
                 --tax-id NIF
                 --activity TEXT
                 --iva-regime REGIME
                 [--tax-residence CCAA]
                 [--auth-provider certificate|clave_movil|none]
                 [--certificate-path PATH]
                 [--certificate-password-env VAR]
                 [--output-language LANG]
                 [--drafts-dir PATH]
                 [--submissions-dir PATH]
                 [--manuals-root PATH]
                 [--from PATH]
                 [--non-interactive]
                 [--dry-run]
                 [--format json|text]
```

`config init` creates the user's first bucket atomically with profile record
creation, selects the active profile/bucket, validates readiness, and runs
backend/internal migration for pre-existing `setup`-mounted state without
exposing old CLI roots.

Required events: `bucket.created`, `profile.created`, `profile.activated`,
`profile.updated`, `auth.provider.configured`, optional `config.env.updated`,
and backend-only `setup.state.migrated`.

`SetupWizard` is not exposed as `config init wizard`. It is retired as a
command backend unless refactored onto the bucket/profile init service; only
typed answers, prompter abstraction, and verifier checks may be salvaged.

#### 3.2 `aeat config profile` (locked elsewhere — needs execution)

Profile lifecycle. The 2026-05-07 `config-cli-profile-surface` ADR is
accepted but unexecuted. Required verbs per that ADR:

- `add`, `remove`, `edit`, `list`, `show`, `get`, `set`, `unset`,
  `duplicate`, `export`, `import`, `validate`, `preflight`.

Apex requirements that extend the 2026-05-07 ADR:

- PROFILE_KEYS schema must cover IVA / IRPF / regime / SII / Verifactu /
  ROI / intracomunitario axes (UX-007). Today `iva.regime` returns
  "Clave de perfil desconocida".
- Every profile mutation emits a bucket event (`profile.set`,
  `profile.unset`, `profile.activated`, `profile.imported`,
  `profile.exported`).
- `aeat setup profile` is removed from public help when this lands. No alias
  to old entrypoints remains.

#### 3.3 `aeat config auth` (locked by config-auth-shape + apoderamientos-surface ADRs)

AEAT Sede authentication provider configuration and session maintenance.

Canonical verb tree:

- `providers [--format json|text]`
- `configure --provider certificate|clave_movil|clave_pin|clave_permanente|dnie_pkcs [provider flags] [--format json|text]`
- `status [--provider PROVIDER] [--format json|text]`
- `test [--provider PROVIDER] [--format json|text]`
- `clear [--provider PROVIDER|--all] [--sessions] [--locks] [--format json|text]`
- `apoderado status [--format json|text]`
- `apoderado configure --represented-nif NIF --scope SCOPE [--format json|text]`
- `apoderado clear [--format json|text]`
- `apoderado check [--format json|text]`

Implemented providers: `certificate`, `clave_movil`.

Reserved provider slots: `clave_pin`, `clave_permanente`, `dnie_pkcs`. These
may be listed as reserved/unavailable, but configuration attempts fail closed
for unavailable providers.

Google OAuth is not an AEAT Sede auth provider and belongs under
`aeat config google` per the Google OAuth ADR.

Apoderado / representative identity selection is local configuration plus
read-only live checks. `configure` and `clear` mutate bucket-scoped auth
configuration and emit auth events. `check` is read-only live verification
and calls `require_live_read()` before remote contact. Live apoderamiento
registration, extension, revocation, confirmation, renunciation, or filing
as representative shortcuts are rejected.

Migration: `aeat setup auth`, top-level `aeat auth`, and all aliases/shims are
removed from operator UX.

#### 3.4 Profile storage maintenance (backend/application locked)

Storage-level bucket management is no longer an operator-facing `config bucket`
command group. The backend/application lifecycle operations are:

- `browse`, `export`, `import`, `rename`, `delete` (with destructive
  safeguards).
- `search` is deferred to the accepted bucket-search ADR and must route through
  domain repositories rather than scanning secure-object ciphertext directly.

Bucket semantics, identity, and the relationship between bucket and active
profile are restated in §2. Future operator exposure must use profile-named
vocabulary and consume the application service.

#### 3.5 `aeat config profile history PROFILE` (locked)

Append-only event history view per bucket-event-history ADR. Verbs:

- `list` (with filters: by event type, object kind, period, actor).
- `show <event_id>` (full payload, deep-link to affected object).
- `export` (for audit handoff).

Event payloads are versioned. Stable rendering for stable history output.

#### 3.6 `aeat config repair` (locked by config-repair-shape ADR, supersedes config-doctor-shape ADR)

Configuration health, storage integrity, secure-object inventory, persisted
maintenance (quarantine, workflow-state reset), and recent logs surface.

The namespace is named for the operator's vocabulary, not the maintenance
taxonomy: first-time users blocked by a stuck install reach for "repair" or
"fix", not "doctor". Diagnose and act share one root because the operator's
mental model is unified; safety is preserved by requiring explicit `--yes`
on the mutating subcommands.

Canonical commands:

```text
aeat config repair [--format json|text]

aeat config repair connectivity
    [--target browser|auth|sede|all]
    [--format json|text]

aeat config repair integrity
    [--namespace NAMESPACE]
    [--format json|text]

aeat config repair list <namespace>
    [--all|--unreadable]
    [--format json|text]

aeat config repair quarantine
    [--namespace NAMESPACE]
    [--dry-run]
    --yes
    [--format json|text]

aeat config repair reset-state
    [--dry-run]
    --yes
    [--format json|text]

aeat config repair logs
    [--lines N]
    [--format json|text]
```

`connectivity` absorbs the historical browser health probe.
`integrity` and `list` expose AES-256-GCM secure-object tag-verification
and namespace inventory. `quarantine` is bucket-scoped and emits
`secure_object.quarantined`. `reset-state` drops the single unreadable
`WorkflowState` envelope (namespace `aeat.workflow`, key `state`) and
emits `workflow_state.reset`; it touches no other namespace.

The bare `aeat config repair` invocation (no subcommand) runs the
composite health report — `connectivity`, `integrity`, registry load,
secure-state load, profile and auth readiness, and recent logs — as a
single rollup. This is the canonical "is everything OK?" entry point.

Every diagnostic row whose status is `fail` or `warn` MUST populate
either `next_action` (a runnable `aeat …` command string) or `dead_end`
(a short reason no automated route exists). This is a Pydantic
discriminated-union contract on `DiagnosticCheck`, enforced by
construction; silent failing rows are unreachable by type.

Every redesigned repair command renders through `_emit`. Legacy `--json`,
root `aeat doctor`, root `aeat repair`, root `aeat browser`, app-scoped
quarantine, app-scoped reset-state, app-scoped bucket maintenance, and
all compatibility aliases (including `aeat config doctor` and its
historical subcommands) are rejected.

### 4. `aeat app` mini-app requirements

The `app` surface is the operational tax workflow. Its sub-mini-apps are:

#### 4.1 `aeat app overview` (locked by app-overview-shape ADR)

Operational read surface over the active profile and active bucket. Absorbs the
historical roleplay `status` family and the legacy deadlines package.

Canonical commands:

```text
aeat app overview status
    [--period PERIOD]
    [--verbose]
    [--format json|text]

aeat app overview calendar
    --from YYYY-MM-DD
    --to YYYY-MM-DD
    [--allow-incomplete]
    [--format json|text]

aeat app overview agenda
    [--date YYYY-MM-DD]
    [--allow-incomplete]
    [--format json|text]

aeat app overview backlog
    [--from YYYY-MM-DD]
    [--to YYYY-MM-DD]
    [--format json|text]

aeat app overview explain MODELO
    [--year YYYY]
    [--format json|text]
```

Migration mapping:

- `deadlines list` becomes `overview calendar`.
- `deadlines next` becomes `overview agenda` with `next_due` in the payload.
- `deadlines explain` becomes `overview explain`.
- Phantom `status show` becomes `overview status`.
- Phantom daily-status view becomes `overview agenda`.
- Phantom `backlog show/scaffold` becomes read-only `overview backlog`.

Overview commands are read-only and emit no bucket events for normal reads.
They summarize recent material events using the bucket-event-history fields,
while full event browsing stays at `aeat config profile history PROFILE`.
`overview status` and `overview backlog` may summarize review counts and point
to `aeat app review queue`, but they do not own review queue rows or review
mutations.

Root `aeat status`, root `aeat deadlines`, legacy `--profile PATH`,
`AEAT_DEFAULT_PROFILE_PATH`, Rich-only deadlines rendering, and compatibility
shims are rejected. Production-grade `calendar` and `agenda` use the
festivos/business-day deadline-shift ADR. Resume/continue behavior uses
workflow-resumption semantics.

#### 4.2 `aeat app ledger` (locked by ledger-transaction-management + app-ledger-ratios-shape ADRs)

Eleven canonical verbs (operator-facing names per the ledger ADR's verb-naming
refinement):

- `import` — provider ingest via transaction application import services
  and catalogue persistence.
- `list` — movement-fact rows with filters.
- `status` — completeness, review progress, check blockers, bucket event
  state.
- `review` — inspect rows and review state.
- `classify` — write classification through transaction domain services.
- `allocate` — record `business_pct` and allocation rationale (previously
  named `split` in earlier drafts).
- `attach` — attach receipts and `purchase_invoice_evidence` to a ledger
  transaction.
- `attachments` — browse, verify, replace, remove, or repair the canonical
  attachment anchor and supplementary attachments (previously named
  `evidence` in earlier drafts).
- `link` — link a `ledger_transaction` to a business-operation object
  (`payable_invoice` or `collectible_invoice`).
- `check` — duplicate / orphan-link / inconsistent-direction /
  unsupported-evidence / modelo-ineligible checks; report-only (previously
  named `sanitize` in earlier drafts).
- `preflight` — confirm ledger data is ready for modelo calculation with
  `--mode complete` or `--mode modelo --modelo M`; renamed from `verify`
  to avoid collision with the `app modelo verify` lifecycle gate.
- `export` — sanitized facts for downstream modelo calculation.

Apex requirements that extend the ledger ADR:

- `usage_ratios` lives under `app ledger ratios`:

```text
aeat app ledger ratios list [--format json|text]
aeat app ledger ratios set KEY VALUE [--format json|text]
aeat app ledger ratios unset KEY [--format json|text]
```

This surface is proportional deduction / business-personal split context for
ledger facts. It is not IVA prorrata. `aeat financial profile`, `set-ratio`,
`unset-ratio`, `app modelo ratios`, and `app ledger prorrata` are rejected with
no aliases or shims. Mutations emit `ledger.ratios.set` and
`ledger.ratios.unset`.

- `app ledger classify` consumes the domain VAT classifier through
  `aeat.application.ledger.classify_ledger_transaction(...)`. Business
  classification and optional VAT-derived output share the same persisted
  operation, `ledger.classification.set`. `classify_vat` remains pure domain
  logic and is not a CLI or persistence API. OSS/IOSS and IVA prorrata remain
  separate domains.

- `app ledger attach` accepts structured evidence plus OCR/PDF evidence
  adapters for supplier receipts and purchase invoice evidence. OCR/PDF
  outputs are `purchase_invoice_evidence`, never bare `invoice`, and carry
  source hash, extraction provenance, confidence, manual-review state, and
  transaction link.
- `app ledger export libros ...` is the libro-registro export surface for
  facturas emitidas, facturas recibidas, ingresos/gastos, and bienes de
  inversión. It is separate from `app modelo export`.
- Provider expansion (ING, Sabadell, Openbank, Bankinter, Triodos) is
  implemented as inbound adapters behind `app ledger import` / ingest, not
  provider-specific roots or live bank scraping.

- `app ledger inventory` consumes the accepted inventory ledger backend
  under the root contract:

```text
aeat app ledger inventory list [--format json|text]
aeat app ledger inventory create ACTIVIDAD --year YEAR --valuation-method METHOD [--opening-stock AMOUNT] [--format json|text]
aeat app ledger inventory movement add --actividad ID --year YEAR --movement-id ID --date DATE --kind KIND --quantity QTY [--unit-cost AMOUNT] [--taxable-base AMOUNT] [--vat-rate RATE] [--format json|text]
aeat app ledger inventory valuation preview --actividad ID --year YEAR [--format json|text]
```

`list` and `valuation preview` are read-only. `create` and `movement add`
are bucket-scoped persisted mutations and emit `ledger.inventory.*` events.
`aeat data ledgers`, hidden compatibility shims, config placement, and
modelo placement are rejected.

#### 4.3 `aeat app modelo` (locked by app-modelo-shape + app-modelo-bindings-shape + lifecycle ADRs)

Modelo work-unit management and calculation/verification/internal-filing
lifecycle. The app-modelo-shape ADR locks the command grammar; the lifecycle
ADRs lock revision, verification, internal filing, and filing-record semantics.

Canonical verb tree:

- `list [--modelo] [--year] [--period] [--state draft|verified_complete|filed|superseded]`
- `create --modelo M --year YYYY --period P [--name TEXT]`
- `status WORK_UNIT_ID | --modelo M --year YYYY --period P [--revision REV]`
- `rename WORK_UNIT_ID --name TEXT`
- `bindings list --modelo M --year YYYY --period P [--missing]`
- `bindings preview --modelo M --year YYYY --period P [--binding KEY=VALUE]`
- `calculate WORK_UNIT_ID | --modelo M --year YYYY --period P [--binding KEY=VALUE]`
- `verify WORK_UNIT_ID [--revision REV]`
- `file WORK_UNIT_ID [--revision REV] --by ACTOR [--reason TEXT]` — marks a
  verified revision as internally filed in the active bucket; help text,
  successful-output footer, and confirmation prompts all carry the qualifier
  "(internal only — does not submit to AEAT)" per the modelo-file ADR
  refinement.
- `work resume WORKFLOW_RUN_ID`
- `audit show WORK_UNIT_ID [--revision REV | --filing-record ID]`
- `audit check WORK_UNIT_ID [--revision REV | --filing-record ID]` — report-only bundle integrity check (renamed from `verify` to avoid collision with the `app modelo verify` lifecycle gate)
- `audit export WORK_UNIT_ID --output PATH [--revision REV | --filing-record ID] [--force-incomplete]`
- `audit replay WORK_UNIT_ID [--revision REV | --filing-record ID]`
- `filing-record list|show ...`
- `export WORK_UNIT_ID --output PATH [--revision REV]`
- `import --from-justificante PATH | --from-declaracion PATH`
- `reconcile WORK_UNIT_ID --justificante PATH`
- `amend WORK_UNIT_ID --kind complementaria --from-filing-record ID --set CASILLA=VALUE [--reason TEXT]`
- `history --modelo M [--year YYYY] [--period P]`

Implementation mandate: register the work-unit, lifecycle, filing-record,
audit, resume, import/export, reconcile, amend, and history verbs in
`aeat app modelo`. Migrate accepted declaration lifecycle behavior into this
surface and remove `app declaration` from operator UX. Keep
registry-introspection commands only where they do not obscure the modelo
work-unit lifecycle.

Rejected alternatives:

- `name` is not a verb; use `rename`.
- `complement` is not a verb or alias; use `amend --kind complementaria`.
- `inputs` is not a command family; use `bindings`.
- `compare` is not a command family; use `reconcile`.
- `preflight`, `submit`, and `presentation` are not standalone modelo verbs.
  Readiness checks are internal to `verify` / `file`.
- `help` is not a modelo support surface; use command help and registry/topic
  documentation.
- Mutating inventory is not under `app modelo`; inventory placement is decided
  by the inventory-placement ADR. `app modelo bindings/status` may consume
  inventory-derived readiness.

Bindings shape:

- `bindings list` reports required and available binding keys for the
  modelo/year/period. `--missing` filters to unresolved required keys.
- `bindings preview` resolves temporary `--binding KEY=VALUE` overrides without
  mutation and preserves scalar, list, and mapping values.
- `calculate --binding` uses the same explicit binding override model as
  `bindings preview`.
- Missing binding failures render readiness categories (`bucket`, `ledger
  source`, `profile fact`, `prior filed revision`, `live observation`,
  `casilla`, `waiver`, `blocking finding`) instead of raw binding errors.
- `bindings list` and `bindings preview` are read-only and emit no bucket
  events.

Resume shape:

- `app modelo work resume <workflow_run_id>` accepts workflow-engine run ids only.
- Resume means continue from a prior terminal aborted modelo filing result, not
  run-trace replay.
- Resume validates the prior aborted run, emits current-state retry context
  with `resumed_from_run_id`, and never resumes mid-stage.
- Resume itself is read-only and creates no filing record; subsequent verify
  or file attempts pass through the normal current-state lifecycle gates.
- Root `aeat workflow`, root `aeat run`, observability replay ids, historical
  argv reconstruction, and shims are rejected.
- W80 ratifies resume under the reconciled W72 nested work-unit surface:
  `app modelo work resume WORKFLOW_RUN_ID` is the accepted path. A flat
  `app modelo resume` path is not introduced.

Audit/evidence shape:

- `app modelo audit show|verify|export|replay` is the evidence packaging
  surface.
- EvidenceBundle is a bucket-scoped, work-unit-bound manifest and referenced
  records, not the source of relational truth.
- Durable manifests and verification reports are stored inside the active
  bucket under the modelo work unit or filing case.
- Events are `modelo.audit.verified`, `modelo.audit.exported`, and
  `modelo.audit.replayed`.
- `audit export` writes a ZIP with `manifest.json` last and runs verification
  first; failed verification refuses export and partial verification requires
  `--force-incomplete`.
- `audit replay` is evidence-case replay, not root argv replay, and never
  contacts AEAT or performs live submission.

Per-modelo entry points and modelo-specific UX hooks are catalogued in §5.
Complementaria amendments from externally filed returns are handled only
through `app modelo amend --kind complementaria --from-filing-record ID`.
The filing record must contain official justificante/CSV minimum fields and
schema-compatible evidence; incomplete imported records block amendment
construction.

#### 4.4 `aeat app live` (locked by app-live-shape ADR)

Read-only AEAT remote-observation surface. This is the explicit operator
boundary for commands that may contact AEAT now but cannot file, present, sign,
pay, or submit.

Canonical commands:

```text
aeat app live notifications list [--summary] [--format json|text]
aeat app live notifications show ID [--format json|text]

aeat app live expedientes list [--modelo MODELO] [--year YEAR] [--format json|text]
aeat app live expedientes show EXPEDIENTE_ID [--format json|text]

aeat app live filed list --modelo MODELO --from-year YYYY --to-year YYYY [--format json|text]
aeat app live filed capture --modelo MODELO --year YYYY [--period PERIOD] [--expediente ID] [--limit N] [--format json|text]
aeat app live filed capture-sources --modelo MODELO --year YYYY --period PERIOD [--format json|text]

aeat app live verify nif-iva NIF_IVA [--expected valid|invalid|unknown] [--format json|text]
aeat app live verify tgvi NIF [--expected valid|invalid|unknown] [--format json|text]

aeat app live borrador 100 fetch [--payload PATH] [--format json|text]
aeat app live borrador 100 show SNAPSHOT_ID [--format json|text]

aeat app live portals list [--category CATEGORY] [--modelo MODELO] [--format json|text]
aeat app live portals show PORTAL [--format json|text]
```

Implementation mandate: introduce `aeat app live`, move filed-declaration live
reads to `app live filed`, and remove registry filed-read registrations without
aliases or shims.

`app live portals list/show` is local portal-registry discovery. It does
not call AEAT and does not require `require_live_read()`.

Every remote-navigation or remote-request command calls
`AeatAccessGate.require_live_read()` before remote contact and authenticated
session creation. No command calls `require_live_write()`, except refusal tests.

Non-persisting reads emit no bucket event. Persisted captures and snapshots are
bucket-linked and emit:

- `live.notifications.snapshot_captured`
- `live.expedientes.snapshot_captured`
- `live.filed.capture_created`
- `live.verify.nif_iva_checked`
- `live.verify.tgvi_checked`
- `live.borrador100.snapshot_captured`

`app modelo` consumes observations and snapshots but does not own live session
traversal. `app overview` summarizes captured snapshots. `config repair`
diagnoses live-read readiness only.

#### 4.5 `aeat app registry` (locked by app-registry-boundary + domain-harvest-normatives ADRs)

Registry introspection, local reference-catalogue inspection, and authority
audit.

Canonical commands:

```text
aeat app registry inspect [--registry-root PATH] [--format json|text]
aeat app registry verify [--registry-root PATH] [--source-root PATH] [--format json|text]
aeat app registry audit-oracles [--registry-root PATH] [--environment production|test_environment|both] [--format json|text]
aeat app registry verify-filed-state --observation PATH [--source-observation PATH ...] [--registry-root PATH] [--source-root PATH] [--casilla ID ...] [--format json|text]
aeat app registry citations list [--tag TAG] [--format json|text]
aeat app registry citations show NORMATIVE_ID [--articulo NUM] [--format json|text]
aeat app registry citations verify [--format json|text]
aeat app registry manuals list [--manual renta|iva] [--year YYYY] [--format json|text]
aeat app registry manuals show --manual renta|iva --year YYYY --part PART [--section SECTION] [--format json|text]
aeat app registry manuals rules --manual renta|iva --year YYYY --part PART [--kind KIND] [--format json|text]
aeat app registry manuals verify --manual renta|iva --year YYYY --part PART [--format json|text]
aeat app registry workbooks verify [--root PATH] [--limit N] [--per-file-timeout SECONDS] [--output PATH] [--resume-from PATH] [--format json|text]
aeat app registry parity run --scenario PATH [--registry-root PATH] [--source-root PATH] [--store-root PATH] [--output PATH] [--format json|text]
aeat app registry parity replay --tape PATH [--registry-root PATH] [--source-root PATH] [--format json|text]
```

Static modelo registry introspection (`list`, `describe`, `casillas`,
`bindings`, `formulas`) remains under `aeat app modelo`.
`citations` and `manuals` are read-only local corpus inspection surfaces
and emit no bucket events. Operator-facing manual fetch is rejected.

Implementation mandate: filed live reads move to `app live filed`; registry
retains only local registry authority, structural verification,
oracle/workbook/parity, and local filed-state verification.
No compatibility aliases or shims survive. `config repair` receives no filed
list/capture, NIF-IVA/TGVI operational read, or registry parity workflow.

#### 4.6 `aeat app review` (locked by app-review-queue-execution ADR)

Cross-domain read-only review queue. The 2026-04-18 review ADR is
superseded for placement and output shape: top-level `aeat review queue`
becomes `aeat app review queue`, command-local `--format table|json`
becomes root `--format json|text`, and old drill commands under retired
roots are removed.

Canonical commands:

```text
aeat app review queue
    [--kind ledger_transaction|purchase_invoice_evidence|payable_invoice|collectible_invoice|modelo_finding|live_notification|sync_divergence]
    [--state pending|all]
    [--modelo MODELO]
    [--source-kind KIND]
    [--format json|text]

aeat app review show REVIEW_ITEM_ID
    [--format json|text]
```

`queue` and `show` are read-only and emit no bucket events. Generic
cross-source `edit`, `approve`, and `defer` are rejected for this surface.
Source-specific mutations remain under their owning app surfaces.

Review `kind` is separate from `source_kind`. The accepted review kinds are
`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`,
`collectible_invoice`, `modelo_finding`, `live_notification`, and
`sync_divergence`. `source_kind` is one of the four source-kind taxonomy
values (`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`,
`collectible_invoice`) or null for modelo/live/sync rows. Legacy
`transaction`, `invoice`, and `finding` review kinds are replaced by the
accepted review kinds. `live_notification` and `sync_divergence` are reserved
vocabulary for concrete live and sync review repositories.

Implementation mandate: register `aeat app review`, migrate legacy item kinds
and drill commands, and remove embedded generic review flows that conflict with
the read-only queue/show interface.

#### 4.7 Retired surfaces (locked by ledger + modelo ADRs)

The retirement decisions below are design-locked by the ledger + modelo ADRs.

- `aeat app declaration` — folded into `aeat app modelo`. The lifecycle is
  `calculate → verify → file`. No `declaration` verb survives.
- `aeat app invoice` — removed from operator UX (per ledger ADR).
  Former verbs split: import/review/edit become ledger evidence/link
  workflows; match becomes ledger check/reconcile workflow. Business-
  operation invoice objects (`payable_invoice`, `collectible_invoice`) are
  modelo inputs, not a standalone `app invoice` surface.
- `aeat app archive` — retired. Browse/export/import/rename/delete remain
  backend/application bucket-maintenance lifecycle operations; search remains a
  bucket-search ADR follow-up.

### 5. Per-modelo requirements

Each modelo follows the locked lifecycle (`calculate → verify → file`) and
inherits the locked source-kind taxonomy. This section catalogues modelo-
specific requirements, backend dependencies, and gaps.

Modelos are grouped by family. Status legend:

- **Calc-ready**: registry + bindings + calculate path proven against the
  workbook or worked example.
- **Backend-partial**: registry present, generic calculate works, but
  modelo-specific UX hooks (counterpart aggregation, attachment evidence,
  external import) are missing.
- **Registry-only**: TOML present, no domain binding or calculation depth.
- **Missing**: not in registry.

#### 5.1 IVA family

- **303** (IVA trimestral / mensual) — calc-ready. UX hooks: prorrata
  (gap, art. 101/103 LIVA), recargo equivalencia (present), SII / Verifactu
  emission status (gap, profile axis missing).
- **390** (IVA resumen anual) — calc-ready. UX hook: cross-period
  aggregation from 303 observations (present via
  `resolve_relation_values_from_observations`).
- **369** (OSS / IOSS one-stop-shop) — registry-present; binding-path
  design locked by the domain-harvest-oss-ioss ADR. Execution requires
  the 2026-05-06 modelo-369-vat-centralization ADR to be accepted or
  superseded first. `app modelo` owns the work-unit and calculate path;
  `domain/vat/_oss.py` remains pure substrate. The application wrapper
  resolves profile and ledger facts into `ledger_oss_aggregation`
  bindings, validates destination member-state VAT rates, and emits the
  modelo calculation event.
- **308** (devolución mensual / no establecidos) — registry-only. UX hook:
  refund-status workflow.
- **309** (no periódica) — registry-only. UX hook: triggered by adquisición
  intracomunitaria de medios de transporte and analogous one-off events.
- **322** (IVA grupos) — registry-only. UX hook: group-member aggregation.
- **353** (IVA grupos consolidación) — registry-only. Same family as 322.
- **360** (devolución no establecidos) — registry-only.

#### 5.2 IRPF family

- **130** (pago fraccionado estimación directa) — calc-ready. UX hook:
  proportional deduction binding for office, vehicle, supplies; ledger →
  modelo binding via `_renta_ledger.py`.
- **131** (pago fraccionado estimación objetiva / módulos) — calc-ready.
  UX hook: módulos rate selection (módulos legal refs declared through
  2025).
- **100** (IRPF anual) — calc-ready (multi-revision dir, 2020–2025). UX
  hooks: CCAA autonomic scale (present, all 15 CCAA × multiple years
  wired), rental aggregation (domain-harvest-rental ADR requires
  `aeat.application.rental`, `app ledger rental ...`, and
  `rental_register_aggregation` consumed through `app modelo bindings`),
  datos fiscales borrador pre-fill (backend present via `_renta_web_open.py`,
  no verb).
- **145** (comunicación retenciones empleados) — foundation locked by the
  modelo-145-foundation ADR. New work: registry TOML, form schema, and
  profile/binding contract. Lifecycle is non-filing payer communication:
  no AEAT presentation is implied.

#### 5.3 Retenciones (informativas) family

All registry-present, calc-ready for generic draft build. Common gap
locked by the per-modelo-aggregation-pipeline ADR: aggregation must flow
through `application/aggregation` and registry binding providers using
`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and
`collectible_invoice`; bare `invoice` source bindings must be removed.

- **111** (retenciones trabajo + actividades económicas — trimestral) —
  backend-partial.
- **115** (retenciones arrendamientos urbanos) — backend-partial.
- **123** (retenciones capital mobiliario) — backend-partial.
- **180** (resumen anual retenciones arrendamientos) — backend-partial.
- **190** (resumen anual retenciones trabajo + económicas) —
  backend-partial.
- **193** (resumen anual retenciones capital mobiliario) — backend-partial.

#### 5.4 Informativas family

- **347** (operaciones con terceros > €3 005,06) — backend-partial.
  Aggregation path locked by per-modelo-aggregation-pipeline ADR:
  counterpart aggregation from explicit ledger/business-operation source
  kinds.
- **349** (operaciones intracomunitarias) — backend-partial. Same
  aggregation pattern as 347, plus GROI / NIF-IVA readiness before
  declaring counterparts.
- **720** (bienes y derechos en el extranjero) — backend-partial.
  Aggregation path locked by per-modelo-aggregation-pipeline ADR:
  assets/evidence aggregation to 720 casillas.
- **184** (entidades en atribución de rentas) — registry-only. Marginal
  autónomo relevance.
- **232** (operaciones vinculadas) — registry-only. UX hook: related-party
  transaction declaration.
- **840** (IAE — impuesto actividades económicas) — registry-only. UX hook:
  IAE-epígrafe-aware filing.

#### 5.5 Impuesto Sociedades family

- **200** (IS anual) — calc-ready (cuota-chain verification_expectations
  declared on 200 2024-y-siguientes). Narrow autónomo relevance.
- **202** (pago fraccionado IS) — registry-only. UX hook: same as 130 for
  IS payers.

#### 5.6 Censo family

- **036 / 037** (censo alta/baja/modificación) — foundation locked by
  the modelo-036-037-foundation ADR. Modelo 036 needs registry, profile
  bindings, and event-triggered `alta` / `modificacion` / `baja`
  lifecycle. Modelo 037 is historical inactive metadata only because it
  was suppressed from 2025-02-03 and superseded by 036.

### 6. Phantom-family adjudication

The 2026-04-24 operator-cli-roleplay audit and several related audits
propose command families that do not exist in the live code. Each must be
explicitly adopted or retired.

- **`status` family** (`status show / agenda / resume / history /
  backlog`) — **adopted as `aeat app overview`**. `status show` becomes
  `app overview status`; the daily-status view becomes `app overview agenda`;
  `backlog show/scaffold` becomes read-only `app overview backlog`;
  `history` is satisfied by `app modelo history` plus
  `config profile history PROFILE`; `resume` becomes
  `app modelo work resume <workflow_run_id>` per the workflow-resumption-semantics ADR.
- **`compare` family** (`compare show / explain / fix / verify`,
  `ComparisonCase`) — **retired**. Reconciliation (the underlying
  question "does my draft agree with AEAT's record?") is served by `aeat
  app modelo reconcile` (per §4.3, backed by
  `application/filing/reconciliation/_reconcile.py`). A separate `compare`
  surface is not needed.
- **`audit` evidence family** (`audit show / verify / export / replay`,
  `EvidenceBundle`) — **adopted as `aeat app modelo audit`**. The bundle is
  bucket-scoped, work-unit-bound provenance and replay material; it is not root
  `audit`, root `run`, or a live AEAT submission surface.
- **`backlog` family** (`backlog show / import / scaffold / resume`) —
  **partially adopted**: `app overview backlog` covers the show/scaffold
  read model. The `import` verb is rejected here. `backlog resume` is not a
  command; lifecycle continuation is `app modelo work resume <workflow_run_id>`.
- **`data require / readiness` family** — **adopted as `aeat app modelo
  bindings`** (the `--missing` filter variant). The per-period data
  checklist becomes
  `app modelo bindings list --modelo X --year YYYY --period P --missing`
  rather than a separate top-level verb. Aligns with the UX-012 supplier-flag
  closure.
- **`review` family legacy shape** (`aeat review`, generic review
  `edit` / `approve` / `accept` / `lock` / `defer`, and old drill commands
  `aeat financial txs classify`, `aeat financial invoices show`,
  `aeat filing show`, `aeat review show`) — **retired**. The accepted
  surface is read-only `aeat app review queue/show`; source-specific
  mutations stay with owning app surfaces.

### 7. Functional gap inventory (no backend, needs new work)

These are absent from both backend and CLI. The apex flags them; each
needs its own follow-up ADR + plan + execution.

- **Festivos / business-day deadline shift** — design locked by the
  festivos-deadline-shift ADR. Add `domain/deadlines` holiday-adjustment
  service with national plus CCAA/local source layering, explainable
  adjusted dates, and modelo-specific exceptions such as Modelo 369.
- **IVA prorrata under arts. 101/103 LIVA** — design locked by the
  iva-prorrata-art-101-103 ADR. Add `domain/vat` legal prorrata
  substrate and application aggregation observations for 303/390.
  `domain/usage_ratios` and `app ledger ratios` remain proportional
  expense/allocation machinery, not legal prorrata.
- **Foreign-currency normalization** — design locked by the
  foreign-currency-normalization ADR. Normalize in
  `application/aggregation` before modelo bindings; retain original
  currency, amount, rate source, rate date, and EUR-normalized value in
  evidence.
- **Retenciones aggregation pipeline** — design locked by the
  per-modelo-aggregation-pipeline ADR. Use application aggregation and
  explicit source kinds for 111/115/123/180/190/193.
- **347 / 349 counterpart aggregation pipeline** — design locked by the
  per-modelo-aggregation-pipeline ADR. Use ledger/business-operation
  source kinds and live-read readiness where applicable for NIF-IVA/GROI.
- **Libros BOE-format exporters** — design locked by the
  libros-boe-format-exporters ADR. Add `app ledger export libros ...`;
  do not reuse `app modelo export`.
- **Apoderamientos** (proxy / representation filing) — design locked by
  the apoderamientos-surface ADR. Local representation config plus
  read-only live checks under `aeat config auth apoderado`; no live
  mutation.
- **DNI-e smart-card PKCS driver** — portal entry catalogued; no driver
  authenticator.
- **Receipt OCR / PDF parsing for evidence** — design locked by the
  receipt-ocr-pdf-evidence ADR. `app ledger attach` emits
  `purchase_invoice_evidence` with stored provenance; AEAT justificante
  parsing is not reused for supplier receipts.
- **Bank-provider coverage gaps** — design locked by the
  bank-provider-expansion ADR. Add explicit inbound adapters for ING,
  Sabadell, Openbank, Bankinter, and Triodos; no PSD2/live scraping or
  heuristic unknown-CSV acceptance.

### 8. Backend exit-cap inventory (capabilities awaiting a CLI verb)

This section is the dynamic part of the apex. Every Python backend
capability without a CLI verb appears here with its assigned mini-app
target. As each verb lands, the entry is removed.

- **`WorkflowEngine.run_next` / `run_for_period`** (`application/workflow/
  _engine.py`) — read/preflight lifecycle gate. **Closed by W80**:
  `WorkflowEngine.run_for_period(profile, modelo, period, as_of=...)` is
  invoked internally by `aeat app modelo work verify` and
  `aeat app modelo work file`; `run_next` remains application-only. No
  `aeat workflow` root, per-stage verbs, or standalone `app modelo preflight`
  command.
- **`SubmissionEngine.preflight`** (`domain/submission/_engine.py`,
  `_preflight.py`) — preflight gate (auth, deadline, draft approval, no
  blockers). **Closed by W80**: invoked only through the
  `WorkflowEngine.run_for_period` path reached by `app modelo work verify`
  and `app modelo work file`; modelo actions and CLI handlers must not call
  `SubmissionEngine.preflight` directly, and no standalone
  `app modelo preflight` verb exists.
- **`FilingHistoryRepository`** (`application/filing/_history_repository.py`,
  `_history_models.py`) — encrypted per-modelo filing history. **Target
  verb**: `aeat app modelo history` (§4.3).
- **`reconcile(draft, justificante)`** (`application/filing/reconciliation/
  _reconcile.py`) — MATCH / DIVERGENT / NOT_YET_FOUND. **Target verb**:
  `aeat app modelo reconcile` (§4.3).
- **`build_complementaria`** (`application/filing/_complementaria.py`) —
  complementaria / sustitutiva builder. **Target verb**: `aeat app modelo
  amend --kind complementaria`. **Target behavior locked**: external
  filings may be used only through `--from-filing-record ID` with
  official justificante/CSV minimum fields, schema compatibility checks,
  and bucket events.
- **DEHú notifications** (`adapters/outbound/aeat/sede/_notifications.py`)
  — `fetch_notifications_query`, `fetch_notifications_summary`. **Target
  verb**: `aeat app live notifications` (§4.4).
- **Histórico expedientes** (`adapters/outbound/aeat/sede/_declarations.py`)
  — `walk_expedientes_tree`, `open_declarations_register`. **Target verb**:
  `aeat app live expedientes` (§4.4).
- **NIF-IVA / VIES on-demand** (`_aeat_nif_iva_oracle.py`) — **Target
  verb**: `aeat app live verify nif-iva` (§4.4).
- **Datos fiscales / borrador 100** (`_renta_web_open.py`) — **Target
  verb**: `aeat app live borrador 100` (§4.4). Borrador import refusal
  behavior is replaced by the explicit `app live borrador 100` surface.
- **TGVI / GROI** (`_groi_oracle.py`) — **Target verb**: `aeat app live
  tgvi` (§4.4).
- **`SetupWizard`** (`application/setup/_wizard.py`) — **Decision**: retire
  as a command backend; salvage only typed answers, prompter
  abstraction, and verifier checks.
- **Inventory CLI** (`entrypoints/cli/data/ledgers/inventory.py`) — full
  Typer app per 2026-04-30 ADR. **Target behavior locked**: migrate to
  `aeat app ledger inventory list/create/movement add/valuation preview`;
  retire `aeat data ledgers` with no shim.
- **Usage ratios** (`domain/usage_ratios/`, unmounted `financial profile
  ratios`) — **Target verb locked**: `aeat app ledger ratios list/set/unset`
  (§4.2). Remove the old `financial profile` route with no compatibility shim.
- **`domain/rental/`** — art. 22-24 LIRPF tier resolver, FIFO amortisation.
  **Target behavior locked**: add `aeat.application.rental`; expose source
  facts under `aeat app ledger rental ...`; expose Modelo 100 readiness through
  `app modelo bindings`; add `rental_register_aggregation`.
- **`domain/vat/_classification.py classify_vat`** — deterministic VAT-
  rule classifier. **Target behavior locked**: consumed by
  `aeat.application.ledger.classify_ledger_transaction(...)` behind
  `aeat app ledger classify`; `classify_vat` remains pure domain logic.
- **`domain/vat/_oss.py`** — OSS/IOSS regime substrate. **Target behavior
  locked**: `app modelo` calculation-path binding provider creates
  `OssIossLedgerObservation`, resolves `ledger_oss_aggregation`, validates
  destination-country rates, and feeds Modelo 369 calculate.
- **`domain/normatives/` + `domain/manuals/`** — BOE/manual citation
  and rule lookup. **Target behavior locked**: `aeat app registry
  citations list/show/verify` and `aeat app registry manuals
  list/show/rules/verify`; read-only `_emit` output, no bucket events,
  no operator-facing manual fetch.
- **`domain/portals/PORTAL_REGISTRY`** — 90 entries (verified). **Target
  behavior locked**: `aeat app live portals list/show` local metadata
  discovery.
  No action verbs (`open`, `submit`, `present`, `sign`, `pay`) and no
  remote contact.
- **`_observability.py` helpers** — zero call sites. **Target behavior
  locked**: retire from the CLI layer; bucket event history and evidence
  bundles own accepted audit/replay semantics.
- **`application/wizard/`** — the generic wizard framework that drives
  `aeat config <flow>` commands via `_register_wizard_commands`.
  **Target behavior locked**: salvage prompter/verifier primitives into
  `aeat config init` per the config-init-shape ADR; the generic wizard-flow
  command surface is retired. (Distinct from the
  `SetupWizard` class noted separately.)
- **`application/topics/` + `_topic.py`** — backs the `aeat app topic` and
  `aeat topic`/`aeat help` mounts. **Target behavior locked**: retired from
  operator UX per §1 fold-under map. Topic/help content migrates to inline
  command help and to `app registry citations` / `manuals`.
- **`application/attachments/`** — backs `app ledger attach` and
  `app ledger attachments`. **Target behavior locked**: consumed by the
  ledger ADR's attachment verbs through the existing service interface;
  no separate operator surface.
- **`adapters/inbound/sanitizer/`** — input-sanitization helpers used by
  ingest paths. **Target behavior locked**: consumed internally by
  `aeat app ledger import`; no operator-facing `sanitize` root.
- **`adapters/inbound/pdf/`** — PDF inbound adapter. **Target behavior
  locked**: consumed by `aeat app ledger attach` per the receipt-ocr-pdf-
  evidence ADR.
- **`adapters/outbound/llm/`** — LLM outbound adapter. **Target behavior
  locked**: retired with the `aeat llm` operator root; classification LLM
  workflows route through `aeat app ledger classify` only if explicitly
  scoped by a future ADR.
- **`domain/categories/`** — spending-category classification substrate.
  **Target behavior locked**: consumed by `aeat app ledger classify` and
  the modelo-100 ledger aggregation; no separate operator surface.
- **`domain/renta/` (LIRPF ledger-expense substrate)** — distinct from
  `domain/rental/`. **Target behavior locked**: consumed by
  `application/aggregation/_renta_ledger.py` for modelo 100 bindings; no
  operator surface.
- **`domain/portals/_cli.py`** — fully-built standalone Typer app inside
  the domain layer. **Target behavior locked**: architecture violation;
  the domain layer must not host CLI surfaces. Delete or move to
  `application/portals/` per the domain-portals-harvest ADR before any
  re-wiring under `app live portals` is considered.

### 9. Implementation mandates

Eleven accepted-design retirements and registrations must execute before the
implementation reflects the apex contract:

- **`config-cli-profile-surface`** (2026-05-07) — full `config profile`
  verb tree, removal of `setup profile`. PROFILE_KEYS already covers IVA,
  IRPF, ROI, OSS-enrolment axes (verified); the residual schema work is
  SII and Verifactu axes.
- **`inventory-management-cli-design`** (2026-04-30) — apply the
  superseding placement: `app ledger inventory`; remove the old `data`
  root and all `data ledgers inventory` strings.
- **`unified-review-queue`** (2026-04-18) — register `aeat app review`,
  migrate legacy `transaction` / `invoice` / `finding` review kinds, migrate
  drill commands away from retired `financial`, `filing`, and top-level
  `review` commands, and replace tests that lock old behavior.
- **`modelo-file`** (2026-05-12) — §4.3 requires `_modelo.py` to register
  the lifecycle verbs (`calculate`, `verify`, `file`, `filing-record`).
- **`app invoice` retirement** — `_invoice.py` registered at
  `entrypoints/cli/__init__.py:164` must be removed; legacy verb tree
  splits per the ledger-transaction-management ADR.
- **`app declaration` retirement** — `_declaration.py` registered at
  `entrypoints/cli/__init__.py:165` must be removed; behavior folds into
  `app modelo` per the app-modelo-shape ADR.
- **`app archive` retirement** — `_archive.py` registered at
  `entrypoints/cli/__init__.py:169` must be removed from operator UX.
  Export/import/browse are backend bucket-maintenance service operations until
  a profile-named operator surface is accepted.
- **`app topic` retirement** — `_topic_module` registered at
  `entrypoints/cli/__init__.py:170` must be removed; help content folds
  into inline command help and `app registry citations` / `manuals` per
  §1 fold-under.
- **`config setup` wizard retirement** — the wizard-flow command surface
  registered via `_register_wizard_commands` (with `SETUP_FLOW.id =
  "setup"`) must be removed; setup capabilities consolidate into
  `aeat config init` per the config-init-shape ADR.
- **`app registry` live-read migration** — `list-filed-data`,
  `capture-filed-data`, `capture-source-filed-data` in `registry.py` must
  move to `aeat app live filed` per the app-registry-boundary ADR.
- **`domain/portals/_cli.py` architectural deletion** — the domain-layer
  Typer app must be deleted or moved to `application/portals/` per the
  domain-portals-harvest ADR; the domain layer must not host CLI surfaces.

In addition: `_common.py:95-96` emits `"aeat setup init --name NAME"` as
the recovery hint in the no-active-profile error payload. The recovery hint
must point to `aeat config init` per §2 and §3.1.

(The 2026-05-10 user-CLI retirement plan is closed: `application/
user_cli.py` has been removed from the codebase; remaining occurrences in
`application/overview/__init__.py`, `application/overview/test_calendar.py`,
and `entrypoints/cli/test_workflow_surface.py` are prose/docstring/test-
fixture-name strings, not module imports.)

### 10. Child ADRs still required

No child ADR slots remain open. The 2026-05-13 gap-fill pass added six
follow-up child ADRs that close the remaining UX-pass-3 issues and back
every apex decision with a persisted ADR:

- `actor-attribution` (2026-05-13) — `--by ACTOR` default and grammar on
  `aeat app modelo file`. Defaults to the active profile's display name;
  ACTOR is a free-form label, not a NIF.
- `app-modelo-discard` (2026-05-13) — `aeat app modelo discard
  WORK_UNIT_ID` for draft-only work units; emits
  `modelo.work_unit.discarded` and excludes discarded work units from
  default `list` output.
- `borrador-100-binding-integration` (2026-05-13) — `aeat app modelo
  calculate --modelo 100 --borrador SNAPSHOT_ID` consumes the live-AEAT
  pre-fill snapshot for `aeat_prefilled = true` bindings; source trace
  records the snapshot id per casilla.
- `config-profile-use-and-status` (2026-05-13) — `aeat config profile use
  NAME` alias for `set active`; `aeat config profile list --with-status`
  surfaces draft / verified-unfiled / last-filed counts per profile from
  bucket event history.
- `root-help-shape` (2026-05-13) — `aeat`, `aeat config`, `aeat app`
  bare-invocation and `--help` shape; workflow-ordered grouping; mistype
  suggestions footer; bare `aeat` runs `app overview today`.
- `apoderado-scope-vocabulary` (2026-05-13) — `--scope SCOPE` accepts
  uppercase AEAT apoderamiento codes from a shipped catalogue; repeated
  flag; rejects comma-separated values; `ALL` expands at command time.

The 2026-05-13 surface-coverage sweep added five more child ADRs that
close the remaining concept-coverage gaps surfaced by the per-command
audit:

- `ledger-transaction-removal` (2026-05-13) — `aeat app ledger remove
  TRANSACTION_ID` for unreferenced ledger rows; rejects removal if a
  verified or filed modelo revision cites the row; cascades evidence /
  link / review-item detachment.
- `borrador-snapshot-management` (2026-05-13) — `aeat app live borrador
  100 list / verify / discard / export` complement the existing `fetch`
  and `show` verbs; closes the snapshot lifecycle.
- `config-profile-keys-discovery` (2026-05-13) — `aeat config profile
  keys [--prefix PREFIX]` enumerates the PROFILE_KEYS schema; `set`
  rejection error points operators here.
- `ledger-ratios-eligible-and-validate` (2026-05-13) — `aeat app ledger
  ratios eligible` and `validate [--modelo M]` close the discoverability
  and pre-calculate readiness gap on proportional deduction.
- `explain-legal-ref-convention` (2026-05-13) — cross-cutting `--explain`
  flag on every rule-grounded verb; output enriches with
  `legal_refs: [...]` resolved from the local citations + manuals
  corpus.

Implementation mandates are tracked in §9 and backend exit-caps in §8.

### 10A. Operator vocabulary (apex review 2026-05-12)

A single reference for terms operators encounter at the CLI boundary.
Implementations of any verb in §3–§5 must honour these.

**Period tokens** (canonical, emitted by all output, accepted on input):

- `Q1`, `Q2`, `Q3`, `Q4` — quarterly
- `M01` through `M12` — monthly
- `annual` — annual
- `none` — one-off / non-periodic

Aliases accepted on input only (for AEAT-sede parity): `1T`, `2T`, `3T`,
`4T` ↔ `Q1`–`Q4`; `0A` ↔ `annual`. The valid period set per modelo is
registry-driven and enumerated by `aeat app modelo bindings list --modelo M`.

**Source-kind CLI aliases** (input-only ergonomic aids; canonical names always
emitted by output, events, storage):

- `lt` ↔ `ledger_transaction`
- `pie` ↔ `purchase_invoice_evidence`
- `pi` ↔ `payable_invoice`
- `ci` ↔ `collectible_invoice`

**Spanish-anchored terms with English gloss in help text**:

- `apoderado` ↔ representative / proxy (used in
  `aeat config auth apoderado` per the apoderamientos-surface ADR)
- `borrador` ↔ draft / pre-fill (used in `aeat app live borrador 100`)
- `justificante` ↔ filing receipt (used in `--from-justificante PATH`)
- `expediente` ↔ filing record / case file
- `casilla` ↔ form field / box
- `bucket` ↔ active profile data slice — the profile-scoped data slice
  that owns all calculation, ledger, and filing records for one active
  profile
- `recargo de equivalencia` ↔ equivalence surcharge — special IVA
  regime for retailers without input-VAT deduction
- `prorrata` ↔ proportional VAT deduction (LIVA arts. 101/103) — distinct
  from `app ledger ratios` proportional-deduction allocation
- `módulos` ↔ flat-rate IRPF regime — objective-assessment regime under
  art. 31 LIRPF
- `gestora` / `gestoría` ↔ tax-filing agent / agency — professional
  preparing and filing on behalf of one or more autónomos
- `Cl@ve Móvil` ↔ Spanish-government mobile authentication via OTP
- `Cl@ve PIN` ↔ Spanish-government one-time-PIN authentication
- `datos fiscales` ↔ AEAT pre-fill tax data
- `libro-registro` ↔ official record book (facturas emitidas / facturas
  recibidas / ingresos y gastos / bienes de inversión)
- `apud-acta` ↔ sworn / notarised delegation record (AEAT apoderamiento
  catalogue source)
- `finca` ↔ real-estate unit (rental property register)
- `alta` ↔ initial census registration (modelo 036/037 event)
- `modificacion` ↔ census update (modelo 036/037 event)
- `baja` ↔ census deregistration (modelo 036/037 event)
- `complementaria` ↔ supplementary amendment (`--kind complementaria`)
- `sustitutiva` ↔ replacement amendment (`--kind sustitutiva`)

**Readiness category translations** (rendered by `bindings list --missing` and
`status` output; backend taxonomy → operator language):

- `bucket` → "active profile data slice"
- `ledger source` → "missing ledger classification or split"
- `profile fact` → "missing profile value (e.g., NIF, regime)"
- `prior filed revision` → "prior modelo filing required for this calculation"
- `live observation` → "AEAT live signal absent"
- `casilla` → "form field unresolved"
- `waiver` → "manual waiver required"
- `blocking finding` → "validation error blocking the calculation"

**Verb names that operators commonly mistype** (rejected aliases — fail with a
suggestion, not a silent acceptance):

- `aeat init` → suggest `aeat config init`
- `aeat setup` → suggest `aeat config init` / `aeat config profile`
- `aeat status` → suggest `aeat app overview status`
- `aeat sanitize` → suggest `aeat app ledger check`
- `aeat archive` → reject with "archive is retired; use profile-named workflows"
- `aeat submit` → reject with "live submission is permanently disabled"

### 11. Cross-references and conventions

This apex tracks the redesign series at all times. The `related`
frontmatter lists every accepted ADR known to the apex; the body prose
names ADRs by phrase ("the ledger-transaction-management ADR locks…") and
never via wiki-links. When a new ADR lands:

- Update the `related` frontmatter (via `vault add adr` with `--force` or
  by re-running with extended `--related` flags).
- Update the affected section to reference the new ADR by phrase.
- Move any item from the §10 child-ADR slot list into "locked" status in
  the affected section.
- Update the §8 backend exit-cap inventory to remove the entry the new
  ADR closed.

## Rationale

A single apex reduces the risk that the redesign series produces a tree
that is internally consistent at the ADR level but operationally
incoherent at the surface level. The ten existing child ADRs are
individually well-scoped, but they leave half of the operator's daily
surface (`overview`, `registry`, `live signals`, `review queue`, `app
modelo` beyond lifecycle) under-specified and several backend exit-caps
without target verbs.

This apex enforces three properties:

- **Completeness.** Every domain in the redesigned tree has a mini-app
  section. Every modelo in the registry has a per-modelo section. Every
  backend capability has a target verb (or an explicit deferral).
- **Consistency.** The cross-cutting decisions (bucket, event history,
  source-kind taxonomy, live-AEAT charter, output rendering, profile read
  path) apply uniformly across every section.
- **Traceability.** Every section references the child ADR that locks it
  (or flags the open slot). Vault dev-history (research, audit, exec)
  remains the source for context; ADRs remain the source for decisions;
  this apex is the source for the assembled shape.

The apex is intentionally evolving. It does not freeze the design before
the design is complete. It captures the current state of the design and
the locations where work remains.

## Consequences

- **Migration ordering.** The legacy roots retire in a defined order:
  `archive` first (bucket ADR closes it), `setup` second (config-profile
  ADR closes profile; auth-shape ADR closes auth; init-shape ADR closes
  init), `financial`/`filing`/`deadlines`/`browser`/`data`/`sanitize`/
  `llm` in any order as their replacement child ADRs land.
- **Tests required at each milestone.** Each section that moves from
  "evolving" to "locked" requires CLI surface tests, backend wiring
  tests, bucket-event emission tests, and (where applicable) per-modelo
  workbook-parity or AEAT-oracle-replay tests. No tautological
  calculation tests are admissible per the project's standing rule.
- **Vault hygiene.** Every section adoption updates the `related`
  frontmatter. The apex is a living document; routine `vaultspec-core
  vault check` runs must include this file.
- **Pre-conditions.** The user CLI retirement plan must execute
  before the `config` profile boundary is clean. The UX-019 AES-256-GCM
  read-path fix must execute before `app overview status` and `app
  modelo` review surfaces are stable.
- **Charter.** Live AEAT submission remains permanently forbidden. No
  section, verb, or backend exit-cap in this apex changes that. The operator
  CLI exposes no submitter support layer, and access-gate refusal remains
  authoritative.
- **Authority.** This apex is the operator's reference for the complete
  redesigned CLI shape. §9 tracks implementation debt against this design;
  it does not defer the design's authority. Execution plans and exec records
  carry the remaining build work.

## 2026-05-14 audit amendment — test-user findings

A test-user audit on a fresh Windows install surfaced ten verified
findings that fold into the redesigned CLI's authoritative shape. The
findings are absorbed in place: existing shape ADRs are amended where
they own the topic, three new ADRs cover gaps that no existing shape
ADR addresses, and one cross-cutting ADR locks the `list`-leaf semantic
contract.

The amendment also tightens four apex-level concepts:

- **Transaction identity (full-id vs display-id).** Every record-bearing
  read leaf in the redesigned CLI exposes two identity surfaces: a
  canonical `full_id` (the backend's stable, collision-free identifier)
  and a `display_id` (a presentation-layer prefix sized by the active
  bucket so all current rows remain uniquely addressable). Mutating
  leaves accept either a `full_id` or any unambiguous prefix. The
  apex's §4.2 ledger surface and any future record-bearing surface
  inherit this contract; per-surface ADRs (starting with the
  ledger-transaction-management amendment) lock the wiring.

- **Diagnostic exhaustiveness (`next:` / `report:`).** Every diagnostic
  finding emitted by any `doctor`-shaped, `repair`-shaped, or
  `health`-shaped surface MUST carry exactly one of `next:` (a runnable
  leaf invocation) or `report:` (non-recoverable guidance) at the
  rendering layer, enforced by a Pydantic validator on the finding
  model. Silent dead-end findings are unreachable by construction. The
  config-doctor-shape amendment and the existing config-repair-shape
  ADR's `DiagnosticCheck` discriminated union together cover this rule.

- **Registry exhaustiveness as an import-time invariant.** Every
  `AeatError` subclass MUST have a declared `ErrorCode` entry in
  `ERROR_REGISTRY`. The invariant is enforced at package import time
  AND by a CI test that walks the package subclass graph. Adding a new
  subclass without a registry entry fails CI; running production code
  with a registry gap raises `RuntimeError` synchronously rather than
  later when a specific command's import path is exercised. See the
  error-registry-exhaustiveness-invariant ADR.

- **Hint targets resolve to leaves.** Every post-command "next step"
  hint, every help-footer hint, and every i18n-translated variant MUST
  point at a leaf in the Typer app graph. Group-target hints are a
  programmer error and are refused at construction time. See the
  config-init-shape amendment for the canonical case.

- **Locked evidence verb shape.** The evidence-construction surface is
  the noun group `aeat app ledger evidence` with exactly five CRUD
  subcommands: `add`, `remove`, `update`, `view`, `list`. The earlier
  open-question hedge on verb spelling is closed. The existing
  `aeat app ledger attach --purchase-invoice-evidence-id` flag continues
  to consume the id produced by `aeat app ledger evidence add`. W70
  file-type scope is restricted to PDF and image (OCR path) per the
  receipt-ocr-pdf-evidence ADR; plaintext, email-body, and Drive-URL
  evidence sources are explicitly out of scope and deferred to a future
  `evidence-source-expansion` ADR (not yet authored, referenced as a
  deferred pointer only).

- **Doctor retirement enforced.** The `aeat config doctor` surface is
  retired, not patched. The config-doctor-shape ADR's status is
  superseded by the config-repair-shape ADR; the `next:`/`report:`
  exhaustiveness rule lives natively on `aeat config repair`'s
  `DiagnosticCheck` discriminated union. W70.P334 covers BOTH the
  legacy retirement (entrypoint removal, Typer unwiring, legacy
  diagnostic emitter removal, help-reference removal) AND the
  exhaustiveness verification on `aeat config repair`. No shim, no
  alias, no half-and-half. See the doctor-shape ADR's superseded
  status and the repair-shape ADR's "absorbs from retired doctor"
  section.

### Per-finding loci

| # | Severity | Topic | Patched ADR(s) | New ADR(s) |
|---|----------|-------|----------------|-----------|
| 1 | P0 | `uv run aeat` Windows .exe lock | — | `2026-05-14-cli-workflow-redesign-dev-environment-uv-windows-adr` |
| 2 | P0 | Unregistered `ErrorCode` crashes `app overview status` | — | `2026-05-14-cli-workflow-redesign-error-registry-exhaustiveness-invariant-adr` |
| 3 | P0 | Truncated transaction IDs break ledger workflow | `ledger-transaction-management` | — |
| 4 | P0 | No CLI verb constructs `purchase_invoice_evidence` | `ledger-transaction-management`, `receipt-ocr-pdf-evidence` | — |
| 5 | P1 | `aeat config doctor` retired in favour of `aeat config repair`; `next:`/`report:` exhaustiveness lives natively on the repair surface | `config-doctor-shape` (now `superseded by config-repair-shape`), `config-repair-shape` (absorbs from retired doctor) | — |
| 6 | P1 | Post-`init` hint targets a Typer group | `config-init-shape` | — |
| 7 | P1 | `list` leaves require selectors | `app-modelo-bindings-shape`, `app-live-shape` | `2026-05-14-cli-workflow-redesign-list-vs-query-leaf-semantics-adr` |
| 8 | P1 | All-caps `REFUSED:` tone | `output-rendering-normalization` | — |
| 9 | P2 | Fresh-profile review queue surfaces 20 `critical` legacy borradores | `app-review-queue-execution` | — |
| 10 | P2 | `integrity-warning: unreadable_rows` drifts | — | `2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr` |

Each row's acceptance criteria live in the named ADR's `2026-05-14
amendment` section (for patches) or the ADR's `Acceptance` / `Implementation`
section (for the three new ADRs). The apex plan's appended audit-closure
wave wires the build work for every row.

## 2026-05-14 reconciliation amendment — bi-directional ADR↔code audit

A mechanical per-wave sweep over the W01–W70 implementation surface
surfaced ~40 drift signals between the apex CLI design and the shipped
codebase. Drift is not a defect list; it is a three-way adjudication:

- **Improvement** — the shipped shape is better than the ADR specified.
  The ADR is amended up to ratify the shipped shape; the code stays.
- **Regression** — the shipped shape contradicts intent without
  justification. The code is fixed; the ADR stands.
- **Natural evolution** — the shipped shape is a small, sensible
  refinement (renamed verb, optional flag, demoted axis). The ADR delta
  is inline; both surfaces converge.

This section is the reconciliation ledger. It records the
adjudication per drift cluster and binds each verdict to a
reconciliation wave (`W71`–`W85`) in the apex plan. The reconciliation
track is the plain numeric continuation of the `W01`–`W70` execution
spine; no separate suffix is used.

### Standardized CRUD verb contract for mutating noun-groups

The reconciliation sweep surfaces a cross-cutting pattern: every CLI
domain that exposes an "edit work surface" over persisted records
(ledger transactions, purchase invoice evidence, payable and
collectible invoices, profile values, auth providers, apoderado
configuration, inventory rows, bucket records, usage ratios) has
drifted into a domain-specific verb vocabulary
(`create/edit/archive/stash/reset/track/read` in ledger;
`get/set/unset/status` in profile; `configure/clear` in auth; etc.).

The locked W70.P333 verb shape for `aeat app ledger evidence` —
exactly five verbs `add / remove / update / view / list` — is the
canonical mutating-noun-group contract for the redesigned CLI. Every
mutating noun-group MUST adopt this five-verb spine:

- **`add`** — construction verb. Accepts the inputs needed to
  materialise a new record; emits the matching `*.created` bucket event;
  returns the new record's `full_id`.
- **`remove`** — retirement verb. Accepts a `full_id` or any
  unambiguous prefix per the 2026-05-14 transaction-identity
  amendment; refuses on collision with the matching candidate set;
  cascades evidence/link/review-item detachment per the noun-group's
  retirement policy; emits the matching `*.removed` bucket event.
- **`update`** — mutation verb. Updates user-editable fields on an
  existing record by `full_id` or unambiguous prefix; rejects
  attempts to mutate immutable fields with a typed validation error;
  emits the matching `*.updated` bucket event.
- **`view`** — single-record read verb. Returns the full record
  payload for one `full_id` or unambiguous prefix; read-only; emits
  no bucket event.
- **`list`** — collection read verb. Bare invocation returns the
  full set of records in the active bucket per the W70.P336
  list-vs-query semantic contract; refining filters
  (`--state`, `--kind`, `--year`, etc.) are optional; read-only;
  emits no bucket event.

**Orthogonal axes are sub-verbs, not CRUD substitutes.** Domain-
specific operations that are not record-lifecycle operations
(`classify`, `allocate`, `attach`, `link`, `check`, `preflight`,
`reconcile`) remain as distinct verbs at the noun-group level; they
are orthogonal axes over existing records, not parallel CRUD
vocabularies. A noun-group that exposes `classify` and `allocate`
still owns `add/remove/update/view/list`; the orthogonal verbs
operate on records the CRUD spine materialised.

**Lifecycle-state operations remain explicit.** Verbs that move a
record between named states with distinct semantics (`archive`,
`stash`, `reset`, `discard`) are not CRUD operations; they remain
explicit lifecycle verbs at the noun-group level. They emit
state-specific bucket events (`*.archived`, `*.discarded`, etc.) and
do not collapse into `remove` or `update`.

**Key-value-as-record exceptions.** Where a noun-group's records are
*conceptually keyed scalars* rather than entities (the profile
schema, usage ratios, configuration keys), the canonical CRUD shape
adapts: `add` → `set KEY VALUE`, `remove` → `unset KEY`,
`update` → `set KEY VALUE` (idempotent), `view` → `get KEY`,
`list` → `list [--prefix PREFIX]`. The exception is documented
explicitly per noun-group; default is the strict five-verb CRUD
spine.

**Lock.** The W71 wave inventories every mutating noun-group in the
redesigned tree, adjudicates current verbs against the contract,
and produces per-noun-group migration steps. Subsequent waves
(`W72`–`W77`) close the per-domain reconciliation in priority
order. The contract becomes immutable once W71 lands; future
mutating noun-groups MUST conform without exception.

### Reconciliation ledger — verdict table

Each row records: the drift cluster surfaced by the audit, the
adjudication (improvement / regression / evolution), and the
reconciliation wave that closes it. Detail per row lives in the
named wave's plan section and (for ratifications) in inline
amendments to the affected child ADR.

| # | Drift cluster | Affected waves/ADRs | Verdict | Closes via |
|---|---------------|---------------------|---------|------------|
| R01 | Cross-cutting CRUD verb soup across mutating noun-groups | apex §2, §4.2, §4.3, ledger-transaction-management ADR | Evolution (lock canonical 5-verb spine; document key-value exceptions) | `W71` |
| R02 | `aeat app modelo` uses nested sub-apps (`work/bindings/filing-record/verification-report`) instead of flat verb tree per apex §4.3 | apex §4.3, app-modelo-shape ADR, W46 | Adjudicate — likely Improvement (nested groups carry operator-mental-model grouping ADR did not anticipate); if ratified, amend apex §4.3 to declare nested grammar canonical | `W72` |
| R03 | `aeat app ledger` ships 16 verbs vs locked 11 (extras: `create/edit/archive/stash/reset/track/read`; missing: `link/check/preflight`) | ledger-transaction-management ADR, W23 | Mixed — adjudicate per verb: `create/edit` map onto CRUD `add/update` (Evolution); `archive/stash/reset` are lifecycle state verbs (Evolution, document explicitly); `track/read` likely redundant with `view`/event history (Regression — retire); `link/check/preflight` missing (Regression — add) | `W72` |
| R04 | `payable_invoice` and `collectible_invoice` source kinds have zero CLI noun-group mount despite being locked taxonomy citizens | invoice-domain-decoupling ADR, apex §2 | Regression — Add `aeat app ledger payable-invoice` and `aeat app ledger collectible-invoice` CRUD noun-groups | `W73` |
| R05 | `aeat config profile` ships 5 of 13 locked verbs (`list/get/set/unset/status`); missing `add/remove/edit/show/duplicate/export/import/validate/preflight` + `use` alias | config-cli-profile-surface ADR, config-profile-use-and-status ADR, W10, W19 | Evolution — adopt key-value-as-record exception for value editing (`set/get/unset` ratified); add profile-lifecycle CRUD (`add/remove/update/view/list` for profile *records*) and the `use` alias | `W74` |
| R06 | `aeat config auth apoderado` subgroup entirely absent; `--scope` catalogue absent | apoderamientos-surface ADR, apoderado-scope-vocabulary ADR, W20, W21 | Regression — ship full subgroup; ship `registry/aeat/apoderamientos/scopes.toml` | `W75` |
| R07 | `aeat app ledger inventory` Typer mount absent; `application/inventory` layer absent; domain layer exists | inventory-management-cli-design ADR, inventory-placement ADR, W24, W25 | Regression — wire application service + Typer mount; reconcile verbs to W71 contract | `W76` |
| R08 | `aeat app ledger ratios` and the historically locked `aeat config bucket` shape shipped partial verb sets vs locked grammar | app-ledger-ratios-shape ADR, bucket ADR, W13, W26 | Evolution — ratios are key-value records (apply exception); bucket maintenance verbs (`browse/search/export/import/rename/delete`) are lifecycle operations, not CRUD (document explicitly); operator `config bucket` is retired | `W77` |
| R09 | `aeat app modelo file --by ACTOR` mandatory; ADR specifies optional with default = active profile display_name | actor-attribution ADR, W44 | Regression — change Typer Option to optional with default factory | `W78` |
| R10 | `aeat app modelo discard` exists but `modelo.work_unit.discarded` is not a `BucketEventType` enum member and is never emitted | app-modelo-discard ADR, bucket-event-history ADR, W45 | Regression — add enum entry; emit event in `discard_work_unit` action | `W78` |
| R11 | `aeat app modelo calculate --borrador SNAPSHOT_ID` flag absent | borrador-100-binding-integration ADR, W48 | Regression — wire borrador-100 binding integration per ADR | `W78` |
| R12 | `aeat app live` mounts only `filed` subgroup; ADR §4.4 locks 7 subgroups | app-live-shape ADR, W54 | Regression — mount 6 missing subgroups (notifications/expedientes/verify nif-iva+tgvi/borrador/portals) behind `require_live_read()` | `W79` |
| R13 | `aeat app live portals` mount absent; `application/portals/` wrapper missing | domain-portals-harvest ADR, W35 | Regression — close P174 (application wrapper + Typer mount) | `W79` |
| R14 | `WorkflowEngine.run_for_period` exists but is not invoked from `aeat app modelo file` | workflow-engine-harvest ADR, W58 | Regression — wire `run_for_period` into `file_modelo_revision` per apex §8 backend exit-cap mandate | `W80` |
| R15 | `SubmissionEngine.preflight` exists but is not invoked from `verify_modelo_revision`/`file_modelo_revision` | apex §8, W65 | Regression — invoke preflight inside both modelo actions (alternative: route everything through `WorkflowEngine`; adjudicate during wave) | `W80` |
| R16 | `aeat app modelo work resume <workflow_run_id>` entirely absent | workflow-resumption-semantics ADR, W59 | Regression — ship verb per ADR with `resumed_from_run_id` retry context and no replay semantics | `W80` |
| R17 | `aeat app overview` ships only `status` verb; `calendar/agenda/backlog/explain` not exposed as discrete verbs (`--calendar` is a flag on `status`) | app-overview-shape ADR, W53 | Adjudicate — flag-on-status may be Improvement (single verb with axis switches) or Regression (loses discoverability); if Improvement, amend §4.1 | `W81` |
| R18 | `domain/deadlines/_festivos.shift_deadline` exists but is never called from `OverviewCalendarEntry`; `adjusted_closes_on` field absent | festivos-deadline-shift ADR, W37 | Regression — wire into overview calendar; add field; retire legacy `entrypoints/cli/deadlines/` package | `W81` |
| R19 | `aeat config repair` ships 4 of 6 locked subverbs (`connectivity/quarantine/reset-state/logs`); missing `integrity` and `list` | config-repair-shape ADR, W18 | Regression — add 2 subcommands wired to existing AES-256-GCM scan + namespace inventory functions | `W82` |
| R20 | `aeat config init` exists via wizard but no atomic init service; bucket.created/profile.created/profile.activated events not emitted | config-init-shape ADR, config-vs-setup-namespace ADR, W15, W11 | Regression — build `src/aeat/application/setup` service; close `aeat config auth setup` orphan reference in diagnostics | `W83` |
| R21 | Registry domain admits bare `invoice` source bindings for 347/349/720 despite four-source taxonomy lock | per-modelo-aggregation-pipeline ADR, invoice-domain-decoupling ADR, W52 | Regression — reject bare `invoice` at registry domain layer; ship retenciones (111/115/123/180/190/193), 347/349 counterpart, 720 aggregators using explicit source kinds | `W84` |
| R22 | Modelo 036/037 and 145 foundations absent (no registry TOML) | modelo-036-037-foundation ADR, modelo-145-foundation ADR, W50, W51 | Unstarted greenfield (not drift) — ship TOMLs + binding contracts | `W85` |
| R23 | `EvidenceBundle` class + `aeat app modelo audit show/check/export/replay` verbs absent | evidence-bundle-shape ADR, W57 | Unstarted greenfield — ship per ADR | `W85` |
| R24 | `application.ledger.classify_ledger_transaction` wrapper absent; `application/rental` + CLI absent; `aeat app modelo reconcile --justificante` CLI absent | domain-harvest-vat-classification ADR, domain-harvest-rental ADR, W32, W34, W64 | Regression — backend-done-CLI-deferred pattern; ship wrappers and CLI surfaces | `W85` |
| R25 | Plan rows out of sync with shipped code (`W22` invoice decoupling; `W34` rental domain; `W35` portals `_cli.py` deletion; `W44` actor flags; `W45` discard verb) | epic plan ledger, multiple waves | Bookkeeping — check [x] rows after wave-specific reconciliation lands; no ADR impact | Closed inline as each wave above lands |

W80.P385.S2206/S2207 verdict: `SubmissionEngine.preflight` is routed through
`WorkflowEngine.run_for_period` only. Modelo actions and CLI handlers must not
call `SubmissionEngine.preflight` directly. The verify and file paths satisfy
R15 by delegating to WorkflowEngine before verified-state or filing-state
mutation; both paths use the same WorkflowEngine-owned gate rather than a
second direct preflight policy path.

### Cross-reference index

| Reconciliation wave | Apex section(s) amended | Child ADR(s) amended | Plan scope |
|---|---|---|---|
| `W71` — CRUD verb contract | §12.b (new); §2 cross-cutting | None (cross-cutting amendment lives in apex) | New |
| `W72` — modelo grammar reconcile | §4.3 | `app-modelo-shape`, `ledger-transaction-management` | Closes R02, R03 |
| `W73` — invoice noun-groups | §4.2 | `invoice-domain-decoupling`, `ledger-transaction-management` | Closes R04 |
| `W74` — profile noun-group | §3.2 | `config-cli-profile-surface`, `config-profile-use-and-status` | Closes R05 |
| `W75` — apoderado noun-group | §3.3 | `apoderamientos-surface`, `apoderado-scope-vocabulary` | Closes R06 |
| `W76` — inventory noun-group | §4.2 | `inventory-management-cli-design`, `inventory-placement` | Closes R07 |
| `W77` — ratios + bucket lifecycle services | §3.4, §4.2 | `app-ledger-ratios-shape`, `bucket` | Closes R08 service scope; search deferred by bucket-search ADR |
| `W78` — modelo lifecycle drift fixes | §4.3 | `actor-attribution`, `app-modelo-discard`, `borrador-100-binding-integration` | Closes R09, R10, R11 |
| `W79` — app live shape completion | §4.4 | `app-live-shape`, `domain-portals-harvest` | Closes R12, R13 |
| `W80` — workflow + preflight + resume wiring | §4.3, §8 | `workflow-engine-harvest`, `workflow-resumption-semantics` | Closes R14, R15, R16 |
| `W81` — overview shape completion | §4.1 | `app-overview-shape`, `festivos-deadline-shift` | Closes R17, R18 |
| `W82` — config repair completion | §3.6 | `config-repair-shape` | Closes R19 |
| `W83` — config init backend service | §3.1 | `config-init-shape`, `aeat-cli-config-vs-setup-namespace` | Closes R20 |
| `W84` — aggregation taxonomy enforcement | §2 (source-kind taxonomy) | `per-modelo-aggregation-pipeline`, `invoice-domain-decoupling` | Closes R21 |
| `W85` — modelo foundations + harvest completions | §5, §7, §8 | `modelo-036-037-foundation`, `modelo-145-foundation`, `evidence-bundle-shape`, `domain-harvest-vat-classification`, `domain-harvest-rental` | Closes R22, R23, R24 |

### Implementation discipline

Each reconciliation wave follows the standard 5-phase template
(backend implementation → shadow duplicate removal → de-shim and
de-stub cleanup → real behavior verification → thin CLI exposure),
matching the `W01`–`W70` spine. Wave IDs are the plain numeric
continuation (`W71` … `W85`); no special suffix.

Per-wave ADR amendments are written inline into the affected child
ADR's `2026-05-14 reconciliation amendment` section. The apex's
`related:` frontmatter is updated to reflect any new child ADRs
introduced by reconciliation (none anticipated; the lock lives in
this apex amendment).

The reconciliation ledger is closed when every R-row above is
either marked `closed by W##` or explicitly deferred with a named
follow-up ADR. The 2026-05-14 audit amendment (above this section)
remains the authoritative entry point for the test-user findings;
this section extends it with the per-wave-sweep findings.

### Closure status (updated as waves land)

This block is the truth-of-state companion to the R-row table above.
The "Closes via" column names the *intended* wave; this block names
the *current* state of that wave as of the most recent execution
sweep.

| R-row | Closing wave | State |
|---|---|---|
| R01 | W71 | ✅ closed |
| R02, R03 | W72 | ✅ closed (modelo grammar reconciled; `reconcile` verb naming deferred — does not block closure) |
| R04 | W73 | ✅ closed |
| R05 | W74 | ✅ closed |
| R06 | W75 | ✅ closed |
| R07 | W76 | ✅ closed |
| R08 | W77 | ✅ closed |
| R09, R10, R11 | W78 | ✅ closed |
| R12, R13 | W79 | ✅ closed |
| R14 | W80 | ✅ closed — code: `_run_revision_workflow_gate` routes verify and file through `WorkflowEngine.run_for_period`; no direct CLI workflow surface exists. |
| R15 | W80 | ✅ closed — code: preflight is internal to `WorkflowEngine` at `RUNNING_PREFLIGHT`; modelo actions only compose the real `SubmissionEngine` dependency and never call `SubmissionEngine.preflight` directly; `aeat workflow`, `aeat run`, and `aeat app modelo preflight` remain absent. |
| R16 | W80 | ✅ closed — `resume_modelo_workflow` local action shipped; the reconciled CLI mount is `aeat app modelo work resume WORKFLOW_RUN_ID`; the handler delegates to the workflow application service, accepts workflow run ids only, and does not reconstruct argv, replay traces, resume mid-stage, or create compatibility surfaces. |
| R17, R18 | W81 | ✅ closed (`shift_deadline` wired into `OverviewCalendarEntry`; calendar adjudication ratified) |
| R19 | W82 | ✅ closed |
| R20 | W83 | ✅ closed |
| R21 | W84 | ✅ closed |
| R22 | W85 | ⏸️ deferred — Modelo 036/037 + 145 foundations explicitly deferred pending a live-AEAT reconciliation research pass. Census forms have a special meaning in the Spanish tax system that does not match the filing-modelo template; a separate ADR will succeed `modelo-036-037-foundation` before any registry TOMLs land |
| R23 | W85 | ✅ closed (`EvidenceBundle` + `aeat app modelo audit` verbs shipped) |
| R24 | W85 | 🔄 partial — vat-classification wrapper + rental wrappers shipped; `aeat app modelo reconcile --justificante` verb deferred (verb name under review) |
| R25 | inline | 🔄 ongoing bookkeeping; closes inline as each wave's plan rows are ticked |

#### 2026-05-15 audit correction (overlay on the closure table above)

A read-only ground-truth audit on 2026-05-15 verified each R-row's
closure against the codebase via per-wave subagents. The table above
shows the in-flight closure intent; the audit found the following
R-rows were paper-closed and require reopening or partial annotation.
Detail and per-step reopen list lives in the audit document.

| R-id | Audit verdict | Why |
|---|---|---|
| R02 | reopened | `aeat app modelo reconcile` verb absent from Typer graph |
| R03 | reopened | `aeat app ledger {link, check, preflight}` verbs absent |
| R05 | partial | `export` / `import` profile verbs and `profile.exported` / `.imported` / `.activated` events absent |
| R08 | reopened | `BucketMaintenanceService` and bucket maintenance verbs absent; ratios event emission unwired |
| R14 | partial | `WorkflowResult.resumed_from` field and `run_for_period(resumed_from=)` parameter never landed despite exec-record claim |
| R17 | partial | only `status` verb shipped; `calendar` / `agenda` / `backlog` / `explain` absent |
| R18 | partial | `next_due` field on agenda payload absent |
| R20 | partial | three event types named in plan are absent or named differently in the enum |
| R21 | partial | `registry/aeat/modelos/349.toml` migrated to per-direction `collectible_invoice` / `payable_invoice` (per audit) — done |
| R24 | partial | `aeat app modelo reconcile from-justificante PATH` and Modelo 036 `alta` / `modificacion` / `baja` lifecycle verbs absent |

## 2026-05-20 amendment — testimonial-driven CLI verification

A testimonial-driven CLI verification campaign (nine human-persona
agents operating the real CLI end-to-end; method locked in
`[[2026-05-20-testimonial-driven-cli-verification-playbook]]`,
findings in `[[2026-05-20-cli-testimonial-findings-inventory]]`)
exercised the redesigned CLI as real taxpayers. It confirms several
apex R-rows from live use and surfaces CLI-surface proposals that
belong here.

### Shell defects — fixed, no ADR surface change

Nine operator-shell defects were fixed in place (auth-readiness check,
ledger allocate classification, profile-rename atomicity, silent
profile-create, period-token validation, exit codes, auth-status
consistency, error field scrubbing, Windows console UTF-8). These are
implementation defects within the already-ADR'd surface; they do not
alter the root contract. Detail and regression tests in the inventory.

### Confirmation of existing R-rows from live use

- **R17 (overview `agenda`/`calendar`/`backlog`/`explain` absent)** —
  confirmed live: `aeat app overview status` answers workspace state
  but cannot answer "what must I file and when?". A non-expert
  persona's primary use-case is unmet until R17's remaining verbs land
  under the `app-overview-shape` child ADR.
- **R23 evidence / `app ledger attach`** — confirmed gap: `attach`
  requires an evidence id but no CLI surface creates one. The
  evidence-creation path designed in the `receipt-ocr-pdf-evidence`
  child ADR (§7) is unshipped; until it lands, `attach` is unreachable.

### New CLI-surface proposal — obligation registration for `verify`

`aeat app modelo work verify` dead-ends at `NO_PENDING_OBLIGATION`,
and no verb registers a filing obligation, so `create → calculate →
verify → export` cannot complete (personas Elena, Teresa). The apex
must adjudicate where the "pending obligation" originates:

- **Option A (preferred): derive it from the deadline engine.** When
  R17's `agenda`/`calendar` surface lands, an obligation becomes
  *pending* automatically once its period window opens; `verify`
  consumes that derived obligation. No new verb — the gap closes as a
  dependency of R17. This keeps obligations a property of the
  deadline/agenda surface, not a manual operator action.
- **Option B: an explicit `aeat app modelo work register-obligation`
  verb** under the existing `modelo work` group, for cases where a
  taxpayer files outside the derived calendar (late, complementaria).

Recommendation: adopt Option A as the default and Option B only as the
escape hatch for off-calendar filings. The `modelo-verify` and
`app-overview-shape` child ADRs must jointly own this; whichever
lands, `verify` must surface an actionable `next:` pointing at the
obligation step rather than a bare `NO_PENDING_OBLIGATION` refusal.

### Smaller surface proposals (for child-ADR adjudication)

- `aeat app modelo list` shows all 26 modelos unfiltered; propose a
  profile-applicability filter / `--mine` flag so a taxpayer sees only
  their modelos. Owner: `app-modelo-shape` child ADR.
- Profiles carry no individual-vs-company entity-type discriminator;
  a company admin sees IRPF/personal fields. Propose an entity-type
  field on the profile. Owner: `config-profile-*` child ADRs.

### Cross-references

- Verification method: `[[2026-05-20-testimonial-driven-cli-verification-playbook]]`
- Findings inventory: `[[2026-05-20-cli-testimonial-findings-inventory]]`
- R17 owner: `[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]`
- verify owner: `[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]`
- evidence owner: `[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]`

## 2026-06-03 amendment — R08 progression and composition pattern

The W77 `BucketMaintenanceService` work resumed under the composition
pattern locked by `[[2026-06-03-cli-workflow-redesign-adr]]`. The
service is now operational for three of the six bucket-maintenance
verbs against the existing single-writer primitives. The 2026-05-15
audit correction reopened R08; this amendment records the current
state honestly so a future closure pass has the inventory to verify
against.

### R08 — partial closure progression

| Verb | State | Composition |
|---|---|---|
| `rename` | ✅ landed | Delegates to top-level `rename_profile`; emits `BUCKET_RENAMED` alongside the inner `PROFILE_RENAMED`. |
| `delete` | ✅ landed | Composes `delete_profile_with_lifecycle_span` + `remove_profile_bucket_directory`; service-side `confirmed=True` + active-bucket refusals. |
| `browse` | ✅ landed | Namespace-level inventory via `SecureObjectRepository.list_namespaces` + per-namespace `list_keys`. Key-level browse with `SensitivityClass` redaction is a follow-up. |
| `export` | ✅ landed | Composes `serialize_profile_bundle`, `ExportArchiveHeader`, sealed-archive writer, active bucket DEK or recovery passphrase wrap, and emits `BUCKET_EXPORTED`. |
| `import` | ✅ landed | Composes sealed-archive parse, schema/collision/passphrase guards, bucket provisioning, `deserialize_profile_bundle`, and emits `BUCKET_IMPORTED`. |
| `search` | 🔍 deferred | Search scoping is owned by the accepted bucket-search ADR: per-domain repository dispatch via a closed `BucketSearchScope` enum, recency-first ranking MVP. It is not part of W77 service closure. |

Bucket maintenance verbs are intentionally lifecycle operations, not
CRUD, per W71's contract — the `browse` / `search` axes are key-value
queries on container contents, and the `export` / `import` / `rename`
/ `delete` axes operate on the container itself. The maintenance
events `BUCKET_RENAMED` / `BUCKET_DELETED` / `BUCKET_EXPORTED` /
`BUCKET_IMPORTED` are intentionally distinct from the lifecycle
events the inner primitives emit; two-event co-emission per operator
action is the audit shape.

### CLI mount retired

The older `aeat config bucket` mount requested by `W77.P374.S2150` is
superseded by the 2026-06-10 operator-surface decision. The command group is
retired and must not be restored. `BucketMaintenanceService` remains the
backend/application owner for storage lifecycle operations; any future operator
surface must use profile-named vocabulary and keep the CLI as a service
consumer.

### R08 closure target

R08 closes when the ledger ratios key-value exception is documented, the
bucket-maintenance service owns the verified lifecycle operations
(`browse`, `export`, `import`, `rename`, `delete`), the old `config bucket`
operator mount is retired, and the child ADRs carry the composition-pattern
amendment named in `W77.P374.S2153`. Search is deferred to the accepted
bucket-search ADR and no longer blocks W77.

## 2026-06-12 amendment - `config bucket` operator surface superseded

The 2026-06-10 operator-surface ADR supersedes the older `aeat config
bucket` operator mount. The command group is retired and must not be
reintroduced by W77 closeout work. The accepted operator-facing history
surface is `aeat config profile history PROFILE`; it resolves the supplied
profile through the workflow/profile registry and uses the immutable bucket id
only inside the application/domain event-history read. The stable JSON envelope
token remains `config.bucket.history` as a machine-API carve-out, not as an
operator-facing spelling.

This supersedes the literal `bucket_app` mount requested by
`W77.P374.S2150`. Bucket-maintenance service verbs (`rename`, `delete`,
`browse`, `export`, `import`) remain backend/application lifecycle operations.
They should not be exposed through `aeat config bucket`; any future operator
surface for those operations needs a fresh profile-named design rather than
resurrecting the retired storage noun.

R08 is closed for W77 after export/import landed and the retired mount was
recorded. Search remains a separate bucket-search follow-up rather than a W77
closure blocker.

## 2026-06-03 amendment — full R-row refresh from ground-truth audit

A second 2026-06-03 ground-truth audit pass re-verified every R-row
in the 2026-05-15 audit-correction table against the current HEAD
of `chore/eliminate-shims`. Several R-rows the 2026-05-15 audit
marked as reopened or partial are now closed at HEAD. The refresh
table below supersedes the 2026-05-15 audit-correction table for
the R-rows it covers; R-rows omitted here retain their 2026-05-15
state.

| R-id | 2026-05-15 | 2026-06-03 | Closure evidence |
|---|---|---|---|
| R02 | reopened | ✅ closed | `aeat app modelo reconcile` at `src/aeat/entrypoints/cli/_modelo.py:4739` + coverage in `test_modelo_reconcile_verb.py` |
| R03 | reopened | ✅ closed | `link` / `check` / `preflight` at `src/aeat/entrypoints/cli/_ledger.py:1226` / `:1372` / `:1481` + coverage |
| R05 | partial | ✅ closed | `PROFILE_EXPORTED` emission at `_config/__init__.py:1623`, `PROFILE_IMPORTED` at `:1794`, `PROFILE_ACTIVATED` at `_orchestration.py:277` and `:291` |
| R08 | reopened | ✅ closed | `BucketMaintenanceService` at `_service.py:49`; rename + delete + browse + export + import operational; search deferred by bucket-search ADR; retired `config bucket` mount recorded. See R08 progression amendment above. |
| R14 | partial | ✅ closed | `WorkflowResult.resumed_from` at `_models.py:484` + engine propagation at `_engine.py:254-429` |
| R17 | partial | ✅ closed | overview `calendar` / `agenda` / `backlog` / `explain` verbs at `_overview.py:109` / `:336` / `:431` / `:509` |
| R18 | partial | ✅ closed | `next_due` field at `_agenda.py:76` + computation at `:138-158` + test gate `test_agenda_next_due_is_earliest_future_or_today_deadline` |
| R20 | partial | 🔄 partial (still) | `PROFILE_BUCKET_CREATED` (combines bucket.created + profile.created) + `PROFILE_ACTIVATED` present in `_event.py:83,92`; the 2-into-1 composite is documented and stable but the plan-row vocabulary still differs |
| R21 | partial | 🔄 partial (still) | `349/.../0007-bindings.toml` has 17/17 `collectible_invoice` bindings; `payable_invoice` (intracomunitarias adquisiciones) bindings absent |
| R24 | partial | 🔄 partial (improved) | `reconcile-from-justificante` shipped at `_modelo.py:4834`; M036 `alta` / `modificacion` / `baja` lifecycle verbs still absent — these are the open S2349 work |

R02 / R03 / R05 / R14 / R17 / R18 are NOW honest closures and the
ADR's apex R-row ledger should reflect that on its next consolidation
pass. R20 / R21 / R24 retain their partial qualifier per the
specific gaps named above.

The 2026-06-03 ground-truth audit is the methodology this amendment
applies: per-R-row file:line evidence cited from a fresh-context
read of HEAD, not from the prior closure-claim record.
