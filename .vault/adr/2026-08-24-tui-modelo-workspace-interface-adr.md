---
tags:
  - '#adr'
  - '#tui-modelo-workspace-interface'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bcd2e2f98706940526346eb57e44c4502c6bdd6357b441ff416009849d4830af'
related:
  - "[[2026-08-24-tui-modelo-workspace-interface-research]]"
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-06-04-modelo-addressing-ux-adr]]"
  - '[[2026-08-24-modelo-edit-contract-adr]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-24-tui-operation-observation-adr]]'
---

# `tui-modelo-workspace-interface` adr: `Modelo workspace interface and staged editor amendment` | (**status:** `proposed`)

## Problem Statement

The accepted TUI interface decision reserves `modelo.view` and requires a later
accepted write-side decision before `modelo.edit` can exist. The proposed
registry API gate supplies application read data, the proposed
`2026-08-24-modelo-edit-contract-adr` supplies the frontend-neutral mutation
contract, and the accepted operation architecture supplies supervised execution
and observation. None decides the Modelo destination catalogue, workspace
hierarchy, TUI-local view state, edit interaction, focus and conflict behavior,
or the proof by which visual/editor cohorts may become available.

This record is the focused companion amendment anticipated by
`2026-08-11-tui-interface-adr`. It owns only the Modelo feature's interface,
TUI-local edit session, and visual interaction contract. It does not supersede
that accepted record, create a second root shell, or take ownership from
registry, calculation, application read or edit contracts, operation lifecycle
or custody, localization catalogue, persistence, verification, filing, or
export authorities. The boundary and evidence are grounded in
`2026-08-24-tui-modelo-workspace-interface-research`.

## Considerations

- Current schema and row scale requires bounded, stable-key rendering rather
  than an eagerly mounted generic form
  (`2026-08-24-tui-modelo-workspace-interface-research`).
- Calculation history is immutable and content-addressed, so field-level
  write-through is not an available transaction model
  (`2026-08-24-tui-modelo-workspace-interface-research`).
- Natural visible addressing and advanced exact addressing already have an
  accepted owner (`2026-06-04-modelo-addressing-ux-adr`).
- Operation interaction, progress, cancellation, settlement, effect, and public
  observation already have an accepted owner
  (`2026-08-11-tui-architecture-adr`).
- Locale parity, keyboard access, responsive geometry, and production
  composition are acceptance properties, not late visual polish
  (`2026-08-11-tui-interface-adr`).
- Financial edit values need an operation-owned non-journaled handoff even
  though they are not generic login or recovery secrets
  (`2026-08-24-tui-modelo-workspace-interface-research`).

## Considered options

- **Keep the bounded Modelo review as the only visual surface.** Rejected: it
  preserves a useful read projection but cannot express the requested
  workspace, causal inspection, editing, or lifecycle controls.
- **Interpret registry schema directly into widgets.** Rejected: it gives the
  TUI registry, authority, calculation, and editability policy and makes every
  registry evolution a presentation migration.
- **Model the entire workspace as one generic flow or wizard.** Rejected: its
  atomic review/submit principle is useful, but a linear flow cannot own large
  random-access destinations, lazy provenance, repeated-row paging, or durable
  workspace location.
- **Publish a typed Modelo destination set, map application projections into
  TUI-local view models, and stage one baseline-bound edit transaction.**
  Chosen: it preserves accepted ownership while giving visual and editor cohorts
  one testable target.

## Constraints

- `2026-08-11-tui-interface-adr` remains the canonical authority for root
  composition, shell, navigation mechanics, focus ownership, common components,
  secret inputs, error presentation, and the global proof matrix. Acceptance of
  this record amends only its reserved Modelo feature scope; the parent record
  must be curated to cite this companion before implementation planning closes.
- `2026-08-11-tui-architecture-adr` remains the sole authority for operation
  definitions, envelope state, public observation, pending interaction,
  cancellation, settlement, result, effect, and the global operation surface.
- `2026-08-24-tui-registry-api-gate-adr` owns the frontend-neutral, read-only
  Workspace V1 application contract. This record consumes it and does not
  redefine its registry aggregation or authority decisions.
- `2026-08-24-modelo-edit-contract-adr` owns
  `ModeloEditContractV1`: admission, parsing, preflight, exact edit baseline,
  scalar and row intents, mutation capability, strict refusal, guarded effect,
  and the safe result receipt. This record consumes those DTOs and owns no
  application mutation service.
- A `ModeloWorkspaceBaseline` is read consistency only and is never submitted
  as mutation authority. Editor admission obtains a separate
  `ModeloEditBaselineV1` from `ModeloEditContractV1`. That baseline is also not
  approval or authorization; the application contract revalidates it
  immediately before effect through the enrolled operation.
- The accepted natural Modelo address is the normal route operand. Raw work,
  calculation-revision, registry-revision, or bucket identifiers are advanced
  exact operands and are never the default visual hierarchy.
- Modelo feature code may import only public TUI components, public application
  facades and contracts, and allowed core vocabulary. It may not import CLI or
  MCP entrypoints, registry definitions or snapshots, domain calculation
  internals, repositories, operation journals, or concrete persistence.
- No view model contains a callable, repository, frontend-agnostic service, raw
  exception, untyped payload bag, or mutable domain object. No application
  contract contains a Textual type.
- Editor values live only in mounted controls, the memory-only edit session, the
  strict transient application request, the operation-owned non-journaled
  handoff, and the encrypted authoritative store after successful effect.
  Routes, logs, traces, diagnostics, automatically persisted screenshots or test
  snapshots, operation events, journals, baselines, receipts, and concurrency
  tokens contain no financial values or raw source identities.
- This record does not authorize generic secret collection, recovery mnemonic
  display, live AEAT transmission, new registry semantics, or a compatibility
  layer. Those remain blocked by their own accepted decisions and receipts.
- Workspace, edit, operation public-definition manifest and definition digests,
  observation, REVIEW projection, Workspace refresh target, and transient
  financial-operand protocol are distinct refusal boundaries. Breaking changes
  migrate all in-tree consumers atomically and delete the old version; there is
  no dual-stack legacy adapter.
- A proposed dependency cannot open a cohort. Workspace reads wait for accepted
  Workspace V1 conformance; operation-backed actions wait for the accepted
  public operation projection and enrolled definitions; editing waits for an
  accepted `ModeloEditContractV1` receipt and the operation-owned financial
  operand receipt. The observation proposal is staging provenance only; the
  accepted operation parent must be amended in place before C3.

## Implementation

### D0 — Authority and composition

The Modelo interface is one feature beneath the accepted root application. It
publishes a closed `ModeloDestination` catalogue, route factories, immutable
view-model families, a workspace controller, and an editor controller. The root
application registers those factories, supplies public workspace, edit-input,
operation, localization, and clock ports through constructors, and retains
mounting, global navigation, focus transfer, and the operation modal. There is
no service locator and no feature-created second application shell.

`modelo.view` owns projection-to-view-model mapping and read destinations.
`modelo.edit` owns only memory-local edit state, review construction, and the
translation of explicit user intent into `ModeloEditContractV1` requests. The
application contract owns parsing, authoritative validation, edit-baseline
revalidation, request construction, guarded effect delegation, and result
receipt. The accepted operation parent owns submission custody and settlement;
existing domain writers remain the only effect authorities.

Acceptance of this record makes it the Modelo-specific elaboration of the
accepted interface ADR. A conflict is resolved toward the accepted parent for
root/common concerns and toward this record only for the feature-specific
workspace/editor concerns named here. Neither record supersedes the other.

### D1 — Route and destination catalogue

The closed initial catalogue is:

| Stable destination ID | Purpose | Route operand |
|---|---|---|
| `modelo.work.select` | List, filter, create-capability, and typed ambiguity or absence | active profile/bucket context plus optional visible-target filter |
| `modelo.work.review` | C1 bounded rendering of canonical `ModeloWorkReview` | resolved visible work target |
| `modelo.workspace.overview` | Identity, revision timeline, status, capability summary, and safe actions | resolved visible work target |
| `modelo.workspace.inputs` | Input sections, values, repeated groups, and editor entry | resolved visible work target plus optional semantic section address |
| `modelo.workspace.results` | Current calculated values and explicitly selected historical inspection | resolved visible work target plus optional public `ModeloRevisionPick` |
| `modelo.workspace.provenance` | Bounded causal and source disclosure | resolved visible work target plus optional semantic node address |
| `modelo.workspace.verification` | Verification findings, readiness, and verify action | resolved visible work target |
| `modelo.workspace.filing` | Filing state, history, export capability, and file action | resolved visible work target |
| `modelo.edit.review` | Review of one staged edit transaction before submission | in-memory edit-session identity only |

Destination IDs are untranslated semantic constants. Route operands are typed,
in-memory objects, not serialized strings, and contain no financial values.
Advanced exact addressing may be entered through an explicit inspect control.
Historical calculation inspection uses only the public
`ModeloRevisionPick.explicit(...)`; post-operation return uses only the typed
`ModeloWorkspaceRefreshTargetV1` resolved through D6. The frontend never
interprets a generic result reference, and either exact target is visibly
distinguished from the natural target.

`modelo.work.review` is the only C1 Modelo detail destination and is implemented
under the accepted physical owner `cadrumo.entrypoints.tui.modelo.view`. The C2
cutover atomically removes that destination and its bounded-review route factory
when it registers `modelo.workspace.overview` as the selection result target.
There is no alias, redirect, compatibility route, or dual read projection. The
C2 route census proves one current destination per selection outcome and zero
remaining `modelo.work.review` references.

`modelo.workspace.inputs` hosts the admitted mutation mode rather than creating
a second form hierarchy. C3 admits calculate/recalculate mode; C4 may admit the
separately capability-projected amendment mode. The chrome and
`modelo.edit.review` always name the active mutation family, and an amendment
session cannot reuse a calculate baseline or intents.

An explicit historical `ModeloRevisionPick` starts a labelled read-only
inspection session through its existing public bounded query. It is not
composed with current Workspace facets, does not inherit current capability,
and cannot enter edit mode. Returning to current results establishes a fresh
Workspace read session. Cross-revision comparison is not part of the initial
catalogue.

All workspace destinations share one feature-owned chrome: visible Modelo
address; law-selected registry revision; current calculation-revision state;
declared and required authority grade; resolved locale and fallback disposition;
baseline/stale/dirty state; and capability summary. On narrow terminals the
chrome collapses into an operable summary but remains reachable in keyboard
order. Only the active destination body is mounted.

The global operation destination and `OperationModal` are not duplicated in the
Modelo catalogue. Invoking a Modelo action opens the operation-owned surface
with an origin reference; terminal settlement returns through the root router to
the mapped Modelo destination and initiates the refresh protocol in D6.

### D2 — TUI-local view models

The feature exposes frozen, callback-free view-model families for:

- workspace chrome and destination summaries;
- section summaries and disclosure state;
- scalar fields with stable semantic address, presentation kind, localized
  label/help, formatted display, edit disposition, provenance summary, and
  validation state;
- repeated groups and rows with stable row identity, ordered cells, paging
  state, edit disposition, and row validation;
- current and historical result summaries;
- bounded provenance nodes and expansion references;
- capabilities, refusals, notices, validations, and actions.

The presentation-kind set is a closed TUI enum mapped from application-projected
field semantics. It may distinguish text, integer, decimal, money, ratio, date,
boolean, enumerated choice, identifier, code, and read-only computed or
informational values without reinterpreting registry data types. An unsupported
projected kind produces an explicit renderer-refusal view and fails projection
coverage; it never falls back to a generic editable text box.

Semantic field, section, row, and causal addresses—not display labels,
translated text, list offsets, or widget instance IDs—anchor routing, focus,
dirty state, validation, and test assertions. Widget expansion, selection,
scroll, active lexeme, and focus remain TUI-local ephemeral state and never feed
back into the application projection.

### D3 — Read consistency, scale, and bounded traversal

One workspace load establishes an immutable `ModeloWorkspaceReadSession` with
the visible and exact resolved address, selected registry revision, workspace
contract version, schema fingerprint/version, projection baseline, resolved
locale, and destination summaries. Every later section page, repeated-row page,
provenance expansion, or action refresh carries those
coordinates and must echo the same consistency identity.

A mismatched baseline, selected revision, schema fingerprint, or contract
version invalidates the composed session. The interface does not mix the facet,
retry it against a guessed identity, or retain values from both projections. It
enters the refresh path in D6. Locale-only refresh may reuse canonical identity
only when the producer proves identical non-localized content and returns the
same consistency coordinates.

The application remains responsible for the complete semantic join, but any
unbounded collection exposed to the TUI has a bounded cursor/page or expansion
contract. The TUI mounts one destination body, one bounded section/page, and one
bounded causal expansion at a time. Tables and row groups use stable-key
virtualization or paging; provenance expands lazily with cycle and depth
presentation supplied by the producer. A producer may deliver a bounded
complete workspace in one response, but neither the interface nor its
acceptance tests assume eager construction of every widget or causal node.

### D4 — Edit-session transaction

Entering edit mode sends the current read coordinates through
`ModeloEditAdmissionRequestV1`. A successful response supplies the separate
`ModeloEditBaselineV1`; a refusal is rendered without manufacturing a local
session. One `ModeloEditSession` is then created with the read-consistency
identity, edit baseline, compatibility tuple, visible/exact address, contract
and schema identity, base semantic references, canonical staged values, ordered
row intents, dirty addresses, addressable validation, and state. Its state
machine is:

`CLEAN` enters `DIRTY` on the first edit. Preflight moves `DIRTY` to
`VALIDATING`, then back to `DIRTY` with findings or to `READY`; further edits
move `READY` back to `DIRTY`. Submit moves `READY` to `SUBMITTING`. Confirmed
effect plus refresh moves it to `SETTLED`; proven no effect with a current edit
baseline returns it to `READY`. A consistency conflict or unknown effect enters
`STALE_CONFLICT`. `ABANDONED` is reachable only through explicit discard of
staged edits.

The session consumes the exact scalar-intent family from
`ModeloEditContractV1`; it does not define another nullable or widget-specific
intent. Numeric zero, false, empty optional text, cleared value, absent override,
and unchanged remain visually distinct. The admitted permitted surface decides
which controls exist. Computed, informational, projection-only, backend-only,
and refused fields have no editor control.

An active widget may retain a locale-tagged raw lexeme while
`ModeloEditParseRequestV1` parses it. The session stores a canonical typed value
only after successful parsing and never persists or snapshots the lexeme.
Changing locale never reinterprets an existing raw lexeme: parsed values
reformat under the new locale, while an unparsed lexeme remains visibly tagged
with its entry locale and blocks review until resolved or discarded.

Leaving a dirty workspace invokes an unsaved-change guard. The choices are stay
or explicitly abandon the in-memory session; there is no background save,
checkpoint, clipboard export, or automatic commit. Process loss may lose staged
edits and cannot corrupt an authoritative calculation revision.

`modelo.edit.review` is mandatory before submission. It presents every changed
semantic address, distinguishes scalar and row intents, exposes validation and
refusal state, and returns to the originating control. This review is a
frontend transaction gate, not a fabricated `OperationSupervisor` interaction.
The supervisor shows an approval interaction only when the registered operation
definition declares one.

Submit compiles one `ModeloEditSubmissionV1` containing the edit baseline and
normalized ordered typed intents. The Workspace read baseline remains a
consistency coordinate and is not promoted into a mutation precondition. The
TUI does not reconstruct a complete calculation bundle, call an executor, or
call a writer.

After application preflight, the interface submits only through the public
operation-owned financial-operand capability proven by
`TuiOperationFinancialOperandDependencyReceiptV1`. This record does not decide
that capability's broker, envelope, journal, cleanup, restart, idempotency, or
effect rules. The TUI retains its local session while it observes the resulting
operation identity and discards it only after authoritative settlement and
fresh Workspace projection. Process loss before accepted handoff loses only the
local draft; after handoff, the public operation projection and the application
edit result receipt are the sole recovery truths. C3 cannot open until the
accepted operation parent owns the handoff and its live-tree receipt is green.

### D5 — Repeated-row semantics

An existing row uses the application-issued stable semantic row address. A new
row receives an opaque TUI-local `DraftRowId` that remains stable across local
insert, validation, focus, and delete. A draft ID is never treated as a durable
row coordinate or placed in a route, receipt, or retained artifact. Submission
maps it to the edit contract's client correlation identity only.

The session consumes the edit contract's closed row-intent family. Add and
update stage a whole typed row. An incomplete row may remain visibly dirty but
cannot enter `READY`; deletion and move appear explicitly in review.
Source-derived or calculated rows remain read-only unless the admitted surface
projects the exact override intent.

The submitted order is the producer-projected base order with staged updates and
deletes applied, followed by additions in their displayed order. Explicit moves
are available only when the group is declared reorderable and its full ordered
membership is materialized within the producer-declared bound. The application
edit contract, not the TUI, maps this order to canonical row coordinates and
validates row limits, uniqueness, source identity, and cross-row rules.
Positional widget indexes are never row identity.

### D6 — Validation, conflict, settlement, and refresh

Validation has three owned layers:

1. The widget owns presence of an unparsed lexeme and interaction feedback, but
   delegates parsing and coercion to `ModeloEditContractV1`.
2. `ModeloEditPreflightRequestV1` owns field, section, cross-field, row, and
   complete edit-intent validation against the edit baseline.
3. The enrolled operation invokes the edit contract's guarded executor, which
   revalidates the exact baseline, permitted surface, capability, and complete
   intent immediately before effect; a prior green preflight is not
   authorization and the Workspace read baseline is not substituted for it.

Every validation carries a stable code, severity, semantic address or global
scope, localized message key/arguments or producer-approved display, evidence
reference when applicable, and canonical action reference when recovery exists.
The TUI may group and focus validations but may not parse prose or translate a
warning into readiness.

A clean manual or automatic refresh replaces the read session. Destination,
section expansion, row selection, and focus survive only when the same semantic
addresses exist. A dirty refresh or any read-consistency change,
submission-time edit-baseline refusal, work-catalogue or calculation-head
change, selected revision, schema or permitted-surface change, or contract
mismatch enters `STALE_CONFLICT`, preserves staged values in memory, and blocks
submit. Version 1 offers review of pending edits and explicit abandon-and-reload
only. It performs no automatic merge, silent rebase, or field-level conflict
resolution.

Terminal operation state never patches the prior workspace. The controller
folds the operation-owned observation to terminal settlement, then calls
`OperationWorkspaceRefreshTargetRequestV1` with the operation identity,
terminal revision, definition-contract digest, and declared refresh-target
schema identity. A successful registered adapter returns the typed
`ModeloWorkspaceRefreshTargetV1`; only that target is used for the new Workspace
request. The frontend never interprets or submits `result_ref`. `UPDATED`
effect routes to the action's declared result destination and announces the new
authoritative state. `NONE` preserves the workspace and presents the canonical
notice or refusal. Failed or cancelled no-effect settlement keeps the edit
session only when the operation projection proves no effect and both the read
and edit baselines remain current. Unknown or partial effect invalidates the
session and requires a fresh read before any further action. Refresh failure
retains the terminal operation result and offers a canonical retry; it never
presents the old view as settled truth.

### D7 — Capability, refusal, and action presentation

Each destination renders all of its applicable capability slots from the
application projection. The closed dispositions are `AVAILABLE`,
`NOT_APPLICABLE`, `REFUSED`, and `UNMEASURED`. Available actions are enabled;
not-applicable actions are absent from the primary action rail but remain
inspectable in capability detail; refused and unmeasured primary actions remain
visible and disabled with stable reason, evidence/disposition, reconsideration
condition, and canonical recovery action. A missing or unexplained disabled
control fails conformance.

`ModeloActionView` contains the application-projected stable mutation or query
identity, optional canonical recovery `ActionReference`, localized label/help,
target semantic address, capability disposition, mandatory registered
operation-definition reference when mutating, interaction classification,
destructive flag, and result destination. It contains no callback. The
controller maintains a closed dispatch map to public application or operation
ports.

The complete candidate denominator is generated at
`.vault/reference/2026-08-24-tui-modelo-workspace-action-denominator.md` with
schema `ModeloWorkspaceActionDenominatorV1` by
`build_modelo_workspace_action_denominator` and checked by
`validate_modelo_workspace_action_denominator`. It joins:

- every canonical application action-catalogue row;
- every operation definition and permitted frontend projection;
- every Modelo command-graph leaf and its current `TuiCapability`;
- every direct application mutation or outbound-effect site;
- every Modelo route factory, action view, and dispatch-map row; and
- every typed flow-owned, global-operation, deferred, or non-visual exclusion.

Each candidate is classified exactly once as `DIRECT_QUERY`,
`WORKSPACE_OPERATION`, `OPERATION_MODAL_CONTROL`, `FLOW_OWNED`, `DEFERRED`, or
`NOT_VISUAL`. `DEFERRED` and `NOT_VISUAL` require a stable code, owner, bounded
reason, evidence reference, and reopening condition. Duplicate, unclassified,
stale, or missing candidates fail. Counts, a list of already-visible buttons,
and permanent allowlists are not a denominator.

The initial cohort mapping is:

| Cohort | Workspace mapping | Authorized actions |
|---|---|---|
| C1 | selection and bounded review | list, status, review, revisions, revision inspect, observations, dependencies, and refresh as direct queries |
| C2 | all read destinations | bounded section/row/provenance traversal, capability detail, and refresh as direct queries |
| C3 | selection, inputs, and edit review | calculate/recalculate through `ModeloEditContractV1` and enrolled operations |
| C4 | overview, inputs, verification, and filing | rename, discard, verify, file, export, and amend only where independently enrolled, capability-projected, and receipted |

`modelo.work.create` is a `DEFERRED` candidate owned by the existing
`cadrumo.application.modelo` work-lifecycle boundary. The selection destination
may render its deferred capability and reopening facts, but C1-C5 do not invoke
it. Reopening requires a later accepted decision that defines absent-work
admission, its domain capability and enrolled operation, the atomic work-unit
and creation-event write set, an authoritative result/effect receipt, and the
exact dependency and interface receipt proofs. Neither
`ModeloEditContractC3DependencyReceiptV1` nor `ModeloWorkspaceC3ExitReceiptV1`
authorizes creation.

Discard is destructive and must declare the canonical exact approval
interaction. File and any external handoff use their owning interaction and
capability contracts; `file` here means the existing local filing record and
human handoff, never remote AEAT submission. Apply/reject controls shown during
a pending interaction belong to `OperationModal`, not to the Modelo action rail.
CLI `wizard`, `runs`, and `resume` are classified under flow or global-operation
ownership and do not become duplicate workspace actions. The existing
`modelo.work.amend` mutation is a distinct C4 amendment action, not ordinary
recalculation. The currently TUI-available `modelo.work.amend_wizard` is a
`FLOW_OWNED` transitional presentation row: the C4 amendment slice either
replaces it with the workspace amendment mode and retires its legacy TUI
capability atomically, or records it `DEFERRED` with an owner and reopening gate.
It cannot disappear from the denominator or remain as an untracked duplicate at
C5. Command existence alone never authorizes a button.

A mutating action becomes visible and enabled only when its application
capability is `AVAILABLE`, its operation definition is registered for TUI, its
result destination is mapped, the denominator row is green, and the action's
applicable D8 receipt has passed. An unavailable prerequisite renders a typed
refusal; it never removes the candidate from the fixed point.

### D8 — Localization, accessibility, responsiveness, and sensitive display

Resolved locale changes labels, help, formatting, and canonical messages only.
It does not change addresses, values, revision selection, capability, baseline,
action enrollment, validation codes, or edit intent. Visible fallback follows
the accepted catalogue cascade; route/focus identity never depends on translated
text.

Every destination has a deterministic heading and keyboard order. Every
interactive control has a unique visible label or adjacent descriptive text.
Status, dirty state, validation severity, capability, operation state, and
selection use text or symbols in addition to colour. Tables have textual column
headings and a narrow-layout record form; truncated content is reachable through
focus or disclosure; validation summary can move focus to the addressed control;
row add/delete/move, review, abandon, and refresh are keyboard complete. Focus
return after a modal or validation error is asserted by semantic identity.

Acceptance exercises Spanish, English, Catalan, and Hungarian; light and dark
themes; `80x24`, `120x36`, and `160x48`; long labels and fallback; deep section
paths; empty, large, and paged row groups; large calculated schemas; stale and
unknown-effect states; refused and unmeasured capabilities; and production root
composition. Visual fixtures use synthetic sentinel data. Tests assert that
mounted controls stay within declared page/viewport bounds and that sensitive
values are absent from routes, logs, traces, journals, operation events,
diagnostics, snapshots, and golden artifact names or metadata.

Availability is fenced per cohort, not deferred to C5. C1 proves its bounded
review in all four locales, three geometries, two themes, keyboard order, and
non-colour state. C2 adds large/deep schema, paged rows, overflow, provenance,
and refusal/capability disclosure. C3 adds lexical-error focus, scalar and row
editing, review/abandon, stale conflict, locale switch, and sensitive
non-retention. Each C4 action independently proves disabled/refused state,
declared interaction, destructive focus return where applicable, terminal
effect, and refresh at every supported geometry. C5 reruns the aggregate matrix
and installed composition fixed point; it is not the first accessibility test.

A destination or action may exist behind test-only composition while its cohort
is under implementation, but the root application cannot register it as
callable and no command may declare `TuiCapability.AVAILABLE` until that exact
cohort exit receipt is green on current HEAD. A typed `NOT_APPLICABLE` proof is
permitted only under the receipt rules in D10; an omitted matrix cell is never a
pass.

### D9 — Version and compatibility behavior

The TUI declares every compatibility coordinate it actually consumes rather
than one generic operation version. C3 editor admission consumes the exact
`ModeloEditCompatibilityTupleV1`: Workspace and edit contract versions;
operation public-definition manifest version and `contract_set_digest`;
enrolled `OperationDefinitionId`, `definition_contract_digest`, and declared
request/result schema identities; observation request/result/projection/event-
page version; REVIEW-projection request/result version and the definition's
declared REVIEW/response schema identities or explicit absence;
Workspace-refresh-target request/result version and exact
`ModeloWorkspaceRefreshTargetV1` schema identity/fingerprint; and
`OperationTransientFinancialOperandProtocolV1` version and enrolled operand
schema identity/fingerprint. A public-definition version never substitutes for
a definition digest, observation never substitutes for REVIEW or refresh, and
no endpoint version substitutes for a registered payload schema identity.

C0 operation surfaces pin their applicable public-definition, definition-
digest, observation, REVIEW, and refresh-target coordinates. C1 and C2 read-
only admission pins only the Workspace/review coordinates and any C0 operation
surface it actually consumes; it does not require an edit or financial-operand
contract. A missing or unaccepted axis leaves its dependent surface refused or
unmounted and never becomes an implicit compatibility default.

Startup or route admission refuses an unsupported read tuple before a workspace
is mounted; editor admission refuses an unsupported edit tuple before accepting
a lexeme or opening an edit session. Read sessions pin the received Workspace,
public-definition, observation, REVIEW, and refresh coordinates they consume,
plus selected revision, schema fingerprint, and Workspace baseline. Edit
sessions additionally pin the complete admitted edit baseline, financial-
operand coordinates, and compatibility tuple. An in-process version or digest
change follows the stale protocol.

TUI-local view models and route IDs are internal code contracts rather than a
second serialized API version. A breaking in-tree change updates route factories,
dispatch maps, tests, and consumers in one change. No aliases, deprecated
destination IDs, dual projection adapters, permissive extra fields, or fallback
generic widgets remain after migration.

### D10 — Acceptance receipts and staged cohorts

The implementation plan must preserve this receipt chain; later cohorts may not
substitute mocks, prose, or a proposed record for an unmet predecessor:

| Cohort | Required entrance receipts | Canonical exit artifact, schema, and validator | Required proof |
|---|---|---|---|
| C0 — operation foundation | amended accepted `2026-08-11-tui-architecture-adr` | `.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`; `TuiOperationObservationDependencyReceiptV1`; `src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py` | `OperationPublicDefinitionContractV1` and contract-set schema identities/digests; atomic observation fold; registered safe REVIEW resolver, typed refusals, and non-authority; typed result-to-Workspace refresh-target adapter from a fresh process; settlement, interaction, cancellation, effect, recovery, and production DI |
| C1 — bounded review | this companion ADR accepted with exact stem, accepting commit, and body hash; accepted Casilla review; accepted interface migration lane | `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt.md`; `ModeloWorkspaceC1ExitReceiptV1`; `validate_modelo_workspace_c1_exit_receipt` | canonical `modelo.work.review` relocation; four-locale/three-geometry/two-theme keyboard and non-colour proof; no legacy production import |
| C2 — complex read workspace | C1 exit plus `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`; `ModeloWorkspaceC2DependencyReceiptV1`; `validate_modelo_workspace_c2_dependency_receipt` | `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c2-exit-receipt.md`; `ModeloWorkspaceC2ExitReceiptV1`; `validate_modelo_workspace_c2_exit_receipt` | C1-route atomic replacement; destination/factory census; projection coverage; baseline facets; refusal states; large schema/row/provenance matrix; production composition |
| C3 — staged editor | C0 and C2 exits; `.vault/reference/2026-08-24-modelo-edit-contract-c3-dependency-receipt.md`; `ModeloEditContractC3DependencyReceiptV1`; `validate_modelo_edit_contract_c3_dependency_receipt`; and `.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`; `TuiOperationFinancialOperandDependencyReceiptV1`; `src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py` | `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c3-exit-receipt.md`; `ModeloWorkspaceC3ExitReceiptV1`; `validate_modelo_workspace_c3_exit_receipt` | exact compatibility tuple; edit/row state machine; parse and validation focus; review-only submit; stale refusal; atomic-result refresh; locale switch; operation handoff consumption; sensitive non-retention |
| C4 — lifecycle actions | C3 exit, green generated action denominator, and each owning domain capability and operation definition | `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c4-exit-receipt.md`; `ModeloWorkspaceC4ExitReceiptV1`; `validate_modelo_workspace_c4_exit_receipt` | zero unclassified action candidates; exact interaction and terminal refresh; rename, discard, verify, file, export, and amend proofs independently; amendment-wizard disposition |
| C5 — visual closure | C4 exit and every C1-C4 destination/action classified | `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c5-exit-receipt.md`; `ModeloWorkspaceC5ExitReceiptV1`; `validate_modelo_workspace_c5_exit_receipt` | aggregate four-locale, three-geometry, two-theme, keyboard, non-colour, large-schema/row, refusal/conflict, route/action anti-vacuity, no-transitional-TUI, and installed root-app proof |

`ModeloWorkspaceC1ExitReceiptV1` has a closed mandatory governing prefix: exact
stem `2026-08-24-tui-modelo-workspace-interface-adr`, status `accepted`, its
accepting commit, and its then-current body hash. Omission, proposed status,
body-hash drift, or a non-ancestor accepting commit fails
`validate_modelo_workspace_c1_exit_receipt`; the accepted parent migration lane
or Casilla record cannot substitute for this companion identity.

Every C1-C5 exit validator invokes
`validate_modelo_workspace_action_denominator` against the same current-HEAD
source tree before returning green. It records the generated artifact digest
and rejects any missing, duplicate, stale, or unclassified candidate, any typed
exclusion without its owner/reason/evidence/reopening facts, and any route or
command whose `TuiCapability.AVAILABLE` state lacks its exact owning cohort exit
proven green by the same validator invocation on current HEAD, including the
exit receipt then under validation. Earlier cohorts classify future candidates
as `FLOW_OWNED`, `DEFERRED`, or `NOT_VISUAL`; they never omit them. C4
additionally proves the intended lifecycle rows are enrolled and receipted, and
C5 proves no transitional TUI row remains.

Every interface receipt carries its schema version, current-HEAD commit and
ancestry, accepted governing-record identities, exact predecessor receipt
digests, and the applicable distinct Workspace/edit/public-definition/
definition-digest/observation/REVIEW/refresh-target/financial-protocol
compatibility coordinates. An axis the cohort does not consume uses the typed
`NOT_APPLICABLE` proof with owner, reason, evidence, and reopening condition;
an applicable axis cannot. Receipts also carry selected registry/schema
fixtures, destination and validated action-denominator digests, locale/
geometry/theme matrix, synthetic scale fixture, production composition path,
and non-retention proof. A predecessor digest is mandatory and cannot be marked
not applicable.

Each proof cell is the discriminated `ModeloWorkspaceReceiptProofV1`: `PASSED`
contains the executable evidence identity and digest; `NOT_APPLICABLE` contains
a stable code, owning authority, bounded reason, evidence reference, and
reopening condition. Null, omitted, free-form "n/a", `UNMEASURED`, a proposed
dependency, or a reason without an owner fails validation. `NOT_APPLICABLE`
cannot waive a required locale, geometry, keyboard path, sensitive-data gate,
production composition, predecessor, available action, or registered route.

A cohort closes only when its named validator is green against the live tree
and every route/action it makes callable has passed the applicable D8 matrix.
Global registry completeness is not a prerequisite: an honestly refused
capability is valid C2 behavior, while a mutation cannot enter C3 or C4 until
its selected revision, application contract, operation dependency, and action
receipt are green.

This ADR does not authorize a second TUI rollout plan. After acceptance, the
canonical TUI architecture and interface plans are amended to consume these
cohorts and receipts; implementation execution remains under their single
roll-up authority.

## Rationale

The chosen design is the smallest boundary that satisfies both the accepted
ownership model and the proven complexity of current Modelo data. Application
projections remain authoritative, but local view models prevent the application
API from becoming Textual-specific. A destination catalogue makes scale and
location explicit. A single baseline-bound memory transaction fits immutable
calculation history without inventing a mutable draft repository, while
`ModeloEditContractV1` keeps parsing, validation, capability, concurrency, and
effect outside presentation. Operation references preserve supervision without
letting the interface own custody, and fresh-read settlement prevents the TUI
from becoming a second materializer.

The rejected generic approaches fail a knockout criterion: they either cannot
support the visual/editor goal or move policy into the entrypoint. The staged
cohorts then keep the architecture useful during ongoing registry work: complex
read surfaces may display honest refusals before every Modelo can calculate or
file, while no edit or lifecycle control appears before its exact capability,
operation, concurrency, custody, and accessibility receipts exist.

## Consequences

- Visual work receives a finite route catalogue, hierarchy, view-model boundary,
  transaction state machine, row semantics, refresh protocol, and acceptance
  target.
- The accepted TUI interface ADR remains the root authority and gains one
  focused Modelo companion; Workspace V1, `ModeloEditContractV1`, and the
  accepted operation parent remain authoritative in their layers.
- Large revisions and repeated rows require bounded application traversal,
  virtualization/paging, stable semantic identities, and consistency tests.
- Editing is deliberately conservative: no write-through, durable draft,
  automatic merge, or silent rebase. Operators must explicitly abandon stale
  edits until a future accepted merge decision exists.
- Every mutation needs a registered operation, projected capability,
  operation-owned non-journaled operand path where values are sensitive,
  application edit-baseline check, result mapping, applicable accessibility
  proof, and independent receipt. Existing CLI coverage does not satisfy that
  obligation.
- The generated action denominator makes `amend`, `amend-wizard`, direct
  queries, flow-owned commands, and future Modelo candidates impossible to omit
  silently.
- Unsupported schema kinds, projection versions, capability states, and
  renderers become visible refusals and failing coverage rather than generic
  fallback behavior.
- Implementation work is larger than a screen build, but it is partitioned into
  C0-C5 cohorts that can be planned and verified without a competing rollout
  plan or a global registry-completeness blockade.
