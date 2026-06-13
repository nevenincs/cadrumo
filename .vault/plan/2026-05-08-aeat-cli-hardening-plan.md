---
tags: ["#plan", "#aeat-cli-hardening"]
date: 2026-05-08
modified: '2026-05-08'
related:
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-05-07-user-profile-backend-schema-plan]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-research]]"
  - "[[2026-05-02-aeat-cli-redesign-research]]"
  - "[[2026-04-27-auth-cli-research]]"
  - "[[2026-05-12-cli-design-research]]"
---



# `aeat-cli-hardening` `Broad CLI Review And Backend Alignment` plan

This plan turns the 2026-05-08 CLI gap audit into an executable, review-gated
rollout. The work is broader than user-interface text: missing backend APIs,
schema routing, validation ownership, registry query surfaces, output/error
contracts, and test integrity are in scope whenever the CLI currently
reimplements or shadows core behavior.

The current live root exposes `aeat setup` and `aeat app`. The target design
must reconcile that live tree with the accepted `aeat config profile` profile
facade and with the broader CLI wireframe direction. This plan is intentionally
repetitive: every audit issue and every action has its own row so execution can
close work mechanically without losing provenance.

## Proposed Changes

Replace the CLI-as-transactional-command shape with a self-documenting,
state-aware, backend-owned command product surface.

The CLI layer remains transport only. It may parse command arguments, route to
application/domain APIs, format typed results, and set exit codes. It must not
own business decisions, schema validation, profile semantics, modelo
requirements, filing calculations, auth behavior, persistence behavior, or
recovery logic. Any missing backend behavior discovered during CLI hardening is
implementation scope for this rollout.

The rollout preserves the audit's original `UX-*` and `A*` identifiers. New
surfaces discovered during implementation must be appended to this plan before
coding continues.

## Hard Invariants

- [ ] CLI changes are limited to argument parsing, command registration, output
      formatting, exit behavior, and delegation.
- [ ] Validation, mutation, persistence, schema decisions, filing decisions,
      deadline decisions, auth decisions, and modelo calculations live in
      backend/application/domain code.
- [ ] Missing backend changes are in scope and must be implemented before the
      CLI exposes the affected behavior.
- [ ] Tests must be meaningful, non-tautological, and capable of failing when
      the protected behavior regresses.
- [ ] Tests must not use fakes, mocks, stubs, patches, monkeypatches, `skip`,
      or `xfail` as shortcuts for a passing run.
- [ ] Every closed row requires a code review pass.
- [ ] Every major wave and significant repair pass is committed separately with
      explicit staging only.
- [ ] The shared worktree is protected: no destructive git commands, no broad
      staging, no reverting unrelated changes.
- [ ] Newly discovered CLI, backend, registry, profile, filing, or test surface
      is appended here before implementation proceeds.

## Execution Contract

Each execution step must record:

| Field | Required content |
|---|---|
| `audit_id` | Original `UX-*`, `A*`, or `DISCOVERED-*` id. |
| `wave` | Current rollout wave. |
| `owner_scope` | Backend and CLI files/modules owned by the step. |
| `backend_owner` | Application/domain/registry owner for behavior. |
| `cli_owner` | Command module that presents behavior. |
| `entry_criteria` | Preconditions before editing. |
| `work_items` | Concrete backend and CLI work. |
| `verification` | Real behavior checks; no tautological tests. |
| `review_gate` | Code review scope and required finding resolution. |
| `commit_policy` | Explicit staging list and commit boundary. |
| `residual_risk` | Known remaining risk after the step. |

## Backend Ownership Map

| Surface | Backend owner | CLI owner | Notes |
|---|---|---|---|
| Root command tree and global flags | Application-level CLI contract APIs where needed | `src/aeat/entrypoints/cli/__init__.py` | CLI registration only; no business logic. |
| Legacy setup profile | `src/aeat/application/profile`, `src/aeat/domain/profile` | `src/aeat/entrypoints/cli/_setup.py` | Replacement target; do not extend as second schema authority. |
| Central user profile | `src/aeat/domain/user_profile`, secure profile backend to be added | `aeat config profile` surface | Must use schema-driven backend, not `PROFILE_KEYS` duplication. |
| User CLI state | `src/aeat/application/user_cli.py` | setup/config/profile/app status commands | Encrypted state is backend-owned. |
| Auth providers and sessions | `src/aeat/application/auth` | setup/auth or future auth/config commands | CLI only presents typed auth results. |
| Overview/calendar readiness | `src/aeat/application/overview`, `src/aeat/domain/deadlines`, profile backend | `src/aeat/entrypoints/cli/_overview.py` | Calendar completeness and next-action logic must be backend-owned. |
| Filing calculation/review/export | `src/aeat/application/filing`, `src/aeat/application/review`, `src/aeat/domain/filing` | `src/aeat/entrypoints/cli/_declaration.py` | Missing binding/preflight/fix suggestions must be backend-owned. |
| Registry/modelo introspection | `src/aeat/domain/calculations/registry`, new registry query API | app modelo/config/registry surfaces | CLI must not read TOML directly. |
| Error and output contracts | `src/aeat/core/errors`, `src/aeat/entrypoints/cli/_errors.py`, output models | All CLI modules | Structured error/fix rendering is shared infrastructure. |
| Diagnostics and logs | `src/aeat/core.logging`, application diagnostics service | `config doctor` surface | `config doctor` composes typed backend diagnostics. |

## Waves

- [ ] `W0 Evidence And Guardrails`: import the audit mapping, freeze invariants,
      record dirty-worktree policy, and create the first execution records.
- [ ] `W1 Live CLI Inventory`: inventory executable help, registered commands,
      unregistered CLI modules, i18n/help flags, output formats, and tests.
- [ ] `W2 Boundary Classification`: classify each command and action as
      transport-only, backend-owned, live-read, live-write, deprecated, or
      missing backend.
- [ ] `W3 Backend Ownership Routing`: assign every action to concrete backend
      and CLI owners before code changes.
- [ ] `W4 User Profile And Config Alignment`: align `aeat setup profile` with
      the approved `aeat config profile` backend design.
- [ ] `W5 Registry, Modelo, And Live-Read Hardening`: expose schema/modelo
      introspection through backend APIs and audit registry live-read/capture.
- [ ] `W6 Output, Error, Warning, And JSON Contract`: centralize rendering,
      suggestions, topics, formats, and logging policy.
- [ ] `W7 Root Migration And Alias Policy`: implement the root command strategy,
      onboarding, doctor, topics, config, and alias/removal decisions.
- [ ] `W8 Test And Review Gate Enforcement`: replace weak tests, add
      real-behavior tests, and formalize code review gates.
- [ ] `W9 Surface Closure Audit`: search all registered, unregistered, and new
      CLI surfaces; append and close discovered rows.
- [ ] `W10 Continuous Review And Repair Loop`: repeat review, repair, verify,
      and commit until no actionable CLI hardening findings remain.

## Issue Ledger

| Done | audit_id | Severity | Surfaces | Required action ids | Primary owner route | Verification gate |
|---|---|---|---|---|---|---|
| [x] | UX-001 | HIGH | `aeat`, missing `aeat config doctor` | A1, A2 | diagnostics backend plus config CLI | Missing dependency is rendered as structured diagnostic, not traceback. |
| [ ] | UX-002 | HIGH | `aeat --version` | A3 | root CLI plus registry summary backend | `aeat --version`, `aeat -V`, and `aeat version` return version and registry summary. |
| [ ] | UX-003 | HIGH | missing `aeat init`, setup/profile help ordering | A4, A5, A6 | onboarding backend plus root/setup CLI | Help and command tree expose workflow order and root quickstart. |
| [ ] | UX-004 | HIGH | setup init/auth configure help | A7, A8 | command metadata/query backends plus setup CLI | Help output includes examples, format hints, and discovery pointers. |
| [x] | UX-005 | HIGH | internal warning on every command | A9, A10, A11 | logging/crypto backend plus root CLI | Normal commands emit no internal logs; verbose/debug opt in. |
| [ ] | UX-006 | HIGH | setup status/profile show/profile validate | A12, A13, A14, A15 | readiness/profile backend plus setup/config CLI | Per-modelo readiness replaces boolean-only validity. |
| [ ] | UX-007 | HIGH | profile list-keys/profile set | A16, A17, A18 | central user-profile backend plus config/profile CLI | IVA/IRPF/modelo enrollment keys are schema-backed and engine-readable. |
| [ ] | UX-008 | HIGH | overview calendar | A19, A20 | overview/deadline/profile backend plus overview CLI | Incomplete profile emits warnings/completeness or requires explicit override. |
| [ ] | UX-009 | HIGH | app overview status, app help | A21 | state/next-action backend plus app CLI | App summary emits `Siguiente` from backend state graph. |
| [ ] | UX-010 | MEDIUM | overview calendar overdue entries | A22 | deadline/recovery backend plus overview CLI | OVERDUE entries include recovery action and legal reference. |
| [ ] | UX-011 | LOW | auth reset, profile show, setup reset | A23, A24, A14 | auth/profile/setup backends plus setup CLI | Language, reset, and all-key display behavior are consistent. |
| [ ] | UX-012 | HIGH | unknown keys, calculate missing bindings, all failures | A25, A26 | error/fix backend plus all CLI modules | Errors include code, suggestion, concrete fix, and learning pointer. |
| [ ] | UX-013 | MEDIUM | format/provider/kind help | A27, A28, A29 | catalogue/topic/completion backends plus CLI | Flag catalogues, topic docs, and completion match accepted values. |
| [ ] | UX-014 | HIGH | missing `aeat config doctor` | A1, A30 | diagnostics backend plus config CLI | Doctor reports env, registry, profile, auth, data, network, logs. |
| [ ] | UX-015 | HIGH | missing help/topic system | A31, A32 | topic catalogue backend plus root CLI | `aeat topic` and `aeat help <topic>` expose conceptual docs. |
| [ ] | UX-016 | MEDIUM | missing `aeat config` | A33, A34 | config/profile backend plus config CLI | Config list/get/set/unset/configurations route through backend. |
| [x] | UX-017 | HIGH | missing modelo introspection | A35, A36 | registry query backend plus app modelo CLI | Modelos, casillas, bindings, formulas available through backend API and CLI. |

## Action Ledger

| Done | action_id | Issue | Verb | Action | Wave | Backend owner | CLI owner | Verification | Review gate | Commit policy |
|---|---|---|---|---|---|---|---|---|---|---|
| [x] | A1 | UX-001, UX-014 | ADD | Add `aeat config doctor` command. | W7 | diagnostics service | config CLI | Real doctor run reports typed sections. | Review doctor owns no diagnostics logic. | Commit doctor backend before CLI if large. |
| [x] | A2 | UX-001 | WRAP | Wrap CLI entry point import errors with one-line diagnostic pointing to `aeat config doctor`. | W6 | error boundary/diagnostics | root CLI | Import-error scenario emits no traceback. | Review boundary does not swallow developer diagnostics in debug. | Commit with error-boundary tests. |
| [x] | A3 | UX-002 | ADD | Add `--version`, `-V`, and `aeat version`. | W7 | registry/package summary API | root CLI | Version output includes package and registry summary. | Review no direct TOML counting in CLI. | Commit as small root slice. |
| [ ] | A4 | UX-003 | ADD | Add root `aeat init` onboarding wizard. | W7 | onboarding/profile/auth backend | root CLI | Non-interactive and interactive paths write through backend. | Review no profile/auth business logic in CLI. | Commit backend and CLI separately if needed. |
| [ ] | A5 | UX-003 | REORDER | Group setup subcommands by workflow phase. | W7 | command metadata if needed | setup CLI | Help output matches workflow order. | Review no behavior hidden by help grouping. | Commit with help tests. |
| [ ] | A6 | UX-003 | ADD | Add root quickstart pointer to `aeat --help`. | W7 | command metadata | root CLI | Help includes quickstart and current state hint. | Review wording matches current behavior. | Commit with A5 if same files. |
| [ ] | A7 | UX-004 | AUDIT | Audit every setup/app flag against `auth providers` quality bar. | W1 | command metadata owners | all CLI modules | Audit record lists every flag and quality status. | Review audit completeness. | Commit audit record. |
| [ ] | A8 | UX-004 | ADD | Add examples, format hints, and valid-value pointers per flag. | W6 | catalogue/topic backends | all CLI modules | Help tests assert representative examples and pointers. | Review no stale examples. | Commit by command group. |
| [x] | A9 | UX-005 | REROUTE | Route internal logs to user log files. | W6 | logging backend | root CLI | Normal command stderr is clean; log file receives internals. | Review no secrets in logs. | Commit logging slice. |
| [x] | A10 | UX-005 | SUPPRESS | Suppress or fix the short-plaintext hashed lookup warning. | W6 | crypto/storage backend | none or root CLI | Warning absent because underlying cause or routing fixed. | Security review required. | Commit with storage/logging tests. |
| [x] | A11 | UX-005 | ADD | Add global `--verbose` and `--debug`. | W6 | logging backend | root CLI | Verbose/debug change log routing deterministically. | Review debug does not expose secrets by default. | Commit with A9 if coupled. |
| [ ] | A12 | UX-006 | REPLACE | Replace boolean profile valid with per-modelo readiness matrix. | W4 | readiness/profile backend | setup/config CLI | Readiness differs by modelo and fails when required facts missing. | Review matrix rules live outside CLI. | Commit backend before CLI. |
| [ ] | A13 | UX-006 | ADD | Add `--for-modelo` to setup status and profile validate. | W4 | readiness/profile backend | setup/config CLI | Per-modelo status returns model-specific missing profile/bindings. | Review CLI delegates to backend preflight. | Commit with A12 CLI slice. |
| [ ] | A14 | UX-006, UX-011 | ADD | Add `--all-keys` or `--unset` profile show. | W4 | profile schema/read backend | setup/config CLI | Empty optional keys display as unset/redacted by schema. | Review CLI does not enumerate old `PROFILE_KEYS` directly. | Commit with profile display slice. |
| [ ] | A15 | UX-006 | SHOW | Show completeness ratios in default profile/status output. | W4 | readiness/profile backend | setup/config CLI | Output and JSON carry ratios from backend. | Review ratios are not computed in CLI. | Commit with A12 if same API. |
| [ ] | A16 | UX-007 | EXTEND | Extend schema/profile editable keys for IVA, IRPF, modelo enrollment, SII, Verifactu, intracomunitario. | W4 | `domain/user_profile` and schema TOML | config/profile CLI | Schema and registry contract cover deadline/calculation needs. | Review against modelo backend dependencies. | Commit schema/backend slice. |
| [ ] | A17 | UX-007 | EMIT | Emit cross-regime coordination warnings on set. | W4 | profile validation backend | config/profile CLI | Backend returns warnings for incompatible regimes. | Review CLI only renders warnings. | Commit backend warnings before CLI. |
| [ ] | A18 | UX-007 | ROUND-TRIP | Profile set writes through typed profile/backend model read by engine. | W4 | secure profile backend/deadline projection | config/profile CLI | Engine consumes values written by profile CLI. | Review no legacy shadow store remains. | Commit storage/projection slice. |
| [ ] | A19 | UX-008 | EMIT | Calendar warnings and completeness blocks for underspecified profiles. | W5 | overview/deadline/profile backend | overview CLI | Incomplete profile calendar includes warnings and missing modelos. | Review no silent omissions. | Commit backend then CLI. |
| [ ] | A20 | UX-008 | REFUSE | Refuse partial calendar below threshold unless `--allow-incomplete`. | W5 | overview/deadline backend | overview CLI | Partial calendar exits or requires explicit override. | Review refusal is structured. | Commit with A19 if coupled. |
| [ ] | A21 | UX-009 | ADD | Add next-action computation to every app summary surface. | W5 | state graph backend | app CLI modules | App summary emits backend `Siguiente`. | Review state graph not in CLI. | Commit by app group. |
| [ ] | A22 | UX-010 | ADD | Add recovery field to OVERDUE calendar entries. | W5 | deadline/recovery backend | overview CLI | OVERDUE entry includes recovery command/legal ref. | Review legal refs grounded in registry. | Commit with deadline tests. |
| [x] | A23 | UX-011 | TRANSLATE | Translate `auth reset` description to Spanish. | W6 | i18n catalogue | setup/auth CLI | Help output language is consistent. | Review translation key used, not inline text. | Commit small help slice. |
| [ ] | A24 | UX-011 | ADD | Add `aeat setup reset --profile --auth --data --all`. | W7 | reset/orchestration backend | setup CLI | Reset scopes route through safe backend APIs. | Review no destructive default behavior. | Commit reset backend before CLI. |
| [ ] | A25 | UX-012 | WRAP | Wrap errors in structured emitter with did-you-mean, fix, learn-more. | W6 | core error/fix registry | all CLI modules | Error tests assert suggestion and exit code. | Review no raw `BadParameter` leaks remain in scoped commands. | Commit error infrastructure. |
| [ ] | A26 | UX-012 | REGISTER | Register per-error-code to fix-template mappings. | W6 | core error/fix registry | all CLI modules | Missing binding/unknown key maps to concrete command. | Review templates are backend data. | Commit with A25 or per domain. |
| [x] | A27 | UX-013 | FIX | Fix invoice `--kind` help or accepted values. | W6 | invoice import backend if value set changes | invoice CLI | Help and accepted values agree. | Review no backwards alias unless approved. | Commit small invoice help/value slice. |
| [ ] | A28 | UX-013 | ADD | Add topic pages for formats, providers, regimens. | W6 | topic/catalogue backend | topic/help CLI | Topics render from backend catalogue. | Documentation review required. | Commit docs/topic backend. |
| [ ] | A29 | UX-013 | ADD | Add shell completion command. | W7 | completion metadata if needed | root CLI | Completion output generated for shells. | Review no command tree drift. | Commit completion slice. |
| [ ] | A30 | UX-014 | ADD | `config doctor` covers env, registry, profile, auth, data, network. | W7 | diagnostics backend | config CLI | Doctor JSON and text include all sections. | Review diagnostics do not mutate unless `--fix`. | Commit with A1 if same implementation. |
| [ ] | A31 | UX-015 | ADD | Add `aeat topic` and `aeat help <topic>`. | W7 | topic backend | root CLI | Topic list and topic detail render. | Review content source is backend/docs, not CLI literals. | Commit topic surface. |
| [ ] | A32 | UX-015 | AUTHOR | Author initial conceptual topics. | W7 | documentation/topic backend | topic CLI | Required topics exist and are discoverable. | Documentation Researcher/Author/Editor review. | Commit docs slice. |
| [ ] | A33 | UX-016 | ADD | Add `aeat config` family. | W4/W7 | config/profile backend | config CLI | Config commands operate through backend. | Review no setup compatibility alias unless explicitly approved. | Commit backend then facade. |
| [ ] | A34 | UX-016 | UNIFY | Unify profile keys, auth, registry root, format, verbosity, language under config. | W4/W7 | config backend | config CLI | Config list shows typed cross-domain values. | Review each value has backend owner. | Commit by domain. |
| [x] | A35 | UX-017 | ADD | Add `aeat app modelo list/describe/casillas/bindings/formulas`. | W5 | registry query backend | app modelo CLI | Commands expose registry data through API. | Review CLI does not read TOML directly. | Commit query API before CLI. |
| [x] | A36 | UX-017 | IMPLEMENT | Implement `aeat.domain.calculations.registry` query Python API. | W5 | registry query backend | app modelo CLI consumers | API tests cover modelo list/describe/casillas/bindings/formulas. | Review API is stable and typed. | Commit backend API first. |

## Discovered Surface Ledger

| Done | discovered_id | Surface | Current state | Required action | Wave | Verification | Review gate |
|---|---|---|---|---|---|---|---|
| [ ] | DISCOVERED-001 | `attachments.py`, `categories.py`, `normatives.py`, `browser`, `data/ledgers/inventory`, `deadlines`, `filing`, `financial`, `llm`, `sanitize` | CLI modules exist on disk but were not present in the current root help inventory. | Classify each as register, remove, move under target root, backend-only, or document as non-user entrypoint. Add one new row per actionable module before coding it. | W1/W2 | Executable command tree inventory plus file inventory reconciled. | Review ensures no hidden user surface is omitted. |
| [ ] | DISCOVERED-002 | `aeat app registry` live capture/read commands | Live-read/capture commands exist under technical registry namespace. | Classify as Kent-facing, advanced, live-read, live-write, or restricted; align with access-gate policy before UX changes. | W5 | Command help/output and access behavior reviewed. | Live-read/write boundary review required. |
| [ ] | DISCOVERED-003 | Profile schema modified by parallel work | `registry/aeat/user_profile/schema.toml` is currently dirty in the shared worktree after prior commits. | Inspect before any profile/config change; preserve other-agent edits and append new profile issues here if schema drift affects CLI readiness. | W4 | Dirty-slice audit and schema contract tests. | Shared-worktree review required. |
| [ ] | DISCOVERED-004 | `aeat app registry audit-oracles` | Live inventory found this registered technical command, but the source audit did not enumerate it. Help text is English and technical. | Classify as advanced/operator/audit surface; either move under the approved advanced or modelo/registry shape or harden help/output in place. | W1/W2/W5 | Command help and output contract are inventoried and covered by tests. | Review ensures technical diagnostics do not pollute first-contact app registry UX. |
| [ ] | DISCOVERED-005 | CLI structured error boundary | `src/aeat/entrypoints/cli/_errors.py` defines a structured boundary, but the root app does not call `decorate_typer_app`. | Wire a single root-level error boundary or document why specific commands must opt out; add regression tests for unknown backend errors and typed errors. | W6 | A command raising an `AeatError` renders through the shared error contract. | Review ensures Click/Typer control-flow still propagates correctly. |
| [x] | DISCOVERED-006 | `aeat setup status` readiness and next-action logic | Live handler computes profile readiness, auth readiness, and next action in CLI code. | Move readiness and next-action computation into backend/application services before extending status behavior. | W2/W4/W5 | Tests prove backend returns readiness/next-action and CLI only renders it. | Review checks CLI does not own status business rules. |
| [ ] | DISCOVERED-007 | Filing input aggregation in CLI common helpers | `_aggregate_filing_inputs` currently returns an empty dictionary from the CLI helper layer. | Replace with backend aggregation/preflight API before declaration calculate/modelo binding hardening. | W2/W5 | Modelo calculation tests prove required bindings are supplied or reported by backend preflight. | Review treats placeholder aggregation as a blocker for closing UX-012 and UX-017. |
| [x] | DISCOVERED-008 | Doctor command placement | The accepted product direction moved diagnostics under the config facade instead of the root command namespace. | Implement diagnostics as `aeat config doctor`; keep root `aeat doctor` unregistered. | W7 | Root help lists `config`, `aeat config doctor` runs text/JSON, and `aeat doctor` fails. | Review ensures diagnostics are backend-owned and the root surface remains focused. |
| [ ] | DISCOVERED-009 | Profile-aware modelo applicability filter | `aeat app modelo list` now exposes registry inventory, but profile-aware filtering depends on hardened user-profile enrollment facts. | Add `--applicable-to-profile` only after the user-profile schema/read API can supply IVA/IRPF/modelo enrollment facts to the registry query backend. | W4/W5 | A profile with IVA general shows Modelo 303/390 applicability and an under-specified profile receives typed incompleteness reasons. | Review ensures applicability is not guessed in CLI. |

## Wave Task Checklists

- `W0 Evidence And Guardrails`
  1. [ ] Create or persist the pasted 2026-05-08 CLI audit as a VaultSpec audit
         artifact if it is not already present in the repo.
  1. [ ] Record dirty-worktree state and explicit ownership boundaries before
         any implementation.
  1. [ ] Verify every `UX-*`, `A*`, and `DISCOVERED-*` row is represented.
  1. [ ] Establish commit boundary and review gate for each planned slice.

- `W1 Live CLI Inventory`
  1. [ ] Generate executable command tree from `aeat --help` and nested help.
  1. [ ] Inventory all CLI modules on disk and reconcile against registered root.
  1. [ ] Inventory tests for CLI command surfaces and classify weak or missing
         coverage.
  1. [ ] Append newly discovered user-facing or hidden surfaces to this plan.

- `W2 Boundary Classification`
  1. [ ] Classify every registered command as transport-only, backend-owned
         orchestration, deprecated, advanced, live-read, or live-write.
  1. [ ] Identify CLI code that performs validation, schema decisions,
         persistence semantics, calculations, readiness logic, or recovery logic.
  1. [ ] Convert each misplaced business-logic finding into a backend-owned
         task row.

- `W3 Backend Ownership Routing`
  1. [ ] Route each `UX-*`, `A*`, and `DISCOVERED-*` row to a backend owner and a
         CLI owner.
  1. [ ] Confirm backend APIs exist before CLI facade work begins.
  1. [ ] Add missing backend API tasks for diagnostics, readiness, topics,
         registry queries, config, profile lifecycle, and error fix templates.

- `W4 User Profile And Config Alignment`
  1. [ ] Compose this plan with the existing user-profile backend rollout.
  1. [ ] Implement schema-backed config/profile APIs needed by UX-006, UX-007,
         UX-008, and UX-016.
  1. [ ] Remove live dependence on old setup profile validation when equivalent
         config/profile backend behavior is verified.
  1. [ ] Ensure profile tests prove engine-visible behavior, not only key storage.

- `W5 Registry, Modelo, And Live-Read Hardening`
  1. [ ] Implement typed registry query API for modelo list/describe/casillas/
         bindings/formulas.
  1. [ ] Implement calendar completeness, missing-modelo warnings, and overdue
         recovery through backend APIs.
  1. [ ] Audit app registry live-read/capture commands for access-gate and
         operator-facing placement.
  1. [ ] Ensure CLI does not parse registry TOML directly.

- `W6 Output, Error, Warning, And JSON Contract`
  1. [ ] Centralize structured error rendering and fix-template lookup.
  1. [ ] Route internal logs away from normal command stderr.
  1. [ ] Add global verbose/debug behavior.
  1. [ ] Define output schema expectations for text, table, JSON, and topic
         surfaces.

- `W7 Root Migration And Alias Policy`
  1. [ ] Add root version, doctor, init, topic/help, config, and completion
         surfaces once backend owners exist.
  1. [ ] Define whether `setup` and `app` remain, move, or are removed in the
         merge-ready state.
  1. [ ] Do not preserve compatibility aliases unless an accepted ADR or plan
         update explicitly approves them.

- `W8 Test And Review Gate Enforcement`
  1. [ ] Replace tests that only assert implementation echoes itself.
  1. [ ] Add real command invocation tests backed by real backend behavior.
  1. [ ] Add review checklist items for CLI business logic, backend ownership,
         output contracts, and hidden surface drift.
  1. [ ] Run a code review pass for every closed implementation slice.

- `W9 Surface Closure Audit`
  1. [ ] Re-run command tree inventory.
  1. [ ] Re-run CLI module file inventory.
  1. [ ] Re-run search for old setup/profile stores, `PROFILE_KEYS`, raw
         `BadParameter`, direct TOML registry reads, and CLI-local readiness
         logic.
  1. [ ] Append and close new findings before the rollout can be considered
         closed.

- `W10 Continuous Review And Repair Loop`
  1. [ ] Run final multi-surface code review.
  1. [ ] Repair HIGH and CRITICAL findings before proceeding.
  1. [ ] Commit each repair slice separately.
  1. [ ] Repeat audit/review/repair until no actionable CLI hardening findings
         remain.

## Parallelization

Parallel work is allowed only after W1 inventory and W3 owner routing are
complete. Safe parallel lanes are:

- diagnostics/logging/error contract work;
- registry query backend work;
- profile/config backend work;
- documentation/topic authoring;
- CLI root/help surface work after backend APIs exist.

Do not split work so two agents edit the same CLI command file or the same
backend owner in parallel. Every worker must be told that the shared worktree is
dirty and that unrelated edits must not be reverted.

## Verification

Closure requires:

- all `UX-001` through `UX-017` rows closed;
- all `A1` through `A36` rows closed;
- every `DISCOVERED-*` row closed or expanded into closed follow-up rows;
- real command invocation tests for changed CLI surfaces;
- backend tests for each moved business rule;
- output/error/JSON/stderr tests for changed rendering contracts;
- registry query tests proving model introspection comes from typed backend APIs;
- profile/config tests proving values written by CLI are readable by deadline,
  filing, registry, and overview backends;
- code review records showing no CLI business logic remains in changed surfaces;
- explicit commits between major waves and repair passes.

Known current blocker: the shared worktree contains many unrelated modified,
deleted, and untracked files. Execution must stage only the current owned plan,
exec, audit, backend, and CLI paths for each slice.
