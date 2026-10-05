# CLI command contracts and operator surfaces

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-156` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope

This chunk covers 26 CLI entrypoint modules. I read all assigned ranges across nine bounded pages; where page output truncated, I inspected the unfinished file tails as smaller line slices. The modules declare diagnostics and ledger command trees, parameter/transport contracts, execution policies, typed payloads, and thin Typer handlers. Static inspection only: I did not import the application, invoke commands, or run tests. No test files are assigned here.

## Product capabilities

The CLI has a deliberately inert package namespace and an import-light declarative command tree. CommandSpec fragments describe each command’s parent, token, arguments and options, defaults, value contracts, help translation keys, execution policy, lazy handler target, and typed result schema. The ledger fragment composer joins the families into a single tuple; deferred targets let the surface describe command options and payloads without eagerly loading handler or domain modules (inert namespace (`src/cadrumo/entrypoints/cli/__init__.py`), ledger tree (`src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`), policy vocabulary (`src/cadrumo/entrypoints/cli/_app_ledger_command_spec_policies.py`)).

The ledger command families cover transaction creation, allocation, classification, review, lifecycle changes, exports/imports, evidence intake and review, invoices, activity assets, investment inventory, participation, prorrata, and annual usage ratios. Their declarations distinguish read-only, local-state, calculation, network, and destructive effects; some commands also identify file or directory inputs or local export outputs. For example, classification accepts a local file and explicitly includes network capability, and exports name a local output path (classification contract (`src/cadrumo/entrypoints/cli/_app_ledger_classification_command_specs.py`), export contract (`src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`)). These declarations make data movement and destructive intent visible at the CLI boundary, while the handler and worker modules own actual I/O and authorization.

The activity-asset handler adapts typed JSON revisions to registered runtime operations, then validates that successful operations returned the data needed for a receipt. It distinguishes creating and correcting history, inspecting revisions, forecasting a charge, recording an explicit claim, and projecting filing handoff totals. Forecasting is described as non-consuming; a claim requires a forecast JSON input and creating-operation identity, and its receipt reports whether an existing claim was reused. Filing handoff is also a projection, not a consume/write command (asset handlers (`src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`), forecast and claim (`src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`), handoff (`src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`)). Activity-asset output models wrap domain facts in explicit Pydantic schemas, and every handler emits a standard envelope with stable command identity.

The diagnostics group provides local reports of recent LLM run health, individual runs, latency percentiles, error kinds, and provider/model usage, alongside persisted AEAT-session presence and staleness. The displayed fields include provider, model, caller, timestamps, duration, success state, and typed error kind; these handlers project operational metadata rather than prompt or invoice contents (run health and session state (`src/cadrumo/entrypoints/cli/_app_diagnostics.py`), run records (`src/cadrumo/entrypoints/cli/_app_diagnostics.py`), provider/model usage (`src/cadrumo/entrypoints/cli/_app_diagnostics.py`)).

The shared command-spec support functions reduce repeated option-shape definitions and can project application-owned operator input contracts into CLI fields. Resolved precondition actions are serialized from the exact typed DTO in deterministic compact JSON; the CLI helper says it does not invent a recovery command or prose (shared option constructors (`src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`), action rendering (`src/cadrumo/entrypoints/cli/_action_rendering.py`)).

## Knowledge and data

This layer mostly declares and transports inputs; it does not implement tax calculations or establish legal applicability. Registry-backed category, prorrata, inventory, and model types are referenced through deferred targets, while application input contracts supply selected option vocabularies. File and directory transport markers are useful descriptions of intended handling, but do not by themselves establish path confinement, file-content validation, or network behavior. Those properties depend on the referenced handler, worker, and adapter implementations.

The diagnostics commands read local run records according to the module contract. Ledger options can carry taxpayer identifiers, counterparty details, notes, tax classifications, invoice facts, and local evidence paths. This chunk’s declarations show how these values enter the CLI but not how handlers redact, retain, or export them.

## Security and safety assessment

The strongest CLI-boundary controls visible here are typed input contracts, explicit file/remote transport metadata, typed result schemas, and execution-policy tags that mark external and destructive operations. Removal/reset commands expose a separate yes flag and their policy marks them destructive; Google and network operations use distinct effect labels. These are declarations rather than proof that downstream authorization, consent, or write fences are correct; synthesis should compare them with the registered worker contracts and handler paths.

The no-data notices in diagnostics resolve to the classification action from an action catalogue, and resolved-action rendering preserves the typed action object rather than deriving shell text locally. This is a safer presentation seam than string-building a recovery command, but the correctness of action resolution is outside this chunk. The handlers translate absent projections into typed runtime refusal errors rather than emitting a misleading empty success payload.

## Implementation assessment and follow-up

The declarative tree is split into focused fragments with shared helpers for common options, plus typed schemas at output boundaries. Repeated ledger parameter shapes are centralized while meaningful distinctions—absent versus empty defaults, repeated values, file versus remote handle, and required versus optional values—remain explicit. The activity-asset CLI keeps schedule previews separate from persisted claims.

The breadth of ledger fragments creates a large public surface, but the immutable tuple composition and stable command identities give synthesis a concrete basis to compare declared commands against handler registrations. Cross-check that destructive flags are required by handlers, and that every transport marker matches actual local-file/network usage. The inspection found no test evidence in this chunk, and no command was run.

## Dependencies and follow-up

Handlers delegate to application operations, domain models, result payload schemas, common envelope rendering, and the command materialization/runtime graph outside the assigned files. Synthesis should connect these declarations to actual registration and handler behavior, especially ledger file handling, and the effect route for destructive operations. Current legal accuracy and end-to-end CLI behavior are unverified.

## Complete assigned-file coverage

- `src/cadrumo/entrypoints/cli/__init__.py`
- `src/cadrumo/entrypoints/cli/_action_rendering.py`
- `src/cadrumo/entrypoints/cli/_actividad_asset_cli.py`
- `src/cadrumo/entrypoints/cli/_actividad_asset_payloads.py`
- `src/cadrumo/entrypoints/cli/_app_diagnostics.py`
- `src/cadrumo/entrypoints/cli/_app_diagnostics_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_actividad_asset_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_bienes_inversion_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_classification_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_policies.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_counterparty_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_evidence_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_evidence_followup_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_foundation_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_inventory_analysis_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_inventory_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_invoice_intake_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_invoice_lifecycle_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_lifecycle_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_management_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_participation_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_prorrata_command_specs.py`
- `src/cadrumo/entrypoints/cli/_app_ledger_ratios_command_specs.py`
<!-- /preserved:article -->
