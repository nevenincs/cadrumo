# Modelo local records, wallet, preview, and non-work command contracts

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-162` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope

This 24-file chunk combines four concrete CLI adapters with most of the declarative command surface for Modelo features outside the core work commands, plus the shared output payload models. I read all 5,929 manifest lines (47,768 proxy tokens) across the nine planned pages. The handlers shown here parse and project operator requests; substantive storage, reconciliation, cryptographic, browser, and calculation behavior is delegated to runtime/application services, while the many `CommandSpec` modules declare how those commands are exposed and classified.

The M303 IVA-wallet group has a read-only balance command and three state-changing commands: seed a carry-forward amount, correct a seeded amount with a reason, and explicitly override the taxpayer carry with both a reason and evidence locator. The mutating commands require `--confirm`; amount strings share a canonical euro grammar with cent precision, avoiding ambiguity such as reading `1.000` as one euro. The balance payload validates nonnegative canonical amounts and lot/year constraints. The override result describes a taxpayer-selected authority and divergence, but its schema explicitly states that this only unblocks calculation; the dependent return still needs official evidence to pass verification. The source does not contact AEAT for the balance query (wallet CLI (`src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py`), wallet payloads (`src/cadrumo/entrypoints/cli/_modelo_iva_wallet_payloads.py`)).

The M036 commands create local declarations for alta, modificación, and baja, and list or view declarations for the active profile. Dates are parsed at the boundary; justificante and note are optional. View translates only the expected missing/ambiguous refusals, and checks their refusal/effect context before presenting the privacy-preserving not-found response. These are records of a declaration the operator says was filed, not a submission operation or independent proof of filing. M145 similarly manages local payer-communication records: create requires at least one casilla assignment, while validate, export, mark-delivered, and mark-locally-completed operate on a persisted communication record. Repeated assignment of the same casilla overwrites the earlier value in the parser's dictionary, so duplicate-key behavior is last-wins at this boundary; downstream intent should not rely on duplicate detection here. The renderers include record state and timestamps, validation issues, and the exported layout, byte length, digest, and rendered payload text (M036 commands (`src/cadrumo/entrypoints/cli/_modelo_m036_cli.py`), M145 parsing (`src/cadrumo/entrypoints/cli/_modelo_m145_parsing.py`), M145 handlers (`src/cadrumo/entrypoints/cli/_modelo_m145_cli.py`), M145 rendering (`src/cadrumo/entrypoints/cli/_modelo_m145_rendering.py`)).

The maritime-exemption work preview parses optional annual salary and gross navigation income through the shared decimal parser, applies output-language selection, calls the registered preview bridge, and emits profile facts and casilla observations with legal/source references. A RETMAR warning is rendered through the registered error-message catalogue. The preview's legal pathway and profile extraction stay in the application operation; this CLI layer does not establish tax-law correctness (maritime preview (`src/cadrumo/entrypoints/cli/_modelo_maritime_cli.py`)).

## Command surface and effects

The command-spec composer groups command declarations for discovery, bindings, aggregate/formulas/support matrix, filing records, verification reports, reconcile, M036, M145, work preview/amend wizard, IVA wallet, and review packages. Shared parameter contracts define common selectors and elections, including work-unit/model/year/period/revision/bucket selection and refund/payment/domiciliation defaults. The policies distinguish metadata and registry reads from calculation and local-state writes. They also mark reconciliation pull as browser/network I/O; export and M145 export as local handoff; review-package signing/encryption/import as profile-bound local writes; and package verification as crypto reads. Feedback encryption has a separate encrypted-facts/file-write route. The package commands declare file input/output loci and primary versus auxiliary paths, which helps identify where confidential material enters or leaves the CLI. These declarations describe the intended effect contract; the cryptographic and browser implementations are outside this chunk (policy declarations (`src/cadrumo/entrypoints/cli/_modelo_nonwork_command_spec_policies.py`), review-package specs (`src/cadrumo/entrypoints/cli/_modelo_nonwork_review_package_command_specs.py`), reconcile specs (`src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`), command composer (`src/cadrumo/entrypoints/cli/_modelo_nonwork_command_specs.py`)).

The filing-record command contracts separate list/view from import and local observation. Import requires an evidence kind and evidence identifier, accepts a primary local file and optional casilla overrides, and distinguishes declared filing kind. `observe-local` has a local-file input, a reason, and an explicit clear option, making it a separate local observation route. Verification reports have list/view commands; M145 export and reconciliation import are modeled as handoffs, while reconcile pull carries browser/network effects. These specifications are useful for surface and data-flow review, but they are not evidence that a selected file is authentic or that a browser pull succeeded.

## Payload guarantees and review limits

The shared `_modelo_payloads.py` module defines the public JSON envelopes for lifecycle and calculation revisions, verification and filing records, registry requirements, aggregation, work review, compare, project, and related commands. It retains domain identifier/enumeration types and uses validators where the wire boundary could otherwise make a stronger claim than the canonical result. Examples include: verification-finding prose is elided at 500 characters rather than dropping the finding; `ModeloRecordPayload` ties AEAT acceptance to confirmation and external-evidence presence, and checks supersession metadata; amendment output requires an `amends_filing_record_id`; imported filing output requires external evidence and derives evidence kind/reference from that evidence; and local observation output pins official-evidence, filing-record-created, and AEAT-accepted to false while checking action-specific detail shape and casilla count. `WorkReviewPayload` deliberately projects counts and sanitized findings instead of encrypted row-source identity details (finding and record models (`src/cadrumo/entrypoints/cli/_modelo_payloads.py`), record consistency (`src/cadrumo/entrypoints/cli/_modelo_payloads.py`), amend/import/local-observation contracts (`src/cadrumo/entrypoints/cli/_modelo_payloads.py`)).

The data-inventory and aggregation payloads preserve provenance and avoid misleading cross-checks. Requirements keep manual, detail-row, ledger, profile, prior-filing, relation, live-observation, and unbucketed sources distinct. Aggregate results project closed provider/source enums and unique source kinds from the canonical service result; withholding-window readback exposes generation/baseline metadata but not encrypted active entries. The schema explains why `observation_count` and per-clave withholding rows are not forced to match: they are projections of distinct stores, and some models consume one without the other. These are useful data-shape guarantees at the output boundary (requirements payload (`src/cadrumo/entrypoints/cli/_modelo_payloads.py`), withholding and aggregate payloads (`src/cadrumo/entrypoints/cli/_modelo_payloads.py`)).

One review seam is that the balance result applies explicit canonical amount validation, while seed and override result models declare amount as a plain string (and several related fields as broad primitives). Current handlers construct them from typed operation projections, which may be sufficient in the intended producer path, but this chunk does not demonstrate equivalent validation if those schemas are reconstructed from arbitrary data. Treat that as a contract question for the producer/schema boundary rather than a confirmed product defect. Likewise, the review-package specs reveal key/file pathways and trust-sensitive operations, but actual key custody, signature verification, encryption, and replacement/atomic-write behavior must be checked in their service implementations. No application or cryptographic operations were executed in this static pass.

## Coverage appendix

All 24 assigned files are linked below.

- `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_m036_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_m145_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_m145_parsing.py`
- `src/cadrumo/entrypoints/cli/_modelo_m145_rendering.py`
- `src/cadrumo/entrypoints/cli/_modelo_maritime_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_bindings_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_calculations_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_command_spec_policies.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_common_command_parameters.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_discovery_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_filing_record_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_groups_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_iva_wallet_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_m036_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_m145_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_review_package_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_verification_report_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_work_amend_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_nonwork_work_preview_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
<!-- /preserved:article -->
