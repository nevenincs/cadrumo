---
tags:
  - '#reference'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:9b784034d5247d4ae033147f0870f42519470ac0566d29b8d2eb934770c4f839'
related:
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
---

# `tuimodelo` reference: `modelo declaration TUI capability inventory`

Grounding for the modelo declaration TUI campaign: what the backend can do, what each
frontend reaches, and where the joins are missing. Sources are the live command graph,
the validated registry authority, the application and domain trees, the Textual
entrypoint tree, and the accepted decision corpus. Counts were measured against the
working tree, not quoted from prior documents.

## Summary

The modelo declaration surfaces are **largely built and structurally unreachable**. The
campaign's centre of gravity is joining existing capability, not authoring new screens.
Three independent measurements agree.

| Measure | Value |
| --- | --- |
| CLI command graph | 370 nodes, 299 leaves |
| `app modelo` leaves | 79 |
| `app modelo` leaves with a TUI route | 2 |
| Registered operations | 20 |
| Registered operations reachable from the TUI | 2 |
| Modelo workspace destination screens built | 6 |
| Those reachable by an operator | 1 (overview only) |
| Modelo action request builders built | 6 (7 views) |
| Those with a production caller | 0 |

The two TUI-routed commands are `app_modelo_work_review` and `app_modelo_work_select`.
The enrolled set is pinned by assertion in
`src/cadrumo/entrypoints/cli/tests/test_global_tui_request.py:70`, so it is an enforced
contract rather than drift. `TuiCapability` is declared at
`src/cadrumo/entrypoints/cli/command_spec.py:725` and defaults to `NOT_IMPLEMENTED` at
`:780`.

## Registry and schema authority

`bundled_authority()` at
`src/cadrumo/domain/calculations/registry/authority.py:1000` returns the
`ValidatedRegistryAuthority` defined at `:434`. Snapshot selection is
`snapshot(modelo, *, filing_year, period, on=None, revision_id=None, grade=FILING)` at
`:676`; `select_revision` at
`src/cadrumo/domain/calculations/registry/temporal.py:119` is the sole resolver and
fails closed in both directions. There is no territory axis; jurisdiction is pinned to a
single literal.

Measured population: 58 modelos, 128 revisions, 29,678 casillas, 1,457 formulas, 9,230
bindings, 121 relations, 516 parameters. Authority grades divide as 69 filing, 54
applicability, 5 calculation. The modelo enum carries 149 members, so 91 have no registry
definition at all and refuse work creation.

`CasillaDefinition` is defined at
`src/cadrumo/domain/calculations/registry/schema_surfaces.py:261` with 22 fields, and
`CasillaConstraints` at `:164` carries `violates()` and `violates_text()`. Labels and
help resolve through `get_label(locale)` at `:346` and `get_help(locale)` at `:350`.
`CasillaGroundingReport` at
`src/cadrumo/domain/calculations/registry/query_reports.py:124` already exposes label,
help text, section, data type, input kind and required together, and is the cheapest
starting point for a projection.

### What the schema does not carry

The registry has no display order, no page, row or column, and no section labels. There
are 1,448 distinct snake_case section tokens with no catalogue entries; modelo 200 alone
declares 618 sections, many bare-numeric. Metadata density is low: constraints on 909 of
29,678 casillas, Spanish help on 11.5 per cent, `form_number` on 0.46 per cent, aliases
on none. There are no widget hints, no precision, no currency, no per-casilla
conditionality and no defaults. Widget selection must therefore be inferred from the
19-member data-type enum at
`src/cadrumo/domain/calculations/registry/schema_base.py:645`, the 5-member input-kind
enum at `schema_input_kind.py:15`, and whatever constraints exist.

Two live defects affect any generated surface. `src/cadrumo/application/modelo/workspace.py:1153`
resolves only the occurrence key and bypasses the continuity tier in `localization_keys`,
degrading 885 of 1,203 modelo 303 labels and 1,068 of 1,450 modelo 390 labels to bare
casilla identifiers. Separately, 26 per cent of English labels are silently the Spanish
string, rising to 43 per cent for modelo 303 in 2025, and the API exposes no fallback
signal.

Never read authored export layouts off a revision directly: binding-derived fields
materialise only at snapshot build, and the mistake produces false data-loss findings
(`src/cadrumo/domain/calculations/registry/schema.py:753`).

## Calculation, bindings and overrides

There is one calculation entry point and no second path:
`calculate_modelo_work_revision` at
`src/cadrumo/application/modelo/calculate_input.py:312`, delegating to
`src/cadrumo/application/modelo/calculation_actions.py:1282` and then to
`calculate_registry_snapshot` at
`src/cadrumo/domain/calculations/registry/formula_runtime.py:318`. The module named
`calculation.py` computes nothing; it handles capture and currentness only.

Observations carry value, formula identity, operands, at least one legal reference, at
least one source reference, and an `absent_by_design` marker
(`src/cadrumo/domain/calculations/registry/bindings.py:257`). The derived flat value view
is Decimal-only, so text-family casillas disappear from it.

Overrides run on two independent axes. The disposition ladder at
`src/cadrumo/application/aggregation/_source_mesh.py:359` marks 12 sources LOCK — all ledger
aggregations, invoices, modelo 347, modelo 303 régimen simplificado, and inventory —
where an operator override is refused outright by
`calculation_actions.py:1772`. Four sources are CARRY, where the override wins. The
overlay order is profile, then backend mesh, then borrador, then caller. When an operator
value displaces a computed one, `collect_operator_override_divergence_diagnostics` at
`src/cadrumo/application/modelo/_operator_override_advisory.py:48` is the only disclosure
that it happened. Editor writability must derive from the same lock set the engine uses
(`src/cadrumo/application/modelo/edit_services.py:160`).

There are 38 machine-verified diagnostic reasons on
`src/cadrumo/application/aggregation/_source_mesh.py:524`, of which 36 are not persisted onto
the revision. A surface that reads a stored revision loses them; they must be captured at
calculation time. The CLI structured calculate result carries none at all.

## Filing lifecycle

The authoritative track is `WorkUnit` (`src/cadrumo/domain/modelos/work_unit.py:121`) to
`CalculationRevision` (`src/cadrumo/domain/modelos/calculation_revision.py:595`) to
`VerificationReport` (`verification_report.py:235`) to `ModeloRecord`
(`filing_record.py:158`). A work unit is a content-addressed handle, so renaming does not
change its identity. `application/filing/history_models.py` has no production
writer and an untyped status field, which makes it a trap for an implementer searching by
name, but it is not dead: `history_repository.py` imports it and the custody-carry resolver
at `src/cadrumo/adapters/persistence/storage/_profile_custody_carry.py:207` reaches it from
production. It is correspondingly absent from the unreachable-module ratchet. Retiring it
would require a stored-data custody migration. Use `CURRENT_SEALED_REVISION_STATES`
(`calculation_revision.py:118`) for status display so a superseded revision never renders
as current.

Amendment kinds are declared at
`src/cadrumo/domain/modelos/calculation_revision_amendment.py:17`: complementaria under
LGT 122.2, sustitutiva under 122.1, and rectificativa under 120.4 with a per-modelo
effective date. A pre-rectificativa complementaria that lowers liability is refused by
the period-aware gate at
`src/cadrumo/application/modelo/_amendment_kind_resolution.py:58`.

Filing never means live submission. `AeatAccessGate.require_live_write()` at
`src/cadrumo/core/access_gate/gate.py:133` unconditionally raises, every capture model is
read-mode, and no submitter transport exists. The product produces a fichero which the
operator uploads at the Sede themselves, after which the local record is marked filed and
a justificante may be observed.

Status is two independent axes by governed decision: a local filing state and an AEAT
submission state, held apart by four validators so that a local "filed" never implies
AEAT received it. Obligation status supplies upcoming, due-soon, due-today, overdue,
filed and not-applicable. There is no domain concept corresponding to "projected".
"Missed" exists only on calendar rows, not on the record, so a history surface must join
two projections by natural address.

`OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER` at
`src/cadrumo/application/calculations/cross_period_models.py:102` maps all 21 blockers to an
operator-action axis with an import-time totality check, and is a ready-made
"what to do next" projection.

Discard is terminal: `DESCARTADO` has no undo and re-creation is refused; the source
comment explaining recovery is truncated mid-sentence at
`src/cadrumo/application/modelo/work_lifecycle.py:360`.

## Reconciliation and verification

There are four distinct comparison surfaces, not one, and they differ in result type,
severity and persistence: revision against an operator document, revision against pulled
justificante bytes, revision against an AEAT-pulled filing, and the modelo 303 to modelo
349 intracommunity check. The service lives at
`src/cadrumo/application/modelo/reconciliation.py`; the exception classes alone live under
`src/cadrumo/domain/filing/reconciliation/errors.py:13`.

`ModeloReconciliationReport` at `reconciliation.py:225` yields a binary verdict derived
purely as match-if-no-diffs. Diffs carry field name, both values, kind, a three-member
diff kind, and grounding references, with a validator refusing ungrounded value diffs.
Advisories carry three constructed codes with no severity field, no resolution action, and an English
prose message rather than a locale key.

Verification exposes 30 verify-time gates plus 9 raising gates; registry predicates
divide as 103 advisory and 78 blocking. The frontend contract is the invariant at
`src/cadrumo/application/modelo/verification_preconditions.py:29`: blocking findings carry a
typed precondition failure with a recovery action, warnings carry none.

## Edit contract

`open_modelo_edit_session` at
`src/cadrumo/application/modelo/edit_session.py:554` is the intended frontend API: 15
methods over one opaque handle, with no contract record crossing the boundary. Concurrency
is optimistic compare-and-swap on four coordinates within a fifteen-minute window,
checked at preflight and again immediately before effect, never rebasing.

`project_modelo_edit_mutation_capability` in
`src/cadrumo/application/modelo/_edit_facade.py` is the designated admission seam. Every
row is deliberately `UNMEASURED` in this version. Its `reconsideration_condition` at
`:71` still cites a dependency receipt that an accepted decision retired, and is stale
text requiring correction.

## Export and destinations

There is no destination abstraction: no port, no target enum, no registry. Every verb
hardcodes one transport. The name `destination` is already taken inside the TUI for
screen routing (`src/cadrumo/entrypoints/tui/destination_session.py`), which is a naming
hazard for any new vocabulary.

The sole byte producer for fixed-width output is
`src/cadrumo/domain/calculations/registry/fixed_width_codec.py:300`, consumed through
`src/cadrumo/application/filing/export.py:419`. Layout coverage is 94 layouts across 47
of 58 modelos: 88 fixed-width and 6 XML-dictionary, the latter for modelo 100 only, which
therefore has no offsets. Eleven modelos have no layout. Coverage is per revision, so
several modelos carry bare revisions. Completeness manifests exist for 34 modelos, so
other exports report completeness as unverified. No golden byte fixtures exist on disk and
the canonical live proof roster is empty.

An offline workbook exporter is fully built and styled at
`src/cadrumo/application/storage/calc_sheets/workbook_export.py:363` with zero production
callers. The preview seam already exists: `export_draft` overloads on destination, with a
payload-consumer arm currently used only by export proof.

Two defects matter for parity. The TUI-permitted export operation drops the refund,
payment, prior-domiciliation and product-identity elections that the CLI threads
(`src/cadrumo/application/modelo/operation_definitions.py:774`), so the two surfaces can
emit different modelo 303 declaration types. An existing output file is silently
overwritten, and the output-path docstring contradicts its own validator.

Google export is capability-gated and configured through the config command family.
Interactive login refuses a non-terminal host at
`src/cadrumo/adapters/outbound/google/oauth_flow.py:60` and blocks a loopback receiver for
up to 300 seconds, so any full-screen surface must delegate login to a child process.
Folder selection accepts a bare identifier with no existence check although a folder
listing helper already exists unused.

## Frontend substrate

There is no service locator. The sole composition root is
`src/cadrumo/entrypoints/tui/launcher.py:962`, which binds application ports through
`src/cadrumo/entrypoints/adapter_composition.py:24`, composes the operation graph once per
authenticated session at `launcher.py:755`, and captures one immutable generation of
projections at `launcher.py:87`. Screens receive services by closure binding at
composition time, with actions and submitters passed in pairs so a control cannot render
as wired while refusing. Only three attributes may be read off the running application
(`src/cadrumo/entrypoints/tui/app.py:104`).

A workspace follows a seven-part recipe, fully extracted in the ledger package: a closed
destination literal, a route table with an import-time totality check
(`src/cadrumo/entrypoints/tui/ledger/routes.py:83`), a controller refusing foreign
destinations and wrong contract versions (`ledger/controller.py:139`), frozen view models
holding no presentation strings, an injection dataclass validating in post-init
(`ledger/workspace_injection.py:31`), a table of action guards
(`ledger/action_guards.py:23`), and a presentation seam. Long-running work should follow
the sync package instead, which hands mutations to the host operation modal rather than
submitting inline.

Modelo is not a shell destination. The shell alias has five members
(`src/cadrumo/entrypoints/tui/navigation.py:28`) and modelo is injected as a sub-workspace
of declarations (`launcher.py:574`), with modelo search results already emitted under the
declarations admission (`src/cadrumo/application/search/installed_workbench.py:107`).

A modelo wizard already exists at `src/cadrumo/application/modelo/work_wizard.py` and
renders as an ordinary flow screen, so guided creation needs no new entrypoint class. The
guided-flow substrate is `src/cadrumo/application/flows/`; the wizard package is legacy
vocabulary bridged one way.

Long-running work reaches the operator through two symbols only:
`present_operation_modal` and `is_detached_outcome`
(`src/cadrumo/entrypoints/tui/operations/facade.py:30`).

## Governance mechanisms in force

The exit-receipt family was retired outright — schemas, five validators and the shared
proof type — by the accepted interface decision, and the corresponding quality module was
deleted. Rebuilding it is an identified hazard.

What survives, explicitly retained because it asserts implementation shape, is the modelo
action denominator at `dev/quality/modelo_workspace_action_denominator.py`. It derives its
candidate set from production imports only, never a filesystem walk, and diffs the live
candidate set against a closed hand-reviewed table. A new modelo command reds the gate
immediately rather than inheriting a mechanical classification. Its dispositions are
bounded review, read pending, mutation pending, flow owned, deferred, and a reserved
non-visual case. Measured green at 11 passing tests, with 79 classifications over 79 live
identities and zero violations: 43 read pending, 31 mutation pending, 2 flow owned, 2 bounded
review, 1 deferred.

It is a scope enumerator, not an admission gate, and the distinction is load-bearing. Its
drift check compares only the four fields named in `_SIGNATURE_FIELDS` at
`dev/quality/modelo_workspace_action_denominator.py:1178` — command key, write route, side
effects, and action-catalogue membership. Neither the recorded disposition nor the interface
capability is observed, so moving a row's disposition, enrolling its operation, or wiring a
route changes no gate outcome. The closed taxonomy also offers no arm a delivered mutation can
occupy: the only completed arm is read-only, leaving all 31 mutation rows without a
destination. Two review-package rows compound this by declaring no write route while carrying
local-state side effects, a contradiction the drift check cannot see because it compares
against the spec's own declaration.

Making it an admission gate requires observing interface capability and dispatchability
alongside the mechanical fields, adding delivered arms, and failing when a recorded disposition
contradicts the observed shape — applied to the intersection of the command graph and the
dispatch table only, which is the boundary the module's own comment at `:1203` draws and
explains.

Five enrolment registries exist and none is aware of the others: the modelo workspace
destination table, the shell destination catalogue, the visual-verification surface list,
the workbench fixtures, and the modelo fixtures. The modelo fixtures at
`src/cadrumo/entrypoints/tui/devtools/modelo_fixtures.py:294` are consumed by nothing but
their own test, so the six modelo destinations, the editor and the selection surfaces are
not drivable from the harness. Every new full-screen class additionally requires a
classification entry or the coverage gate refuses.

Acceptance for a modelo surface requires four locales, two themes and three geometries
with synthetic sentinel data, and an omitted cell is never a pass.

## Known defects carried into the campaign

The filing-history zone is hardcoded unavailable, with empty lifecycle facts, and the
AEAT evidence axis is hardcoded as never captured, although the history merge helper
already exists. The capability facade hardcodes an unmeasured disposition. The edit apply
operation discards the typed stale-baseline refusal. Row-group edit intents are
structurally dead and no repeated-row editor exists, so detail-row modelos have no editing
surface. Text-family casillas receive a structural zero. Six workspace titles in the
English flow catalogue carry a trailing carriage return. The modelo history CLI verb
bypasses the application layer and instantiates a persistence repository directly, and the
spreadsheet calculate verb calls an outbound adapter directly.

## Measured figures

Every figure the decision records cite is recorded here so that the decisions cite grounding
rather than restate it. Measurements were taken against the working tree during the campaign's
research phase and re-checked by an independent pass; where the two disagreed the re-checked
value is given and the discrepancy noted.

### Registry population and coverage

Casillas 29,678 across 58 modelos and 128 revisions, with 1,457 formulas, 9,230 bindings, 121
relations and 516 parameters. Authority grades divide 69 filing, 54 applicability, 5
calculation; a filing-grade snapshot is therefore refused for 59 revisions, being the
applicability and calculation grades together. The modelo enumeration carries 149 members, so 91
have no registry definition.

Export layouts number 94 across 47 of the 58 modelos, comprising 88 fixed-width and 6
xml-dictionary layouts, with completeness manifests for 34 modelos. Every modelo 100 revision
declares an xml-dictionary layout carrying zero records, zero fields and zero offsets, and no
modelo 100 casilla carries an export reference.

### Placement and ordering

Export offsets place 11,268 of the 29,678 casillas. Of the 18,410 unplaced, exactly 97 carry a
classification, so the remainder would disappear without a diagnostic under a placement scheme
that omits rather than declares them. Coverage by casilla weight is roughly one third.

Modelo 200 addresses 812 casillas on between two and eleven pages; corpus-wide 1,062 casillas
resolve to more than one export field. Modelo 200's input surface is 3,452 of its 3,462
casillas, so suppressing computed and internal casillas does not materially reduce the editable
surface at scale. Its slotted records resolve into 14 rectangular tables.

Constructs do not partition a modelo: 109 of 128 revisions declare exactly one construct for the
whole modelo, and modelo 200's single construct holds 3,215 casillas.

An ordering probe reported a perfect rank correlation between export-offset order and the
official record design for modelo 303 in 2025, against a near-zero correlation for
section-plus-declaration order. An independent pass could not reproduce the probe's casilla
population, so the precise correlation figure is unestablished and is recorded here as an open
measurement. The qualitative finding is separately corroborated by section contiguity.

### Metadata density

Constraints are present on 909 casillas, 3.1 per cent of the population, leaving 96.9 per cent
where absent constraints cannot be distinguished from unmeasured ones. Spanish help text covers
11.47 per cent; `form_number` covers 0.465 per cent; aliases cover none. Section tokens number
1,448 distinct values with no catalogue entries, and modelo 200 alone declares 618 sections.

Labels resolve for all 29,678 casillas in all four locales. Untranslated English is 25.8 per
cent corpus-wide and 43.5 per cent for modelo 303 in 2025. The continuity-tier bypass degrades
885 of 1,203 modelo 303 labels and 1,068 of 1,450 modelo 390 labels to bare identifiers; that is
97 per cent on the two worst modelo 303 revisions and 74 per cent across the modelo overall.

### Value handling

The scalar parser returns raw text for 12 of the 19 data types, and 4,715 casillas fall under
those types, of which 1,941 carry an export reference and 219 are required. The declared
unsupported-kind refusal is never constructed. Corpus-wide casilla counts sum the same casilla
across revisions and should be read accordingly.

### Diagnostics, gates and verification

Diagnostic reasons number 38, of which 36 are not persisted onto the revision. Registry
predicates divide 103 advisory to 78 blocking. Verification findings carry 37 locale keys. The
source disposition ladder marks 12 sources locked against operator override and 4 as carrying
it. Cross-period blockers number 21, each mapped to an operator-action axis.

### Reconciliation

The reconciliation service accepts two closed evidence kinds, a justificante and a filed
declaración, through two entry points, and returns a reconciliation report. Two further
comparison mechanisms live outside that service and return verification findings instead: the
divergence check against an authority-pulled filing, and the modelo 303 to modelo 349
intracommunity check. Reconciliation advisories are three constructed codes carrying no severity
field, no resolution action, and authored English prose rather than locale keys.

### Action denominator

79 live action identities, 79 classifications, zero violations, 11 passing tests. Dispositions
divide 43 read pending, 31 mutation pending, 2 flow owned, 2 bounded review and 1 deferred; the
work family alone contributes 13 reads and 6 mutations. Seven modelo operations are registered,
and the frontend dispatch table is keyed to the same seven, so every other mutation writes
outside the supervisor.

### Official source material

The record-design corpus holds 749 files across 58 modelo directories, 56 of which carry
extracted sidecars. Twenty-eight generation-provenance files across 13 modelos pre-join official
section descriptions to casilla identity and export offset. The modelo 100 RentaWeb dictionaries
and schema definitions cover 2,215 of that modelo's 2,249 casillas. The legal source catalogue
holds 499 official artefacts, each with a local corpus path, a digest and an authority URL, none
missing locally. Printed forms exist for two modelos only. The precise casilla-to-description
join rate and the official heading count are open measurements; independently reproduced figures
varied with the counting definition.

### Adapter migration

The command-line tree holds 159 identified violations of the adapter boundary across 224 modules
and roughly 77,000 lines: 71 blocking a frontend surface, 61 correctness, 27 hygiene. By lane
the split is 62 ledger, 52 configuration and profile, 26 live and overview, 18 modelo, 1
cross-lane. Direct adapter imports appear in 46 modules over 122 import lines, repositories are
instantiated in 43 handler sites, and repositories are injected from the command line into
application functions at 68 call sites. Only 7 modules touch decimal arithmetic, so the
violations are classification and routing rather than computation.
