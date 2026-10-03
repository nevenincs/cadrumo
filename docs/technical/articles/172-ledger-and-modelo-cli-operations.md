# Ledger and Modelo CLI operations

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-172` · **Topic:** [Operator interfaces, part 2: secure transport and operation bridges](../topics/operator-interfaces-part-2.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 51 CLI modules, 6,190 lines and 47,834 measured `o200k_base` proxy tokens. I read every manifest range across all ten bounded pages, including continuations at split-file boundaries. This is static analysis of command adapters; no application, worker, provider or test suite was executed. The files expose ledger history, edits, imports, evidence, inventory, lifecycle and review operations, plus Modelo calculation, filings, communication, IVA wallet and work-unit operations.

## Capabilities and how they work

Ledger users can review and retrieve transaction lists and individual records, inspect history/track/participation, and check status or period preflight. Handle-based readers first normalize a transaction ID prefix, submit it under the active profile, and require the response to name that profile and prefix with a no-effect receipt. A worker refusal for an unresolved prefix is mapped to the same no-recovery CLI policy as local validation (`runtime_ledger_prefix.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_prefix.py`), `runtime_ledger_prefix_read.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_prefix_read.py`), `runtime_ledger_history.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_history.py`)). These are prefix-scoped selections; uniqueness and collision policy ultimately depend on the shared resolver and worker.

The mutation bridge covers corrections, allocation, invoice evidence updates/removal, invoice linking, merge and split, archive/stash/restore/exclude, removal and catalogue reset. Requests are profile-bound and results are checked against submitted coordinates and the terminal operation receipt. Patch fields are serialized into stable wire forms and compared with the returned canonical transaction or evidence record. Merge checks that each submitted child prefix resolves one-to-one to a unique returned child; split checks child count/uniqueness and parent/child separation. Lifecycle operations require one update event and the expected new state, with exclusion additionally bound to its review status/classification (`runtime_ledger_update.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_update.py`), `runtime_ledger_merge.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_merge.py`), `runtime_ledger_split.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_split.py`), `runtime_ledger_lifecycle.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_lifecycle.py`)). Removal and reset support dry runs and correlate the reason, actor, dry-run flag and effect; reset requires `NONE` for preview and `UPDATED` for actual reset (`runtime_ledger_remove.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_remove.py`), `runtime_ledger_reset.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_reset.py`)). The irreversible scope and confirmation UX are outside these adapters and need checking in command definitions and workers.

Import/export flows accept bounded provider files, period/verification options, or an output path and format. The import bridge limits file count, anchors submitted paths to absolute caller paths without resolving symlinks, and correlates counts, selected period and dry-run/verify flags. Export correlates the exact destination, format, profile-owned rows and one mutation event. Invoice-evidence reads enforce unique profile-owned IDs; mutations compare every supplied field and allow zero events only for an empty patch. The export/link bridge distinguishes a closed no-effect refusal for a missing or cross-profile invoice from a successful link with one event (`runtime_ledger_import.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_import.py`), `runtime_ledger_export_link.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_export_link.py`), `runtime_ledger_evidence_mutation.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_mutation.py`)). Since import leaves symlink resolution to downstream code, the worker’s canonicalization and root policy should be verified before claiming a filesystem boundary.

Ledger rules and ratios provide profile-scoped list, create, preview/apply, validate, and override set/unset operations. Rule validation refusals require the declared code, no effect, and nonempty messages; a dry run must have no effect, while an apply’s effect follows its event count. Ratio set binds the returned category/value, eligible reads bind year and count, and censo mismatch/no-override outcomes are represented as explicit registered refusals. Inventory provides a profile catalogue, ledger creation, movement addition, valuation preview and immutable closing-authority record; the adapters translate allowlisted refusal reasons and serialize decimal values into the established result shape. Notably, valuation preview is accepted as `UPDATED` with one event because the operation records/audits the preview; the CLI cannot establish that it is state-free (`runtime_ledger_rules.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_rules.py`), `runtime_ledger_ratios.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_ratios.py`), `runtime_ledger_inventory.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_inventory.py`)). LLM diagnostics read canonical metric windows for a profile and threshold, with an explicit no-effect result; this exposes metrics but does not call an LLM in this adapter (`runtime_ledger_llm_diagnostics.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_llm_diagnostics.py`)).

Modelo commands operate on work units and tax-return records. The calculation adapter submits the canonical calculate request, allows a long 1,800-second settlement wait, and checks the returned work unit and current revision against the published calculation revision. It then projects casilla facts, formula/operand/provenance observations, summaries, details and lifecycle timestamps into CLI output; verbose traces are built from the stored observation fields rather than recomputing calculations locally (`runtime_modelo_calculation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_calculation.py`), `runtime_modelo_calculation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_calculation.py`)). Related commands verify a calculation-report digest, inspect cross-period dependencies, export a selected revision to a local artefact, and read audit bundles or reports (`runtime_modelo_calculation_report_verify.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_calculation_report_verify.py`), `runtime_modelo_dependencies.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_dependencies.py`), `runtime_modelo_export.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_export.py`), `runtime_modelo_audit.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_audit.py`)). Export requires a writer receipt marked `UPDATED`, and returns the worker’s file/report receipt; it does not itself prove the filesystem write’s durability or destination safety.

The filing adapters import, list and view external filing records; link observation layers to a filing; read/import a live Modelo 100 draft; amend an existing work unit; and record M303 attestation. Filing import accepts exactly one mode—spreadsheet path or casilla values—and correlates the imported evidence kind/reference and reconciliation outcome with the effect. Lists validate profile, optional Modelo, supersession and AEAT-acceptance consistency. Views adapt official, pending-local and override observations into the CLI payload. Local observation commands record or clear a period-scoped layer and compare all returned casilla values and actor/reason. The M303 adapter requires an explicit period and no work-unit result; filing/workflow semantics remain worker-owned (`runtime_modelo_filing_record_import.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_filing_record_import.py`), `runtime_modelo_filing_record_list.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_filing_record_list.py`), `runtime_modelo_filing_record_view.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_filing_record_view.py`), `runtime_modelo_local_observation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_local_observation.py`), `runtime_modelo_attestation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_attestation.py`)).

Other Modelo bridges cover work-unit rename/discard with a read-then-write observed timestamp/name baseline, annual aggregate and projection/comparison, invoice-withholding capture, IVA-wallet balance and operator seed/correction/override, M036 censal declarations, and M145 payer-communication records. Aggregation checks period/Modelo, a complete success payload and the expected withholding-window identity; invoice-withholding capture also requires a pinned baseline and positive generation. Wallet mutations echo amount, period, provenance or override evidence back into a profile-bound receipt. M145 provides create, validate, export, mark-delivered and mark-locally-completed transitions, correlating record state and declared refusal details. Maritime exemption is a no-effect preview from parsed inputs. These are integrations and presentation boundaries, not independent verification of the legal rules or of any official response (`runtime_modelo_aggregate.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_aggregate.py`), `runtime_modelo_invoice_withholding.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_invoice_withholding.py`), `runtime_modelo_iva_wallet_override.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_iva_wallet_override.py`), `runtime_modelo_m036.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_m036.py`), `runtime_modelo_m145_communication.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_m145_communication.py`), `runtime_modelo_maritime_preview.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_maritime_preview.py`)).

## Data, safety and assessment

Across these command families, the visible controls are exact profile binding, registered definition/version selection, result identity checks, and effect/terminal-state correlation. Reads generally require `NONE`; writes usually require `UPDATED`, with explicitly idempotent or repeated operations sometimes allowing `NONE`. Several interfaces deliberately preserve unknown outcomes and receipts on mismatch instead of retrying or claiming success. Declared refusal detail is translated only after the code and unchanged/no-effect receipt match. Prefixes are commonly used to address transaction or filing IDs; this is an intentional CLI handle model, but synthesis should resolve uniqueness and ambiguity behavior in the shared ID resolver.

Payloads contain taxpayer data: transaction descriptions and notes, invoice identifiers and amounts, casilla values, external filing references, NIFs, authority evidence, and file paths. These bridges send such facts into the profile worker and selectively reconstruct public result models; they do not establish encryption, log redaction, retention, provider freshness or authorization inside each worker. Local path resolution varies: filing import calls `resolve()`, while ledger import calls `absolute()` and explicitly does not resolve symlinks; live draft import passes a protected path to the worker. Trace file opening, size/type checks, path-root enforcement and export write behavior in their handlers. The adapters contain no test evidence, and static receipt checks cannot verify handler correctness or legal accuracy.

The principal architectural strength is that CLI responses are tied to the operation result and its effect, including detailed field-by-field correlation for edits, imports, amendments and review transitions. Follow-up should focus on the application handlers and persistence layer for inventory valuation and authority records; ledger reset/removal/import rollback and concurrency; filesystem and network access; Modelo registry/calculation and filing provenance; and the conditions under which an aggregation or invoice capture legitimately changes durable state. Verify whether the long settlement pending command is actionable and whether retries are idempotent for every mutation.

## Complete assigned-file coverage

All 51 assigned modules were fully read at their manifest-specified lines:

- `runtime_ledger_evidence_mutation.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_mutation.py`)
- `runtime_ledger_evidence_read.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_read.py`)
- `runtime_ledger_export_link.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_export_link.py`)
- `runtime_ledger_history.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_history.py`)
- `runtime_ledger_import.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_import.py`)
- `runtime_ledger_inventory.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_inventory.py`)
- `runtime_ledger_invoice_evidence.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_invoice_evidence.py`)
- `runtime_ledger_lifecycle.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_lifecycle.py`)
- `runtime_ledger_list.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_list.py`)
- `runtime_ledger_llm_diagnostics.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_llm_diagnostics.py`)
- `runtime_ledger_merge.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_merge.py`)
- `runtime_ledger_participation.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_participation.py`)
- `runtime_ledger_participation_rebuild.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_participation_rebuild.py`)
- `runtime_ledger_prefix.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_prefix.py`)
- `runtime_ledger_prefix_read.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_prefix_read.py`)
- `runtime_ledger_preflight.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_preflight.py`)
- `runtime_ledger_prorrata_register.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_prorrata_register.py`)
- `runtime_ledger_ratios.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_ratios.py`)
- `runtime_ledger_remove.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_remove.py`)
- `runtime_ledger_reset.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_reset.py`)
- `runtime_ledger_review.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_review.py`)
- `runtime_ledger_rules.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_rules.py`)
- `runtime_ledger_split.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_split.py`)
- `runtime_ledger_status.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_status.py`)
- `runtime_ledger_track.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_track.py`)
- `runtime_ledger_update.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_update.py`)
- `runtime_ledger_view.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_view.py`)
- `runtime_live_borrador.py` (`src/cadrumo/entrypoints/cli/runtime_live_borrador.py`)
- `runtime_modelo_aggregate.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_aggregate.py`)
- `runtime_modelo_amendment.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_amendment.py`)
- `runtime_modelo_attestation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_attestation.py`)
- `runtime_modelo_audit.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_audit.py`)
- `runtime_modelo_calculation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_calculation.py`)
- `runtime_modelo_calculation_report_verify.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_calculation_report_verify.py`)
- `runtime_modelo_dependencies.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_dependencies.py`)
- `runtime_modelo_export.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_export.py`)
- `runtime_modelo_filing_record_import.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_filing_record_import.py`)
- `runtime_modelo_filing_record_list.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_filing_record_list.py`)
- `runtime_modelo_filing_record_view.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_filing_record_view.py`)
- `runtime_modelo_history.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_history.py`)
- `runtime_modelo_invoice_withholding.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_invoice_withholding.py`)
- `runtime_modelo_iva_wallet_balance.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_iva_wallet_balance.py`)
- `runtime_modelo_iva_wallet_correction.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_iva_wallet_correction.py`)
- `runtime_modelo_iva_wallet_override.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_iva_wallet_override.py`)
- `runtime_modelo_iva_wallet_seed.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_iva_wallet_seed.py`)
- `runtime_modelo_local_observation.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_local_observation.py`)
- `runtime_modelo_m036.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_m036.py`)
- `runtime_modelo_m145_communication.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_m145_communication.py`)
- `runtime_modelo_maritime_preview.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_maritime_preview.py`)
- `runtime_modelo_metadata.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_metadata.py`)
- `runtime_modelo_projection.py` (`src/cadrumo/entrypoints/cli/runtime_modelo_projection.py`)
<!-- /preserved:article -->
