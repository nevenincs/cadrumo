# Modelo projection, readiness, filing evidence and sharing surfaces

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-163` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope and behavior

This 19-file slice covers projection/comparison and readiness handlers, reconciliation and filing-record adapters, common rendering, review-package exchanges, spreadsheet command contracts, calculation and lifecycle commands, and their result schemas. I read all 5,501 lines (47,398 proxy tokens) across the nine planned pages. The code mainly coordinates typed requests and output envelopes around application/runtime services; this pass did not execute those services or contact external systems.

`modelo project` resolves the active profile, parses casilla/binding overrides, and presents M130 accumulated income/expenses and payments alongside an M100 projection for a year and CCAA. It preserves formula/legal/source references on casilla observations and explicitly labels quarter-based extrapolation. `modelo compare` requires exactly two years (the command defaults to Modelo 100), carries all delta rows and registry grounding in JSON, and suppresses rows that are zero in both years and in delta only in the text table. Both convert Decimal values through the canonical JSON output normalizer. Recovery translations are selected only from settled, registered failure codes rather than private worker error text (projection handlers (`src/cadrumo/entrypoints/cli/_modelo_projection_cli.py`), projection command specs (`src/cadrumo/entrypoints/cli/_modelo_projection_command_specs.py`)).

`modelo readiness` reads a profile/model/year target under a pinned authority generation, with an optional period and revision assertion. Its output explicitly says its readiness scope is profile and source preflight, not manual casilla completeness. It exits with code 2 when the target is not ready, and emits separate details for profile, registry, bindings, ledger transaction preflight, and export eligibility. If a model has no per-operation profile requirements, the command warns that `profile_ready` covers only export identity and conditional checks. This qualification helps prevent scripts and operators from interpreting readiness as a complete return review (readiness handler (`src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`), readiness command declaration (`src/cadrumo/entrypoints/cli/_modelo_readiness_command_specs.py`)).

Reconciliation has two explicit evidence paths: `pull` retrieves an AEAT justificante through the browser/runtime route, while `import` reconciles against a local PDF and does not contact AEAT. The `kind` axis distinguishes a justificante from a declaration document. Results include source kind/path, verdict, per-field differences, and advisories; history is scoped to the active profile and may filter by work unit. Filing-record import separately takes a typed evidence kind and reference plus either a local file or casilla values, never both; it projects the imported AEAT-attested baseline and reconciliation. `observe-local` reads CSV/XLSX casilla values or overrides, records an operator reason above an official observation layer, and can clear that local overlay. Its result and notice explicitly keep official evidence, filing-record creation, and AEAT acceptance false. Verification-report reads reuse the shared report projection rather than reconstructing recovery actions from historical prose (reconcile handler (`src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`), record and local-observation handlers (`src/cadrumo/entrypoints/cli/_modelo_records_cli.py`), filing and observation rendering (`src/cadrumo/entrypoints/cli/_modelo_rendering.py`)).

The common renderer projects lifecycle state, calculation snapshots, deadline posture, formula traces, source diagnostics, and filing/verification facts. It retains legal/source references in notices and exposes formula operand references and values when requested. Deadline output carefully labels any Article 27 rate preview `unassessed`, and the warning says it does not determine surcharge or interest liability. Calculation snapshots include visible casilla values, detail rows, result summaries, source provenance, registry snapshot identity, and lifecycle timestamps. `work calculate` validates operator amounts and rows, asserts the selected active-profile work unit, builds a canonical-JSON outbound request, submits it through the registered worker, and emits a saved draft revision plus structured source/deadline notices. Duplicate notices are removed by stable serialized identity. Work create is idempotent on the natural model/year/period/revision key; list hides discarded units by default; discard requires confirmation and retains lifecycle data through the operation rather than deleting revisions (renderer (`src/cadrumo/entrypoints/cli/_modelo_rendering.py`), calculate handler (`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`), lifecycle handler (`src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`)).

Review packages support local build, integrity verification, signing/counter-signing, signature/receipt verification, recipient encryption/decryption, and encrypted feedback exchange. The build path reuses the normal export safety gates and emits the export bucket event. `verify` checks package manifest integrity; the payload explicitly distinguishes that from signer authenticity, which belongs to signature/receipt commands. Private keys and ciphertext/plaintext bytes are excluded from result payloads, and decrypted plaintext is written only to the operator-selected path. The CLI performs local integrity and signature verification directly; secure signing, counter-signing, encryption, and feedback operations use the profile worker. The payloads expose checksums, public keys, recipient IDs, validity, and written paths, giving useful verification metadata without returning secrets (review-package handlers (`src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py`), result payloads (`src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py`)).

The spreadsheet command specs cover remote push/pull/calculate/verify and offline XLSX export. Their policies identify Google/network effects, profile-bound local writes, and file transport roles. Pull retrieves operator, binding, relation, and optional row-set edits; compute produces registry-grounded casilla results but does not persist; verify is declared to create/write the remote workbook before comparing results. Push's dry run reads remote state without writing. A real apply rewrites every cell in its plan rather than diffing the current workbook, so preview-only changed/unchanged counts do not describe a real apply. This overwrite behavior should be kept visible when assessing user-impact or retry semantics (spreadsheet specs (`src/cadrumo/entrypoints/cli/_modelo_spreadsheet_command_specs.py`), spreadsheet payloads (`src/cadrumo/entrypoints/cli/_modelo_spreadsheet_payloads.py`)).

## Findings and limits

One confirmed CLI diagnostic mismatch appears in `work_calculate`: the `--autoconsumo-promotor-base` parser passes the `sal_reserva_not_decimal` translation key, even though the adjacent shared helper declares the field-specific `autoconsumo_promotor_base_not_decimal` key. Invalid input for that option can therefore show the SAL-reserve error wording rather than naming the autoconsumo option. This affects refusal guidance, not the calculation result. The matching field-specific declaration is visible in the earlier shared parser (work calculation call site (`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`), shared field contract (`src/cadrumo/entrypoints/cli/_modelo_cli_support.py`)).

The strongest design qualities are explicit non-official versus AEAT-backed state, typed result envelopes, preserved provenance and authority-generation metadata, and clear classification of local, profile, browser, file, and Google effects. Some output is intentionally sensitive: calculation snapshots can contain taxpayer amounts/source fingerprints, filing views may include taxpayer identifiers, and Modelo 184 handoff notices include a member's NIF/name/attributed amount for manual cross-profile transfer. The review boundary limits that exposure for ordinary WorkReview output, but terminal/JSON consumers still need to treat full-detail commands as taxpayer data. Correctness of projections, browser pulls, signature/key custody, workbook overwrite atomicity, and external evidence authenticity depends on delegated services outside this chunk. No application operation was run.

## Coverage appendix

All 19 assigned files are represented and linked below.

- `src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads_m145.py`
- `src/cadrumo/entrypoints/cli/_modelo_projection_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_projection_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_readiness_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_records_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_rendering.py`
- `src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_review_package_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_review_package_rendering.py`
- `src/cadrumo/entrypoints/cli/_modelo_revision_payload_parts.py`
- `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_command_specs.py`
- `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_support_matrix_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_work_m303_attestation_cli.py`
<!-- /preserved:article -->
