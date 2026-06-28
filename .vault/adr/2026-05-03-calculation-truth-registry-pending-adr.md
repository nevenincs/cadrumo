---
tags:
  - '#adr'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-inventory-research]]'
  - '[[2026-05-03-external-tax-definition-engines-reference]]'
  - '[[2026-04-21-modelo-100-renta-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-research]]'
  - '[[2026-04-29-m100-per-ano-test-parity-research]]'
  - '[[2026-05-05-modelo-100-renta-source-dependency-reference]]'
  - '[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]'
---



# `calculation-truth-registry` adr: `Central AEAT legal calculation registry` | (**status:** `accepted`)

## Review State

This ADR is accepted for implementation. It authorizes the teardown and rebuild
plan that replaces duplicated legal calculation authorities with one strict
registry-backed architecture.

Future review notes should be added against:

- Parent and child domain model.
- External configuration boundaries.
- Formula execution model.
- Source, legal basis, and evidence requirements.
- Migration and deletion boundaries.
- Test and verification obligations.

## Problem Statement

The current codebase does not have a single, auditable source of truth for AEAT
modelos, casillas, legal references, formula definitions, filing schemas, VAT
category mappings, deadline/applicability rules, and export bindings. These
concepts are duplicated across formula rulesets, modelo metadata entries,
casilla corpus JSON, hydrate modules, filing builders, VAT/category registries,
schema extraction code, outbound export specs, manual/normative corpora, and
CLI surfaces.

This fragmentation creates shadowing risk. A modelo or casilla can be described
in one domain, calculated in another, exported through a third, and validated
against a fourth. That is unacceptable for tax filing support because AEAT
declarations are legal acts, and incorrect calculations or stale filing metadata
can expose the user to penalties, corrections, or administrative proceedings.

The architecture must separate legal truth from runtime scaffolding. Python code
may load, validate, execute, trace, and test definitions, but it must not be the
owner of live modelo/casilla metadata, thresholds, rates, formula bindings, or
development-process notes.

## Decision

This ADR proposes the following concrete architecture.

1. Create one authoritative AEAT registry inside the existing legal calculation
   boundary, under `src/aeat/domain/calculations/registry/`, with
   `aeat.domain.calculations` remaining the public calculation authority.
2. Store registry definitions as reviewed TOML under `registry/aeat/modelos/`
   and shared legal/source catalogues under `registry/aeat/legal/`.
3. Treat `ModeloDefinition` as the parent object, `ModeloRevision` as the
   effective-dated filing-period object, and `CasillaDefinition` as a revision
   child object.
4. Load, resolve, and validate TOML into immutable `RegistrySnapshot` objects
   before runtime use.
5. Execute only typed registry formulas through the formula runtime.
6. Forbid filing-grade legal values, thresholds, rates, casilla mappings,
   formula dependencies, and validity windows in Python modules.
7. Allow Python hooks only for data access, orchestration, and complex
   algorithms whose legal constants and casilla dependencies are supplied by the
   registry.
8. Remove app-facing hydrate/write commands from the filing workflow and
   quarantine every repository write path that can mutate legal-rule data.
9. Keep ingestion/extraction tools only as non-authoritative review aids.
10. Make registry validation a required gate before calculation, review,
    approval, export, or filing-draft creation.
11. Reject runtime mode exceptions. Registry data is legally binding once loaded;
    malformed, contradictory, incomplete, provisional, or incalculable modelo
    definitions fail hard and produce no snapshot.
12. Require every modelo revision to carry an AEAT cross-reference decision:
    read-only Open simulator, authorized Integration/test web service, static
    official documentation only, or forbidden authenticated/stateful surface.
13. Add a remote-state guard for every live AEAT cross-reference path. It must
    fail closed before any AEAT POST, presentation, signing, server-side save,
    payment, direct debit, amendment, cancellation, or document submission can
    occur.
14. Build XLS/XLSX parity infrastructure before modelo rebuild work. The
    infrastructure must discover formula coverage in official AEAT workbooks,
    classify workbook suitability, and run identical synthetic inputs through
    both the registry engine and the official workbook/simulator parity surface.
15. Block modelo refactor work until the parity backend exists and is verified.
    The required backend includes workbook inventory, formula discovery,
    workbook classification, synthetic input fixture loading, workbook runner
    integration, registry-vs-workbook comparison, remote-state guarding, and
    verification commands.
16. Require every modelo revision to declare a workbook parity coverage decision
    as part of registry validation. Formula-bearing workbooks require executable
    parity outputs; static layouts, record designs, unsupported binary XLS files,
    and unreadable artefacts are explicit source/legal evidence decisions and
    cannot be treated as passed calculation parity.
17. Treat Modelo 100 as a dedicated Renta aggregation architecture inside the
    same registry, not as a normal small-modelo wave. It must aggregate
    year-scoped official AEAT record designs, AEAT Renta handbook parts, BOE
    law/regulation references, CCAA legal sources, Renta WEB Open parity
    evidence where safe, authenticated filed-data observations where read-only,
    and every Renta subdomain that currently carries casilla or calculation
    meaning.

## Proposed Base Schema

The base schema is a parent-child graph, not a generator format and not a test
format. One TOML file represents one modelo. Yearly and intra-year changes are
represented as explicit `ModeloRevision` records inside that file.

The root object is:

```text
ModeloDefinition
  id: ModeloId
  title: str
  official_name: str
  tax_domain: TaxDomain
  cadence: Cadence
  jurisdiction: "ES-AEAT"
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]
  revisions: dict[RevisionId, ModeloRevision]
```

The revision object is the filing-period truth boundary:

```text
ModeloRevision
  id: RevisionId
  label: str
  valid_from: date
  valid_to: date | null
  period_selector: PeriodSelector
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]
  parameters: dict[ParameterId, ParameterDefinition]
  casillas: dict[CasillaId, CasillaDefinition]
  formulas: dict[FormulaId, FormulaDefinition]
  bindings: dict[BindingId, DataBindingDefinition]
  export_layouts: dict[ExportLayoutId, ExportLayoutDefinition]
  relations: dict[RelationId, RelationDefinition]
  aeat_cross_reference: LiveCrossReferenceDecision
  workbook_parity_refs: list[WorkbookParityRefId]
```

The child objects are:

```text
CasillaDefinition
  id: CasillaId
  number: str
  label: str
  section: SectionPath
  data_type: CasillaDataType
  required: bool
  input_kind: manual | bound | computed | informational
  formula: FormulaId | null
  binding: BindingId | null
  validation_refs: list[ValidationRefId]
  export_refs: list[ExportFieldRef]
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

FormulaDefinition
  id: FormulaId
  target: CasillaId
  op: FormulaOp
  args: list[FormulaArg]
  rounding: RoundingRule | null
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

ParameterDefinition
  id: ParameterId
  data_type: decimal | money | integer | ratio | text | boolean
  unit: Unit
  values: list[DatedValue]
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

DataBindingDefinition
  id: BindingId
  source: ledger_transaction | purchase_invoice_evidence | payable_invoice | collectible_invoice | rental | vat | category | profile | previous_filing | manual_input
  selector: dict[str, scalar]
  aggregation: AggregationSpec | null
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

AlgorithmBindingDefinition
  id: AlgorithmBindingId
  provider: AlgorithmProviderId
  target: CasillaId | OutputId
  inputs: dict[InputId, BindingId | CasillaId | ParameterId | RelationId]
  outputs: dict[OutputId, CasillaId | TraceFieldId]
  constants: list[ParameterId]
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

AlgorithmProviderDefinition
  id: AlgorithmProviderId
  import_path: str
  callable_name: str
  deterministic: true
  side_effect_free: true
  allowed_input_schema: dict[str, SchemaRef]
  output_schema: dict[str, SchemaRef]
  trace_contract: TraceContractId
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

RelationDefinition
  id: RelationId
  kind: previous_period | annual_summary | cross_model_output
  source_modelo: ModeloId
  source_revision_selector: RevisionSelector
  source_output: CasillaId | OutputId
  target_binding: BindingId
  period_alignment: PeriodAlignment
  aggregation: AggregationSpec | null
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]

ExportLayoutDefinition
  id: ExportLayoutId
  source_refs: list[SourceRefId]
  legal_refs: list[LegalRefId]
  records: dict[RecordId, ExportRecordDefinition]

ExportRecordDefinition
  id: RecordId
  record_type: str
  order: int
  encoding: str
  line_ending: crlf | lf | none
  fields: list[ExportFieldDefinition]

ExportFieldDefinition
  id: ExportFieldId
  offset: int | null
  length: int | null
  kind: literal | casilla | computed | filler | checksum
  casilla: CasillaId | null
  literal: str | null
  data_type: text | integer | decimal | money | date | boolean
  required: bool
  padding: left_zero | left_space | right_space | none
  justification: left | right | none
  date_format: str | null
  signed: bool
  legal_refs: list[LegalRefId]
  source_refs: list[SourceRefId]
```

Legal and source evidence are first-class schema objects. They do not live as
free-form strings inside formula descriptions.

```text
LegalReference
  id: LegalRefId
  authority: boe | aeat | eu | autonomous_community | other
  kind: ley | real_decreto | orden | reglamento | directiva | manual | instruction
  corpus_ref: CorpusRef
  document_id: str
  article: str | null
  section: str | null
  permalink: str
  published_at: date | null
  effective_from: date
  effective_to: date | null
  consolidated_as_of: date | null
  review_status: reviewed | provisional | rejected
  reviewed_at: date | null
  reviewed_by: str | null
  notes: str | null

SourceReference
  id: SourceRefId
  authority: aeat | boe | eu | autonomous_community | other
  kind: record_design | manual_pdf | instructions | xsd | dictionary | form_spec
  corpus_path: str
  sha256: str
  bytes: int
  retrieved_at: date
  published_at: date | null
  applies_from: date | null
  applies_to: date | null
  source_url: str
  review_status: reviewed | provisional | rejected

LiveCrossReferenceDecision
  modelo: ModeloId
  revision: RevisionId
  classification: open_simulator | integration_test_service | static_official_only | forbidden_stateful_surface
  official_source_refs: list[SourceRefId]
  allowed_operations: list[ReadOnlyOperation]
  forbidden_operations: list[ForbiddenRemoteOperation]
  synthetic_data_allowed: bool
  requires_authentication: bool
  requires_aeat_authorization: bool
  guard_policy: RemoteStateGuardPolicyId
  reviewed_at: date
  reviewed_by: str
  notes: str | null

WorkbookParityReference
  id: WorkbookParityRefId
  modelo: ModeloId
  revision: RevisionId
  source_ref: SourceRefId
  workbook_kind: formula_form | record_design_layout | validation_hints | static_layout | unsupported_binary_xls | unreadable
  formula_cells: int
  input_cells: list[WorkbookCellRef]
  output_cells: list[WorkbookCellRef]
  supported_by_runner: bool
  coverage_status: complete | partial | static_only | unsupported | failed
  review_status: reviewed | provisional | rejected
```

BOE legal references are legal references. AEAT manuals, instructions, and
handbooks may be legal references only when the registry is citing official
interpretive guidance; they are otherwise source references that explain
casilla/form layout or official filing instructions. AEAT record designs are
source references, not calculation law.

AEAT live simulators are parity evidence, not calculation law. A live
cross-reference can increase confidence only after the legal formula, rate,
threshold, applicability rule, casilla definition, and export binding already
resolve to reviewed BOE, AEAT manual/instruction, or official source evidence.
An authenticated AEAT filing surface is not a development oracle.

AEAT XLS/XLSX workbooks may also be parity evidence when they contain
executable formulas or explicit official validation semantics. They remain
official source evidence, not legal authority by themselves. Every workbook
parity assertion must record the source artefact hash, workbook kind, sheet and
cell mapping, synthetic input set, expected workbook outputs, registry outputs,
and legal/source references that explain why the compared cells matter.

The actual legal and source corpus is not copied into every modelo TOML file.
It is kept as reviewed catalogues and referenced by stable ids. Existing
`corpus/normatives/*.json` and `corpus/manuals/**/manifest.json` become
catalogue inputs. The new registry may expose those through TOML catalogues
under `registry/aeat/legal/`, but modelo files should normally reference ids
such as `ley-37-1992:art-90` or `manual-iva-2025:section-x`, not inline full
legal text.

Shared catalogues are authoritative for `LegalReference` and
`SourceReference`. A modelo file may reference catalogue ids, but it must not
define local `[source]` or `[legal]` tables and must not override catalogue
metadata. Duplicate, missing, contradictory, provisional, or stale catalogue
entries are fatal registry errors.

The schema has these hard invariants:

- A `ModeloRevision` is selected by filing period before any calculation,
  validation, draft building, or export.
- Revision windows for the same modelo cannot overlap unless their
  `period_selector` values are disjoint.
- Every casilla, formula, parameter, binding, and export field belongs to
  exactly one revision.
- Casilla IDs and formula IDs are unique inside a revision.
- A formula target must be a casilla in the same revision.
- A formula argument may reference only same-revision casillas, same-revision
  parameters, or explicitly imported cross-model outputs.
- Cross-model references are allowed only through typed relation declarations,
  such as Modelo 390 consuming reviewed Modelo 303 quarterly outputs.
- Cross-model relation declarations must state source modelo, source revision
  selector, source casilla or output, period alignment, aggregation semantics,
  legal references, and source references. Implicit reads from previous filing
  objects are forbidden.
- Every filing-grade calculation object must have at least one legal reference
  and one official source reference.
- Every legal reference used for filing-grade calculation must be effective for
  the selected rule date axis.
- Every source reference used for filing-grade layout or casilla interpretation
  must resolve to a local corpus artefact with the expected hash and size.
- A provisional, rejected, stale, malformed, or contradictory legal/source
  reference cannot be loaded into a registry snapshot.
- Coverage gaps are fatal. A modelo revision with missing legal evidence,
  missing source evidence, missing casilla definitions, missing formula targets,
  unresolved bindings, unresolved export mappings, or incalculable formulas is
  invalid.
- Source catalogue coverage and calculation coverage are separate. The system
  may catalogue official artefacts for a modelo before its calculation registry
  is complete, but it must not emit a `RegistrySnapshot` for that modelo
  revision until the revision is fully validated. Modelo 037 currently has no
  official record-design artefact in the pulled AEAT corpus; it therefore must
  not have a filing-grade registry snapshot unless reviewed official evidence is
  added or the modelo is removed from the supported registry set.
- Live AEAT cross-reference coverage and legal/source coverage are separate.
  If AEAT provides no safe Open simulator or authorized Integration test
  service for a modelo, the revision may still be implemented from static
  official evidence, but the ledger must record `static_official_only` and all
  authenticated/stateful AEAT surfaces must remain forbidden.
- A live AEAT cross-reference decision is mandatory for every filing-grade
  revision. Missing, stale, contradictory, or unsafe cross-reference decisions
  prevent snapshot creation.
- XLS/XLSX parity coverage is mandatory to assess before a modelo wave starts.
  A formula-bearing workbook can become a required parity oracle for the
  revision; a static or unsupported workbook becomes a recorded evidence gap,
  not a hidden omission.
- Tests are not configuration. Test cases, fixtures, mutation tests, parity
  checks, and regression suites stay in the repository test suite.

This design answers yearly variation directly: variations are not separate
Python modules and not generated JSON. They are reviewed `ModeloRevision`
records inside the single TOML file for that modelo. Modelo 303 can therefore
carry `2024-until-08-2t`, `2024-from-09-3t`, `2025`, and `2026` revisions in
one modelo file, while Modelo 390 can carry older XSD-backed annual revisions
and later XLSX-backed revisions without splitting the modelo identity.

This design also answers legal changes inside a year, inside a filing period,
or inside a month. The schema must not assume that the filing layout date and
the legal calculation date are the same axis. The registry therefore needs
separate temporal selectors:

```text
TemporalApplicability
  date_axis: filing_period | devengo_date | transaction_date | invoice_date | submission_date
  valid_from: date
  valid_to: date | null
  period_selector: PeriodSelector | null
```

The selected `ModeloRevision` controls the official filing surface. Selection
preference is strict: explicit revision id, filing year, period code, and every
declared date axis must all agree. An explicit revision id is not an override;
it is valid only when it is consistent with the filing period and period code.
If no revision matches, multiple revisions match, or a date-axis rule has no
single applicable value, validation fails.

A `ParameterDefinition`, `FormulaDefinition`, `DataBindingDefinition`, or
`LegalReference` may carry narrower `TemporalApplicability` windows. If a VAT
rate changes on the 15th day of a month, the parameter values are split by
`transaction_date` or `devengo_date`; the binding groups input facts by those
date windows; the formula sums the dated slices into the casilla selected by
the monthly or quarterly modelo revision. The schema must reject any ambiguous
case where a rule does not declare which date axis selects it.

## Proposed Code Shape

The registry implementation should live under the existing calculation domain
instead of creating a second legal authority:

```text
src/aeat/domain/calculations/
  __init__.py
  _registry.py
  registry/
    __init__.py
    _ids.py
    _errors.py
    _schema.py
    _schema_export.py
    _loader.py
    _snapshot.py
    _temporal.py
    _validate.py
    _resolve.py
    _runtime_graph.py
    _formula_runtime.py
    _sources.py
    _legal.py
    _bindings.py
    _algorithms.py
    _relations.py
    _export.py
    _remote_state_guard.py
    _workbook_parity.py
    _trace.py
    _cli.py
```

The current `src/aeat/domain/calculations/_registry.py` is not retained as a
parallel registry. It is either migrated into the new registry facade or kept
only as a compatibility facade that delegates to validated `RegistrySnapshot`
objects. The public package `aeat.domain.calculations` must expose one
filing-grade calculation authority.

`_schema.py` is the Python-side schema authority. It defines strict frozen
Pydantic v2 models for `ModeloDefinition`, `ModeloRevision`,
`LegalReference`, `SourceReference`, `TemporalApplicability`,
`CasillaDefinition`, `FormulaDefinition`, `ParameterDefinition`,
`DataBindingDefinition`, `AlgorithmBindingDefinition`,
`AlgorithmProviderDefinition`, `RelationDefinition`, `ExportLayoutDefinition`,
`ExportRecordDefinition`, `ExportFieldDefinition`, and `RegistrySnapshot`
input records. It must not perform calculation, read files, or resolve
cross-references. It must be strict and frozen; invalid shape is a construction
error, not a late warning.

`_schema_export.py` may expose machine-readable schema output from the Pydantic
models for editor tooling and documentation. Exported schemas are derived
developer aids, not registry truth.

`_loader.py` finds TOML files, parses them, normalizes ids, and builds raw
schema objects.

`_resolve.py` links modelo, casilla, formula, parameter, source, legal, export,
and data-source references.

`_validate.py` performs all legal and structural gates. It must reject duplicate
ids, unknown references, shadowed definitions, overlapping validity ranges,
missing citations, unknown formula operations, unsupported placeholders,
coverage gaps, contradictory definitions, and any incalculable modelo
definition.

`_snapshot.py` exposes immutable `RegistrySnapshot` objects selected by modelo,
filing period, period code, and revision.

`_temporal.py` defines temporal applicability, date-axis selection, period-code
selection, overlap checks, and legal/source effective-date checks. It is where
the system distinguishes filing-period layout selection from transaction-date,
devengo-date, invoice-date, and submission-date rule selection.

`_runtime_graph.py` builds the in-memory formula DAG and resolved runtime graph
from already-validated registry objects. It does not write generated files and
does not create a second source of truth.

`_formula_runtime.py` executes resolved formula graphs and emits ledger entries. It
may reuse existing formula engine and ledger concepts only after they become
registry-backed.

`_bindings.py` defines typed data-source bindings for ledger financial transaction, purchase invoice evidence, payable invoice, collectible invoice, rental,
VAT, category, previous-filing, manual-input, and profile inputs. Bindings are
not formulas; they select and aggregate external factual inputs before formula
execution. Names such as `vat` and `category` are factual input selectors only;
they cannot own legal rates, thresholds, casilla mappings, or formula meaning.

`_algorithms.py` registers audited algorithm providers. Algorithm providers are
allowed only for complex deterministic calculations whose legal constants,
input bindings, target casillas, and source/legal references are declared in the
registry. Providers must be deterministic, side-effect-free, covered by an
explicit trace contract, and blocked from filesystem, network, clock, random,
and environment access during calculation.

`_relations.py` resolves typed cross-model and previous-period relationships,
including annual summary relationships such as Modelo 390 consuming reviewed
Modelo 303 outputs. Cross-model reads through ad hoc application objects are
forbidden.

`_export.py` resolves export field bindings from registry definitions and
official AEAT record-design source artefacts. It must not evaluate arbitrary
config expressions.

`_remote_state_guard.py` classifies and enforces live AEAT cross-reference
boundaries. It must allow only reviewed read-only Open simulator operations or
authorized Integration/test-service operations, and it must reject unsafe HTTP
methods, authenticated filing portals, server-side saves, signing,
presentation, payments, direct debits, amendments, cancellations, and document
submissions.

`_workbook_parity.py` discovers and executes official AEAT workbook parity
checks. It must inventory XLS/XLSX formula coverage, classify workbook kind,
map synthetic input cells and output cells, run the registry engine and the
workbook with identical inputs, and emit mismatch traces. Workbook execution is
platform-neutral by default through LibreOffice headless where available.
Windows Excel COM may be an optional local runner, but it is never the required
project path. Unsupported binary XLS files fail as explicit coverage gaps until
a safe cross-platform reader or conversion path is implemented.

The workbook/live parity backend is a prerequisite, not a model-wave task. It
must exist, expose verification commands, and pass those commands before Modelo
130 or any other modelo refactor begins.

`_trace.py` emits calculation evidence: source definition ids, selected validity
windows, formula DAG, input bindings, legal references, and computed outputs.

`_cli.py` exposes read-only inspection and verification commands. It must not
write registry definitions.

## Proposed Repository Data Shape

The authoritative registry data lives outside `src/`:

```text
registry/
  aeat/
    legal/
      boe-normatives.toml
      aeat-manuals.toml
      official-sources.toml
    modelos/
      036.toml
      037.toml
      100.toml
      111.toml
      115.toml
      123.toml
      130.toml
      131.toml
      180.toml
      190.toml
      193.toml
      200.toml
      202.toml
      232.toml
      303.toml
      347.toml
      349.toml
      369.toml
      390.toml
      720.toml
      840.toml
```

One modelo file is the human review unit. Shared legal/source catalogues are
split from modelo files so BOE, AEAT manual, and AEAT record-design metadata do
not get repeated and drift. Modelo files reference those catalogues by stable
ids. The registry loader must reject a modelo TOML that depends on a source
artefact not present in the local official corpus or on a legal reference not
present in the normative catalogue, manual catalogue, or an explicitly reviewed
external-source catalogue.

The file list above is the discovered corpus surface, not an acceptance list.
A modelo file that cannot validate against reviewed official evidence, including
the current zero-evidence Modelo 037 case, cannot produce a filing-grade
snapshot.

## Naming and Verification Conventions

The registry uses one naming scheme across TOML, corpus references, and Python
modules.

Python modules:

- Registry code lives under `src/aeat/domain/calculations/registry/`.
- `src/aeat/domain/calculations/_registry.py` may remain only as the public
  compatibility facade for validated snapshots; it cannot own independent
  ruleset truth.
- Module names are lowercase snake-case private modules: `_schema.py`,
  `_schema_export.py`, `_loader.py`, `_sources.py`, `_legal.py`,
  `_temporal.py`, `_validate.py`, `_resolve.py`, `_snapshot.py`,
  `_runtime_graph.py`, `_formula_runtime.py`, `_bindings.py`,
  `_algorithms.py`, `_relations.py`, `_export.py`, and `_trace.py`.
- Python module names do not encode modelo numbers, years, revisions, waves,
  phases, issues, PRs, or any other process metadata.

Registry TOML:

- Authoritative modelo files live under `registry/aeat/modelos/`.
- Modelo file names are exactly the three-digit modelo id plus `.toml`, for
  example `130.toml`, `303.toml`, and `390.toml`.
- Shared legal and source catalogues live under `registry/aeat/legal/`.
- Shared catalogue file names are lowercase kebab-case, for example
  `boe-normatives.toml`, `aeat-manuals.toml`, and `official-sources.toml`.
- TOML ids are stable kebab-case ids unless the official id is numeric.
- Legal reference ids use the source id plus article or section, for example
  `ley-37-1992:art-90`.
- Source reference ids identify the authority, source type, modelo, and source
  version without process metadata, for example `aeat-dr-303-2024-v2`.
- Revision ids describe official applicability, not implementation work, for
  example `2024-until-08-2t`, `2024-from-09-3t`, `2025`, or `2026`.
- Casilla ids preserve official casilla numbering as strings, including leading
  zeroes when AEAT uses them.
- Formula, binding, parameter, and export ids are stable kebab-case or dotted
  domain ids. They must not include development-flow metadata.

Corpus material:

- Official AEAT record-design artefacts live under
  `corpus/aeat_official/disenos_registro/`.
- Per-modelo official artefacts live under
  `corpus/aeat_official/disenos_registro/modelo_<id>/`.
- Each official artefact directory has a `manifest.json` with source URL, local
  path, byte count, SHA-256, retrieval date, and content type.
- BOE legal corpus remains under `corpus/normatives/`.
- AEAT manual corpus remains under `corpus/manuals/`.
- Registry TOML references corpus artefacts by stable ids plus path/hash
  evidence; it does not copy full legal/manual text into every modelo file.

Reader and verifier responsibilities:

- `_loader.py` reads TOML only and builds raw schema objects.
- `_sources.py` reads `corpus/aeat_official/**/manifest.json` and manual
  manifests, then verifies corpus path, byte count, SHA-256, source URL, and
  retrieval metadata.
- `_legal.py` reads legal catalogues and `corpus/normatives`, then resolves BOE,
  AEAT manual, instruction, and official guidance references.
- `_temporal.py` validates effective-date windows, period selectors, date axes,
  and overlap rules.
- `_resolve.py` links modelo, revision, casilla, formula, parameter, binding,
  source, legal, and export references into one object graph.
- `_schema.py` is the programmatic schema authority and must use strict frozen
  Pydantic models. TOML is only the authored serialization format.
- `_schema_export.py` can emit derived JSON Schema or documentation schemas
  from Pydantic models, but those exports are not authoritative inputs.
- `_validate.py` is the legal registry gate. It rejects missing evidence,
  unresolved references, duplicate ids, shadowed definitions, illegal
  provisional references, ambiguous temporal rules, coverage gaps, formula
  cycles, incalculable formulas, contradictory revisions, and export binding
  drift. No downgraded mode may bypass these checks.
- `_snapshot.py` selects immutable runtime views after validation. It must not
  read or write files directly.
- `_trace.py` emits evidence for the selected revision, legal references,
  source artefacts, date-axis choices, inputs, formulas, and outputs.

## Proposed TOML Shape

The following is the proposed shape. It is deliberately small: model identity,
revision windows, catalogue references, casillas, formulas, parameters,
bindings, relations, algorithm bindings, and export layout references. The
modelo file references shared legal/source catalogue ids; it does not define
local `[source]` or `[legal]` tables.

```toml
[modelo]
id = "303"
title = "IVA autoliquidacion"
official_name = "Impuesto sobre el Valor Anadido. Autoliquidacion"
tax_domain = "iva"
cadence = "quarterly"
jurisdiction = "ES-AEAT"

legal_refs = ["ley-37-1992", "rd-1624-1992"]
source_refs = ["aeat-manual-iva-2024"]

[revisions."2024-until-08-2t"]
valid_from = "2024-01-01"
valid_to = "2024-08-31"
period_selector = { years = [2024], periods = ["01", "02", "03", "04", "05", "06", "07", "08", "1T", "2T"] }
legal_refs = ["ley-37-1992:art-92", "ley-37-1992:art-99"]
source_refs = ["aeat-dr-303-2024-v1"]

[revisions."2024-from-09-3t"]
valid_from = "2024-09-01"
valid_to = "2024-12-31"
period_selector = { years = [2024], periods = ["09", "10", "11", "12", "3T", "4T"] }
legal_refs = ["ley-37-1992:art-92", "ley-37-1992:art-99"]
source_refs = ["aeat-dr-303-2024-v2"]

[[revisions."2024-from-09-3t".casillas]]
id = "03"
number = "03"
label = "IVA devengado por operaciones interiores"
section = ["iva_devengado", "regimen_general"]
data_type = "money"
required = true
input_kind = "bound"
binding = "vat.output.general.quota"
legal_refs = ["ley-37-1992:art-90", "ley-37-1992:art-164"]
source_refs = ["aeat-dr-303-2024-v2"]
export_refs = ["dp30301.casilla_03"]

[[revisions."2024-from-09-3t".casillas]]
id = "46"
number = "46"
label = "Resultado regimen general"
section = ["resultado"]
data_type = "money"
required = true
input_kind = "computed"
formula = "resultado-regimen-general"
legal_refs = ["ley-37-1992:art-92", "ley-37-1992:art-99"]
source_refs = ["aeat-dr-303-2024-v2"]
export_refs = ["dp30304.casilla_46"]

[[revisions."2024-from-09-3t".formulas]]
id = "resultado-regimen-general"
target = "46"
op = "subtract"
args = [{ casilla = "27" }, { casilla = "45" }]
rounding = "money_2"
legal_refs = ["ley-37-1992:art-92", "ley-37-1992:art-99"]
source_refs = ["aeat-dr-303-2024-v2"]

[[revisions."2024-from-09-3t".parameters]]
id = "iva.general.rate"
data_type = "ratio"
unit = "ratio"
legal_refs = ["ley-37-1992:art-90"]
source_refs = ["manual-iva-2025"]

[[revisions."2024-from-09-3t".parameters.values]]
parameter_id = "iva.general.rate"
value = "0.21"
date_axis = "transaction_date"
valid_from = "2024-09-01"
valid_to = "2024-12-31"

[[revisions."2024-from-09-3t".bindings]]
id = "vat.output.general.quota"
source = "vat"
selector = { fact = "output_quota", regime = "general" }
aggregation = { op = "sum", date_axis = "transaction_date" }
legal_refs = ["ley-37-1992:art-90", "ley-37-1992:art-164"]
source_refs = ["manual-iva-2025"]

[[revisions."2024-from-09-3t".export_layouts]]
id = "record-design-2024-v2"
legal_refs = ["ley-37-1992:art-164"]
source_refs = ["aeat-dr-303-2024-v2"]

[[revisions."2024-from-09-3t".export_layouts.records]]
id = "dp30304"
record_type = "4"
order = 4
encoding = "iso-8859-1"
line_ending = "crlf"

[[revisions."2024-from-09-3t".export_layouts.records.fields]]
id = "dp30304.casilla_46"
offset = 120
length = 15
kind = "casilla"
casilla = "46"
data_type = "money"
required = true
padding = "left_zero"
justification = "right"
signed = true
legal_refs = ["ley-37-1992:art-92", "ley-37-1992:art-99"]
source_refs = ["aeat-dr-303-2024-v2"]
```

The exact casilla examples above are illustrative placeholders for schema
shape only. The accepted implementation must populate real casilla labels,
formula targets, and export fields from reviewed AEAT/BOE sources and tests.

Formula operations are closed enum values. Initial operations should be `add`,
`subtract`, `multiply`, `divide`, `percent`, `sum`, `min`, `max`, `clamp`,
`negate`, `copy`, `if_then_else`, `lookup_parameter`, `previous_period_value`,
`previous_period_sum`, and `cross_model_sum`. Every operation must have a typed
validator, DAG traversal behaviour, and trace renderer. TOML never evaluates
arbitrary Python or string expressions.

## Proposed Runtime Flow

Calculation should flow in this order:

```text
load TOML
  -> parse strict schema
  -> parse shared legal/source catalogues
  -> validate source artefact hashes against local corpus
  -> validate legal references against normative/manual catalogues
  -> validate workbook parity coverage classification
  -> validate AEAT live/static cross-reference classification
  -> attach remote-state guard policy
  -> resolve references
  -> validate temporal applicability and date-axis declarations
  -> reject coverage gaps and contradictions
  -> validate registry snapshot
  -> select modelo revision by id, filing period, and period code
  -> bind input data
  -> build runtime formula graph
  -> execute formulas
  -> emit calculation ledger
  -> assemble filing draft
  -> validate export binding
  -> export only after approval gates
```

No caller should be able to bypass registry validation and directly invoke old
ruleset modules or filing builders for filing-grade outputs.
No caller should be able to use AEAT live cross-reference as an unguarded
runtime dependency or as a substitute for reviewed legal/source evidence.
Diagnostic commands may report invalid registry files, missing evidence, or
unavailable snapshots, but review, approval, export, filing draft creation, and
any calculation claimed as filing-grade must fail instead of downgrading to
`UNVERIFIABLE`, `no-ruleset`, or equivalent soft states.

## Proposed Migration Plan

Stage 1 introduces the registry package, TOML loader, immutable snapshot, and
validator. No existing filing behavior changes in this stage.

Stage 2 migrates the source/evidence catalogue for the currently discovered
supported-model corpus. This does not implement every calculation and does not
authorize snapshots for incomplete modelos. It wires the official AEAT
record-design corpus into the registry validator so a modelo revision cannot
claim an artefact that is not present locally with the expected hash. Modelo
037 is explicitly blocked from filing-grade snapshot creation until reviewed
official record-design evidence exists or the modelo is removed from the
supported registry set.

Stage 3 migrates Modelo 130 because it is small enough to expose the core
design problems: thresholds, rates, cumulative periods, previous payments,
casilla dependencies, and legal references. Existing Modelo 130 behavior becomes
the parity target but not the authority.

Stage 4 removes Modelo 130 formula ownership from Python filing builders and
ruleset modules. The builder becomes output orchestration over registry results.

Stage 5 migrates Modelo 303 because it tests VAT/category/data-source bindings
and casilla mapping.

Stage 6 migrates Modelo 390 because it tests parent-child relationships between
modelos, especially annual summary logic derived from Modelo 303 outputs.

Stage 7 quarantines or deletes hydrate, schema write paths, export layout
writers, and raw formula/ruleset bypasses that can mutate or bypass
repository legal-rule files.

Stage 8 migrates additional modelos. Modelo 100/Renta gets a separate
architecture pass because it is not just one form; it is a compound tax system
with anexos, CCAA rules, rental logic, amortization, reductions, and special
domain objects.

## Explicit Architecture Decisions

The following decisions are proposed for review:

| ID | Proposed decision | Reason |
| --- | --- | --- |
| D1 | Registry definitions live outside Python under `registry/aeat/`. | Keeps legal/config truth reviewable as data. |
| D2 | `ModeloDefinition` is the parent object. | Modelo owns cadence, applicability, source set, legal context, export context. |
| D3 | `ModeloRevision` is the temporal child of `ModeloDefinition`. | Official AEAT forms change by year and sometimes inside a year. |
| D4 | `CasillaDefinition` is a child of a revision, not only of the abstract modelo. | Casillas are added, removed, renamed, and repositioned by revision. |
| D5 | One TOML file represents one modelo. | Avoids fragmented model truth and makes the modelo the review unit. |
| D6 | Revision blocks inside that TOML represent yearly and intra-year variation. | Handles AEAT variation without code shadowing or generated JSON. |
| D7 | Formula config is a typed operation graph. | Enables validation, tracing, and dependency checks. |
| D8 | Arbitrary Python/string expression evaluation is forbidden in config. | Not reviewable enough for legal calculation. |
| D9 | Python hooks may orchestrate and perform algorithms, but not own legal constants or casilla dependencies. | Allows complex models without reintroducing private legal truth. |
| D10 | Registry validation is mandatory before calculation/export. | Prevents shadowed, incomplete, or uncited definitions from running. |
| D11 | Hydrate cannot be part of the app workflow and cannot write authoritative files. | Runtime source mutation is incompatible with audited legal config. |
| D12 | Official AEAT record-design artefacts are local source evidence, not generated truth. | The registry references them by hash and path; it does not derive law from them automatically. |
| D13 | Modelo 130 is the first calculation migration slice after the source catalogue. | Smallest useful legal calculation slice with rates, thresholds, cumulative logic, and previous-period behavior. |
| D14 | Modelo 303 follows 130. | Proves VAT/category bindings, period variation, and casilla mapping. |
| D15 | Modelo 390 follows 303. | Proves cross-model annual summary behaviour. |
| D16 | Modelo 100/Renta requires a dedicated aggregation phase under the same central registry. | It is one modelo, but its Renta universe has yearly schemas, source families, CCAA law, anexos, rental/amortization logic, and live filed-data observations that must be reconciled before normal per-modelo completion. |
| D17 | There are no relaxed runtime modes for registry validity. | The system is legally binding; incomplete or provisional definitions must fail before execution. |
| D18 | `_schema.py` is the Python-side schema authority. | The authored file format is serialization; strict Pydantic models define the programmatic contract. |
| D19 | The implementation lives under `src/aeat/domain/calculations/registry/`. | Reuses the existing calculation-domain authority and prevents a second central registry. |
| D20 | Shared legal/source catalogues are authoritative; modelo files reference ids only. | Prevents duplicated BOE, AEAT manual, and source metadata from drifting inside per-model files. |
| D21 | Incomplete modelos can have evidence catalogue entries but cannot emit snapshots. | Reconciles corpus inventory work with fail-hard legal execution. |
| D22 | Cross-model dependencies are declared as typed relations. | Makes annual summaries and previous-period dependencies explicit and traceable. |
| D23 | Algorithm providers require explicit registry bindings and trace contracts. | Allows complex deterministic calculations without hiding legal constants in Python. |
| D24 | Every modelo revision requires a live/static AEAT cross-reference decision. | Prevents assuming that AEAT has a safe simulator or sanctioned test engine for every modelo. |
| D25 | Remote-state guards are mandatory for live AEAT cross-reference work. | Synthetic calculation tests must never write AEAT remote state or touch authenticated filing actions. |
| D26 | XLS/XLSX formula coverage is discovered before model migration. | Official workbooks may be the strongest available parity surface and must be treated as first-class evidence. |
| D27 | Workbook parity uses identical synthetic inputs for the registry engine and workbook runner. | Prevents comparing hand-adjusted examples and gives reproducible calculation mismatches. |
| D28 | The workbook/live parity backend must exist and pass verification before modelo refactor. | Prevents starting model migration without the evidence and parity infrastructure needed to prove correctness. |
| D29 | Modelo 100 registry work starts from official AEAT record designs, AEAT Renta handbook parts, BOE law/regulation, and CCAA legal sources for each supported ejercicio. | The existing Python extractors, rental modules, ruleset-era documents, and tests are audit inputs only; they are not authorities. |
| D30 | Modelo 100 live AEAT access is read-only evidence capture only. | Renta WEB Open can be parity evidence; authenticated Renta WEB, fiscal-data, borrador, filed-declaration and justificante surfaces may provide observations only through the remote-state guard and encrypted storage. |
| D31 | Modelo 100 is selected by ejercicio-specific `ModeloRevision` records, not by Python module names or variant slots. | Renta record designs and manual content change by year; the registry must select the exact revision before calculation, parsing, export, or observation reconciliation. |
| D32 | Modelo 100 is decomposed into gated Renta constructs under the one official modelo parent. | The implementation can progress section by section without inventing unofficial AEAT modelo ids or leaving unverified partial Renta snapshots executable. |

## Modelo 100 Renta Aggregation Decision

Modelo 100 is not a separate registry and not an exception to the hard teardown.
It is a large registry subgraph rooted at `registry/aeat/modelos/100.toml`.
That file owns the Modelo 100 identity, supported ejercicios, revision
selection, common IRPF legal basis, source references, final settlement
structure, cross-model relations, live/static cross-reference decisions, and
the checklist of Renta subdomains that must be complete before any filing-grade
snapshot can be emitted.

The Renta subdomains are registry children, not independent authorities:
personal/family circumstances, work income, real-estate capital, movable
capital, economic activities, imputations and attribution of income, capital
gains/losses, bases, reductions, minimos, quotas, state deductions, autonomous
community deductions, rental ledgers, amortization, inventory, final result,
payment/refund structure, export layout, filed-data observations, borrador
observations, and justificante observations.

Those children should be implemented as gated Renta constructs. A construct is
not a new AEAT modelo and cannot emit a filing-grade snapshot by itself. It is a
reviewable unit with its own legal refs, source refs, casillas, formulas,
algorithm bindings, parser bindings, observation bindings, tests, and teardown
targets. Modelo 100 can only emit a snapshot when every required construct for
the selected ejercicio has passed validation and relation checks.

Each supported ejercicio must have a reviewed revision record. For current
coverage the official corpus already contains AEAT Modelo 100 record-design
artefacts for ejercicio 2020 through 2025, with 2025 files updated on
2026-04-14 and 2023/2024 historical files updated in January 2026. The plan
must close the source ledger for every retained ejercicio rather than assuming
that a previous Renta ruleset or PDF parser proves coverage.

Authority tiers for Modelo 100 are explicit:

- BOE law and regulation are the legal authority for calculations, rates,
  deductions, obligations, and temporal applicability.
- AEAT Renta manuals, instructions, presentation help, dictionaries,
  properties, XSD, PDFs, and XLS/XLSX record designs are official guidance,
  layout authority, or parity evidence according to what the specific artefact
  proves.
- Renta WEB Open can be used only as read-only parity evidence because AEAT
  describes it as a simulator that does not require taxpayer identification and
  does not permit presentation.
- Authenticated fiscal-data, borrador, declaration, and justificante surfaces
  are observation sources only. They can populate encrypted local evidence for
  already-filed or user-owned data, but they cannot become calculation law and
  cannot write AEAT remote state.

Existing Renta-era Python modules are not retained as compatibility layers.
Rental, amortization, inbound borrador/declaracion extraction, outbound Sede
filed-data capture, portal entries, category profiles, old formula/ruleset
documentation, and tests must either become lean consumers of validated Modelo
100 registry snapshots or be deleted when their authority has been represented
and verified in the registry.

The Renta source and dependency boundary is controlled by the dedicated Modelo
100 source-dependency reference. That reference classifies each supported
modelo as a direct annual-settlement dependency, factual evidence, or explicit
non-dependency before Modelo 100 can produce filing-grade output. This prevents
periodic, informative, VAT, censal, corporate, or foreign-asset declarations
from silently shadowing the annual IRPF legal calculation.

## Considerations

The existing research found useful foundations already present in the codebase:
formula ASTs, ruleset validation, calculation ledgers, legal citation models,
normative corpora, manual corpora, registry validation, and test contracts for
citations and ruleset closure. These should be preserved where they can be made
subordinate to the new registry.

The same research found several unacceptable duplicate authorities:

- Python formula ruleset modules own modelo/casilla calculations.
- Modelo entry modules own identity, applicability, cadence, and citations.
- Casilla corpus JSON owns materialized casilla records and references.
- Hydrate modules can create and write casilla corpus records.
- Filing builders for 130, 303, and 390 duplicate calculation logic.
- VAT and category registries carry rates, legal references, and casilla maps.
- Deadline and applicability modules encode obligation logic separately.
- Inbound extractors and outbound export specs carry modelo/casilla layout
  truth in separate surfaces.

Spain-specific external review showed that OCA `l10n-spain` uses a reusable
AEAT base report plus per-model modules and year-scoped data records. That
supports the parent-model architecture. It also shows what not to accept here:
significant casilla calculations remain hardcoded in Python, and export config
uses executable expressions.

OpenFisca and PolicyEngine are relevant only as jurisdiction-neutral engine
references. Their useful pattern is an external parameter tree with dated values
and runtime lookup. Their country-specific tax content is not evidence for
Spanish AEAT filing logic.

## Constraints

Every registry item that participates in calculation or filing must carry source
and legal evidence. Missing legal basis, missing AEAT source, unknown citation,
unreviewed source status, or uncited formula operation must be a fatal
validation error for filing-grade calculation.

Duplicate modelo ids, duplicate casilla ids within a modelo/version, duplicate
formula ids, overlapping validity windows, incompatible export bindings, and
shadowed definitions must be fatal validation errors.

The registry must preserve temporal semantics. Rates, thresholds, formulas,
field layouts, and applicability conditions are selected by filing period and
validity range, not by hardcoded module names.

The registry must preserve multiple date axes. Filing layout revisions are
selected by filing period and period code. Legal references are selected by
their legal effective dates. Parameters and data bindings are selected by their
declared date axis, such as transaction date, devengo date, invoice date, or
submission date. A rule with no declared date axis is invalid for filing-grade
calculation.

The registry has no partial-success semantics. A malformed TOML file,
contradictory revision, missing official source, missing legal reference,
unresolved casilla, formula cycle, unsupported formula operation, missing input
binding, or export mismatch prevents snapshot creation for that modelo.

TOML must remain configuration, not a second programming language. Any
expression layer must be constrained to audited operation names and typed
operands.

Renta and complex annual models may require specialized domain objects and
model-specific extension hooks. Those hooks must consume registry definitions
and return traced calculation results; they must not reintroduce private
hardcoded legal truth.

AEAT Open simulators and Integration test services may be used only as
classified parity evidence. Official Open simulators are model-specific and
year-specific. AEAT Integration services require per-service authorization and
prepared test NIFs. Neither surface is a universal formula oracle.

Official AEAT XLS/XLSX/PDF/XSD record designs are authoritative for filing
layout, field structure, import/export shape, and any explicit validation rules
they contain. They are not sufficient as calculation-law authority unless the
specific document explicitly states the calculation or validation rule being
implemented.

Formula-bearing AEAT XLSX files should be treated as the first parity target
where available. Binary XLS files require separate parser/conversion research
before they can be a parity gate.

The following current surfaces must be explicitly migrated, quarantined, or
deleted during implementation:

| Current surface | Required disposition |
| --- | --- |
| `src/aeat/domain/calculations/_registry.py` | Migrate into the registry facade or delegate to validated snapshots only. |
| `src/aeat/domain/formulas/__init__.py` public `Engine`, `Ruleset`, and `get_registry` exports | Quarantine as runtime internals; filing-grade callers must use registry snapshots. |
| `src/aeat/application/verification/_verify.py` raw `Ruleset` and `Engine` path | Refactor to consume `RegistrySnapshot`; missing rulesets are fatal for filing workflows. |
| `src/aeat/application/filing/_review.py` `no-ruleset` review state | Remove from filing-grade approval paths; invalid registry blocks review approval. |
| `src/aeat/domain/filing/_builders/modelo_130.py` | Remove calculation ownership; builder assembles registry-backed outputs only. |
| `src/aeat/domain/filing/_builders/modelo_303.py` | Remove calculation ownership; builder assembles registry-backed outputs only. |
| `src/aeat/domain/filing/_builders/modelo_390.py` | Remove calculation ownership; annual summary inputs come through typed relations. |
| `src/aeat/entrypoints/cli/casillas.py` hydrate `--write` | Delete or convert to read-only corpus inspection outside filing workflows. |
| `src/aeat/domain/casillas/catalogue.py` `save_casillas` | Delete for authoritative data or quarantine as non-authoritative research import. |
| `src/aeat/domain/schema/_cache.py` write cache | Quarantine from registry truth; cache cannot feed filing-grade definitions. |
| `src/aeat/adapters/inbound/schema/_fetch.py` placeholder extraction | Keep only as evidence acquisition/review aid; it cannot write authoritative registry definitions. |
| `src/aeat/adapters/outbound/aeat/export/_formats/_generate.py` | Delete or quarantine; export layouts must be reviewed registry data backed by official sources. |

## Implementation Direction

Create `src/aeat/domain/calculations/registry/`, with strict schema models that
load all legal calculation configuration into immutable runtime objects:

- `ModeloDefinition`
- `ModeloRevision`
- `CasillaDefinition`
- `FormulaDefinition`
- `ParameterDefinition`
- `DataBindingDefinition`
- `AlgorithmBindingDefinition`
- `AlgorithmProviderDefinition`
- `RelationDefinition`
- `ExportLayoutDefinition`
- `ExportRecordDefinition`
- `ExportFieldDefinition`
- `LegalReference`
- `SourceReference`
- `ValidityWindow`
- `RegistrySnapshot`

Define strict schema models for the TOML shape. The loader must normalize ids,
resolve references, build parent-child relationships, attach inherited modelo
context to revisions and casillas, and emit a complete registry snapshot.

Implement a registry validator before any calculation runtime can execute. The
validator must check identity uniqueness, reference closure, formula DAG closure,
legal/source coverage, negative citation blocklists, validity window
consistency, export binding consistency, data-binding consistency, algorithm
trace contracts, relation closure, complete modelo coverage, and calculability.
Validation failure must be fatal; no partially valid filing-grade snapshot may
escape the registry package.

Refactor the formula engine to execute only registry-backed formulas. Existing
formula AST and ledger concepts can remain if they become in-memory runtime
representations built from validated registry definitions.

Refactor filing builders to consume registry-backed calculation results rather
than owning formulas. Modelo 130, 303, and 390 builder logic should become
orchestration and output assembly only.

Remove the app-facing hydrate command and any write path that mutates legal-rule
corpus files. Extraction/import utilities may remain only behind review/audit
surfaces that cannot silently update authoritative registry files.

Preserve normative and manual corpora as evidence catalogues. The registry must
reference those catalogues by stable ids instead of embedding citation strings
ad hoc in formula code. Source validation should extend or reuse
`aeat.core.corpus_manifest` and the manual manifest hash checks instead of
creating a weaker parallel integrity mechanism. Legal validation must preserve
the known-bad citation blocklist in `aeat.domain.modelos._citation_registry`.

Add import-contract tests that prevent application, filing, review, export, and
CLI code from importing old formula rulesets or filing builders as filing-grade
calculation authorities. Those tests must exercise real imports and real
registry validation; they must not use mocks, skips, or tautological assertions.

Add remote-state guard tests that exercise real cross-reference policy objects
and representative browser/network actions. The tests must prove that unsafe
AEAT methods, stateful authenticated portals, server-side save, signing,
presentation, payment, direct debit, amendment, cancellation, and document
submission are rejected before execution.

## Rationale

Centralization is required because the current architecture lets multiple
domains answer the same legal question differently. A tax calculation system
must make it obvious which object owns the legal definition for a modelo,
casilla, formula, rate, threshold, and export field.

External reviewed configuration is required because legal truth changes by
official source and filing period. It must be inspectable without reading Python
implementation modules, and changes must be reviewable as data changes with
legal citations. Tests remain normal repository tests against that reviewed
configuration.

Typed formulas are required because arbitrary executable expressions are too
opaque for legal review. A constrained operation graph allows validation,
dependency analysis, trace output, mutation testing, and citation checks.

The parent-child model reflects the domain. A modelo provides stable official
identity, cadence, applicability, source catalogues, export context, and common
legal basis. A revision represents the exact official version selected for a
filing period. A casilla belongs to that revision and adds its own field
semantics, formula, references, validation, and export binding.

## Consequences

This is a hard architectural cut. Large parts of the existing formula, casilla,
filing, VAT/category, deadline, schema, and export code become legacy surfaces
until migrated behind the central registry.

The migration must be staged. The first stage should introduce the registry
schema and validator without changing filing behavior. The second stage should
register the full official source catalogue for all supported modelos. The
third stage should port Modelo 130 with strong tests. Later stages should
replace duplicated filing builders, migrate Modelo 303 and Modelo 390, remove
hydrate/write paths, and then move broader modelo families and Renta-specific
complexity.

Tests must shift from asserting scattered module behavior to asserting registry
truth: legal/source coverage, uniqueness, validity selection, formula closure,
trace correctness, export binding alignment, and parity against existing trusted
fixtures where available.

The architecture will make bad or incomplete legal data impossible to ignore.
That increases upfront work, but it is the correct tradeoff for AEAT-facing
calculation support.

## Explicit Non-Decisions

This ADR proposes the base schema shape but does not approve populated TOML
content for any real modelo.

This ADR does not approve automatic ingestion as an authoritative source.

This ADR now decides the Renta internal authority boundary: Modelo 100 is a
dedicated aggregation phase under the central registry, with ejercicio-scoped
revisions and Renta subdomains as registry children. The exact populated
casilla/formula content remains subject to source-ledger review and registry
validation.

This ADR does not decide final migration ticket boundaries.

## Open Review Questions

Should export layout definitions live in the same modelo TOML file as casilla
definitions, or in a sibling TOML file linked by modelo/version?

Should data-source bindings for ledger financial transaction, purchase invoice evidence, payable invoice, collectible invoice, rental, VAT, and category
aggregation be part of casilla definitions directly, or separate reusable
binding definitions referenced by casillas?

Should pending or unverified legal references be allowed anywhere outside the
authoritative registry as quarantined research evidence, or should they be
rejected from the repository entirely?

## Amendment (2026-05-21): _ingest.py and DR-spec fixture deletion

The Migration Disposition in this ADR authorised deleting or
quarantining the DR-spec to Python-module generator
(`export/_formats/_generate.py`). The companion `_ingest.py` (JSON
DR-spec ingestion) and the DR-spec JSON fixtures (`tests/fixtures/
dr_specs/*.json`) were deleted in the same registry-truth migration
(commit `97dac2be7`) but were not named in the original disposition.
This amendment records that deletion as sanctioned: `_ingest.py` and
the DR-spec JSON fixtures belonged to the same generate/ingest
toolchain that this ADR's registry-TOML-first authoring direction
supersedes. Export layouts are now reviewed registry data authored
directly from the official AEAT Diseño de Registros, not generated
from intermediate DR-spec JSON. The deleted toolchain remains
recoverable from branch history if a future ADR reinstates a
generation pipeline.
