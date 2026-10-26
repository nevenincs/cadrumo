---
tags:
  - '#research'
  - '#tui-interface'
date: '2026-08-11'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:4b271f5e48d604a886543587e3f3ccdfb66836c282032e783b27fbd7e8aa83e6'
related:
  - "[[2026-08-11-profile-setup-flow-critical-baseline-research]]"
  - "[[2026-08-11-tui-architecture-research]]"
  - "[[2026-08-11-censal-sync-control-architecture-research]]"
  - "[[2026-07-23-tui-wizard-substrate-adr]]"
  - "[[2026-07-23-profile-setup-flow-adr]]"
  - "[[2026-07-24-profile-bundle-tui-adr]]"
  - '[[2026-06-01-domain-boundary-audit-adr]]'
  - '[[2026-08-10-casilla-schema-research]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
---

# `tui-interface` research: `Canonical modular Textual package and flat-module migration`

The current Textual frontend spreads reusable behavior across fifteen modules
in one inbound-adapter package. Its facade mixes widgets, screens, data transfer
objects, runners, and frontend selection. CLI modules then construct those
TUI-specific types. The accepted topology places the replacement at
`cadrumo.entrypoints.tui` and divides it into interface, operation, and
integration lanes. Within that constraint, the evidence favors task-led profile
navigation, a presentation-only `components` seam, explicit source review, and
separate secret surfaces. Application services must retain reconciliation,
redaction, error classification, and operation lifecycle authority.

The governing architecture artifacts contain unresolved contradictions. Their
tree and lane clauses disagree on root-file ownership, while their roll-up omits
contracts required by secret custody and the new profile information
architecture. The accepted operation ADR also retains an unmet sentence-level
precondition to its own acceptance. This research records those conflicts for
the governing authorities to resolve; it does not authorize scaffolding or
prescribe the later interface schedule.

## Findings

### The flat package contains four natural ownership clusters that its facade erases

The modules already separate into flow rendering, profile management,
secret/session interaction, and reusable presentation. Login and registration
subclass the credential base, while manager, credentials, forms, status, and
flows consume the same theme and status primitives.

The facade exports more than fifty names across those clusters, and production
CLI modules import them to build manager actions, login choices, status
projections, forms, and wizard frontends.

Grouping only by Textual kind (`apps`, `screens`, `widgets`) would leave
capability ownership implicit. Ownership-oriented areas make the existing
clusters and their dependency directions mechanically visible.

### The accepted operation architecture fixes the root and divides ownership

The accepted `tui-architecture` ADR makes
`src/cadrumo/entrypoints/tui/` the canonical outermost Textual root and divides
it into `INTERFACE`, `OPERATIONS`, `JOIN`, and `RESERVED` rows. It assigns the
shell, components, profile, secret, flows, devtools, and presentation tests to
this concern; the operation projection to its own concern; and root composition
to one serialized integration lane. It also requires one roll-up implementation
plan and deletion of the old adapter package without a compatibility facade.
`.vault/adr/2026-08-11-tui-architecture-adr.md:106`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:432`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:603`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:637`.

The two campaigns initially used `shared/` and `core/` for the visual seam.
Both names are misleading beside the innermost `cadrumo.core`: one is vague and
the other collides conceptually with the kernel layer. The evidence and
cross-campaign review favor the converged `components/` name. Both ADRs must
publish that identical join tree before overlapping code is scaffolded.

### Reusable components are viable only as a visual and interaction-mechanics layer

`_theme.py` supplies domain-neutral themes, constrained scrolling,
content-sized tables, notices, and appearance control; `_status_bar.py` is a
reusable pinned channel that redacts before updating widget state.

`ConfirmScreen` is generic, while `confirm_restart_dialog` carries flow policy.

Forms expose the hard split. Immutable field/page models and edit widgets are
domain-neutral, but the `ContextVar` presenter lets CLI-owned orchestration
open Textual screens from manager workers.

Putting the whole module in components canonizes orchestration; duplicating
forms per feature canonizes drift. The evidence favors component-owned visual form contracts,
operation-owned interaction transport, and feature-owned validation and
projection. The ADR must define their public contracts and retire the presenter
bridge.

### Profile is a task surface over application projections

The manager renders `ProfileOverview` but also owns workers, callback execution,
progress settlement, fallback errors, embedded-form presentation, and session
close behavior. `ManagerAction` is an arbitrary callable and
`ManagerActionOutcome` is a TUI-owned execution result.

The accepted operation lane replaces that authority with application
operations and immutable projections; `profile/` can own navigation, overview,
field editing, status, readiness, and profile-specific review without owning
execution. `.vault/adr/2026-08-11-tui-architecture-adr.md:605`.

The package move must not preserve the current information-architecture defect.
The related baseline records 26 sections and 152 fields rendered as one expanded
inventory, with provenance and applicability absent from the row projection;
task-led progressive disclosure is the relevant alternative to a larger table
or another long wizard.
`.vault/research/2026-08-11-profile-setup-flow-critical-baseline-research.md:18`,
`.vault/research/2026-08-11-profile-setup-flow-critical-baseline-research.md:42`,
`.vault/research/2026-08-11-profile-setup-flow-critical-baseline-research.md:74`.

### Requiredness and applicability already have three distinct authorities

The schema declares only a static `required` boolean, defaulting to false. It
also carries selectors and schedule predicates, but no advisory or importance
tier. the former source file.

Application completeness adds cross-field conditional requirements for Clave,
IRNR residence and representation, and repeatable attribution rows. A separate
`iva_regime_required` rule supplies IVA conditionality to profile validation.
Those rules evaluate known profile facts; they do not expose a generic
`unassessed applicability` state.

Modelo preflight adds a third context: it selects schema-required fields whose
selectors match one filing and appends conditional requirements. Its own
`per_operation_requirements_assessed` flag distinguishes an empty assessment
from a clean result. the former source file,

The interface therefore cannot infer applicability from the schema or locale.
Any future unassessed state needs an application projection that distinguishes
static requiredness, evaluated conditional rules, and filing-specific preflight.
The ADR must define only how those supplied states appear and affect navigation.

### Profile sync needs a specific review projection over a generic operation modal

The current TUI censal action acquires and applies, while the CLI previews unless
explicitly told to apply. Application reconciliation already distinguishes
adoption, divergence, and clearing and delegates the write through its authority.
`.vault/research/2026-08-11-censal-sync-control-architecture-research.md:25`,
`.vault/research/2026-08-11-censal-sync-control-architecture-research.md:40`,

A dedicated sync application would duplicate navigation and lifecycle; a
generic modal alone may not express side-by-side field adjudication. The
evidence favors a thin profile renderer for an application-produced proposal,
mounted through the operation surface. It may show provenance, current and
proposed values, conflicts, and typed decisions; it may not fetch, reconcile,
persist, or decide safety.

### Secret collection requires an ephemeral command path

The current login presenter selects the full-screen page only for an interactive
host without stdin, environment, or JSON secret channels. The page chooses a
profile and collects a value in a masked field. Its injected CLI authentication
seam supplies that plaintext value to the public `login_profile` application
door. Non-screen routes retain their existing custody channels.

Registration also uses masked inputs. It copies the submitted password into a
bounded byte buffer and overwrites that buffer in `finally` after the
application callback returns. This limits one controlled copy without claiming
runtime-wide erasure. the former source file,

The accepted profile-bundle decision separately forbids passphrases in generic
flow answers and retains a hidden secret-input channel.
`.vault/adr/2026-07-24-profile-bundle-tui-adr.md:24`,
`.vault/adr/2026-07-24-profile-bundle-tui-adr.md:35`.

Treating login, registration, and password change as ordinary durable operation
responses would enlarge the current custody boundary. The evidence supports a
`secret/` presentation area for masked collection, profile choice,
confirmation, strength display, and password change. The backend authority must
still decide the non-persisted submission contract. Policy, storage, and refusal
classification remain application concerns, and generated recovery material
remains prohibited from the TUI.

### Generic flows remain a thin renderer over the accepted engine

The accepted wizard ADR places branching, validation, checkpoints, and submit
semantics in one renderer-neutral application engine.
`.vault/adr/2026-07-23-tui-wizard-substrate-adr.md:78`,
`.vault/adr/2026-07-23-tui-wizard-substrate-adr.md:120`,
`.vault/adr/2026-07-23-tui-wizard-substrate-adr.md:266`.
The current app, question, and review modules already consume its projections,
so relocation to `flows/` can preserve that direction.

Frontend selection remains unresolved because the new boundary forbids CLI
imports of the TUI; moving `select_flow_frontend` unchanged would retain the
reverse edge.

### Live logs and error envelopes are projections of already-safe contracts

The status widget defensively redacts before holding a message, while the
canonical error builder scrubs context and produces a frozen `ErrorEnvelope`
with code, category, localized message, typed action, retryability, runbook,
safe context, and trace ID.

The current manager reduces unexpected failures to a sentence and loses that
structure. the former source file.

A reusable live-log view can own bounded rendering, severity styling,
follow/pause, and accessible empty state, but must accept only typed,
already-redacted records. Subscription, cursor, retention, and operation
identity remain in `operations/`. An error view can render the canonical safe
fields and typed action, but must not accept raw exceptions or reclassify them.
Notices remain distinct from blocking errors.
`src/cadrumo/core/json_contract.py:237`,

### Modelo presentation depends on the in-flight canonical casilla schema

The accepted `casilla-schema` read-model ADR exists because every current
surface re-derives schema, values, findings, readiness, and blockers. It places
one frozen `ModeloWorkReview` and its producer in `application.modelo`, so CLI
and TUI can consume the same truth.
`.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:15`,
`.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:44`.

That campaign is still in flight. Its plan currently reports 1 of 41 steps
closed. W03 builds the read model, while W04 builds a review screen at the
legacy TUI path. The later TUI architecture campaign must account for that
surface in its canonical migration before this interface campaign builds on it.
`.vault/plan/2026-08-10-casilla-schema-plan.md:94`,
`.vault/plan/2026-08-10-casilla-schema-plan.md:115`,
`.vault/plan/2026-08-10-casilla-schema-plan.md:129`.

The evidence supports reserving `cadrumo.entrypoints.tui.modelo.view` as the
eventual presentation owner without creating it early. `modelo.edit` needs a
separate write-side decision because the casilla read model is deliberately
read-only. `.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:58`.

### Migration is roll-up work, not a second interface campaign

The repository forbids compatibility bridges, and the upstream proposal
requires deletion of the old adapter package and zero backend or CLI imports of
the new TUI. `.codex/rules/no-legacy-compatibility.md:12`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:485`.
The accepted roll-up plan already owns the checked migration manifest, reverse
consumer changes, packaging cutover, and legacy deletion. The interface concern
supplies destinations and behavior-parity criteria for its owned rows; it must
not create a second migration plan or edit CLI consumers independently.
Completion still cannot leave flat private modules, reverse imports, dynamic
loading bypasses, or a compatibility facade.

### The accepted roll-up exposes unresolved integration risks

The architecture ADR assigns root files to different lanes in D10 and D12, and
the roll-up places the root facade in the earlier interface wave. The same plan
relocates production definitions before later consumer migration and legacy
deletion. Under the repository's no-compatibility rule, that ordering exposes
either parallel authorities or broken imports between waves.
`.vault/adr/2026-08-11-tui-architecture-adr.md:484`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:603`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:129`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:138`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:183`.

The roll-up also lacks named contracts for ephemeral secret submission, safe
diagnostic projection, and public journal reuse. Its filed-history row shares
`profile/sync_review.py` with census review even though the application owners
differ, and its passphrase row names `application.auth` while the current public
custody API sits under `application.user_profile`.
`.vault/plan/2026-08-11-tui-architecture-plan.md:68`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:80`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:113`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:170`,
`src/cadrumo/application/user_profile/__init__.py:41`.

These are evidence-backed join conflicts, not interface scheduling decisions.
The proposed ADR can state the presentation contract and its acceptance
dependencies. The topology authority and its existing roll-up remain the only
places that can adjudicate ownership and execution order.

### TUI and CLI are sibling entrypoints, not a parent-child pair

The package intent resolves the placement question. `cadrumo.entrypoints`
explicitly owns user-facing transports, process-level translation,
presentation, parsing, exit mapping, and terminal error contracts; its concrete
transports are child packages. `cadrumo.adapters.inbound` instead owns external
artefact import and normalization. `src/cadrumo/entrypoints/__init__.py:1`,
`src/cadrumo/adapters/inbound/__init__.py:1`.

The accepted layer direction places both adapters and entrypoints at the outer
edge and forbids adapters from importing entrypoints. The executable import
contract orders `entrypoints > adapters > application > domain > core`. A
holistic interactive application with its own composition root therefore fits
`cadrumo.entrypoints.tui`, sibling to the existing canonical
`cadrumo.entrypoints.cli` and `cadrumo.entrypoints.mcp`, better than either a
submodule of CLI or an artefact-ingestion adapter.
`.vault/adr/2026-06-01-domain-boundary-audit-adr.md:73`, `.importlinter:283`.

Packaging targets the existing canonical `cadrumo.entrypoints.cli:main`, and
accepted CLI decisions require that boundary to remain a thin transport with no
business logic, schema conversion, validation policy, orchestration,
persistence, provider behavior, or compatibility shims. `pyproject.toml:125`,
`.vault/adr/2026-05-12-cli-workflow-redesign-inventory-placement-adr.md:18`.
TUI is not nested beneath CLI and does not import it. The accepted operation ADR
has now adjudicated launch shape: packaging invokes
`cadrumo.entrypoints.tui.launcher:main` directly, and no Python module outside
the TUI imports the TUI package. The roll-up plan owns amendment of the older
frontend-selection clauses and removal of legacy TUI construction from CLI
consumers. That work is integration migration, not a CLI package migration and
not part of the interface lane.
`.vault/adr/2026-08-11-tui-architecture-adr.md:547`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:560`.

### Investigation boundaries

This research inspected current production modules and importers, related
profile and sync grounding, canonical error/redaction contracts, and governing
wizard/profile/CLI decisions. It did not modify the parallel operation artifacts,
run a live AEAT operation, test a human terminal, prototype the tree, or
implement Modelo view/edit. The operation roll-up remains the dependency-
migration schedule. This research does not assess readiness or sequence a later
interface plan; the governing ADRs own the dependencies. One unresolved lifecycle
defect remains in that upstream record: its accepted status conflicts with its
later statement that a census-policy reconciliation is still required before
acceptance. The governing authority needs to resolve that contradiction before
census implementation can rely on it.

## Sources

- `.vault/adr/2026-08-11-tui-architecture-adr.md:106`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:116`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:398`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:432`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:547`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:560`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:603`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:605`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:637`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:68`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:80`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:113`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:129`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:138`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:170`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:183`
- `.vault/research/2026-08-11-profile-setup-flow-critical-baseline-research.md:18`
- `.vault/research/2026-08-11-profile-setup-flow-critical-baseline-research.md:42`
- `.vault/research/2026-08-11-profile-setup-flow-critical-baseline-research.md:74`
- `.vault/research/2026-08-11-censal-sync-control-architecture-research.md:25`
- `.vault/research/2026-08-11-censal-sync-control-architecture-research.md:40`
- `.vault/adr/2026-07-23-tui-wizard-substrate-adr.md:78`
- `.vault/adr/2026-07-23-tui-wizard-substrate-adr.md:120`
- `.vault/adr/2026-07-23-tui-wizard-substrate-adr.md:266`
- `.vault/adr/2026-07-24-profile-bundle-tui-adr.md:24`
- `.vault/adr/2026-07-24-profile-bundle-tui-adr.md:35`
- `.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:15`
- `.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:44`
- `.vault/adr/2026-08-10-casilla-schema-read-model-adr.md:58`
- `.vault/plan/2026-08-10-casilla-schema-plan.md:94`
- `.vault/plan/2026-08-10-casilla-schema-plan.md:115`
- `.vault/plan/2026-08-10-casilla-schema-plan.md:129`

- `src/cadrumo/application/user_profile/__init__.py:41`

- `src/cadrumo/core/json_contract.py:237`

- `src/cadrumo/entrypoints/__init__.py:1`
- `src/cadrumo/adapters/inbound/__init__.py:1`
- `.vault/adr/2026-06-01-domain-boundary-audit-adr.md:73`
- `.importlinter:283`
- `pyproject.toml:125`
- `.vault/adr/2026-05-12-cli-workflow-redesign-inventory-placement-adr.md:18`
- `.codex/rules/no-legacy-compatibility.md:12`
