# CLI error handling, ledger actions, and Modelo work

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-170` · **Topic:** [Operator interfaces, part 2: secure transport and operation bridges](../topics/operator-interfaces-part-2.md)

<!-- preserved:article -->
## Scope

This chunk contains 14 CLI modules and all 5,345 assigned lines (46,371 measured proxy tokens). I read all nine bounded pages, covering the full error boundary, command entrypoint, ledger lifecycle handlers and schemas, Modelo work command contracts, workbook transport, and operator-surface reconciliation. This is static inspection only; I did not run a command, call a worker/provider, or verify emitted output against runtime services. The tokenizer count is a proxy, not an authoritative model context limit.

## CLI execution and failure behavior

`main()` builds the CLI from the declarative command graph, decorates command callbacks with a shared error boundary, configures UTF-8 output, disables Rich output, and lazily imports command families so help/version can avoid the full runtime graph. Ordinary invocations admit the shipped authority before dispatch; metadata invocations temporarily point storage/database settings at a temporary root and restore the prior environment afterward. A raw-argv language pre-parser promotes `--language`, `--lang`, or `--output-language` before help strings are imported, then clears the settings cache so the help tree observes the explicit choice. A separate `--cadrumo-command-surface` path emits graph-owned JSON contracts, policies, result/input schemas, and registration projections for an outer process to consume (CLI root (`src/cadrumo/entrypoints/cli/main.py`), language pre-parser (`src/cadrumo/entrypoints/cli/language_argv.py`)).

The boundary preserves Typer/Click control-flow exceptions, forwards typed `CadrumoError`s, distinguishes stored-record drift from bad invocation input and outbound-payload validation, and wraps otherwise unexpected failures as internal errors. A depth-bounded cause/orig walk recovers registered refusals wrapped by libraries such as SQLAlchemy. The recursive decorator covers materialized command and group callbacks, supports explicit skip paths, and memoizes wrappers. Error documents use the same registered code/exit mapping and carry dotted command identity, best-effort active-profile label, typed precondition action, and sandbox/authentication notices. The command and profile identity are intentionally null/best-effort when failure happens before dispatch or lookup fails. Stderr text passes through CLI redaction and UTF-8-safe output fallbacks (error callback boundary (`src/cadrumo/entrypoints/cli/errors.py`), error rendering (`src/cadrumo/entrypoints/cli/errors.py`), stderr writer (`src/cadrumo/entrypoints/cli/errors.py`), terminal emission (`src/cadrumo/entrypoints/cli/errors.py`)).

`_project_validation_error` passes `ValidationError.errors()` to the standard logger, but this call alone does not prove raw sensitive output: project logging installs a `SecretScrubbingFilter` that recursively scrubs supported mappings, sequences, message arguments, exceptions and extra fields before handlers format records, and the configured root logger/handlers and run sinks receive that filter (validation-error projection (`src/cadrumo/entrypoints/cli/errors.py`), recursive mapping/value scrubbing (`src/cadrumo/core/logging.py`), record filter (`src/cadrumo/core/logging.py`), handler installation (`src/cadrumo/core/logging.py`), run-sink installation (`src/cadrumo/core/logging.py`)). The CLI module obtains its logger with `logging.getLogger`, so configured handler filters still apply. A residual conditional concern is that Pydantic errors can place a rejected value under a generic `input` key while the sensitive schema field name appears separately in `loc`; confirm the scrubber's key/payload rules cover those shapes before concluding all such values are redacted. No end-to-end sensitive-value leak is demonstrated by these source paths. Unexpected exception tracebacks are logged at debug level, and the terminal receives a generic internal error (unexpected-error projection (`src/cadrumo/entrypoints/cli/errors.py`)).

## Ledger and evidence operations

Ledger lifecycle handlers attach/detach existing secure evidence, pull one linked document or Drive-folder children, archive/stash/exclude/restore transactions, remove/reset records, split a transaction, and merge a complete split cohort. Broad lifecycle changes require explicit `--yes`; remove/reset also offer a dry-run path. Drive folder references are parsed to a bare ID before being sent to the worker. Manual split requires matching amount/description lists and at least two children, parses amounts to Decimal, and requires confirmation. Children do not silently inherit the parent’s tax classification; a notice tells the operator to classify them. Merge likewise requires confirmation and at least two child IDs (ledger lifecycle handlers (`src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`), split and merge (`src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`)).

The LLM split path has separate preview and apply behavior. Preview reports proposed children and persists nothing; apply requires `--yes` and uses the registered review workflow. The handler compares the review to the requested transaction, correlates reviewed-proposal digest and provenance with the settled operation, and requires an updated effect before rendering persisted children. Application logic owns the split, classification, evidence, and registry-derived amounts, so those calculations are not independently verified in this CLI slice (LLM split review (`src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`)). Allocation and classification correlation helpers check exact profile, request-selected fields, expected classification/share/category/ratio/pro-rata values, event-derived effect, and validation-refusal shape before treating a worker projection as success (allocation correlation (`src/cadrumo/entrypoints/cli/ledger_allocate_correlation.py`), classification correlation (`src/cadrumo/entrypoints/cli/ledger_classify_correlation.py`), selected fields (`src/cadrumo/entrypoints/cli/ledger_classify_fields.py`), classification input projection (`src/cadrumo/entrypoints/cli/ledger_classify_inputs.py`)).

The business payload module defines strict wire schemas for inventory and purchase-invoice evidence. Inventory amounts remain canonical decimal strings with distinct percentage and unit-proportion bounds, exact enum values, and a canonical schema version. Its valuation preview revalidates nonnegative canonical totals. Evidence review payloads retain the printed value, extraction origin, grounding, verbatim anchor, refused-anchor reason, candidates, role evidence, deterministic blockers, and advisories; a confirmation carries both original extraction provenance and separately stamped operator corrections. Attachment review exposes non-secret provenance, while the consent inventory states in structured data that transmitted bytes are unrecallable. These schemas show what the CLI can report, not whether upstream extraction, consent recording, or invoice persistence is correct (ledger business payloads (`src/cadrumo/entrypoints/cli/ledger_business_payloads.py`)).

## Modelo work and workbook workflows

The Modelo work command graph declares calculate, create, dependencies, discard, list/select, rename/status/review, reports and report verification, revision/history, workflow runs, resume, verify, file, and wizard leaves. Policies distinguish profile-bound calculation/model writes, file handoff, local report export, and reads; required options declare local input/output transport. The full filing-year/model/revision and election inputs are typed in the graph, including explicit paired positive/negative boolean flags with no implicit answer. Those policies and parameter declarations make the surface auditable but still depend on the shared graph builder for concrete Click behavior (Modelo work command graph (`src/cadrumo/entrypoints/cli/modelo_work_command_specs.py`)).

Workbook commands export a local `.xlsx`, push a workbook to Google Sheets, pull operator-edited cells into typed projections, calculate from those edits without persisting, and verify a three-way comparison across the AEAT oracle, local Decimal runtime, and Sheets. The CLI parses period/year into a public period, delegates worker operations, and emits structured metadata, counts, edits, computations, URLs, and divergence rows. This is useful for review and parity investigation; it does not establish that an external oracle or workbook is authoritative or current (spreadsheet transport (`src/cadrumo/entrypoints/cli/modelo_spreadsheet_cli.py`)). Auxiliary result schemas carry evidence-bundle verification/export, work-event history, workflow-run state and typed details, and full `ModeloDescribeReport` metadata including authority grade and legal/source references. The revision renderer sorts observations by casilla for stable text output. Registry reference names and declared grades are projected here, not independently verified (Modelo auxiliary payloads (`src/cadrumo/entrypoints/cli/modelo_aux_payloads.py`), revision renderer (`src/cadrumo/entrypoints/cli/modelo_revision_rendering.py`)).

`operator_surface_reconciliation.py` derives live command identities, callback aliases, input names, result schema references, mounted families, profile policies, external exposure, and explicit root-landing exclusions from the same graph and schema projections. It validates identity correspondence and caches the full reconciliation only within the current Click/Typer invocation; target reconciliation loads only the command families on the path to one target. This provides an audit connection between declared CLI leaves and externally exposed operator surfaces, while completeness remains the full reconciler’s responsibility (surface reconciliation (`src/cadrumo/entrypoints/cli/operator_surface_reconciliation.py`)).

## Limits and follow-up

The strongest local properties are consistent typed errors, receipt correlation for ledger mutations, explicit confirmation and preview semantics, provenance-preserving evidence review schemas, and cross-checks between declared and exposed operator commands. Important follow-up is to inspect the logging configuration and sensitive-field policies for validation logs, inspect the actual Click construction of paired boolean declarations, and trace ledger/Modelo worker operations before making end-to-end mutation or filing claims. The snapshot omits tests, so none were run. This slice does not validate tax calculations, legal references, workbook parity, evidence extraction quality, AEAT connectivity, or persistence/network effects.

## Coverage appendix

All 14 assigned source files were read in full.

- `src/cadrumo/entrypoints/cli/errors.py`
- `src/cadrumo/entrypoints/cli/language_argv.py`
- `src/cadrumo/entrypoints/cli/ledger_allocate_correlation.py`
- `src/cadrumo/entrypoints/cli/ledger_business_payloads.py`
- `src/cadrumo/entrypoints/cli/ledger_classify_correlation.py`
- `src/cadrumo/entrypoints/cli/ledger_classify_fields.py`
- `src/cadrumo/entrypoints/cli/ledger_classify_inputs.py`
- `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`
- `src/cadrumo/entrypoints/cli/main.py`
- `src/cadrumo/entrypoints/cli/modelo_aux_payloads.py`
- `src/cadrumo/entrypoints/cli/modelo_revision_rendering.py`
- `src/cadrumo/entrypoints/cli/modelo_spreadsheet_cli.py`
- `src/cadrumo/entrypoints/cli/modelo_work_command_specs.py`
- `src/cadrumo/entrypoints/cli/operator_surface_reconciliation.py`
<!-- /preserved:article -->
