---
tags:
  - '#adr'
  - '#modelo-edit-contract'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:c96c35c0995db4e718eaaf346b1197d33ecacfb1fc1f5c03819237639f53d014'
related:
  - "[[2026-08-24-tui-modelo-workspace-interface-research]]"
  - "[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]"
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
---

# `modelo-edit-contract` adr: `Versioned Modelo edit and mutation contract` | (**status:** `accepted`)

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
financial input. `ModeloEditCompatibilityTupleV1` then binds the admitted
mutation to these distinct current-only axes:

- Workspace contract version `1`;
- edit contract version `1`;
- operation public-definition manifest version `1` and exact
  `contract_set_digest`;
- enrolled `OperationDefinitionId`, exact `definition_contract_digest`, and
  request/result schema identities;
- operation observation request/result/projection/event-page version `1`;
- REVIEW-projection request/result version `1` plus the enrolled definition's
  exact REVIEW and response schema identities, or explicit declared absence
  when that definition has no REVIEW interaction;
- Workspace-refresh-target request/result version `1` plus the exact
  `ModeloWorkspaceRefreshTargetV1` schema identity and fingerprint; and
- `OperationTransientFinancialOperandProtocolV1` version `1` plus the enrolled
  operand schema identity and fingerprint.

No member is collapsed into a generic shared `version`, and a manifest version
never substitutes for a definition or contract-set digest. Admission refuses
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
sole compatibility tuple with its public-definition manifest version,
contract-set and definition digests, observation, REVIEW, refresh-target, and
financial-operand axes and exact registered schema identities/fingerprints;
schema and permitted-surface fingerprints; mutation capability and refusal
inventories; real parse/preflight parity; real
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
Its closed predecessor tuple must cite the amended accepted operation parent;
the exact C0 observation receipt path, schema, producing commit, and content
digest; this accepted ADR's body hash; and the C2 Workspace dependency receipt
path, `ModeloWorkspaceC2DependencyReceiptV1` schema, producing commit, and
content digest. Neither operation receipt nor edit receipt can stand in for the
other.

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

## Amendment 2026-08-26: no registry binding is the D4 repeated-row group

**What this corrects.** D4's `ADD_ROW`/`UPDATE_ROW`/`DELETE_ROW`/`MOVE_ROW`
row intents, and the permitted-surface projection that admitted them, assumed
`BindingSourceKind.MANUAL_INPUT` was the taxpayer-typed repeated-row axis
(donativo, invoice, and withholding rows were the motivating examples). A
registry-wide audit found no binding of that shape: every `manual_input`
binding across every modelo declares `aggregation = {op = "copy"}` — a 1:1
scalar copy — and none carries a row index. Modelo 131's ninety-seven, the
fixture this contract's own tests exercise, are static fichero-BOE
record-field positions (e.g. a fixed `actividad-2-epigrafe` slot at a
preprinted offset); none is bound to any casilla either. Admitting
`ADD_ROW`/`DELETE_ROW` against one would let an intent address a static form
slot under a fabricated row semantic — the same class of category error as
`REMOVE_OVERRIDE` addressing a store no addressable casilla has, and the
unreachable compatibility refusal before it. All three errors share one root:
the row and override language in D1/D4 described a registry shape that had
not yet materialised, not the shape the registry actually declares today.

**The decision.** `_writable_row_group_entries` (`_edit_services.py`) is
corrected to return no entries, unconditionally, for every current registry
revision — not a per-modelo carve-out, because no modelo's `manual_input`
binding matches the row shape D4 assumed. `_validate_row_intent` therefore
refuses every row intent as `DISALLOWED_INTENT` against every current
baseline; this is a correct, evidence-grounded refusal, not a dormant or
placeholder one. The `ModeloEditRowIntentKind`, `ModeloEditRowAddressV1`
(`ModeloEditExistingRowAddressV1` / `ModeloEditNewRowCorrelationV1`), and
`ModeloEditWritableRowGroupSurfaceEntryV1` / `ModeloEditNonWritableRowGroupSurfaceEntryV1`
model vocabulary is retained rather than deleted: the `BindingId` + row-index
shape is not inherently wrong, only unpopulated by current registry data, and
remains the correct address shape IF a genuine binding-keyed row set is ever
added to the registry.

**What was NOT decided here.** The genuine repeatable, taxpayer-typed row
mechanism this codebase already has is the per-modelo `ModeloDetailRow`
discriminated union (M184 member, M232 vinculada, M349 operador/rectificación,
M347 contraparte, M210 agrupación renta), already threaded through the
calculate boundary's `detail_rows` and already content-addressed on the
revision. It is NOT `BindingId`-keyed and does not fit `_writable_row_group_entries`'s
shape; projecting it into a new permitted-surface entry kind is the
recommended direction for a future Step, deferred because which detail-row
kind a given modelo may accept is not yet a queryable registry authority — it
is implicit today in which CLI subcommand the operator invokes for `--row`,
not a fact this contract's admission path can read from `ModeloRevision`.
Building that projection ahead of a real per-modelo eligibility authority
would risk repeating exactly this amendment's mistake.

**Consequence for D4.** D4's row-intent vocabulary (`ADD_ROW`/`UPDATE_ROW`/
`DELETE_ROW`/`MOVE_ROW`, existing-row and new-row-correlation addressing) is
otherwise unchanged and remains this contract's row-intent shape; only its
motivating binding-source axis and current reachability are corrected. No
frontend cohort may present row editing as available until a real
permitted-surface entry for `ModeloDetailRow` (or another genuinely
row-shaped registry axis) exists and is admitted.

## Amendment 2026-08-26: the baseline's schema identity is its own type

**What this corrects.** D2's `ModeloEditBaselineV1.schema_identity` field
reused `ModeloWorkspaceSchemaIdentityV1` (defined for
`2026-08-24-tui-registry-api-gate-adr`'s STATIC_INSPECTION and Workspace
projections) rather than declaring its own type. The two producers filled the
shared `field_manifest_digest` field with two structurally and semantically
unrelated digests: this contract's producer (`_edit_services.py`) digested the
registry's `CalculationCompletenessManifest` — the required calculation-closure
casilla set, a TAX-SEMANTIC completeness declaration — while the Workspace
producer (`workspace.py::resolve_static_inspection_schema_identity`) digests
the S278 field-CLASSIFICATION manifest, a deterministic walk over the public
registry TYPE denominator for display rendering. One field name, one shared
record type, two meanings that silently compare unequal for the same
revision. (The Workspace producer's own docstring already flagged the
collision — "never the `CalculationCompletenessManifest` digest that a
sibling module happens to also store under the same field name" — without
the contract being corrected to stop doing so.)

**The decision: rename, not converge.** These are legitimately different
digests answering different questions (does the registry's declared
completeness set for this revision still match what the baseline was admitted
against, versus does the type-level field-classification manifest the
Workspace read side renders from still match) and neither should be repointed
at the other's source — a completeness-set change and a field-classification
change are independent events, and collapsing them would make the edit
baseline's compare-and-swap re-check insensitive to the axis it actually
needs (registry completeness) or spuriously sensitive to one it does not
(display-field classification). `ModeloEditBaselineV1.schema_identity` is now
typed `ModeloEditSchemaIdentityV1` (`_edit_models.py`): `schema_id`,
`schema_fingerprint`, and `completeness_manifest_digest` — a distinct field
name, never `field_manifest_digest`. `ModeloWorkspaceSchemaIdentityV1` and its
`field_manifest_digest` field are unchanged and remain exclusively the S278
field-classification digest; `2026-08-24-tui-registry-api-gate-adr` is
amended alongside this record to state that explicitly.

**Proof.** A cross-producer test
(`test_edit_models.py::test_edit_schema_identity_is_never_confused_with_the_workspace_field_manifest_digest`)
constructs both types from data that changes one axis while holding the other
fixed and asserts the two digests move independently, so a future re-merge of
the two fields under one name would fail it rather than silently reintroducing
this defect.

## Amendment 2026-08-26: REMOVE_OVERRIDE is binding-addressed, not casilla-addressed

**What this corrects.** D4's `REMOVE_OVERRIDE` scalar intent addressed
`ModeloEditScalarAddressV1` (`casilla_id`-keyed), but the store it withdraws
from, `CalculationRevision.binding_overrides`, is keyed by `BindingId`. No
casilla-addressed intent can ever reach it: most eligible bindings -- a
fichero-BOE record-field `manual_input` binding, most notably -- are not
bound to any casilla at all. This is the same category error class as the
row-group correction two Steps earlier in this same contract: an intent kind
existed with an address shape that could never reach the store it named.

**The decision: address by binding.** `REMOVE_OVERRIDE` is retired from
`ModeloEditScalarIntentKind` (now `SET_TYPED_VALUE`/`CLEAR_DECLARED_VALUE`
only, both casilla-addressed). A new `ModeloEditBindingAddressV1`
(`binding_id`-keyed), `ModeloEditBindingIntentKind`
(`SET_OVERRIDE_VALUE`/`REMOVE_OVERRIDE`), `ModeloBindingEditIntentV1`, and a
new permitted-surface entry pair (`ModeloEditWritableBindingOverrideSurfaceEntryV1`
/ `ModeloEditNonWritableBindingOverrideSurfaceEntryV1`) address the binding
directly. `ModeloEditSubmissionV1` gains a `binding_intents` tuple alongside
`scalar_intents` and `row_intents`, participating in the same
duplicate-address uniqueness check.

**Eligibility is derived from the real, already-tested CLI gate**, not
invented: every declared binding whose source is NOT in
`BUCKET_AGGREGATION_LOCK_SOURCES` (the same set
`_reject_caller_overrides_of_source_bindings` in `_calculation_actions.py`
uses to refuse a caller-supplied `--binding` override) is admitted as a
writable binding-override entry; every locked binding surfaces as a
non-writable entry naming the reason. A date-channel binding is excluded
entirely, mirroring the real CLI's own `--binding` refusal for date-consumed
bindings (routed through `--casilla` instead). This is why REMOVE_OVERRIDE's
correction did NOT need the row category's "no registry data matches this
shape" outcome: unlike the row axis, a real, live, tested `--binding`
override mechanism already exists and already has a queryable eligibility
authority to ground the new surface entry against -- modelo 131's ninety-seven
`manual_input` bindings, wrongly surfaced as row groups before the prior
amendment, now correctly surface here instead.

**What was NOT decided here.** Guarded execution and persistence for a
binding-override intent (threading a `--binding`-equivalent clear axis
through the calculate boundary, mirroring `cleared_casilla_ids`) is deferred:
every binding intent kind refuses today with a typed, enumerated
`ModeloEditUnsupportedIntentReason` (`SET_OVERRIDE_VALUE_NOT_YET_WIRED` /
`REMOVE_OVERRIDE_NOT_YET_WIRED`), matching the row-intent precedent. The
permitted surface and admission are real and grounded; only execution is
future work.
