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
memory-only session, submits application-owned operation requests, and refreshes
from a new authoritative projection after settlement. The ADR must decide that
interface contract, its staged cohorts, and its proof gates without taking
registry, calculation, operation-lifecycle, persistence, or root-shell
authority.

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

### Editing is one baseline-bound transaction, not a sequence of domain writes

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

The interface decision therefore needs a memory-only edit session containing a
visible work address, the Workspace read-consistency identity, a separately
admitted write-side edit baseline, schema/version identity, base projection
reference, staged typed intents, dirty semantic addresses, ordered row intents,
validation presentation, and submit state. `UNCHANGED`, `SET`, `CLEAR` or
override removal, zero, row add, row delete, and row move cannot be collapsed
into one nullable value. Review should compile one application-owned mutation
request; the TUI must neither persist a partial calculation revision nor write
through on blur. A durable editor checkpoint would duplicate sensitive
financial inputs outside the existing work repository and has no accepted
custody contract, so it is not supported by current evidence.

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

### Actions are typed capability references, not button callbacks

The accepted operation architecture owns enrollment, interaction, progress,
cancellation, settlement, result, and effect semantics. The current operation
registry already distinguishes frontend projection enrollment, while current
inspection still exposes a persisted snapshot rather than the complete public
observation required by that architecture
(`src/cadrumo/application/operations/_registry.py:61-65`,
`src/cadrumo/application/operations/_supervisor.py:366-369`). The Modelo
workspace must therefore consume the operation projection only after the
operation cohort closes; it cannot define a sibling operation DTO.

Each visual action needs an application-projected stable action reference,
registered operation definition reference, capability disposition, refusal or
reconsideration condition, interaction kind, and result destination. A control
is enabled only when the projection says the capability is available. Refused,
not-applicable, and unmeasured are distinct visible states; an
unexplained disabled control is not sufficient. Canonical application error and
action envelopes remain the sources for top-level failure and recovery actions.

The lifecycle action inventory must be explicit per cohort. Read destinations
may offer refresh and inspect actions before mutation exists. Calculate or
recalculate is the first editor submit action. Verify, file, export,
discard, rename, and similar lifecycle actions cannot appear merely because a
CLI command exists; each requires its own enrolled operation, projected
capability, interaction classification, terminal refresh mapping, and acceptance
receipt.

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
capability/refusal, and production root-app composition
(`2026-08-11-tui-interface-adr`).

Financial values are not generic application secrets, but they are sensitive.
They must remain in the workspace projection, mounted widgets, and memory-only
edit session; they cannot be placed in route strings, telemetry, snapshots,
operation journals, diagnostics, concurrency tokens, or golden fixtures. This
ADR does not reopen the separate generic secret-submission or recovery-display
decisions.

### The dependency order is sequential, but registry completeness is not a global gate

The audit's C0-C5 sequence matches the real dependencies: operation observation;
bounded review relocation; complex read workspace; staged calculate/edit;
lifecycle actions; then fixed-point visual, scale, accessibility, and
composition closure. A cohort should open only when its named API and
architecture dependencies have accepted records plus executable receipts.

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
workspace with local view models and a staged edit session; the ADR must settle
that option and its exact gates.

### Not investigated

This research does not choose visual styling, copy, a design-token palette,
framework-specific widget classes, or numeric performance budgets beyond the
architectural requirement for bounded rendering. It does not expand which
Modelos have filing authority, authorize live AEAT side effects, define registry
fields, or decide a general-purpose merge algorithm. Those remain with their
existing authorities or future focused decisions.

## Sources

- `2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`
- `2026-08-11-tui-interface-adr`
- `2026-08-11-tui-architecture-adr`
- `2026-08-24-tui-registry-api-gate-adr`
- `2026-06-04-modelo-addressing-ux-adr`
- `2026-07-23-tui-wizard-substrate-adr`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:102-303`
- `src/cadrumo/application/modelo/_calculate_input.py:149-177`
- `src/cadrumo/domain/modelos/_calculation_revision.py:399-463`
- `src/cadrumo/domain/modelos/_calculation_revision.py:1011-1094`
- `src/cadrumo/application/operations/_registry.py:61-65`
- `src/cadrumo/application/operations/_supervisor.py:366-369`
- Runtime measurement on 2026-08-24: `uv run --no-sync python -c` over
  `cadrumo.domain.calculations.registry.bundled_authority()`.
