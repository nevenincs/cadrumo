---
tags:
  - '#research'
  - '#tui-modelo-workspace-interface'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:525187e863e3a90c448d30d2984ba15564b32c7cf48bfb88db048dc294955cca'
related:
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]"
---

# `tui-modelo-workspace-interface` research: `Modelo workspace interface and editor`

The question is whether the accepted TUI architecture plus the proposed
registry API gate gives visual cohorts a sufficiently concrete target for a
complex Modelo workspace and editor. It does not yet do so by itself. The
accepted interface record deliberately reserves `modelo.edit` for a later
write-side decision, and the API proposal owns application data rather than
routes, view state, transactions, or accessibility. Current registry scale also
rules out treating the workspace as one eagerly mounted generic schema form.

The evidence favors a typed, destination-oriented Modelo workspace that maps an
application-owned projection into TUI-local view models, stages edits in one
memory-only session, consumes a separate versioned application edit contract,
and refreshes from a new authoritative projection after operation settlement.
The interface ADR must decide destinations, local state, staged cohorts, and
visual proof without taking registry, calculation, application mutation,
operation-lifecycle, persistence, or root-shell authority. The missing
frontend-neutral edit contract is a separate decision consumed by that
interface.

## Findings

### The accepted interface contains the amendment seam but not the missing decision

The accepted interface authority assigns shell layout, navigation, route
selection, mounting, focus, and renderer registration to the root application.
Feature areas supply route factories, and Modelo read and edit packages remain
reserved. In particular, `modelo.edit` may exist only after a later accepted
write-side ADR defines mutation, validation, and persistence interaction
contracts. The accepted operation architecture separately disclaims holistic
information architecture and owns the public operation projection. The
reconciliation audit therefore correctly identifies one unowned decision, not
permission for the API record to absorb frontend or operation authority. The new
record should be an amendment of `2026-08-11-tui-interface-adr`, consume
`2026-08-11-tui-architecture-adr`, and leave the application join to
`2026-08-24-tui-registry-api-gate-adr`.

### A workspace needs a finite destination catalogue and persistent context

Natural Modelo work identity is already established as active profile or
bucket, modelo, filing year, and period. Registry revision and raw identifiers
are advanced exact-addressing escape hatches, and ambiguous visible targets
must refuse. The interface can therefore route by a typed visible work target
and display the selected revision, rather than exposing a registry-tree or raw
ID browser as its normal navigation model
(`2026-06-04-modelo-addressing-ux-adr`).

The lifecycle facts that operators must inspect span current work and
calculation revision, inputs, results, causal provenance, verification, filing,
and historical status. A single scroll surface would not preserve location or
permit bounded loading. Evidence instead calls for a stable selection
destination followed by a workspace header and child destinations for overview,
inputs, results, provenance, verification, and filing/history. The root shell
must still own navigation mechanics; the Modelo feature should publish typed
destination identities and factories. Operation observation remains the global
operation destination or modal, joined back to the originating workspace by
safe references.

### TUI-local view models are required even when the application projection is complete

The registry exposes a much richer grammar than a widget toolkit: Casillas
include input classification, formulas or bindings, constraints, continuity,
export metadata, semantic role, legal/source references, and localization
accessors. Calculation input is also split across numeric and text Casillas,
numeric and enum bindings, relations, and detail rows
(`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:102-303`,
`src/cadrumo/application/modelo/_calculate_input.py:149-177`). Letting widgets
interpret those domain objects would move registry and calculation policy into
the entrypoint.

The visual layer instead needs immutable, callback-free local carriers for the
workspace header, navigation summary, section, field, repeated group and row,
value/provenance, validation, capability/refusal, and action presentation. These
carriers can choose control kind, disclosure state, focus identity, localized
text key, formatting, and density from application-projected semantics. They
must not decide authority grade, editability, calculation rules, lifecycle
readiness, or operation eligibility. This mapping also gives snapshot tests a
stable interface without making Textual types part of the application API.

### Editing has a local transaction and a separate application write contract

Calculation revisions are immutable, content-addressed records whose identity
includes scalar, binding, relation, row, provenance, and detail-row inputs
(`src/cadrumo/domain/modelos/_calculation_revision.py:399-463`). The existing
calculate-input builder validates a complete input bundle before passing it to
the calculation boundary. There is no mutable domain draft that a field widget
can safely patch. The wizard substrate supplies a useful precedent: edit in
memory, review, then commit once; however, a large non-linear workspace needs
random destination navigation, virtualization, and conflict state rather than
being modelled as one linear generic flow
(`2026-07-23-tui-wizard-substrate-adr`).

The interface needs a memory-only edit session containing a visible work
address, Workspace read-consistency identity, separately admitted write-side
baseline, schema/version identity, base semantic references, staged typed
intents, dirty addresses, ordered row intents, validation presentation, and
submit state. `UNCHANGED`, `SET`, `CLEAR` or override removal, zero, row add,
row delete, and row move cannot be collapsed into one nullable value. Review
must compile one application-owned mutation request; the TUI must neither
persist a partial calculation revision nor write through on blur. A durable
editor checkpoint would duplicate sensitive financial inputs outside the
existing work repository and has no accepted custody contract.

That local session is not itself the write contract. Workspace V1 is expressly
read-only, while the operation registry owns lifecycle rather than parsing,
editability, repeated rows, or Modelo persistence. A frontend-neutral public
contract is therefore still required behind `application.modelo` for version
dispatch, admission, locale-aware parsing, authoritative preflight, normalized
intents, capability/refusal, and execution result. Its current-only
compatibility boundary must name Workspace, edit, public operation projection,
and operation financial-operand versions independently; sharing one generic
version or letting an operation definition stand in for the edit schema would
hide incompatible seams.

### The mutation baseline spans both catalogues and the selected registry schema

The existing calculation writer already receives the revision-stamped work
catalogue, revision-loads the calculation catalogue, and compares both during a
single secure-object save. The work unit additionally carries its law-selected
registry revision and nullable current calculation head. Workspace V1 supplies
the canonical schema identity and fingerprint. Those are the minimum complete
edit baseline: work-catalogue revision, calculation-catalogue revision, current
calculation-revision id, registry revision, schema identity/fingerprint, and the
application-issued permitted edit surface. A Workspace read token cannot replace
them because it is explicitly not a mutation precondition
(`src/cadrumo/application/modelo/_revision_persistence.py:224-427`,
`src/cadrumo/domain/modelos/_work_unit.py:125-177`).

The existing success path already co-commits an immutable calculation revision,
the advanced work-unit pointer, and the corresponding bucket event under
compare-and-swap. It returns the revision to the caller but has no durable
edit-result receipt that an operation reconciler can use after a crash. The
stable edit boundary therefore needs to extend that same single writer with a
safe encrypted result receipt, not create a second persistence path. Stale work
catalogue, calculation catalogue/head, registry, schema, or permitted-surface
coordinates must refuse before any write; a failed compare-and-swap leaves all
four records absent. A receipt that contains only safe identities can prove an
already-committed `UPDATED` effect without retaining financial values
(`src/cadrumo/adapters/persistence/profile/modelos_work_units.py:221-282`,
`src/cadrumo/application/modelo/tests/test_lifecycle_event_atomicity.py:1-18`).

### Repeated rows require draft identity distinct from canonical row coordinates

Persisted row materialization is keyed by canonical binding and row coordinates,
and the calculation revision validates row values and provenance together
(`src/cadrumo/domain/modelos/_calculation_revision.py:1011-1017`). A newly added
unsaved row has no such durable coordinate, while positional widget IDs change
under insert, delete, or reorder. Stable TUI-local draft row keys are therefore
needed for focus and dirty tracking. The ordered edit intent can be mapped to
canonical one-based coordinates only by the application mutation boundary at
submission. Existing source-derived rows must carry the producer-projected row
identity and edit capability; the TUI cannot infer that a visible row is
overrideable.

Whole-row add and delete are the safe interaction unit. Partially completed new
rows may remain staged, but they cannot enter the submitted operation request.
Any row limit or ordering rule is application-projected validation, not a
frontend constant.

### Validation, staleness, and refresh have three different owners

The TUI can own lexical editing feedback and focus, while authoritative field,
cross-field, row, and lifecycle validation belongs to the application/domain
boundary. Errors need semantic addresses so the editor can focus a field or row
without parsing prose. The Workspace baseline proves one coherent read and is
explicitly not a mutation precondition. A public write-side admission port must
mint a distinct safe edit baseline for the selected work and calculation state;
preflight can produce an addressable validation projection against it, but the
operation executor must revalidate that edit baseline and the complete intent
immediately before effect (`2026-08-24-tui-registry-api-gate-adr`).

Refresh is safe when the session is clean: fetch a new workspace projection,
replace local view models, and retain a destination or focus only if its semantic
identity still exists. Refresh during a dirty session is a concurrency decision.
Current evidence supplies neither a three-way merge contract nor field-level
conflict authority; silently rebasing against a changed registry or calculation
revision would be policy. The minimum reliable behavior is an explicit stale
conflict that blocks submission and preserves the in-memory draft until the
operator discards it or an independently accepted rebase contract exists.
Successful operation settlement must similarly trigger a fresh authoritative
workspace read; patching the old projection from a terminal result would create
a second materializer.

### Actions need a generated complete denominator, not a chosen button list

The accepted operation architecture owns enrollment, interaction, progress,
cancellation, settlement, result, and effect semantics. The current operation
registry already distinguishes frontend projection enrollment, while current
inspection still exposes a persisted snapshot rather than the complete public
observation required by that architecture
(`src/cadrumo/application/operations/_registry.py:61-65`,
`src/cadrumo/application/operations/_supervisor.py:366-369`). The Modelo
workspace must therefore consume the operation projection only after the
operation cohort closes; it cannot define a sibling operation DTO.

Each visual action needs an application-projected stable mutation identity,
registered operation definition reference, capability disposition, refusal or
reconsideration condition, interaction kind, and result destination. A
canonical recovery `ActionReference` may be joined but does not grant invocation
authority. A control is enabled only when the projection says the capability is
available. Refused, not-applicable, and unmeasured are distinct visible states;
an unexplained disabled control is not sufficient. Canonical application error
and action envelopes remain the sources for top-level failure and recovery
actions.

The lifecycle action inventory must be derived and explicit per cohort. Its
candidate denominator must join the canonical action catalogue, operation
definitions, complete command graph and `TuiCapability` declarations, direct
application mutation/outbound sites, TUI routes/dispatch, and typed exclusions.
A fixed point over only actions already chosen for display can never detect an
omitted action.

Current code makes that failure concrete. `modelo.work.amend` is a live
calculation mutation, and `modelo.work.amend_wizard` is a separate guided
command currently marked `TuiCapability.AVAILABLE`
(`src/cadrumo/entrypoints/cli/_modelo_core_command_specs.py:167-199`,
`src/cadrumo/entrypoints/cli/_modelo_nonwork_command_specs.py:2311-2415`). The
domain amendment service atomically advances filing and calculation state
rather than behaving like ordinary recalculation. The inventory must therefore
classify `amend` as a separately enrolled lifecycle/editor action and the wizard
as a flow-owned transitional presentation to replace or retire, rather than
letting either disappear from a hand-maintained workspace table. The same
generated denominator must classify direct queries and other flow/global
operation commands exactly once.

Read destinations may offer refresh and inspect actions before mutation exists.
Calculate or recalculate is the first editor submit action. Verify, file,
export, amend, discard, rename, and similar lifecycle actions cannot appear
merely because a CLI command exists; each requires its own application
capability, enrolled operation, interaction classification, terminal refresh
mapping, and acceptance receipt.

### Registry scale requires bounded rendering and consistency tokens

A reproducible current-HEAD measurement of `bundled_authority()` on 2026-08-24
found 58 Modelos and 102 revisions. The largest revision carries 3,462 Casillas,
707 distinct section paths, 975 bindings, and 578 projection endpoints. Repeated
row mappings and detail-row tuples have no interface-level upper bound
(`src/cadrumo/domain/modelos/_calculation_revision.py:1011-1094`). An eager
widget-per-field workspace and an unbounded provenance tree are therefore not
credible acceptance targets.

The application can remain the sole owner of the complete semantic join while
the interface consumes bounded section, row-page, and provenance-expansion
facets. Every facet must be bound to the same workspace baseline, schema
version/fingerprint, selected revision, and projection-contract version; a
mismatch invalidates the composed view rather than mixing snapshots. Only the
active destination body should be mounted, large tables need stable-key
virtualization or paging, and causal disclosure needs lazy bounded expansion.
An equally valid producer implementation may return a bounded complete
projection, but the interface contract cannot require eager materialization or
rendering of unbounded collections.

### Locale, accessibility, responsiveness, and custody are acceptance dimensions

Locale is a projection axis, not identity or schema selection. The interface
must display resolved locale and fallback when relevant, use stable semantic
IDs rather than translated labels for routing and focus, and preserve equal
capability and value identity across supported locales. The accepted interface
proof matrix already establishes Spanish, English, Catalan, and Hungarian;
`80x24`, `120x36`, and `160x48`; light and dark themes; keyboard traversal; and
non-colour-only status. Complex Modelo proof must extend that matrix with long
labels, deep sections, large row counts, validation focus, stale conflict,
capability/refusal, and production root-app composition before each route or
action becomes callable or declares `TuiCapability.AVAILABLE`
(`2026-08-11-tui-interface-adr`).

Financial values are not generic application secrets, but they are sensitive.
They must remain in the workspace projection, mounted widgets, and memory-only
edit session; they cannot be placed in route strings, telemetry, snapshots,
operation journals, diagnostics, concurrency tokens, or golden fixtures. This
ADR does not reopen the separate generic secret-submission or recovery-display
decisions.

### The dependency order is sequential, but registry completeness is not a global gate

The audit's C0-C5 sequence matches the real dependencies: operation observation;
bounded review relocation; complex read workspace; the application edit
contract plus operation-owned financial-operand submission; lifecycle actions;
then fixed-point visual and composition closure. A cohort should open only when
its named API and architecture dependencies have accepted records plus
executable receipts. Accessibility cannot be delayed until the final cohort if
an earlier route becomes callable; each cohort needs its applicable
locale/geometry/theme/keyboard/non-colour proof before availability.

The accepted Casilla record gives C1 one canonical bounded review at
`entrypoints.tui.modelo.view`, but the larger destination catalogue needs an
explicit C1 destination identity and an atomic C2 replacement rule. Otherwise a
"closed" catalogue can omit the only screen its first cohort migrates
(`2026-08-10-casilla-schema-read-model-adr`).

Receipt identity also needs one home. The C1 interface exit is
`ModeloWorkspaceC1ExitReceiptV1`; the API-owned C2 dependency is
`ModeloWorkspaceC2DependencyReceiptV1`; C3 must consume a separately green edit
contract receipt and the operation-owned financial-operand receipt. Every later
receipt needs predecessor digests and a typed not-applicable disposition with
owner, code, reason, and evidence. Null or prose "n/a" would let a missing
required axis masquerade as a green matrix cell.

Global registry completion need not precede complex reads. A selected revision
can honestly render available inspection capability and evidence-backed
refusals for unsupported calculation, verification, export, or filing. Editing
and later actions do require their selected revision and operation definition to
meet the projected capability contract without downgrade.

Three implementation shapes were compared. Keeping only the bounded review
cannot deliver the requested workspace. A generic registry-to-widget interpreter
is superficially fast but violates application and registry boundaries. Treating
the whole workspace as one generic wizard preserves atomic submit but fails
non-linear navigation and scale. The evidence favors a destination-oriented
workspace with local view models, a staged local session, and a separate
application edit contract; the ADR cluster must settle those boundaries and
their exact gates.

### Not investigated

This research does not choose visual styling, copy, a design-token palette,
framework-specific widget classes, or numeric performance budgets beyond the
architectural requirement for bounded rendering. It does not expand which
Modelos have filing authority, authorize live AEAT side effects, define registry
fields, decide operation custody, or introduce a general-purpose merge
algorithm. Those remain with their existing authorities or future focused
decisions.

## Sources

- `2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`
- `2026-08-11-tui-interface-adr`
- `2026-08-11-tui-architecture-adr`
- `2026-08-24-tui-registry-api-gate-adr`
- `2026-08-24-tui-operation-observation-adr`
- `2026-08-10-casilla-schema-read-model-adr`
- `2026-06-04-modelo-addressing-ux-adr`
- `2026-07-23-tui-wizard-substrate-adr`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:102-303`
- `src/cadrumo/application/modelo/_calculate_input.py:149-177`
- `src/cadrumo/application/modelo/_revision_persistence.py:224-427`
- `src/cadrumo/adapters/persistence/profile/modelos_work_units.py:221-282`
- `src/cadrumo/domain/modelos/_calculation_revision.py:399-463`
- `src/cadrumo/domain/modelos/_calculation_revision.py:1011-1094`
- `src/cadrumo/domain/modelos/_work_unit.py:125-177`
- `src/cadrumo/application/operations/_registry.py:61-65`
- `src/cadrumo/application/operations/_supervisor.py:366-369`
- `src/cadrumo/entrypoints/cli/_modelo_core_command_specs.py:167-199`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_command_specs.py:2311-2415`
- `src/cadrumo/application/modelo/tests/test_lifecycle_event_atomicity.py:1-18`
- Runtime measurement on 2026-08-24: `uv run --no-sync python -c` over
  `cadrumo.domain.calculations.registry.bundled_authority()`.
