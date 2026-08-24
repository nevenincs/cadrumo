---
tags:
  - '#adr'
  - '#tui-interface'
date: '2026-08-11'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:95b5208bbc5deda78a25c4feeead1743444141939fb396897d2fb24955cdd806'
related:
  - "[[2026-08-11-tui-interface-research]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-07-23-tui-wizard-substrate-adr]]"
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-07-24-profile-bundle-tui-adr]]"
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-plan]]'
---
# `tui-interface` adr: `Canonical modular Textual application surface` | (**status:** `accepted`)

## Problem Statement

The Textual frontend requires one architectural home, explicit feature
ownership, narrow public facades, and a legal dependency direction. This record
decides the frontend half of the join with
`2026-08-11-tui-architecture-adr`. It fixes the
`cadrumo.entrypoints.tui` presentation tree, component boundary, profile and
secret surfaces, generic flows, and cross-feature joins. It also defines future
Modelo ownership and the interface conditions for retiring the flat adapter
(`2026-08-11-tui-interface-research`).

`cadrumo.entrypoints.tui` is the canonical Textual transport, sibling to
`cadrumo.entrypoints.cli` and `cadrumo.entrypoints.mcp`. It is neither an
inbound artefact adapter, a CLI subpackage, a top-level package, nor a backend
service.

The canonical CLI remains `cadrumo.entrypoints.cli`, and the dedicated future
full-screen application remains `cadrumo.entrypoints.tui`. The CLI exposes one
root-owned frontend request, `aeat --tui [COMMAND_PATH]`; leaf commands do not define
independent TUI policy or a second local flag. `TuiCapability.AVAILABLE` means that the
resolved command has a real callable full-screen interface today. It does not claim
that the interface has already migrated to the dedicated entrypoint. A command without
such an interface returns the localized typed `TUI_NOT_IMPLEMENTED` refusal instead of
ignoring the request or falling back to line mode.

This record does not redefine operation lifecycle, supervision, settlement,
cancellation, profile reconciliation, flow semantics, redaction, error
classification, CLI behavior, or MCP behavior.

## Considerations

- The flat facade erases flow, profile, secret, and reusable-presentation
  ownership and causes CLI modules to construct frontend-specific values
  (`2026-08-11-tui-interface-research`).
- User-facing transports belong beneath `cadrumo.entrypoints`; inbound adapters
  own external artefact normalization (`2026-04-30-aeat-restructure-adr`,
  `2026-06-01-domain-boundary-audit-adr`).
- The accepted operation decision owns application supervision and the TUI
  operation projection (`2026-08-11-tui-architecture-adr`).
- Forms divide into visual mechanics, operation interaction transport, and
  feature-owned projection and validation (`2026-08-11-tui-interface-research`).
- Profile sync needs a specialized review renderer without a second lifecycle
  or reconciliation authority (`2026-08-11-tui-interface-research`).
- Secrets cannot enter persisted flow answers or durable operations
  (`2026-07-24-profile-bundle-tui-adr`).
- Generic flows remain projections of the accepted application engine
  (`2026-07-23-tui-wizard-substrate-adr`).
- The accepted operation decision selects a dedicated installed TUI entrypoint,
  prohibits Python imports of TUI from other entrypoints, and assigns amendment
  of older frontend-selection clauses to its integration lane
  (`2026-08-11-tui-architecture-adr`).

## Considered options

- **Retain the flat inbound adapter.** Rejected: wrong physical owner and
  continued facade entanglement.
- **Use top-level `cadrumo.tui`.** Rejected: it bypasses the established
  entrypoint layer and creates an unclassified top-level layer.
- **Nest TUI under CLI.** Rejected: TUI, CLI, and MCP are sibling transports;
  TUI must not depend on Typer or CLI projections.
- **Organize by apps, screens, and widgets.** Rejected: framework-kind grouping
  hides feature ownership.
- **Use `core` or `shared`.** Rejected: `core` collides conceptually with the
  innermost kernel and `shared` has no bounded ownership criterion.
- **Preserve selection through a Python CLI-to-TUI facade.** Rejected: it makes
  one entrypoint import another and conflicts with the accepted topology.
- **Add independently owned leaf-specific `--tui` flags.** Rejected: frontend-selection
  policy would vary accidentally by command and could drift from the command graph.
- **Add one root-owned `aeat --tui` request with per-command capability metadata.**
  Chosen: the root captures one request, the resolved command declares whether a
  callable full-screen interface exists, and genuinely unimplemented commands return
  the same typed refusal.
- **Use the dedicated installed TUI entrypoint selected by the topology
  authority.** Chosen: packaging calls the TUI launcher directly; older
  frontend-selection consumers are reconciled by the roll-up integration lane.
- **Create empty Modelo packages or markers.** Rejected: design-only shells
  imply APIs without behavior and tests.
- **Use an ownership-oriented sibling entrypoint with `components`.** Chosen.

## Constraints

- The accepted operation ADR is the topology authority. This record adopts its
  root, names, dependency direction, launch behavior, and D12 integration
  ownership pending reconciliation of that ADR's conflicting D10 labels; it
  does not independently reopen topology.
- `cadrumo.entrypoints.tui.components` is the sole TUI-local visual seam.
  Neither `tui.core` nor `tui.shared` exists.
- `cadrumo.core` remains innermost and frontend-neutral. Textual and TUI types
  cannot enter it.
- No CLI, MCP, backend, shared test utility, or development tool may import,
  load, re-export, annotate against, or register from the TUI package. TUI also
  cannot import CLI or MCP. This interface lane does not edit CLI files.
- `--tui` has one authority at the CLI root. Introspection (help, version,
  completion, and equivalent metadata traversal) takes precedence and exits without
  launching or refusing a frontend.
- `TuiCapability.AVAILABLE` records present callable behavior, not completion of the
  dedicated-entrypoint migration. `NOT_IMPLEMENTED` means no callable full-screen
  interface exists for that resolved command.
- Until the dedicated migration replaces them, the already-existing bounded CLI
  imports of `cadrumo.adapters.inbound.tui` used by an `AVAILABLE` command are
  authorized transitional consumers. This adds no new consumer and is not evidence
  that the launcher, packaging, reverse-consumer migration, or legacy deletion is complete.
- Explicit `--tui` never silently falls back to line mode: an `AVAILABLE` command
  invokes its current full-screen interface and a `NOT_IMPLEMENTED` command refuses.
- No top-level bootstrap package is introduced. TUI composition belongs in
  `cadrumo.entrypoints.tui.launcher`; shared frontend-neutral construction, if
  required, remains with the owning application facade and accepts ports.
- Operation supervision and the `operations` subtree remain governed by the
  sibling ADR. Profile reconciliation remains application-owned.
- The later `tui-interface` plan starts only after both dependency campaigns close:
  `2026-08-11-tui-architecture-plan` and
  `2026-08-10-casilla-schema-plan`. An accepted interface decision does not
  waive that execution gate.
- Secret collection requires a backend-owned, exact, single-use submission
  capability with ephemeral custody. The accepted operation ADR and roll-up
  plan do not yet name or schedule that capability. This record defines only
  masked presentation and bounded UI custody; secret implementation remains
  blocked until the operation authority amends its public API and tests. Values
  and reversible derivatives cannot enter durable operation or flow records.
- Migration requires consumer-complete vertical slices and allows no facade,
  alias, dynamic bridge, duplicate package, or permanent allowlist.
- Modelo view/edit names are reservations until the casilla-schema dependency
  publishes its canonical read model and the TUI architecture dependency gives
  the review surface a final canonical disposition. No placeholder package is
  permitted before then.

## Implementation

### D0 - Ownership and reconciliation gate

This record owns the `INTERFACE` rows fixed by the topology authority:
`components`, `profile`, `secret`, `flows`, `devtools`, and their
presentation-owned tests. It also owns the application-shell information
architecture expressed through the integration contract, but not the
integration files themselves.

The operation ADR retains operation semantics, application supervision,
persistence ports, executors, runtime construction contract, and the behavior
of `cadrumo.entrypoints.tui.operations`.

The accepted roll-up plan owns migration inventory, operations, root integration,
packaging, reverse-consumer migration, and legacy deletion. The integration lane
alone owns `__init__.py`, `__main__.py`, `launcher.py`, `app.py`, and packaging.
This feature produces one post-dependency information-architecture plan. That
plan must not duplicate operation-platform or package-migration work, and it
performs no CLI change.

| Exact path or contract | Single owner | Interface relationship |
|---|---|---|
| `entrypoints/tui/components`, `profile`, `secret`, `flows`, `devtools` | `tui-interface` | Implements presentation only. |
| `entrypoints/tui/operations` | `tui-architecture` operation lane | Consumes the components facade; publishes interaction registration. |
| `entrypoints/tui/__init__.py`, `__main__.py`, `launcher.py`, `app.py`, packaging | roll-up integration lane | Joins independently green areas; interface supplies routes and factories. |
| `core.operations`, `application.operations`, operation persistence and executors | `tui-architecture` backend lane | Interface consumes public immutable projections and commands only. |
| legacy manifest, reverse consumers, physical deletion and fixed-point gates | roll-up integration lane | Interface supplies destinations and parity evidence for its rows. |
| profile sync renderer | `tui-interface` | Publishes a renderer factory; the integration `app` registers it. |
| `EphemeralSecretSubmission` capability | `tui-architecture` operation lane after an operation ADR and plan amendment | Interface consumes the frozen public facade only and remains blocked beyond masked collection until its conformance suite is green. |

The architecture decision can be accepted before its dependencies land. The
dependency campaigns may execute their own interface and migration rows; this
ADR blocks only the later `tui-interface` plan.

Execution uses this dependency order:

1. **Casilla-schema receipt.** `2026-08-10-casilla-schema-plan` reaches its S40
   completion gate. `application.modelo` exports the canonical
   `ModeloWorkReview`, and the campaign records the review screen it produced.
2. **TUI architecture receipt.** After the casilla receipt, the
   `2026-08-11-tui-architecture-plan` reaches its completion gate. Its final
   migration absorbs the casilla review screen, resolves the D10/D12 ownership
   conflict, and leaves no legacy TUI identity. If this campaign closes first,
   it must be reopened or formally reconciled after casilla-schema lands.
   That receipt is invalid for this campaign unless the owning architecture
   ADR and plan have also added and closed two explicit gaps:
   - migration of the casilla review screen to
     `cadrumo.entrypoints.tui.modelo.view` as a read-only consumer of the
     public `application.modelo.ModeloWorkReview`, with named outlier proof;
   - an operation-owned public `EphemeralSecretSubmission` capability with
     exact operation and interaction binding, expiry, single use, duplicate
     and mismatch refusal, cancellation, cleanup, and non-retention tests.
3. **Interface start gate.** The first interface-plan Phase records a
   machine-readable dependency receipt at
   `.vault/reference/2026-08-11-tui-interface-dependency-receipt.md`. It names
   the casilla S40 and architecture S103 close evidence and commits, proves by
   Git ancestry that the casilla receipt precedes the architecture receipt,
   and records the settled public secret facade. A production test validates
   the receipt against the live tree. It requires the canonical
   `cadrumo.entrypoints.tui` package, public operation contracts,
   `ModeloWorkReview`, the canonical Modelo view, the conformance-tested
   secret capability, and zero legacy TUI implementation.

Until the third gate passes, no later `tui-interface` component, profile,
secret, flow, Modelo, launcher, or test step may start.

### D1 - Exact package tree

The following tree contains implementation packages only. Modelo reservations
are listed separately and must not be scaffolded from this tree.

```text
src/cadrumo/entrypoints/tui/
  __init__.py          # JOIN: narrow launcher-level facade
  __main__.py          # JOIN: delegates only to launcher.main
  launcher.py          # JOIN: sole TUI composition root
  app.py               # JOIN: navigation and area composition

  components/
    __init__.py
    theme.py
    widgets.py
    forms.py
    dialogs.py
    status.py
    errors.py
    logs.py
    tests/

  operations/
    __init__.py
    controller.py
    modal.py
    projection.py
    interactions.py
    logs.py
    tests/

  profile/
    __init__.py
    app.py
    overview.py
    editor.py
    status.py
    sync_review.py
    tests/

  secret/
    __init__.py
    credentials.py
    login.py
    registration.py
    passphrase.py
    tests/

  flows/
    __init__.py
    app.py
    question.py
    review.py
    projection.py
    dialogs.py
    tests/

  devtools/
    __init__.py
    tests/
  tests/                # JOIN integration tests only
```

`components`, `profile`, `secret`, `flows`, and `devtools` are `INTERFACE`;
`operations` is externally owned by the operation concern; root files are
`JOIN`. Tests live with their narrowest owner. There is no TUI `core` or
`shared` package.

| Reserved owner | Physical creation rule |
|---|---|
| `cadrumo.entrypoints.tui.modelo.view` | Create only after the `casilla-schema` campaign publishes its canonical `ModeloWorkReview` and the integration lane assigns the settled review surface here. |
| `cadrumo.entrypoints.tui.modelo.edit` | Create only after a later accepted write-side ADR defines mutation, validation, and persistence contracts. |

### D2 - Exact import DAG

- No inter-entrypoint import edge exists.
- `__main__` imports only `launcher`.
- `launcher` imports `app`, public application facades, and public concrete
  adapter facades needed for composition.
- `app` imports public facades of `components`, `operations`, `profile`,
  `secret`, and `flows`.
- Each feature area imports `components`, its owning public application facade,
  and layer-neutral core contracts.
- `components` imports Textual/Rich and safe `cadrumo.core` contracts only.
- Feature areas do not import one another. `app` is their sole composition
  point; they share visual primitives only through `components`.
- TUI does not import CLI/MCP, private application modules, domain internals,
  repositories, or concrete persistence. Only `launcher` may compose concrete
  adapters through public facades.
- Backend layers never import entrypoints.
- Textual types, CSS, screens, view models, pilots, replay, and screenshots live
  only below `cadrumo.entrypoints.tui`.

Import-linter and AST gates cover static/local imports, `TYPE_CHECKING`,
annotations, dynamic strings, registrations, re-exports, and facade mirrors.

### D3 - Facades and dedicated launch behavior

`cadrumo.entrypoints.tui.__init__` will expose launcher-level API only after the
dedicated migration creates that boundary. Packaging and out-of-process smoke tests
remain its eventual external boundaries. Area facades remain public only to sibling
TUI composition and export presentation factories or contracts, never operation
authority, repositories, or application services.

The target dedicated installed command remains `cadrumo-tui`, targeting
`cadrumo.entrypoints.tui.launcher:main`; `python -m cadrumo.entrypoints.tui`
will delegate to the same function. This target is not yet implemented and this
amendment does not mark it complete. The launcher returns process status only after
the TUI application closes; authoritative operation outcomes remain supervisor
receipts displayed in the application, not a CLI envelope or subprocess result
protocol. Reconciliation of older full-screen selection behavior is owned by
the roll-up integration lane and does not authorize this interface lane to edit
CLI.

Before that migration completes, `aeat --tui [COMMAND_PATH]` dispatches only commands
whose graph metadata is `TuiCapability.AVAILABLE`. Such a declaration requires a real
callable full-screen interface and may route through an existing bounded
`cadrumo.adapters.inbound.tui` consumer. All other resolved commands return localized
`TUI_NOT_IMPLEMENTED`. The migration lane must replace the transitional imports and
remove the legacy tree; present availability is not migration evidence.

### D4 - Launcher and application composition

`launcher` may compose concrete adapters and obtain application services
through public facades, then inject them into `app`. It owns dependency
assembly, terminal startup/shutdown, and startup-refusal projection only. It
contains no policy, operation semantics, reconciliation, persistence
implementation, or CLI behavior.

No top-level bootstrap package is created. Shared operation runtime
construction, if needed, belongs to the application operation facade, accepts
ports/resources, and imports neither entrypoints nor concrete adapters.

`app` owns shell layout, navigation, route selection, mounting, focus, and
feature-renderer registration. It executes no application work. Profile
publishes its sync renderer, operations publishes interaction registration,
secret publishes masked collection, and flows publishes routes; `app` binds
them without lateral feature imports.

### D5 - Components boundary

`components` owns shell/layout primitives, screen/modal mechanics, navigation
contracts, themes, notices, status, generic dialogs, visual form contracts and
widgets, safe error display, and bounded already-redacted log display.

It owns no validation/policy, operation lifecycle/subscription, flow state,
reconciliation, persistence/provider access, callbacks, worker settlement, raw
exceptions, or raw/unredacted logs.

Forms split among `components` visual mechanics, `operations.interactions`
transport, and feature-owned projection/validation presentation. The presenter
context and callback bridge are retired, never promoted into components.

### D6 - Profile setup and synchronization

Profile owns navigation, task-led overview, editing, readiness/status, and the
guided `Overview -> Get data -> Required -> Review -> Ready` projection. These
five stages form one ordered top navigation strip; only the active stage body is
mounted, with Previous/Next actions preserving a linear path. This is not a
second persisted wizard: route and focus are presentation state, while answers,
validation, applicability, and readiness remain application-owned.

`Overview` states the filing/person context and the smallest next action. `Get
data` lists available sources and runs explicit sync operations. `Required`
shows only applicable missing or disputed facts, grouped into collapsible task
sections. `Review` shows adopted/proposed facts, provenance, warnings, and
unresolved conflicts. `Ready` reports truthful filing readiness and remaining
blocking actions. Optional facts are collapsed behind a separate filter and
advisory material is visually distinct from requirements. Unknown applicability
is displayed as unassessed, never silently treated as an applicable missing
value, optional, or not applicable. The unresolved assessment itself may block
readiness when application policy says the answer controls a conditional
requirement.

| Classification | Default placement | Readiness effect | Available action |
|---|---|---|---|
| Applicable required, missing or invalid | Expanded in `Required` | Blocks `Ready` | Edit manually or start a disclosed source operation. |
| Conditionally required, applicability unassessed | Expanded first in `Required` as `Needs applicability`; no missing-value claim | The unresolved assessment blocks `Ready` when the application marks it readiness-relevant | Answer the applicability question; never guess from locale or presentation state. |
| Applicable required, present | Collapsed completed group in `Required`; summarized in `Review` | Satisfies only that application-owned requirement | Inspect provenance or edit. |
| Optional | Hidden behind `Show optional` in its task section | Never blocks `Ready` | Inspect, edit, or include in an explicit source review. |
| Advisory notice | Pinned notice band in the relevant stage and collected in `Review` | Never blocks `Ready`; a blocking condition must be classified separately | Inspect details or dismiss for the current view only; dismissal changes no domain state. |
| Not applicable | Hidden from `Required`; visible through `Show not applicable` | Never blocks `Ready` | Inspect the application-provided reason and inputs. |
| Unresolved proposal or conflict | Expanded in `Review` | Blocks only when the application projection marks it blocking | Apply/reject the exact proposal or edit the authoritative input. |

Automatic population is not implied by moving between stages. Existing stored
facts appear immediately; a registered acquisition/reconciliation operation may
propose additional facts; only application-approved adoption changes the
profile. Free text and prior filings remain evidence or observations unless an
application contract explicitly maps them to typed profile facts. Every shown
fact carries source/provenance or an explicit unknown-source state.

| Source class | Trigger | Profile effect | Required disclosure and consent |
|---|---|---|---|
| Existing stored profile fact | Opening or refreshing the profile surface | Display only; it is already authoritative profile state | Show recorded source, validity, and last update; no new consent. |
| Manual edit | Explicit `Edit` and `Save` | Writes through the application profile authority | Label as manual and show validation before save. |
| AEAT census acquisition | Explicit action in `Get data` | Produces a review proposal; no profile write before accepted apply | Show source, requested scope, fields available, and authentication need before start; apply/reject exact reviewed values. |
| Certificate identity suggestion | Authentication context only | Suggestion, never an adopted profile fact | Label as certificate-derived; user must explicitly choose it where the application permits. |
| Previous-filing history | Explicit operation in `Get data` | Stores observations/reconciliation evidence, not profile facts unless a separate typed mapper is accepted | State that it does not automatically complete profile fields; show operation outcome and provenance. |
| Free text or reconciled document text | Explicit import/reconciliation action | Evidence only unless a registered application mapper emits a typed proposal | Preserve verbatim provenance and state that no legal meaning was inferred. |
| Future registered source | Explicit operator action by default | Proposal or evidence according to its application contract | Background acquisition is prohibited unless a later ADR names trigger, scope, notice, cancellation, and adoption policy. |

There is no background sensor sweep in this decision. A source operation may
refresh already source-owned values under its application policy, but it still
shows a review outcome; manual/operator-owned values and clears are never
silently overwritten. Advancing stages, changing locale, opening a tab, or
reaching `Ready` triggers no acquisition.

Profile sync is an application operation. Application constructs the proposal
and alone owns adoption, divergence, clearing, safety, baseline validation, and
persistence. `sync_review` renders provenance, current/proposed values,
conflicts, and typed decisions inside the generic operation modal. It cannot
acquire, reconcile, persist, or classify safety.

Profile does not import operations. Its facade publishes a `SyncReviewFactory`
protocol whose input is a profile-owned immutable review projection and whose
output is a component-owned renderable. The integration `app` adapts and
registers that factory through the public operation interaction registry;
neither feature imports the other. Decisions return to the
supervisor for the exact pending interaction and reviewed proposal.

### D7 - Secret surfaces and ephemeral submission

Secret owns masked entry, confirmation, strength display, authentication-time
profile choice, login, registration, password change, and bounded collection of
operator-supplied recovery material. Generated recovery material is never
displayed.

Durable state may hold only a safe secret-requirement descriptor. Before secret
surfaces move beyond presentation, the operation authority must define and own
the public submission capability, exact operation/interaction binding, expiry,
single-use consumption, duplicate/mismatch refusal, cancellation, cleanup, and
restart behavior. Whether this is a secure specialization of `respond` or a
separate port is deliberately not decided here.

Values and reversible derivatives are excluded from flow answers, form models,
envelopes, journals, receipts, events, snapshots, logs, traces, checkpoints,
replay, retained UI history, exceptions, telemetry, and clipboard actions.
Expiry, duplicate, mismatch, or missing consumer refuses without echo. The
contract promises bounded custody, not impossible runtime-wide erasure.

### D8 - Operation modal, logs, and ErrorEnvelope

The operation ADR owns modal/controller behavior, cursor/replay, cancellation,
interaction, spinner/progress, settlement, and reconnect. The shell mounts it
and preserves observation; TUI never creates operation state.

The live-log component accepts only a component-owned immutable
`SafeLogViewRecord`. The operation projection maps already-redacted application
events into that visual record. The component owns bounded rendering, severity,
follow/pause, wrapping, focus, and empty state, never application event types,
raw records, exceptions, streams, cursors, or arbitrary payloads.

The error component accepts only canonical safe `ErrorEnvelope` and renders
code, category, localized message, typed action, retryability, runbook, safe
context, and trace identity. It does not reclassify or accept raw exceptions.
Notices remain separate; healthy idle is silent and actionable errors pinned.
The operation/backend lane must resolve safe refusal and diagnostic references
into that envelope through a public frontend-neutral projection. Components do
not dereference diagnostics, access observability storage, or build envelopes
from raw exceptions.

### D9 - Interface contribution to the roll-up migration ledger

The roll-up plan's generated fixed-point ledger records each legacy module,
symbol or reference, consumer, consumer kind, exact locator, owner,
destination/retirement, atomic slice, deletion proof, verification, and state.
Row identity supports both imports and non-import references; module/symbol are
nullable where a configuration, documentation, registration, or dynamic-string
reference has no imported symbol. The interface lane supplies dispositions and
parity proof only for rows assigned to it.

| Current module | Canonical disposition |
|---|---|
| `__init__.py` | Delete after consumers move; no compatibility facade. |
| `_app.py` | Flow projection to `flows`; shell mechanics to `app`/components. |
| `_confirm_screen.py` | Generic dialog to components; restart policy to flows. |
| `_credential_screen.py` | Masked presentation to secret; policy stays application-owned. |
| `_field_edit_screen.py` | Profile editing to profile; generic mechanics to components. |
| `_form_screen.py` | Visual contracts/widgets to components; delete presenter bridge. |
| `_login_screen.py` | Presentation to secret; auth remains application-owned. |
| `_manager_screen.py` | Profile presentation to profile; operation execution joins sibling lane. |
| `_question_screen.py` | Relocate to flows. |
| `_registration_screen.py` | Relocate to secret; policy remains application-owned. |
| `_review_screen.py` | Relocate to flows. |
| `_select.py` | Retire after integration replaces its consumers with the dedicated installed boundary or renderer-neutral application selection. |
| `_status_bar.py` | Relocate to components. |
| `_status_screen.py` | Presentation to profile; data authority stays outside TUI. |
| `_theme.py` | Theme/notice mechanics split into components. |

The ledger includes every production importer, CLI/TUI/backend test, manager
pilot, development surface/replay/screenshot tool, facade baseline, annotation,
documentation reference, dynamic string, and registration. AST discovery is
cross-checked with `rg`; counts/allowlists are non-authoritative. Each identity
joins one row and no new legacy identity enters after baseline.

Each relocation is a consumer-complete integration slice: new definition and
facade, every affected production/test/development consumer, and deletion of
the old definition land together. Interface owners supply the presentation
change, but the roll-up integration lane owns the atomic slice. Completion
requires zero old TUI files/references, zero Textual/TUI types outside the new
root, zero outside Python imports of the TUI, no top-level TUI/bootstrap, no TUI
core/shared, no physical Modelo placeholder, no compatibility authority, and
clean structural gates.

### D10 - Real-behavior acceptance and extension proof

Tests use production imports and real behavior, never fakes, mocks, stubs,
patches, monkeypatches, skips, xfails, or mirrored business logic.

Proof includes identical installed-command and `__main__` launch; no Python
imports of the TUI from CLI/MCP/backend and no TUI-to-CLI/MCP edge;
real Textual pilots for profile, login, registration, status, forms, flows, and
operations; real application flow semantics; real profile reconciliation via
the supervisor; operation success/refusal/failure/prompt/cancel/detach/reconnect;
secret canary absence from every durable/diagnostic surface; real log
follow/pause/replay; lossless canonical error rendering; `80x24`, `120x36`, and
`160x48` terminal sizes in English, Spanish, Catalan, and Hungarian, in both
light and dark themes; relocated devtools; clean
collection and focused structural/behavioral gates.

Extension proof connects profile-bundle export after profile sync through
public facades, generic operations, and ephemeral secret submission without
changing components, operation lifecycle, or sibling-private modules and
without adding another modal, log view, error classifier, or secret path.

The roll-up plan must add interface-owned implementation and real-behavior rows
for the five stages, both classification and source tables, provenance display,
collapsible state, keyboard traversal, and the no-background-acquisition rule.
Terminal-size verification alone does not prove this information architecture.

The join gate verifies both ADRs publish the identical root, tree, components
seam, operation subtree, runtime construction boundary, dedicated launch edge,
and exact path ownership before interface execution begins.

## Rationale

`cadrumo.entrypoints.tui` alone matches the repository's physical home for
process-facing transports. It is sibling to CLI/MCP, not an artefact adapter or
backend service (`2026-08-11-tui-interface-research`,
`2026-06-01-domain-boundary-audit-adr`).

Ownership areas make lateral dependencies visible while retaining a bounded
visual vocabulary. `components` avoids collision with innermost `cadrumo.core`
and the unbounded meaning of `shared`.

The dedicated launcher follows the accepted topology and prevents one
entrypoint from importing another. Keeping operation state,
reconciliation, flow semantics, redaction, and error classification outside
presentation prevents a second application layer. Decision-only Modelo
reservation avoids manufacturing an API.

## Consequences

- TUI gains one home at `cadrumo.entrypoints.tui`, sibling to unchanged CLI/MCP.
- The old inbound TUI adapter disappears without a facade.
- This interface lane does not edit or restructure CLI; roll-up integration
  removes legacy TUI consumers under the accepted dedicated-launch contract.
- In the target topology TUI, CLI, and MCP do not import one another; the bounded
  transitional imports above remain migration debt until replaced.
- Existing callable profile and workflow screens may truthfully declare `AVAILABLE`
  while they remain in the inbound TUI location. This transitional availability
  neither narrows nor completes the accepted dedicated TUI migration.
- `components` is the sole reusable TUI-local seam; no TUI core/shared exists.
- No top-level bootstrap package is introduced.
- Profile sync gains review without reconciliation/persistence authority.
- Secret presentation is specified, but implementation is blocked until the
  operation authority owns the `EphemeralSecretSubmission` facade and its
  conformance tests; the interface receipt makes that dependency executable.
- Logs/errors become reusable views while redaction/replay/classification stay
  upstream.
- Generic flows retain application semantics.
- Modelo names are reserved without physical placeholders.
- Dependency migration remains consumer-complete. The interface plan starts
  after both prerequisite campaigns, records their ordered commit receipts,
  and does not duplicate their steps. An architecture close that lacks the
  canonical Modelo migration or secret capability is not a valid receipt.
- Cross-ADR conformance prevents conflicting roots, components, launch contracts,
  runtime construction, or operation trees.
