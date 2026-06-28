---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
  - "[[2026-04-30-inventory-management-cli-design-adr]]"
---



# `cli-workflow-redesign` adr: `App modelo command surface and object boundaries` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The redesigned CLI needs one complete modelo command surface. Today,
`aeat app modelo` is only registry introspection, while lifecycle behavior,
draft building, validation, export, filing history, reconciliation, and
amendment behavior are split across `app declaration`, unmounted `filing`
commands, and backend services with no operator verb.

This drift makes the redesigned root contract hard to execute. The product
needs `aeat app modelo` to become the operator surface for modelo work units:
create the work unit, inspect required bindings, calculate immutable revisions,
verify completion, mark a verified revision as internally filed, read filing
records and history, export/import local AEAT-compatible files, reconcile
against justificantes, and create amendments.

## Considerations

- The redesigned root contract allows only `aeat config` and `aeat app`.
- Existing `app modelo` commands already expose registry concepts such as
  casillas, formulas, and bindings, but not modelo work-unit lifecycle.
- Existing declaration commands already implement lifecycle-like behavior, but
  the `declaration` mini-app is not the target operator boundary.
- Existing unmounted filing commands and backend services contain useful draft,
  validation, export, import, complementaria, reconciliation, and history
  behavior that should be salvaged into `app modelo`.
- The submission engine is intentionally read/preflight only and has no live
  transport method.
- CLI copy must not imply live AEAT submission.
- Domain statuses may retain historical names such as `SUBMITTED`, but operator
  copy must use "internal filed", "exported", and "imported historical filing
  record".
- Inventory mutation is source-data management, not modelo lifecycle
  management.
- Registry binding objects are first-class concepts; `bindings` is clearer
  than `inputs`.

## Constraints

- `aeat app modelo` is the canonical operator surface for modelo work units.
- `aeat app declaration` is rejected as a surviving operator surface. Its
  lifecycle behavior is folded into `app modelo`.
- `aeat filing *` is rejected as an operator root. Backend behavior may be
  harvested, but the root is not restored.
- `aeat app invoice` and bare `invoice` CLI copy are rejected. Source data must
  use explicit source-kind taxonomy defined outside this ADR.
- No `app modelo` verb performs or implies live AEAT submission.
- No standalone `submit`, `presentation`, or `preflight` modelo verb is
  introduced. Preflight behavior is internal to `verify` and `file`.
- No `app modelo help` support-only surface is introduced. Command help and
  registry/topic documentation remain separate.
- No mutating inventory commands live under `app modelo`. Inventory mutation
  belongs under `app ledger inventory` or a future source-data decision.
- `app modelo bindings` and `app modelo status` consume inventory-derived
  readiness through the bindings resolver.
- Use `amend`, not `complement`. No `complement` alias is approved.
- The first implemented amendment kind is `--kind complementaria`; future
  `sustitutiva` support may use the same `amend` verb.
- Use `bindings`, not `inputs`.
- Use `rename`, not `name`.
- Use `reconcile`, not `compare`.
- `filing-record` is a read surface. Filing-record creation remains only
  through `file`.

## Implementation

Approve the following canonical `aeat app modelo` tree:

- `aeat app modelo list [--modelo] [--year] [--period] [--state draft|verified_complete|filed|superseded]`
- `aeat app modelo create --modelo M --year YYYY --period P [--name TEXT]`
- `aeat app modelo status WORK_UNIT_ID | --modelo M --year YYYY --period P [--revision REV]`
- `aeat app modelo rename WORK_UNIT_ID --name TEXT`
- `aeat app modelo bindings list --modelo M --year YYYY --period P [--missing]`
- `aeat app modelo bindings preview --modelo M --year YYYY --period P [--binding KEY=VALUE]`
- `aeat app modelo calculate WORK_UNIT_ID | --modelo M --year YYYY --period P [--binding KEY=VALUE]`
- `aeat app modelo verify WORK_UNIT_ID [--revision REV]`
- `aeat app modelo file WORK_UNIT_ID [--revision REV] --by ACTOR [--reason TEXT]`
- `aeat app modelo filing-record list|show ...`
- `aeat app modelo export WORK_UNIT_ID --output PATH [--revision REV]`
- `aeat app modelo import --from-justificante PATH | --from-declaracion PATH`
- `aeat app modelo reconcile WORK_UNIT_ID --justificante PATH`
- `aeat app modelo amend WORK_UNIT_ID --kind complementaria --from-filing-record ID --set CASILLA=VALUE [--reason TEXT]`
- `aeat app modelo history --modelo M [--year YYYY] [--period P]`

Implementation mandate: register the lifecycle, work-unit, filing-record,
import/export, reconcile, amend, and history verbs under `aeat app modelo`.
Harvest accepted declaration/filing behavior into this surface and remove the
old declaration surface without aliases or shims.

Command groups are defined as follows.

Work-unit commands:

- `list` reads modelo work units and may filter by modelo, year, period, and
  state.
- `create` creates a modelo work unit for modelo/year/period.
- `status` reads work-unit state and may target a specific revision.
- `rename` changes only the display name of a work unit.

Binding commands:

- `bindings list` reads required and available binding keys for a
  modelo/year/period and may show only missing bindings.
- `bindings preview` previews binding resolution using supplied
  `--binding KEY=VALUE` overrides.
- Binding overrides preserve scalar, list, and mapping values.
- Binding commands do not mutate inventory source data.

Lifecycle commands:

- `calculate` creates or refreshes a calculation revision for a work unit.
- `verify` marks a calculation revision as verified complete when all
  verification requirements pass.
- `file` marks a verified complete revision as internally filed by an actor and
  optional reason. It does not submit to AEAT.
- `export` writes a local AEAT-compatible file and remains separate from
  internal filing.
- `import` creates or records an imported historical filing record from a
  justificante or declaracion source.
- `reconcile` compares a work unit against a justificante and records the
  reconciliation outcome.
- `amend` creates an amendment workflow from a prior filing record. The first
  supported kind is `complementaria`.

Read surfaces:

- `filing-record list|show` reads filing records created through `file` or
  imported through `import`.
- `history` reads filing history by modelo and optional year/period.

Object boundaries:

- A modelo work unit is the operator object addressed by work-unit id or by
  modelo/year/period selectors.
- A calculation revision is immutable after creation.
- `verified_complete` is a revision state owned by verification decisions.
- An internal filing record is created by `file` and is distinct from export
  output and imported historical records.
- An imported historical filing record is created by `import` from local
  documentary evidence.
- A reconciliation result records comparison against a justificante and is not a
  separate `compare` command family.
- An amendment is created by `amend` from an existing filing record.
- Inventory records are source data and are not mutated by `app modelo`.

Implementation must retain `_emit`-style output behavior so every command can
support text and JSON output through the shared format switch.

## Rationale

`app modelo` is the correct boundary because the operator works on a specific
modelo obligation, not on a generic declaration or unmounted filing subsystem.
Folding lifecycle behavior into `app modelo` aligns the command tree with
modelo work units, calculation revisions, verification, internal filing, and
filing records.

`amend` is broader and more durable than `complement`. It covers the
complementaria path and leaves room for future sustitutiva behavior
without introducing aliases.

`bindings` is more precise than `inputs` because registry binding objects are
already first-class and because `inputs` is ambiguous with raw casilla values
and JSON input files.

Keeping mutating inventory outside `app modelo` preserves a clean boundary:
source-data management belongs to ledger or a future source-data surface;
modelo consumes readiness and bindings.

Rejecting standalone `preflight`, `submit`, and `presentation` prevents CLI
copy from implying live AEAT submission. Verification and internal filing may
run readiness checks, but they do not expose a live-submission command.

## Consequences

- Existing `app modelo` registry commands must be reconciled with the work-unit
  surface. Registry introspection may remain only where it does not obscure the
  modelo work-unit lifecycle.
- Existing `app declaration` lifecycle behavior must move into `app modelo` or
  be retired from operator help.
- Existing unmounted `filing` behavior must be harvested into `app modelo`
  verbs and must not be remounted as a root or a separate sub-app.
- The apex ADR must mark the `app modelo` shape as locked and remove the open
  `app-modelo-shape` slot.
- Apex grammar must replace `complement` with `amend`, `inputs` with
  `bindings`, `name` with `rename`, `compare` with `reconcile`, and standalone
  `preflight` with internal verify/file readiness behavior.
- Backend execution still depends on bucket identity, bucket events, immutable
  revisions, verified-complete semantics, filing-record storage, source-kind
  taxonomy, inventory placement, live-read boundaries, and workflow-engine
  wiring decisions owned by their respective ADRs.

## 2026-05-15 amendment - reconcile + ledger link / check / preflight

The 2026-05-15 ground-truth audit found that `aeat app modelo
reconcile` and the `aeat app ledger {link, check, preflight}` verbs
that R02 / R03 claimed closed are absent from the Typer graph. This
amendment locks all four verbs so the gaps are closed in follow-up
work.

Required `aeat app modelo reconcile` surface:

- Verb takes `WORK_UNIT_ID` plus exactly one of `--from-justificante
  PATH` or `--from-declaration PATH`; refuses if both or neither.
- Backend service `modelo_reconcile` parses the supplied evidence
  (justificante PDF or declaration PDF) and produces a strict
  `ReconciliationReport` containing diff entries (per-casilla),
  matching evidence references, and a verdict (matches / mismatches /
  evidence-invalid).
- Reconcile is local-only; it does not contact AEAT and does not
  invoke `require_live_read`.
- The `from-justificante` variant under W85.S2342 reuses the same
  service entry point (no fork).

Required `aeat app ledger link / check / preflight` surface (per W71
contract orthogonal axes):

- `link --id ID --invoice-id INV [--evidence-id EV]` - thin handler
  delegating to `ledger.link` service which binds a transaction to
  invoice / evidence / counterpart references in a single canonical
  call. Refuses cross-bucket links.
- `check [--bucket-id ID]` - thin handler delegating to `ledger.check`
  service which probes ledger transactions in the active bucket and
  returns a `LedgerCheckReport` with anomaly rows.
- `preflight [--period PERIOD]` - thin handler delegating to
  `ledger.preflight` service which asserts every transaction in the
  given period has the required taxonomy fields (category, base IVA,
  business %); produces a blocker / warning report consumed by
  downstream `aeat app modelo work calculate`.

All three ledger verbs follow the W71 orthogonal-axis pattern: they
sit alongside the canonical CRUD spine on the ledger noun-group and
do not introduce new sub-noun-groups.

Event-emission clarification (2026-05-19): `check` and `preflight`
are pure read/probe verbs and emit no bucket events. `link` mutates
a ledger transaction (it patches invoice / evidence / counterpart
reference fields), and that mutation legitimately emits a single
`LEDGER_TRANSACTION_UPDATED` event through the canonical
`update_manual_transaction_fields` path. The earlier blanket "emit
no bucket events" wording is corrected: it applies to `check` and
`preflight` only. A `link` that silently patched a transaction
without an audit-trail event would break ledger provenance — the
update event is the correct, intended behaviour and is normative for
`link`. `link` introduces no event type beyond the existing
`LEDGER_TRANSACTION_UPDATED` already emitted by every manual ledger
field patch.
