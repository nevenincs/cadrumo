---
tags:
  - '#adr'
  - '#tui-modelo-workspace-interface'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b7401f0a0dbe15d41bd1472398e74555098a9ea38b910eb2553c6b3e5adb3452'
related:
  - "[[2026-08-24-tui-modelo-workspace-interface-research]]"
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-06-04-modelo-addressing-ux-adr]]"
---

# `tui-modelo-workspace-interface` adr: `Modelo workspace interface and staged editor amendment` | (**status:** `proposed`)

## Problem Statement

The accepted TUI interface decision reserves `modelo.view` and requires a later
accepted write-side decision before `modelo.edit` can exist. The proposed
registry API gate supplies application data, while the accepted operation
architecture supplies supervised execution and observation. Neither authority
decides the Modelo destination catalogue, workspace hierarchy, TUI-local view
state, edit transaction, repeated-row interaction, conflict behavior, or the
proof by which visual/editor cohorts may open.

This record is the focused companion amendment anticipated by
`2026-08-11-tui-interface-adr`. It owns the Modelo feature's interface and
write-side interaction contract. It does not supersede that accepted record,
create a second root shell, or take ownership from registry, calculation,
application projection, operation lifecycle, localization catalogue,
persistence, verification, filing, export, or custody authorities. The boundary
and evidence are grounded in
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
- Financial edit values need an explicitly non-journaled handoff even though
  they are not generic login or recovery secrets
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
  Workspace V1 application contract. This record consumes it and specifies
  additional write-side ports required by the editor; it does not redefine its
  registry aggregation or authority decisions.
- A `ModeloWorkspaceBaseline` is read consistency only and is never submitted
  as mutation authority. Editor admission obtains a separate safe opaque
  `ModeloEditBaseline` from the public write-side port. That baseline is also
  not approval or authorization; the enrolled operation revalidates it against
  current work and calculation state immediately before effect.
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
  non-journaled submission handoff, and the encrypted authoritative store after
  successful effect. Routes, logs, traces, diagnostics, automatically persisted
  screenshots or test snapshots, operation events, journals, baselines, and
  concurrency tokens contain no financial values or raw source identities.
- This record does not authorize generic secret collection, recovery mnemonic
  display, live AEAT transmission, new registry semantics, or a compatibility
  layer. Those remain blocked by their own accepted decisions and receipts.
- Workspace and operation contract versions are explicit refusal boundaries.
  Breaking changes migrate all in-tree consumers atomically and delete the old
  version; there is no dual-stack legacy adapter.
- A proposed dependency cannot open a cohort. Workspace reads wait for accepted
  Workspace V1 conformance; operation-backed actions wait for the accepted
  public operation projection and enrolled definitions; editing waits for the
  non-journaled operand and edit-baseline staleness proofs defined below.

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
translation of explicit user intent into the public application edit port. The
application port owns parsing, authoritative validation, edit-baseline
revalidation, request construction, and effect delegation. Existing domain
writers remain the only effect authorities.

Acceptance of this record makes it the Modelo-specific elaboration of the
accepted interface ADR. A conflict is resolved toward the accepted parent for
root/common concerns and toward this record only for the feature-specific
workspace/editor concerns named here. Neither record supersedes the other.

### D1 — Route and destination catalogue

The closed initial catalogue is:

| Stable destination ID | Purpose | Route operand |
|---|---|---|
| `modelo.work.select` | List, filter, create-capability, and typed ambiguity or absence | active profile/bucket context plus optional visible-target filter |
| `modelo.workspace.overview` | Identity, revision timeline, status, capability summary, and safe actions | resolved visible work target |
| `modelo.workspace.inputs` | Input sections, values, repeated groups, and editor entry | resolved visible work target plus optional semantic section address |
| `modelo.workspace.results` | Current calculated values and explicitly selected historical inspection | resolved visible work target plus optional application-issued calculation selection |
| `modelo.workspace.provenance` | Bounded causal and source disclosure | resolved visible work target plus optional semantic node address |
| `modelo.workspace.verification` | Verification findings, readiness, and verify action | resolved visible work target |
| `modelo.workspace.filing` | Filing state, history, export capability, and file action | resolved visible work target |
| `modelo.edit.review` | Review of one staged edit transaction before submission | in-memory edit-session identity only |

Destination IDs are untranslated semantic constants. Route operands are typed,
in-memory objects, not serialized strings, and contain no financial values.
Advanced exact addressing may be entered through an explicit inspect control or
received as an application-issued result reference; it is always visibly
distinguished from the natural target.

An explicit historical calculation selection starts a labelled read-only
inspection session through its existing public bounded query. It is not composed
with current Workspace facets, does not inherit current capability, and cannot
enter edit mode. Returning to current results establishes a fresh Workspace read
session. Cross-revision comparison is not part of the initial catalogue.

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

Entering edit mode asks the public write-side admission port to admit the current
read coordinates and mint a `ModeloEditBaseline`. This baseline is distinct from
the `ModeloWorkspaceBaseline`; the response either binds the selected work,
calculation state, schema identity, and permitted edit surface or returns a typed
refusal. One `ModeloEditSession` is then created with the read-consistency
identity, edit baseline, visible/exact address, contract and schema identity,
base semantic references, canonical staged values, ordered row intents, dirty
addresses, addressable validation, and state. Its state machine is:

`CLEAN` enters `DIRTY` on the first edit. Preflight moves `DIRTY` to
`VALIDATING`, then back to `DIRTY` with findings or to `READY`; further edits
move `READY` back to `DIRTY`. Submit moves `READY` to `SUBMITTING`. Confirmed
effect plus refresh moves it to `SETTLED`; proven no effect with a current edit
baseline returns it to `READY`. A consistency conflict or unknown effect enters
`STALE_CONFLICT`. `ABANDONED` is reachable only through explicit discard of
staged edits.

The absence of an intent means `UNCHANGED`. Scalar intents are closed and
distinct: `SET_TYPED_VALUE`, `CLEAR_DECLARED_VALUE`, and `REMOVE_OVERRIDE`.
Numeric zero, false, empty optional text, cleared value, and absent override are
never conflated. The application projection determines which intents a field
permits. Computed, informational, projection-only, backend-only, and refused
fields have no editor control.

An active widget may retain a locale-tagged raw lexeme while the public
application input port parses it. The session stores a canonical typed value
only after successful parsing. Changing locale never reinterprets an existing
raw lexeme: parsed values reformat under the new locale, while an unparsed
lexeme remains visibly tagged with its entry locale and blocks review until
resolved or discarded.

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

Submit compiles one application-owned `ModeloEditSubmission` containing the
edit baseline and ordered typed intents. The Workspace read baseline remains a
consistency coordinate and is not promoted into a mutation precondition. The
TUI does not reconstruct a complete calculation bundle or call a writer. The
edit port performs authoritative preflight and hands the sealed financial
operand to the enrolled operation through a single-consumer memory-only
channel. The durable operation envelope
contains only safe identifiers, an opaque one-shot operand reference or digest,
the edit baseline, and operation metadata; journal replay can settle or refuse
the operation but cannot reconstruct financial inputs. The payload is cleared
the handoff after executor acknowledgement, while the TUI retains its session
until settlement and refresh prove the authoritative result. C3 cannot open
until the operation authority accepts and proves this non-journaled handoff.
An unconsumed payload expires and is cleared on cancellation or deadline. On
process loss, a recorded unconsumed state may settle as no effect; a consumed
state is `UNKNOWN` unless an idempotent writer or durable result receipt proves
`NONE` or `UPDATED`. Recovery never guesses, reloads, or logs the operand.

### D5 — Repeated-row semantics

An existing row uses the application-issued stable semantic row address. A new
row receives an opaque TUI-local `DraftRowId` that remains stable across local
insert, validation, focus, and delete. A draft ID is never treated as a durable
row coordinate or written to the operation journal.

Row intents are `ADD_ROW`, `UPDATE_ROW`, `DELETE_ROW`, and, only when explicitly
projected, `MOVE_ROW`. Add and update stage a whole typed row. An incomplete row
may remain visibly dirty but cannot enter `READY`; deletion and move appear
explicitly in review. Source-derived or calculated rows remain read-only unless
the application projects an override capability and the permitted override
intent.

The submitted order is the producer-projected base order with staged updates and
deletes applied, followed by additions in their displayed order. Explicit moves
are available only when the group is declared reorderable and its full ordered
membership is materialized within the producer-declared bound. The application
edit port, not the TUI, maps this order to canonical row coordinates and validates
row limits, uniqueness, source identity, and cross-row rules. Positional widget
indexes are never row identity.

### D6 — Validation, conflict, settlement, and refresh

Validation has three owned layers:

1. The widget owns presence of an unparsed lexeme and interaction feedback, but
   delegates parsing and coercion to the public application input port.
2. Application preflight owns field, section, cross-field, row, and complete
   edit-intent validation against the edit baseline.
3. The enrolled operation revalidates the edit baseline, capability, and
   complete intent immediately before effect; a prior green preflight is not
   authorization and the Workspace read baseline is not substituted for it.

Every validation carries a stable code, severity, semantic address or global
scope, localized message key/arguments or producer-approved display, evidence
reference when applicable, and canonical action reference when recovery exists.
The TUI may group and focus validations but may not parse prose or translate a
warning into readiness.

A clean manual or automatic refresh replaces the read session. Destination,
section expansion, row selection, and focus survive only when the same semantic
addresses exist. A dirty refresh or any read-consistency change,
submission-time edit-baseline refusal, selected revision, schema, work-pointer,
or contract mismatch enters `STALE_CONFLICT`, preserves staged values in memory,
and blocks submit. Version 1 offers review of pending edits and explicit
abandon-and-reload only. It performs no automatic merge, silent rebase, or
field-level conflict resolution.

Terminal operation state never patches the prior workspace. The controller
folds the operation-owned observation to terminal settlement, then requests a
new workspace projection using the safe result/origin reference. `UPDATED`
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

`ModeloActionView` contains a stable action reference, localized label/help,
target semantic address, capability disposition, registered operation-definition
reference when mutating, interaction classification, destructive flag, and
result destination. It contains no callback. The controller maintains a closed
action-reference dispatch map to public application or operation ports, and a
fixed-point test proves every visible mutating action is enrolled and every
enrolled TUI Modelo action is mapped or explicitly classified as not visual.

The initial action inventory is intentionally narrower than the CLI command
tree:

| Cohort | Workspace mapping | Authorized actions |
|---|---|---|
| C1 | selection and bounded review | list, status, review, revisions, revision inspect, observations, dependencies, and refresh as direct queries |
| C2 | all read destinations | bounded section/row/provenance traversal, capability detail, and refresh as direct queries |
| C3 | selection and edit review | create work plus calculate/recalculate through enrolled operations and the non-journaled edit handoff |
| C4 | overview, verification, and filing | rename, discard, verify, file, and export only where separately enrolled and projected available |

Discard is destructive and must declare the canonical exact approval
interaction. File and any external handoff use their owning interaction and
capability contracts; `file` here means the existing local filing record and
human handoff, never remote AEAT submission. Apply/reject controls shown during
a pending interaction belong to `OperationModal`, not to the Modelo action rail.
CLI `wizard`, `runs`, and `resume` remain under flow/CLI ownership and do not
become duplicate workspace actions. A later visual mapping requires an
amendment and a new fixed-point receipt; command existence alone never
authorizes a button.

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

### D9 — Version and compatibility behavior

The TUI declares the exact Workspace and public operation projection versions it
consumes. Startup or route admission refuses an unsupported version before a
workspace is mounted. Read sessions pin the received contract version, selected
revision, schema fingerprint, and Workspace baseline; edit sessions additionally
pin the admitted edit baseline. An in-process version change follows the stale
protocol.

TUI-local view models and route IDs are internal code contracts rather than a
second serialized API version. A breaking in-tree change updates route factories,
dispatch maps, tests, and consumers in one change. No aliases, deprecated
destination IDs, dual projection adapters, permissive extra fields, or fallback
generic widgets remain after migration.

### D10 — Acceptance receipts and staged cohorts

The implementation plan must preserve this dependency order; later cohorts may
not substitute mocks for an unmet earlier receipt:

| Cohort | Entrance gate | Required exit receipt |
|---|---|---|
| C0 — operation foundation | accepted operation architecture | public operation observation version; ordered event fold through terminal settlement; interaction, cancellation, effect, and recovery conformance; production DI smoke |
| C1 — bounded review | accepted interface migration lane and canonical `ModeloWorkReview` | root-route relocation, locale parity, bounded review snapshots, keyboard/geometry proof, and no legacy production import |
| C2 — complex read workspace | this ADR accepted, accepted Workspace V1, accepted or reconciled authority-grade decision, C1 | destination/factory census, projection-to-view-model coverage, baseline-consistent facet tests, typed refusal states, current-registry scale fixtures, and production composition |
| C3 — staged editor | this ADR accepted, C0 and C2, public application edit-admission/input/preflight port, enrolled create and calculate operations | read-baseline/edit-baseline separation; edit/row state-machine and crash-window effect tests; review-only submit; stale refusal; result refresh; locale switch; non-journaled operand and sensitive non-retention proof |
| C4 — lifecycle actions | C3 plus each owning domain capability and operation definition | fixed-point action/operation/capability inventory; exact interaction; terminal-effect refresh; rename, discard, verify, file, and export receipts independently |
| C5 — visual closure | all intended C1-C4 actions declared | four-locale, three-geometry, two-theme, keyboard, non-colour, large-schema/row, refusal/conflict, route/action anti-vacuity, and installed root-app receipts |

Each receipt records the Workspace version, operation-projection version,
selected schema/revision fixtures, action and destination census, locale/geometry
matrix, synthetic scale fixture, production composition path, and non-retention
proof. A cohort is closed only when its executable receipt is green on current
HEAD. Global registry completeness is not a prerequisite: an honestly refused
capability is valid C2 behavior, while a mutation cannot enter C3 or C4 until its
selected revision and operation meet their required capability.

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
calculation history without inventing a mutable draft repository. Operation
references preserve supervision, and fresh-read settlement prevents the TUI
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
  focused Modelo companion; the API and operation ADRs remain authoritative in
  their layers.
- Large revisions and repeated rows require bounded application traversal,
  virtualization/paging, stable semantic identities, and consistency tests.
- Editing is deliberately conservative: no write-through, durable draft,
  automatic merge, or silent rebase. Operators must explicitly abandon stale
  edits until a future accepted merge decision exists.
- Every mutation needs a registered operation, projected capability,
  non-journaled operand path where values are sensitive, edit-baseline check,
  result mapping, and independent receipt. Existing CLI coverage does not
  satisfy that obligation.
- Unsupported schema kinds, projection versions, capability states, and
  renderers become visible refusals and failing coverage rather than generic
  fallback behavior.
- Implementation work is larger than a screen build, but it is partitioned into
  C0-C5 cohorts that can be planned and verified without a competing rollout
  plan or a global registry-completeness blockade.
