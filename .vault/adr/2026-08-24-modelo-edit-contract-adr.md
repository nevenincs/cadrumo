---
tags:
  - '#adr'
  - '#modelo-edit-contract'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1fdb7869c22c53d5f6e5ab27f7765e9a9d89fee60030c7685d4fc5aed6a6c866'
related:
  - "[[2026-08-24-tui-modelo-workspace-interface-research]]"
  - "[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]"
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-24-tui-operation-observation-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
---

# `modelo-edit-contract` adr: `Versioned Modelo edit and mutation contract` | (**status:** `proposed`)

## Problem Statement

The read-only Workspace V1 contract deliberately cannot authorize a mutation,
the accepted operation authority deliberately does not decide domain edit
semantics, and the Modelo interface must not invent an application writer from
widgets. Without a separate application contract, a complex editor would have
no stable definition of admission, parsing, validation, concurrency, permitted
fields and rows, mutation capability, or authoritative result.

This record establishes the frontend-neutral `ModeloEditContractV1` behind the
public `cadrumo.application.modelo` facade. It owns edit admission and parsing,
authoritative preflight, an exact mutation baseline, typed scalar and row
intents, mutation capability projection, compare-and-swap execution through the
existing Modelo single writer, and the safe result receipt. It does not own TUI
state, operation lifecycle or custody, registry meaning, calculation formulas,
or persistence adapters. The split and its evidence are grounded in
`2026-08-24-tui-modelo-workspace-interface-research` and
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`.

## Considerations

- Workspace read consistency and mutation authority are different coordinates;
  promoting a Workspace baseline would authorize from the wrong contract
  (`2026-08-24-tui-modelo-workspace-interface-research`).
- Calculation revisions are immutable and content-addressed, so an edit creates
  a new revision rather than updating visible fields in place
  (`2026-08-24-tui-modelo-workspace-interface-research`).
- The current writer already exposes the work-catalogue and
  calculation-catalogue revisions required for a guarded co-commit, while the
  missing result receipt is the recovery gap the new boundary must close
  (`2026-08-24-tui-modelo-workspace-interface-research`).
- Registry and schema identity determine the permitted edit surface; TUI control
  presence cannot decide editability (`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`).
- Operation enrollment does not define clear versus absent values, repeated-row
  identity, validation, or domain effect (`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`).
- Financial edit values may exist transiently in memory and in the encrypted
  authoritative store, but never in an operation journal, event, route,
  diagnostic, or dependency receipt (`2026-08-24-tui-modelo-workspace-interface-research`).

## Considered options

- **Let the TUI call existing Modelo writers directly.** Rejected: widgets would
  own request construction, concurrency, editability, and persistence topology.
- **Add mutation methods to Workspace V1.** Rejected: it would turn a safe
  read-consistency token into a write precondition and destabilize C2 reads.
- **Treat an enrolled operation definition as the edit API.** Rejected:
  operation registration owns execution lifecycle, not domain input semantics or
  the atomic Modelo write set.
- **Create a public application edit contract and delegate its effect to the
  canonical Modelo writer through an enrolled operation.** Chosen: the
  application owns validation and mutation truth, operation owns custody and
  settlement, and every frontend consumes the same strict contract.

## Constraints

- `ModeloEditContractV1` is exported only through
  `cadrumo.application.modelo`. It exposes no Textual, CLI, MCP, registry
  compiler, domain repository, persistence DTO, raw exception, callback, or
  untyped payload bag.
- The existing natural and exact Modelo targets remain the only addressing
  inputs. Admission re-resolves them and never accepts a caller-selected
  registry revision as authority.
- `ModeloWorkspaceBaseline` is read consistency only. It is never accepted as a
  mutation baseline, permission, or authorization.
- The edit contract delegates formula evaluation and persistence to the existing
  canonical calculation and Modelo lifecycle writers. It cannot reproduce their
  registry join, content-addressing, event emission, or secure-store writes.
- The accepted `2026-08-11-tui-architecture-adr` remains the only operation
  execution, request-custody, journal, reconciliation, and effect authority. The
  proposed `2026-08-24-tui-operation-observation-adr` is observation staging
  provenance only and cannot authorize financial-operand submission.
- No frontend may submit an edit to an operation until the accepted operation
  parent has been amended in place and the green financial-operand dependency
  receipt named below proves the live custody path.
- Public models are strict, frozen, discriminated, current-only, and typed.
  Breaking pre-release change replaces the sole supported version and every
  consumer in one cutover; no alias, permissive extra field, or compatibility
  adapter remains.
- Raw lexemes, typed financial values, row contents, and reversible or
  low-entropy digests of them remain only in process memory until the canonical
  encrypted Modelo write. They are forbidden from receipts, events, baselines,
  logs, traces, diagnostics, routes, snapshots, and operation persistence.

## Implementation

### D0 — Public contract family and ownership

Add one strict V1 family behind `cadrumo.application.modelo`:

- `ModeloEditVersionHeader`, `ModeloEditCompatibilityTupleV1`, and the exact
  version dispatcher;
- `ModeloEditAdmissionRequestV1`, `ModeloEditAdmissionResultV1`, and
  `ModeloEditBaselineV1`;
- `ModeloEditParseRequestV1` and its typed parsed or refused result;
- `ModeloEditPreflightRequestV1`, `ModeloEditPreflightResultV1`, and addressable
  findings;
- `ModeloScalarEditIntentV1`, `ModeloRowEditIntentV1`, and
  `ModeloEditSubmissionV1`;
- `ModeloMutationCapabilityRequestV1` and
  `ModeloMutationCapabilityProjectionV1`;
- `ModeloEditExecutionResultV1`, `ModeloEditMutationResultReceiptV1`, and the
  closed `ModeloEditRefusalV1` family.

These are renderer-neutral application DTOs. Frontends may retain them in
memory and map them to local state, but may not construct a baseline, parse a
domain value, add an editability rule, or call the effect executor directly.

### D1 — Exact version and compatibility boundary

The dispatcher reads only the edit-contract version before parsing a target or
financial input. V1 supports exactly this compatibility tuple:

- Workspace contract version `1`;
- edit contract version `1`;
- public operation projection version `1`; and
- operation financial-operand contract version `1`.

`ModeloEditCompatibilityTupleV1` names all four axes separately. It is never a
generic shared `version` field. Admission refuses
`unsupported_edit_contract_version` or `unsupported_edit_compatibility` before
resolving secure state. Until the operation-owned financial-operand receipt is
green, the sole tuple is structurally known but mutation capability is
`unmeasured`; the facade does not advertise a usable C3 path.

### D2 — Admission and exact edit baseline

Admission consumes the exact current Workspace coordinates and independently
re-resolves the visible or exact work target, law-selected registry revision,
schema, work catalogue, calculation catalogue, and current calculation head. A
successful `ModeloEditBaselineV1` contains only safe coordinates:

- edit-contract version and supported compatibility tuple;
- resolved work identity and natural filing coordinate;
- work-catalogue revision;
- calculation-catalogue revision and nullable current-calculation-revision id;
- law-selected registry revision;
- canonical schema identity, schema version, and schema fingerprint;
- the complete permitted edit surface or its application-issued bounded pages,
  plus one deterministic permitted-surface digest;
- admitted mutation family, issue time, expiry, and one opaque baseline identity.

The permitted surface classifies every semantic scalar and repeated-group
address as writable with an exact allowed intent set or as non-writable with a
typed disposition. It contains no values. Pages echo the baseline, schema
fingerprint, and surface digest; a mismatch invalidates the whole admission.
The baseline is a compare-and-swap coordinate, not actor authorization or proof
that the operation remains available.

### D3 — Parsing and authoritative preflight

The parse service accepts one semantic address, declared input kind, resolved
locale, and transient raw lexeme. It returns a canonical typed value or a
refusal carrying a stable code and safe address; it never echoes the lexeme.
Locale is an input grammar only and cannot change the underlying field kind,
allowed intent, or stored value.

Preflight accepts the edit baseline plus the complete ordered intent set. It
rechecks target, catalogues, calculation head, registry revision, schema
fingerprint, permitted surface, and current mutation capability before running
field, section, row, cross-field, and whole-calculation validation. Findings
carry stable codes, severity, semantic address or global scope, approved message
arguments, and safe evidence references. A green preflight is review material,
not authorization; execution repeats every concurrency and capability check.

### D4 — Scalar and repeated-row intents

Scalar intent is exactly one of `SET_TYPED_VALUE`, `CLEAR_DECLARED_VALUE`, or
`REMOVE_OVERRIDE`; absence means `UNCHANGED`. Zero, false, empty optional text,
cleared declared value, and removed override remain distinct. An address not in
the admitted surface or an intent not allowed for that address refuses.

Row intent is exactly `ADD_ROW`, `UPDATE_ROW`, `DELETE_ROW`, or, when the
permitted surface explicitly allows it, `MOVE_ROW`. Existing rows use the
application-issued canonical row address. A new row uses an opaque client
correlation identity that has no persistence meaning; the result maps it to the
canonical row coordinate. Add and update submit a complete typed row. Move is
accepted only when the producer declared the group reorderable and the full
bounded membership was materialized. Positional widget indexes are never
identity.

`ModeloEditSubmissionV1` contains one baseline, one mutation family, normalized
ordered scalar intents, normalized ordered row intents, and no frontend state.
Duplicate or contradictory address intents refuse before execution.

### D5 — Mutation capability projection

The application facade projects a closed capability row for every mutation
candidate classified by the generated Modelo action denominator. Each row
contains a stable mutation id, owning domain producer, exact target and
revision coordinate, `AVAILABLE`, `NOT_APPLICABLE`, `REFUSED`, or `UNMEASURED`,
safe evidence and reconsideration facts, optional canonical recovery
`ActionReference`, and the mandatory registered `OperationDefinitionId` for a
visual mutation.

The facade composes rather than infers: domain eligibility, action-catalogue
identity, and operation enrollment remain with their canonical owners.
`AVAILABLE` requires all applicable joins and the green operation dependency
receipt. An `ActionReference` remains guidance and never substitutes for an
operation definition, edit baseline, or response capability.

### D6 — Atomic execution and authoritative result

Only the enrolled operation executor may invoke the application execution
service. Immediately before effect it revision-loads the work and calculation
catalogues, resolves the registry and schema again, and compares every baseline
coordinate and permitted-surface digest. Any disagreement returns
`stale_edit_baseline`, writes nothing, and settles the domain effect as `NONE`.
It never silently rebases, merges, retries against a new baseline, or promotes a
green preflight into authority.

For calculate or recalculate, the service builds the complete canonical input
bundle, executes the existing calculation boundary, and delegates to the
canonical Modelo persistence writer. One revision-guarded secure-store
transaction co-commits:

- the new immutable content-addressed calculation revision;
- the work unit's current-calculation pointer;
- the canonical Modelo calculation-created bucket event; and
- one safe `ModeloEditMutationResultReceiptV1`.

The result receipt carries operation and mutation identity, edit-baseline
identity, work identity, resulting calculation-revision id, bucket-event id,
effect, commit time, and result destination reference. It carries no financial
value, raw input, row content, or input digest. The receipt is stored through
the encrypted authoritative repository and is the domain proof used after a
crash: a matching receipt proves `UPDATED`; a proven failed compare-and-swap
proves `NONE`; absence after executor entry remains for the operation authority
to classify. An identical content-addressed revision still advances or confirms
the pointer and co-commits its result receipt under the same guards; the
existing-revision branch may not fall back to an unguarded pointer save.

Other lifecycle mutations keep their existing single-writer primitives and
must independently declare their atomic write set and result receipt before
their visual capability becomes available. This ADR does not turn calculate's
write set into a generic persistence engine.

### D7 — Strict refusal and sensitive-data boundary

The refusal family distinguishes version, compatibility, target absence or
ambiguity, admission, unsupported schema kind, disallowed intent, parsing,
validation, capability, work-catalogue conflict, calculation-head conflict,
registry/schema conflict, surface conflict, expiry, and compare-and-swap
conflict. Each refusal carries only a stable code, affected address or boundary,
safe requested and selected coordinates, owner, reconsideration condition, and
safe evidence reference. Raw validation errors and exceptions never cross the
facade.

Sensitive non-retention is checked at every public model and operation seam.
Financial values may reach the strict in-memory request, the canonical
calculation boundary, and the encrypted authoritative store only. No baseline,
receipt, capability row, refusal fact, event, journal, diagnostic, trace, route,
fixture name, or automatically retained visual artifact contains them or a
reversible derivative.

### D8 — Dependency receipt and implementation gate

The machine-readable C3 application prerequisite is
`.vault/reference/2026-08-24-modelo-edit-contract-c3-dependency-receipt.md`,
schema `ModeloEditContractC3DependencyReceiptV1`, validated by
`validate_modelo_edit_contract_c3_dependency_receipt`. It records this ADR's
accepted status and ancestry; the public export and strict-schema digests; the
sole compatibility tuple; schema and permitted-surface fingerprints; mutation
capability and refusal inventories; real parse/preflight parity; real
work/calculation/event/result-receipt atomicity and rollback under each stale
coordinate; duplicate-result recovery; forbidden-import proof; and sensitive
non-retention.

Its required predecessor is the green
`.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`
with schema `ModeloWorkspaceC2DependencyReceiptV1`, validated by
`validate_modelo_workspace_c2_dependency_receipt`. The operation-side C3
prerequisite is separately
`.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`,
schema `TuiOperationFinancialOperandDependencyReceiptV1`, validated by
`src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`.
It must cite the amended accepted operation parent and chain the C0 observation
receipt digest. Neither receipt can stand in for the other.

Every proof field uses a discriminated `PASSED` or `NOT_APPLICABLE` result.
`NOT_APPLICABLE` requires a stable code, owning authority, bounded reason, and
evidence reference; null, omitted, free-form "n/a", proposed status, and an
unmeasured required dependency fail validation. The validator checks current
HEAD and exact predecessor digests. This ADR may be accepted before the
operation receipt exists, but no frontend C3 cohort opens until both receipts
are green.

## Rationale

The chosen split is the only option that gives every frontend one stable edit
API without moving registry or persistence policy into presentation and without
making the operation supervisor a domain form service. Separate read and edit
baselines preserve the safe C2 boundary. Exact multi-store coordinates plus the
existing atomic writer give stale edits a deterministic no-effect outcome, and
the co-committed result receipt gives operation reconciliation authoritative
domain evidence after commit. These are the decisive ownership and crash-safety
criteria identified by `2026-08-24-tui-modelo-workspace-interface-research` and
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`.

## Consequences

- TUI, CLI, MCP, and future frontends gain one strict edit admission, parsing,
  validation, capability, intent, refusal, and result boundary.
- Workspace V1 remains read-only and independently releasable; its baseline can
  never be mistaken for mutation authority.
- A visual editor can stage values locally while all authoritative parsing,
  editability, concurrency, calculation, and persistence remain upstream.
- Every successful calculation edit creates an immutable revision and a safe
  result receipt in the same guarded transaction as its pointer and event.
- Stale edits fail closed with effect `NONE`; no automatic merge or rebase is
  introduced.
- The operation campaign must still add and prove the financial-operand custody
  path. This record does not make that dependency disappear or accept its
  staging proposal.
- Implementing the contract requires a public DTO family, a mutation-capability
  assembler, guarded duplicate-revision behavior, an encrypted result-receipt
  repository, and real atomicity/non-retention conformance.
- Later lifecycle actions may reuse the capability and receipt shapes, but each
  keeps its existing writer and must prove its own atomic effect boundary.
