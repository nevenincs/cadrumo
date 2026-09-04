---
tags:
  - '#reference'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:6e16f8d786045f6c4365b41cb9264a60e53c160596a4cd6fa9a2c74c11a85c7a'
related:
  - "[[2026-09-04-clitui-ledger-research]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---
# `clitui-ledger` reference: `CLI to backend capability authority census`

This reference maps the first semantic-search-led census of Ledger behavior owned by the CLI to existing or proposed frontend-neutral application homes. It is an initial denominator, not an exhaustive command-graph classification. Every implementation step must refresh affected rows against the live tree.

## Summary

### Campaign matrix publication

This document is the authoritative human-readable publication surface for the `LedgerCapabilityMatrixV1` campaign contract in `dev/quality/clitui_ledger_capability_matrix.py`. The S04 CLI, S05 backend-operation, S06 registry-route, and S07 supported-surface streams are now exact current observations, but the publication remains a **provisional baseline** rather than a serialized accepted matrix: S08 has not adjudicated the live union census, S09 has not recorded the cross-plan hold control, and S12-S14 have not reviewed and accepted the frozen denominator. The contract therefore requires the publication to fail closed instead of inventing a denominator digest, matrix digest, evidence attestation, or G0 closure.

| Publication field | Current value |
| --- | --- |
| Contract / schema | `LedgerCapabilityMatrixV1` / `3` |
| Publication revision | `s07-tui-census-2` |
| Observation timestamp | `2026-09-05T01:09:24+02:00` |
| Source revision | `6380cdbad299720c5909c2cd3fda42d32d6d12bd` |
| Contract source digest | `sha256:c2998c8ff958ae820b59fa7055a36d83117bb35282fe2679761032fab7a15a10` |
| Accepted plan owner | `clitui-ledger` |
| Denominator revision / digest | Not issued: mandatory S08 union adjudication remains open |
| Matrix digest | Not issued: a digest-bound `LedgerCapabilityMatrixV1` cannot exist before the complete denominator and current evidence subjects exist |
| Acceptance attestation | Absent by design: only S14 may record an independent `ACCEPT` ruling bound to the frozen digest |
| TUI hold | Campaign sequencing bars Ledger TUI implementation; the cross-plan recorded control remains open until S09 and row-level applicability/hold classification remains open until S08 and S11 |

#### Mandatory source-stream landscape

Every stream below must become one complete, readable, unambiguous, digest-bound `CensusStreamObservationV1`. A known count is baseline evidence only; it is not a declaration that the stream census is complete.

| Source stream | S03 observation | Readiness | Closure owner |
| --- | --- | --- | --- |
| `cli_endpoint` | 78 invocable endpoints: 77 leaves and executable `participation`; each has an exact path, handler, schema, TUI declaration, and ownership annotation | Complete current CLI stream; not a union-denominator attestation | S04 complete |
| `cli_suboperation` | 50 explicit behavior-distinct sub-operations across ten overloaded endpoints | Complete current CLI stream; not a union-denominator attestation | S04 complete |
| `backend_only` | 63 public frontend-neutral operations are catalogued below; the installed workspace read/projection is the one backend-only product capability absent from the CLI census | Complete current backend-operation stream; product-row admission remains open | S05 complete; S08 adjudication |
| `missing_product` | Ten baseline product/provenance families are confirmed absent or incomplete below | Complete current S05 product-gap observation; union review and canonical row admission remain open | S05 complete; S08 adjudication |
| `registry_route` | Seven families, 546 declarations, 35 family/revision sites, 510 registry-bound destinations, three application-sidecar destinations, and 33 destinationless declarations are enumerated below | Complete current registry stream; not a union-denominator attestation | S06 complete; S08 adjudication |
| `artifact_product` | Flat CSV/JSONL/XLSX exists; M369 has a successful Modelo export path, while observed M100/M303/M390 routes refuse unavailable layouts; review package, Google transport, and recovery archive remain distinct missing products | Complete current S05/S06 application-product observation; row admission remains open | S08 adjudication |
| `supported_surface` | Seven internal routes and seven concrete route screens exist; Overview is installed read-only through the outer Ledger destination, the other six remain component-only, no installed consumer handles internal Ledger route/action messages, and no mutation door is installed | Complete current supported-surface stream with committed drift detector; capability-row applicability remains open | S07 complete; S08 adjudication |

#### Axis contract and publication notation

The eight independent axes are `backend`, `cli`, `tui`, `composition`, `artifact`, `provenance`, `registry`, and `proof`. A reviewed row will carry `applicable` or `not_applicable` plus `unproven`, `partial`, or `proven`; backend/CLI/TUI additionally carry `absent`, `partial`, or `proven`. Ownership and reachability use the independent annotations `cli_owned`, `delegating`, `component_only`, and `installed`. In the provisional tables, `REVIEW` means the S07/S08 applicability decision has not happened and therefore no contract state is asserted.

| Profile | Backend | CLI | TUI | Composition | Artifact | Provenance | Registry | Proof |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AUTHORITY` | `applicable`; `absent` or `partial`; `unproven`/`partial` | `applicable`; `partial`; `cli_owned` | `REVIEW` | `REVIEW` | `REVIEW` | `REVIEW` | `REVIEW` | `applicable`; `unproven`/`partial` |
| `DELEGATE` | `applicable`; current primitive present; proof bounded below | `applicable`; parser/adapter exists; delegation proof remains open | `REVIEW` | `REVIEW` | `REVIEW` | `REVIEW` | `REVIEW` | Current proof is bounded to cited behavior, never whole-row completion |
| `PRODUCT` | `applicable`; `absent`; `unproven` | Surface applicability remains for S08 | `REVIEW` | `applicable`; `unproven` | `applicable`; `unproven` where artifact-bearing | `applicable`; `unproven` | `REVIEW` | `applicable`; `unproven` |
| `REGISTRY` | `applicable`; `partial` | `REVIEW` | `REVIEW` | `applicable`; `partial` | `REVIEW` | `applicable`; `partial` | `applicable`; `partial` | `applicable`; `partial` or `unproven` per the registry table below |

#### Provisional capability rows

These 41 family rows are the S03 baseline keys. They are not yet admitted `LedgerCapabilityRowV1` instances: S04-S07 may split them into endpoint/sub-operation rows or add rows from another stream, and S08 must adjudicate their canonical identity, applicability, exact command type, and exact result type. The table names the candidate semantic owner and the planned step that must turn that candidate into an exact typed contract.

| Baseline row key | Profile | Candidate semantic owner and typed-contract closure | Open gap / next evidence |
| --- | --- | --- | --- |
| `ledger.transaction.create` | `AUTHORITY` | `application/ledger/operator_commands.py`; exact command/result in S23 and S70 | `authority`; disposition and backend direct proof in S04/S05 then S23/S34 |
| `ledger.transaction.allocate` | `AUTHORITY` | `application/ledger/operator_commands.py`; exact command/result in S24 and S70 | `authority`; S24/S28/S34 |
| `ledger.transaction.classify_direct` | `AUTHORITY` | `application/ledger/operator_commands.py`; discriminated command/result in S24 and S70 | `authority`; S24/S28/S34 |
| `ledger.transaction.classify_m210` | `AUTHORITY` | `application/ledger/operator_commands.py`; discriminated command/result in S24 and S70 | `authority`; S24/S30/S34 |
| `ledger.transaction.invoice_link` | `DELEGATE` | `application/ledger/actions_manual.py`; current atomic writer/result, exact facade disposition in S08/S70 | Duplicate CLI policy; S04/S08 adjudication |
| `ledger.transaction.query` | `AUTHORITY` | `application/ledger/query_service.py`; query/result in S15 and S70 | `authority`, `product`, `proof`; S15/S18/S22 |
| `ledger.transaction.composite_read` | `AUTHORITY` | `application/ledger/composite_reader.py`; discriminated read result in S16 and S70 | `authority`, `composition`, `proof`; S16/S19/S22 |
| `ledger.classification.rule_preview` | `AUTHORITY` | `application/ledger/actions_classification.py`; preview result in S25 and S70 | `authority`, `proof`; S25/S32/S34 |
| `ledger.import.per_file` | `DELEGATE` | `application/ledger/actions_import.py`; existing typed import result, exact row contract in S08 | Direct proof bounded to one source; S05/S08 |
| `ledger.import.multi_source` | `AUTHORITY` | `application/ledger/import_workflows.py`; plan/batch result in S36 and S70 | `authority`, `composition`, `proof`; S36/S44/S53 |
| `ledger.evidence.drive_ingest` | `AUTHORITY` | `application/ledger/provider_evidence_workflows.py`; item/batch result in S38 and S70 | `authority`, `composition`, `proof`; S38/S46/S53 |
| `ledger.evidence.extraction_consent` | `AUTHORITY` | `application/ledger/review_workflows.py`; consent outcome in S40 and S70 | `authority`, `composition`; S40/S48/S53 |
| `ledger.evidence.review` | `AUTHORITY` | `application/ledger/review_queries.py` and `review_workflows.py`; query/disposition results in S17/S40/S70 | `authority`, `composition`, `proof`; S17/S21/S40/S53 |
| `ledger.evidence.consent_survey` | `AUTHORITY` | `application/ledger/review_queries.py`; port-backed projection in S17 and S70 | `authority`, `composition`; S17/S50/S53 |
| `ledger.llm.routing` | `AUTHORITY` | `application/ledger/llm_workflows.py`; discriminated terminal outcome in S42 and S70 | `authority`, `composition`, `provenance`; S42/S52/S53 |
| `ledger.invoice.workflow` | `AUTHORITY` | `application/ledger/invoice_workflows.py`; workflow results in S54 and S70 | `authority`, `composition`; S54/S60/S68 |
| `ledger.ratio.workflow` | `AUTHORITY` | `application/ledger/ratio_workflows.py`; atomic result in S56 and S70 | `authority`, `composition`, `proof`; S56/S63/S68 |
| `ledger.counterparty.confirmation` | `AUTHORITY` | `application/ledger/counterparty_establishment.py`; typed confirmation outcome in S55/S70 | `authority`, `proof`; S55/S61/S68 |
| `ledger.prorrata.workflow` | `AUTHORITY` | `application/ledger/prorrata_workflows.py`; operator-command result in S57/S70 | `authority`, `composition`, `proof`; S57/S65/S68 |
| `ledger.investment_goods.workflow` | `AUTHORITY` | `application/ledger/investment_goods_workflows.py`; acquisition/disposal result in S58/S70 | `authority`, `composition`, `proof`; S58/S66/S68 |
| `ledger.inventory.workflow` | `DELEGATE` | `application/ledger/InventoryService`; exact command/result in S08/S70 | Backend primitive exists; surface delegation and direct-proof scope need S04/S05/S08 |
| `ledger.payload.projection` | `AUTHORITY` | `application/ledger/models.py`; immutable result models in S70 | `authority`, `product`; CLI-local fact redeclaration census in S04 |
| `ledger.export.flat` | `DELEGATE` | `src/cadrumo/application/ledger/actions_export.py`; current flat export, completed manifest/result in S87/S91 | `artifact`, `proof`; flat product only, not restore |
| `ledger.export.review_package` | `PRODUCT` | `src/cadrumo/application/ledger/review_exchange.py`; plan/result in S88/S91 | `product`, `artifact`, `provenance`, `proof` |
| `ledger.export.google_transport` | `PRODUCT` | `src/cadrumo/adapters/outbound/google/ledger_review_exchange.py` over the transport-neutral review plan; result in S89/S91 | `product`, `composition`, `artifact`, `proof` |
| `ledger.export.restore_archive` | `PRODUCT` | `src/cadrumo/application/ledger/recovery_archive.py`; versioned export/restore results in S90/S91 | `product`, `artifact`, `provenance`, `proof` |
| `ledger.evidence.download` | `PRODUCT` | `src/cadrumo/application/ledger/evidence_lifecycle.py`; download result in S82/S86 | `product`, `artifact`, `proof` |
| `ledger.evidence.replace` | `PRODUCT` | `src/cadrumo/application/ledger/evidence_lifecycle.py`; atomic replacement result in S82/S86 | `product`, `composition`, `provenance`, `proof` |
| `ledger.note.append` | `PRODUCT` | `src/cadrumo/application/ledger/notes.py`; append-only and batch result in S80/S86 | `product`, `provenance`, `proof` |
| `ledger.field_change.provenance` | `PRODUCT` | `src/cadrumo/domain/transactions/change_provenance.py`; exact field history in S84/S86 | `product`, `provenance`, `proof` |
| `ledger.manual_override.provenance` | `PRODUCT` | `src/cadrumo/domain/transactions/change_provenance.py`; override basis and authority history in S84/S86 | `product`, `provenance`, `proof` |
| `ledger.import.normalization_provenance` | `PRODUCT` | `src/cadrumo/domain/transactions/change_provenance.py`; source-column mapping and normalized-value history in S84/S86 | `product`, `provenance`, `proof`; CLI projection in S113 |
| `ledger.fx.provenance` | `PRODUCT` | `src/cadrumo/domain/transactions/models.py`; original/normalized currency, rate source/date, and operation identity in S85/S86 | `product`, `provenance`, `proof`; filing evidence in S100 and CLI projection in S113 |
| `ledger.transaction.batch_patch` | `PRODUCT` | `src/cadrumo/application/ledger/change_sets.py`; version-bound atomic multi-row result in S78/S86 | `product`, `composition`, `provenance`, `proof` |
| `ledger.registry.iva` | `REGISTRY` | registry binding/resolution and calculation route; exact route contract in S06/S100 | `registry`, `proof`; 31 destinationless declarations, nonzero M309/M322/M353 production proof, and general unrouted-observation filing refusal remain open |
| `ledger.registry.oss` | `REGISTRY` | registry binding/resolution and M369 route; exact route contract in S06/S100 | Preserve issued-invoice-catalogue distinction; proof bounded below |
| `ledger.registry.renta_expense` | `REGISTRY` | registry binding/resolution and M100 route; exact route contract in S06/S100 | Preserve evidence and deduction-ratio requirements |
| `ledger.registry.renta_income` | `REGISTRY` | registry binding/resolution and M100/M130/M131 routes; exact route contract in S06/S100 | `registry`, `proof`; M131 live path, one M130 c06 application sidecar, and two destinationless M130 declarations remain open |
| `ledger.registry.m130_expense` | `REGISTRY` | registry binding/resolution and M130 c02 route; exact route contract in S06/S100 | `registry`, `proof`; explicit nonzero c02 route assertion open |
| `ledger.registry.impatriado_income` | `REGISTRY` | registry binding/resolution and M151 route; exact route contract in S06/S100 | `registry`, `proof`; calculate-to-export proof and manual savings base open |
| `ledger.registry.irnr_income` | `REGISTRY` | registry binding/resolution and M210 route; exact route contract in S06/S100 | Preserve explicit classification and mutual exclusion; both revisions use an application sidecar rather than a registry destination, and export/file proof remains open |

#### Evidence-coordinate register

These coordinates bind the S03 claims to the current observation revision. They are publication locators, not contract `EvidenceCoordinateV1` objects yet; S08/S12 must assign row/axis roles and current subject snapshots before admission.

| Coordinate | Locator | Subject digest | Claim boundary |
| --- | --- | --- | --- |
| `evidence.baseline.matrix_contract` | `dev/quality/clitui_ledger_capability_matrix.py:22` | `sha256:c2998c8ff958ae820b59fa7055a36d83117bb35282fe2679761032fab7a15a10` | Schema 3, eight axes, source kinds, gaps, controls, evidence currentness, and G0-G4 predicates |
| `evidence.s04.cli_command_census` | `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:51` | `sha256:2cd8e21e2b8602e5e18338c22350301f2bc76f580873af51b1154d5364e6769b` | Exact current CLI stream: 78 invocables, 50 supplemental behavior-distinct sub-operations across ten overloaded endpoints, derived path/handler/schema/TUI facts, and fail-closed ownership annotations |
| `evidence.s05.backend_operation_census` | `src/cadrumo/application/ledger/` operational modules listed in the backend census | `sha256:4b0d917dd20d155f348958559037695cb5bab356867a1c88305bb42080f3b2f0` | Exact current backend observation: 63 operations, actual request/result contracts, direct-test locators, production compositions, and the one backend-only product capability |
| `evidence.baseline.cli_authority` | `2026-09-04-clitui-ledger-reference`, CLI-to-backend disposition matrix | Bound by this document's CLI-maintained `body_hash` after publication | Initial authority families and candidate application homes |
| `evidence.baseline.backend_behavior` | `2026-09-04-clitui-ledger-reference`, Direct backend behavior gate | Bound by this document's CLI-maintained `body_hash` after publication | Existing direct-proof boundaries and missing facades |
| `evidence.baseline.missing_products` | `2026-09-04-clitui-ledger-reference`, Missing capability and reuse map | Bound by this document's CLI-maintained `body_hash` after publication | Explicit product/artifact/provenance gaps |
| `evidence.s06.registry_declaration_sources` | `ledger_registry_source_set_digest` over the 130 registry TOML files whose binding rows declare a member of `LEDGER_BINDING_SOURCE_KINDS` | `sha256:194a9f26ddfbae6c5d7f265ffe58f50964fbe2fcd02a5670fa19845dead5cf6d` | Domain-separated source-set v1 bytes; each sorted source-root-relative POSIX path and file body is independently unsigned-8-byte-big-endian length framed |
| `evidence.s06.registry_route_census` | `build_ledger_registry_route_census` in `dev/quality/clitui_ledger_capability_matrix.py`, derived from `ValidatedRegistryAuthority` through `casillas_by_binding` | `sha256:20b2d2df5558b2a3fdbd1eab6e9f781a973e93c6211e211f8e679cf7b4782aca` | Strict route-census v1 root and rows; domain-separated, length-framed canonical JSON; all 546 declarations, 510 registry-bound and 36 without a registry binding/casilla edge |
| `evidence.s06.production_consumers` | `src/cadrumo/application/modelo/calculation_route.py:112`; `src/cadrumo/application/modelo/calculation_actions.py:767`; `src/cadrumo/application/aggregation/_modelo_bindings.py:171`; `src/cadrumo/application/aggregation/modelo_bindings_renta_expenses.py:48`; `src/cadrumo/application/aggregation/_oss_ioss.py:504` | Bound by this document's CLI-maintained `body_hash` after publication | Unique production ownership for all seven families; three explicit application-sidecar destinations; exact proof and refusal limits below |
| `evidence.s07.tui_supported_surface` | `build_ledger_tui_supported_surface_census` in `dev/quality/clitui_ledger_capability_matrix.py` | `sha256:c136cfe1ae3f82a239476c00e805f8c9a29e010d502e74397963cea7e6f42371` | Strict supported-surface census v1; Overview installed read-only, six component-only routes, one outer destination, two injected read-action references, zero installed mutation doors, zero installed message consumers, 78 CLI `not-implemented` declarations, and six focused harness files with 65 test functions |
| `evidence.baseline.cli_boundary` | `2026-09-04-clitui-ledger-reference`, Valid CLI boundary | Bound by this document's CLI-maintained `body_hash` after publication | Allowed adapter concerns and forbidden business ownership |

#### Gate summary

| Gate | State at S03 | Blocking facts |
| --- | --- | --- |
| G0 denominator and ownership freeze | **OPEN** | S04-S07 current source observations are complete, but S08 union adjudication, S09/S11 hold records, S12 row review, S13 reopening detector, and S14 digest-bound independent `ACCEPT` remain outstanding |
| G1 semantic authority recovery | **LOCKED by G0** | `AUTHORITY` rows retain CLI-owned or missing application authority; no cohort may claim closure before its backend behavior and adapter detector evidence exists |
| G2 backend product completeness | **LOCKED by G0/G1** | Missing products, composition, artifacts, provenance, registry routes, and direct proof remain open |
| G3 CLI clean break and completeness | **LOCKED by G0-G2** | CLI delegation, success/refusal behavior, and artifact proof are not complete across the admitted denominator |
| G4 TUI admission and parity | **HELD and LOCKED by G0-G3** | No Ledger TUI implementation is authorized; component existence and installed reachability remain separate, and S09/S11 must record the hold before G0 can close |

Any new endpoint, sub-operation, backend-only operation, missing product, registry route, artifact, or supported surface invalidates the corresponding current source report and reopens G0 plus all later gates. The detailed baseline sections below remain the single homes for changing counts and proof findings; this publication layer references them rather than restating their evidence.

### Live command denominator

The production `COMMAND_GRAPH` currently contains 91 nodes below `aeat app ledger`: 77 leaf nodes, 14 groups, and the executable `participation` group, for 78 invocable command endpoints. `LEDGER_CLI_COMMAND_CENSUS` derives each invocable's exact path, command key, deferred handler, result-schema identity, and TUI metadata from `LEDGER_COMMAND_SPECS`; it rejects unknown, missing, duplicate, unavailable-handler, and unavailable-schema annotations. A new invocable cannot acquire a default ownership verdict. This projection keeps `COMMAND_GRAPH` and `LEDGER_COMMAND_SPECS` as the sole endpoint authorities, and only supplies non-derivable behavior modes plus the observed adapter burden. It replaces the historical 26-verb count in the 2026-06 interface ADR for this campaign.

The exact current ownership inventory is 44 `policy-bearing`, 27 `mixed`, and 7 `transport-only` invocables. `policy-bearing`: `ledger.add`, `ledger.allocate`, `ledger.bienes_inversion.declare`, `ledger.bienes_inversion.list`, `ledger.check`, `ledger.classify`, `ledger.counterparty.confirm`, `ledger.counterparty.view`, `ledger.counterparty.withdraw`, `ledger.evidence.consent.list`, `ledger.evidence.consent.rederive`, `ledger.evidence.extract`, `ledger.evidence.pull`, `ledger.evidence.pull_all`, `ledger.evidence.review.list`, `ledger.evidence.review.view`, `ledger.history`, `ledger.import`, `ledger.invoice.add`, `ledger.invoice.import`, `ledger.invoice.list`, `ledger.invoice.wizard`, `ledger.link`, `ledger.list`, `ledger.preflight`, `ledger.prorrata.declare_sector`, `ledger.prorrata.elect_especial`, `ledger.prorrata.elect_general`, `ledger.prorrata.list`, `ledger.prorrata.revoke_especial`, `ledger.prorrata.seed`, `ledger.prorrata.seed_sector`, `ledger.prorrata.settle_sector`, `ledger.ratios.eligible`, `ledger.ratios.list`, `ledger.ratios.set`, `ledger.ratios.unset`, `ledger.ratios.validate`, `ledger.review`, `ledger.rule.apply`, `ledger.split`, `ledger.status`, `ledger.track`, `ledger.view`. `mixed`: `ledger.archive`, `ledger.attach`, `ledger.categories`, `ledger.detach`, `ledger.evidence.add`, `ledger.evidence.attachment_queue`, `ledger.evidence.attachment_view`, `ledger.evidence.batch`, `ledger.evidence.confirm`, `ledger.evidence.list`, `ledger.evidence.remove`, `ledger.evidence.update`, `ledger.evidence.view`, `ledger.exclude`, `ledger.export`, `ledger.invoice.remove`, `ledger.invoice.update`, `ledger.invoice.view`, `ledger.llm_diagnostics`, `ledger.merge`, `ledger.remove`, `ledger.reset`, `ledger.restore`, `ledger.rule.add`, `ledger.rule.list`, `ledger.stash`, `ledger.update`. `transport-only`: `ledger.inventory.closing-authority.record`, `ledger.inventory.create`, `ledger.inventory.list`, `ledger.inventory.movement.add`, `ledger.inventory.valuation.preview`, `ledger.participation`, `ledger.participation.rebuild`.

The 50 behavior-distinct supplemental sub-operation identities are `ledger.classify.direct`, `ledger.classify.m210`, `ledger.classify.iva_derive`, `ledger.classify.llm_preview`, `ledger.classify.llm_apply`, `ledger.classify.llm_reject`, `ledger.classify.llm_saturate_preview`, `ledger.classify.llm_saturate_apply`, `ledger.classify.llm_saturate_reject`, `ledger.classify.evidence_read`, `ledger.classify.auto_split.reject`, `ledger.classify.auto_split.split_preview`, `ledger.classify.auto_split.split_apply`, `ledger.classify.auto_split.single_preview`, `ledger.classify.auto_split.single_apply`, `ledger.classify.bulk_csv`, `ledger.evidence.pull.gmail`, `ledger.evidence.pull.drive`, `ledger.evidence.pull.url`, `ledger.export.csv`, `ledger.export.jsonl`, `ledger.export.xlsx`, `ledger.history.direct`, `ledger.history.split_siblings`, `ledger.import.file`, `ledger.import.directory`, `ledger.import.dry_run`, `ledger.import.verify`, `ledger.import.provider_auto`, `ledger.import.provider_csv`, `ledger.import.provider_ofx_qfx`, `ledger.import.provider_xlsx_excel`, `ledger.import.provider_n26`, `ledger.import.provider_pdf`, `ledger.import.provider_pdf_n26`, `ledger.list.filter`, `ledger.list.group`, `ledger.list.sort`, `ledger.list.page`, `ledger.list.rejected_llm_filter`, `ledger.remove.preview`, `ledger.remove.commit`, `ledger.reset.preview`, `ledger.reset.commit`, `ledger.rule.apply.preview`, `ledger.rule.apply.commit`, `ledger.split.manual`, `ledger.split.llm_preview`, `ledger.split.llm_apply`, and `ledger.split.evidence_read`. Auto-split separately records refusal and the split/single preview and apply outcomes because their refusal, result type, and persistence effects differ. Equivalent parser aliases (`qfx`/`ofx`, `excel`/`xlsx`) remain one capability because their importer effect is the same; enum tokens alone do not inflate the denominator.

The leaf families contain evidence 10, lifecycle 10, prorrata 8, foundation 6, operations 6, management 6, invoice lifecycle 5, ratios 5, evidence follow-up 4, counterparty 3, inventory 3, rules 3, bienes de inversión 2, inventory analysis 2, invoice intake 2, classification 1, and participation rebuild 1. All 78 invocables, including the executable group, currently declare `TuiCapability.NOT_IMPLEMENTED`; this command metadata is distinct from the separate installed workbench components and is another reason the matrix must not conflate CLI enrollment, TUI component existence, and installed reachability. S04 establishes only the complete CLI stream and current observations: G0 remains open until every other mandatory stream is collected, row applicability and semantic homes are adjudicated, the TUI hold is recorded, and independent review accepts a digest-bound union denominator.

Focused command-graph/spec tests passed 27 tests, the root Ledger help and all 13 nested group help invocations exited zero. A broader generated-reference run had 19 passing tests and one unrelated failure caused by a config-profile `archive import` versus `restore` mismatch; it does not contradict the exact Ledger tree comparison, but remains visible as pre-existing global documentation drift.

### Live TUI supported-surface denominator

The Ledger TUI package contains seven concrete route screens and seven one-to-one internal route declarations: Overview, Entries, Review, Import, Classification, Evidence, and Reconciliation. `LedgerUnavailableScreen` is a typed refusal body, while `LedgerWorkspaceScreen` and `LedgerConfirmationFlowScreen` are shared bases rather than additional destinations. One `LedgerWorkspaceController`, one `ledger_screen_factory`, and one `resolve_ledger_screen` router join those components. The canonical census classifies each route separately from the outer destination instead of turning component existence into an installed-capability verdict.

| Internal destination | Component / factory | Component behavior | Production-installed state |
| --- | --- | --- | --- |
| `ledger.overview` | `LedgerOverviewScreen` | Read-only area summary, quality, and affected-declaration projection | `installed`: the production `workbench.ledger` composition invokes `ledger_screen_factory`, resolves the Overview target, and returns this operator-reachable read body |
| `ledger.entries` | `LedgerEntriesScreen` | Read-only responsive transaction catalogue and semantic row selection | `component_only`: declared and projection-backed; not independently enrolled in installed navigation |
| `ledger.review` | `LedgerReviewScreen` | Read-only review rows; selecting a row emits `LedgerReviewRequested` | `component_only`: production injects the `operator.ledger.review` reference, but no installed consumer of `LedgerReviewRequested` was located, so selection does not execute the command |
| `ledger.import` | `LedgerImportScreen` | Confirm/cancel flow over an opaque prepared import command | `component_only`: production supplies neither prepared imports nor an import submitter, so the controller returns a typed refusal |
| `ledger.classification` | `LedgerClassificationScreen` | Explicit business/personal/excluded patch confirmation through an injected submitter | `component_only`: production supplies no classify action, target, or submitter, so the controller returns a typed refusal |
| `ledger.evidence` | `LedgerEvidenceScreen` | Read-only safe attachment-review metadata; selection emits `LedgerEvidenceReviewRequested` | `component_only`: production injects the evidence-review action and per-visit queue, but no installed consumer of `LedgerEvidenceReviewRequested` was located, so selection does not execute the command |
| `ledger.reconciliation` | `LedgerReconciliationScreen` | Read-only local link suggestions/inconsistencies; optional confirmed link submission | `component_only`: the read body renders, but production supplies no link action or submitter, so mutation controls remain hidden |

The outer root catalogue does install `workbench.ledger` when the application generation contains a Ledger projection and its admission is available. That outer installation must not be projected onto all seven internal destinations. Its factory always returns Overview first. Internal selections post `LedgerRouteRequested`; review and evidence selections post their corresponding request messages; Back posts `LedgerBackRequested`. Exact search across the installed TUI finds declarations and emitters but no handler or other consumer for any of those four Ledger message types. Therefore the current installed operator-reachable Ledger body is Overview only, and even that body cannot navigate to the other declared components through the production root. This observation is stricter than saying the screens merely lack CLI parity: the route bridge itself is disconnected.

`LedgerTuiSupportedSurfaceCensusV1` is the committed projection owner. Its source selector currently yields 126 repository-relative files: every production Python module below `src/cadrumo/entrypoints/tui/` except tests and devtools; the three dedicated Ledger harness files; the three installed generation/workbench/launcher harness files; four application workspace/search-generation sources; and every `_app_ledger*_command_specs.py` module. Sorted paths and raw bodies are each framed with an unsigned eight-byte big-endian length after the `cadrumo:ledger-tui-supported-surface-source-set:v1` NUL-terminated domain; the current source-set digest is `sha256:e7337508a02ef2260e0b28205c31bb872b69f59aa51a18391ae209c21b8f9d57`. The canonical ASCII JSON projection is independently length-framed after `cadrumo:ledger-tui-supported-surface-census:v1`. Tests pin both live digests, normalize irrelevant record order, and detect new or missing routes, missing screens, new scanned files, message consumers, installed mutation doors, CLI TUI status changes, and reachability-classification drift.

Production composition injects exactly two Ledger action references, `operator.ledger.review` and `operator.ledger.evidence.review.list`, and reads the evidence review queue at screen-factory invocation. It injects zero executable mutation doors: no classification submitter, import submitter, or link submitter. The component harness separately supplies synthetic doors for classification, one-file import, and invoice/transaction linking; those tests prove frontend behavior behind an injected contract, not production enrollment. None of the 78 CLI invocables changes this verdict: all 78 command specs independently declare `TuiCapability.NOT_IMPLEMENTED`, which is CLI global-`--tui` metadata rather than evidence that a similarly named TUI component is installed.

The installed projection path is real and backend-owned. `SecureProfileWorkbenchGenerationReadDoorV1` reads transaction, invoice, event, calculation-revision, and work-unit stores; `read_ledger_workspace_projection` builds the immutable Ledger workspace; `assemble_workbench_generation` carries it; the installed launcher binds it to the outer factory. The same projection is also consumed by installed workbench search to create Ledger-entry search documents. These are backend-only workspace projection consumers, not evidence that CRUD, batch, attachment lifecycle, export, currency-normalization disclosure, or registry/calculation operations are available in the TUI.

The dedicated component harness has 38 test functions and 78 collected integration cases across three files. It covers all seven screens with synthetic fully populated injection, flow refusal and submission, semantic focus, four locales, safe evidence metadata, responsive geometry, and import-boundary checks. The installed-composition tests prove the outer `workbench.ledger` catalogue enrollment and projection/factory parity, but no test drives a production root from Overview through an internal Ledger route or executes a Ledger request message. Harness coverage is therefore `partial` for installed reachability and executable-operation enrollment even though component coverage is broad.

S07 assigns no final TUI applicability or row state. Every candidate TUI-applicable capability remains under the campaign hold and requires S08 semantic adjudication followed by S11 row-level hold marking. G0 remains open.

### Live backend operation denominator

The application Ledger package currently exposes 63 frontend-neutral operations: 58 public functions and the five public methods of `PurchaseInvoiceEvidenceService`. The census admits state-changing commands, repository-backed queries, pure application projections that define a surface result, and composition operations used by another production application host. It excludes public data types, repository bind/resolve plumbing, identity/hash helpers, payload serializers, and lower-level policy predicates; those remain implementation dependencies rather than independently invocable capabilities. This is an operation census, not a completeness verdict: an existing primitive can be partial, unproved, or narrower than the operator workflow.

The `Request contract` column records the contract that exists now. `keyword parameters` means there is no canonical immutable command/query model yet; it must not be read as a typed command. A slash separates distinct existing result types within a family. Exact callable definitions and the cited tests are the evidence authorities; the grouped presentation does not merge their identities.

| Family (count) | Public operation identities | Request contract | Existing result contract | Direct behavioral proof |
| --- | --- | --- | --- | --- |
| Classification rules and bulk (3) | `ledger.classification.bulk_csv`, `ledger.classification.rule_add`, `ledger.classification.rule_apply` | keyword parameters | `BulkClassifyResult` / `LedgerClassificationRule` / `ApplyRulesResult` | Bulk: `test_bulk_classify_scale.py`; rule add/apply: **UNPROVEN** outside CLI tests |
| Flat export (1) | `ledger.export.flat` | `LedgerExportCommand` | `LedgerExportResult` | `test_actions_export_serialization.py`, lifecycle and guard tests |
| Import (3) | `ledger.import.parsed_rows`, `ledger.import.source`, `ledger.import.aggregate_results` | keyword parameters / `LedgerSourceImportCommand` / result sequence | `LedgerImportOperationResult` / `LedgerSourceImportResult` | Parsed rows and source: import/export and transaction tests; aggregate: **UNPROVEN** |
| Lifecycle (6) | `ledger.lifecycle.archive`, `ledger.lifecycle.stash`, `ledger.lifecycle.restore`, `ledger.lifecycle.reviewed_exclude`, `ledger.lifecycle.remove`, `ledger.lifecycle.reset` | keyword parameters | `ManualLedgerTransactionResult` / `LedgerTransactionRemovalReport` / `LedgerCatalogueResetReport` | `test_actions_lifecycle*.py`, `test_actions_reviewed_excluded.py`, remove/reset tests |
| Transaction command/query (10) | `ledger.transaction.create`, `ledger.transaction.attach`, `ledger.transaction.detach`, `ledger.transaction.invoice_link`, `ledger.transaction.get`, `ledger.transaction.list`, `ledger.transaction.review_query`, `ledger.transaction.status_summary`, `ledger.transaction.update`, `ledger.transaction.update_fields` | `ManualLedgerTransactionCommand` for create/update; `LedgerReviewQuery`; `ManualLedgerTransactionPatch`; otherwise keyword parameters | `ManualLedgerTransactionResult`, `InvoiceTransactionLinkResult`, tuple result, `LedgerReviewQueryResult`, `LedgerStatusReport` | Direct create/update/evidence/link/review/status tests under `application/ledger/tests/` |
| Split and merge (3) | `ledger.transaction.split`, `ledger.transaction.split_classified`, `ledger.transaction.merge` | keyword parameters with `SplitChildCommand` tuples | `SplitTransactionResult` / `MergeTransactionsResult` | split, merge, refusal, and LLM evidence-split tests |
| Attachment review (2) | `ledger.evidence.attachment_view`, `ledger.evidence.attachment_queue` | store plus identifier / store | `AttachmentReviewItem` / tuple result | **UNPROVEN** as public operations; locator helper alone is tested |
| Purchase evidence custody (5) | `ledger.evidence.add`, `ledger.evidence.view`, `ledger.evidence.list`, `ledger.evidence.update`, `ledger.evidence.remove` | `PurchaseInvoiceEvidenceService` method parameters | `PurchaseInvoiceEvidenceResult`, `PurchaseInvoiceEvidence`, tuple result | `test_evidence.py` plus custody, back-reference, and finalized-revision tests |
| Evidence batch (1) | `ledger.evidence.batch` | keyword parameters and source sequence | `BatchRunResult` | `test_batch_ingest_runner.py`, `test_batch_inference_pacing.py` |
| Consent withdrawal (2) | `ledger.evidence.consent_survey`, `ledger.evidence.consent_rederive` | keyword parameters and injected ports | `ConsentWithdrawalSurvey` / `LocalRederivation` | `test_consent_withdrawal.py` and batch runner composition |
| Counterparty establishment (3) | `ledger.counterparty.record`, `ledger.counterparty.forget`, `ledger.counterparty.resolve` | keyword parameters | `ConfirmedCounterpartyFacts` / `bool` / `ConfirmedCounterpartyResolution` | counterparty establishment and identity tests |
| Invoice evidence reading (2) | `ledger.invoice.extract_draft`, `ledger.invoice.confirm_draft` | keyword parameters | `InvoiceDraft` / `InvoiceConfirmationResult` | extraction, confirmation, direction, document identity, and establishment tests |
| Model-assisted review (12) | `ledger.llm.classify_with_evidence`, `ledger.llm.suggest`, `ledger.llm.apply`, `ledger.llm.saturate`, `ledger.llm.apply_saturated`, `ledger.llm.iva_derive`, `ledger.llm.suggest_split`, `ledger.llm.apply_split`, `ledger.llm.apply_evidence_classification`, `ledger.llm.reject`, `ledger.llm.diagnostics`, `ledger.llm.review_decision` | typed suggestion/request fragments plus keyword parameters; `LlmReviewRequest` exists but `execute_reviewed_decision` does not consume it | typed suggestion/apply/rejection/diagnostic unions; `LlmReviewResult` | Classification, saturation, split, rejection, telemetry, evidence-wiring, and review-workflow operations have direct tests; `ledger.llm.diagnostics` is **UNPROVEN** directly |
| Participation read (1) | `ledger.participation.get` | keyword parameters | `TransactionRevisionParticipationIndex` | **UNPROVEN** directly; only CLI-surface proof located |
| Preflight (2) | `ledger.preflight.readiness`, `ledger.preflight.catalogue` | keyword parameters | `LedgerPreflightReport` | repository, category, IVA, home-office, and anomaly tests |
| Usage ratios (4) | `ledger.ratio.list`, `ledger.ratio.validate`, `ledger.ratio.set`, `ledger.ratio.unset` | keyword parameters | tuple / `RatiosValidationReport` / prior `Decimal` or `None` | `test_ratios.py`, `test_ratios_concurrency.py` |
| Workspace composition (3) | `ledger.workspace.affected_declarations`, `ledger.workspace.project`, `ledger.workspace.read` | keyword parameters and injected readers/repositories | tuple of `LedgerAffectedDeclarationRefV1` / `LedgerWorkspaceProjectionV1` | Pure projectors: `test_workspace.py`; installed reader: **UNPROVEN** directly |

The exact proof census is 55 operations with a direct symbol-level behavioral test and eight without one: `ledger.classification.rule_add`, `ledger.classification.rule_apply`, `ledger.import.aggregate_results`, `ledger.evidence.attachment_view`, `ledger.evidence.attachment_queue`, `ledger.llm.diagnostics` (`build_llm_diagnostics_report`), `ledger.participation.get`, and `ledger.workspace.read`. CLI integration tests reach `build_llm_diagnostics_report` transitively through the adapter, and the CLI projection-helper test renders a prebuilt report; neither invokes the public application symbol directly, so they are not direct backend proof. A direct test is evidence only for the behavior it exercises; it does not make the enclosing family or backend axis complete.

#### Production composition and backend-only disposition

After lower-level compositions are folded into their owning operator capability, `ledger.workspace.read` is the sole backend-only product capability absent from the S04 command/sub-operation census. It is production-composed by `application/workbench_generation.py:537` for the installed workbench and delegates to the pure `ledger.workspace.project` composition. That makes it a required `backend_only` denominator row; component installation and TUI reachability remain S07 concerns and are not inferred here.

CLI-absent lower-level callables such as `ledger.import.parsed_rows`, `ledger.import.aggregate_results`, `ledger.preflight.catalogue`, `ledger.llm.classify_with_evidence`, and `ledger.workspace.affected_declarations` are internal compositions of an already counted operator capability, not extra backend-only products. Treating each helper as a surface row would double-count one behavior. Conversely, `ledger.workspace.read` returns a distinct installed product projection and therefore cannot be collapsed into its projector helper.

The source-set digest covers the 21 operational modules defining the 63 entries, in sorted path order with path delimiters: `actions_classification.py`, `actions_export.py`, `actions_import.py`, `actions_lifecycle.py`, `actions_manual.py`, `actions_split_merge.py`, `attachment_review.py`, `batch_ingest.py`, `consent_withdrawal.py`, `counterparty_establishment.py`, `evidence.py`, `invoice_confirmation.py`, `invoice_draft_extraction.py`, `llm_classification.py`, `llm_diagnostics.py`, `llm_review_workflow.py`, `participation_read.py`, `preflight.py`, `ratios.py`, `workspace.py`, and `workspace_reader.py`. Any public application operation added outside this observed set must reopen the backend stream rather than inheriting a default verdict.

### CLI-to-backend disposition matrix

| Capability | Current CLI authority | Backend state or destination | Initial disposition |
| --- | --- | --- | --- |
| Create | `_ledger.py:212` owns state, category, Censo percentage, jurisdiction, FX, and prorrata policy | Writer at `application/ledger/actions_manual.py:113` | Backport typed creation facade |
| Allocate | `_ledger.py:624` derives classification from percentage | Generic patch only | Backport dedicated use case |
| Direct/M210 classification | `_ledger.py:450`; `_ledger_m210_classify_cli.py:25` own route/completeness | Generic update and typed facts exist | Backport discriminated commands |
| Transaction/invoice link | `_ledger.py:682` repeats prechecks | Atomic writer enforces them at `actions_manual.py:340` | Delete duplicate CLI policy |
| List/filter/sort/group/page | `_ledger_list.py:35-361` owns full query/event policy | Fixed-order primitives at `actions_manual.py:432,454` | Backport typed query/result first |
| Check/status/history/view/track | `_ledger_read_cli.py:382-1030` composes preflight, links, events, stale revisions, participation | Granular readers only | Backport composite read facades |
| Rule dry-run | `_ledger_rules_cli.py:102` repeats eligibility/first match | Live apply at `actions_classification.py:428` | Put dry-run in canonical engine |
| Per-file import | `_ledger_import_cli.py:183` parses/invokes | `actions_import.py:322` | Already backend |
| Folder import | `_ledger_import_cli.py:83,236` owns enumeration/loop | Per-source import/aggregation exist | Backport multi-source facade |
| Flat export | `_ledger_read_cli.py:661` delegates | `actions_export.py:79` | Already backend; expand separately |
| Drive evidence pull | `ledger_lifecycle_cli.py:170-414` owns fetch, MIME, secure store, link, partial success | No joined application workflow | Backport one/batch workflows over ports |
| Extraction consent | `_ledger_evidence_cli.py:235` owns eligibility/token policy | Extraction at `invoice_draft_extraction.py:128` | Backport policy command |
| Evidence review | `_ledger_evidence_review_cli.py:48-532` owns projection, blockers, filters, advisories | Atomic helpers only | Backport typed queries |
| Consent survey | `_ledger_evidence_consent_cli.py:80-153` joins adapter rows | No port-backed application reader | Backport composition |
| LLM routes | `_ledger_llm_cli.py:211-904`; `ledger_lifecycle_cli.py:755-949` own route/terminal policy | Primitives in `llm_classification.py` and `llm_review_workflow.py` | Backport discriminated workflow |
| Invoice add/import/list | `_ledger_business_invoice_cli.py:54-637` owns IVA mapping, advisories, mapper, repository list | Creation/import/lifecycle primitives exist | Backport facades; investigate mapper port |
| Ratios | `_ledger_ratios_cli.py:34-240` owns Censo joins, persistence, warnings, events | Pure helpers at `application/ledger/ratios.py:177-294` | Backport atomic workflows urgently |
| Counterparty confirmation | `_ledger_counterparty_cli.py:99-230` infers outcomes/repeats prechecks | Writer/resolver in `counterparty_establishment.py` | Return typed application outcomes |
| Prorrata | `_prorrata_register_cli.py:139-635` owns legality, precedence, blockers, persistence | Lower-level services exist | Backport end-to-end commands |
| Bienes de inversión | `_bienes_inversion_cli.py:58` constructs disposal coupling/record | Service accepts finished record | Backport typed command |
| Inventory | `_ledger_inventory_cli.py` mainly parses/redacts | `InventoryService` owns operations | Already backend |
| Payload families | `_ledger_payloads.py` and siblings redeclare facts | Partial application DTO coverage | Add canonical results, then project |

### Missing capability and reuse map

| Gap | Reusable analogue | Required proof |
| --- | --- | --- |
| Review-grade workbook | Modelo shared plan, guide/evidence facets | Open/read semantics, protection, offline/Google parity |
| Restore archive | Profile capsule | Export→restore→canonical equality, integrity, encryption |
| Google Ledger export | Optional Google adapter and Modelo renderer | One transport-neutral plan, value parity |
| Complete export provenance | Transaction facts and package manifests | Versioned schema, redaction, checksum verification |
| Evidence download | Secure byte loader and file/package export boundaries | Exact bytes/hash, safe destination, cleanup |
| Atomic evidence replace | Content-addressed store and ledger events | Atomic transition, finalized-use guard, retention policy |
| Append-only notes | Bucket event history | Immutable identity, actor/time/source, read order |
| Changed-field provenance | Invoice field provenance and bucket events | Sensitive-value policy and exact change-set round trip |
| Generic batch patch | Batch result/precondition machinery | All-or-none rollback, idempotency, stable target identity, baseline concurrency refusal |
| Application paging | Query DTOs and indexed repository reads | Stable snapshot/order and page contract |

### Direct backend behavior gate

| Backend family | Current proof | Gate verdict |
| --- | --- | --- |
| Lifecycle archive/stash/restore/exclude/remove/reset | Direct persistence, event, evidence-detach and finalized-Modelo guard tests | Complete for existing primitives |
| Typed field edit and attachment/link primitives | Direct encrypted repository, event and back-reference tests | Complete for existing primitives; allocate/classification facades missing |
| Manual split/merge | Direct catalogue transition, lineage and refusal tests | Complete for manual operations |
| Per-file import and flat export | Real persistence plus CSV/JSONL/XLSX serialization tests | Complete for those products only; no restore proof |
| Bulk CSV classification | Direct persistence/event scale tests | Complete primitive |
| Manual create | Strong writer tests | Partial: operator-intent/Censo/jurisdiction/prorrata facade missing |
| Review/list query | Direct filter/projection tests | Partial: sort/group/page/rejection policy remains CLI-owned |
| Composite check/status/history/view/track | Granular backend readers only | Missing canonical composite use cases |
| Classification rules | Functions exist; behavior is primarily CLI-tested | Partial; dry-run engine and direct backend gate missing |
| Directory import | Per-source primitive and untested result aggregator | Missing multi-source use case and direct test |
| Drive evidence ingestion | Secure store/link primitives only | Missing joined backend workflow and behavior test |
| Evidence extraction/review/consent | CRUD/extract/confirm primitives are strong | Partial: consent and review-query composition missing |
| LLM classify/saturate/split/apply | Extensive direct primitive/review-decision tests | Partial: frontend-neutral routing/preview outcome missing |
| Invoice create/import/list | Create/import strongly tested | Partial: list proof and operator orchestration missing |
| Ratios/counterparty/prorrata | Lower-level services have direct tests | Partial: atomic operator use cases/outcomes missing |
| Bienes de inversión | Service accepts a finished record | Missing direct service test and operator-intent facade |
| Review export/Google/restore archive | No Ledger backend symbols | Missing |

Backend status is therefore not green. Direct tests establish reusable foundations, but no CLI refactor step may use primitive presence as proof that the backend gate for the corresponding operator capability is complete.

### Registry, calculation, and filing denominator

The canonical `BindingSourceKind` taxonomy and derived `LEDGER_BINDING_SOURCE_KINDS` set define exactly seven Ledger families at `src/cadrumo/core/aggregation.py:233,512`. Each family has one strict selector registration and one validator-dispatch registration at `src/cadrumo/domain/calculations/registry/bindings.py:926,1023`. Each also has exactly one `mesh`-stage production resolver owner in `CALCULATION_ROUTE_RESOLVER_OWNERSHIP`; the ownership validator rejects duplicate or missing source ownership. These are structural facts only. They do not prove that a declaration reaches a casilla, that a nonzero ledger fact survives calculation, or that verification/export refuses unresolved facts.

The exact validated-authority projection contains 546 declarations at 35 family/revision sites. Canonical `casillas_by_binding` joins 510 declarations to a registry casilla. Three more declarations reach a casilla through explicit application-sidecar mappings: M130 retenciones to casilla `06`, and each M210 revision to `rendimientos_integros`. The remaining 33 declarations have neither a registry binding edge nor a located application output mapping. They are not counted as working routes merely because their selectors validate or their resolver returns a binding value.

The committed reproducer is `build_ledger_registry_route_census`. Its root is the literal `cadrumo.ledger_registry_route_census`, schema version is the integer literal `1`, and every row has exactly these typed keys: `source`, `modelo_id`, `revision_id`, `valid_from`, nullable `valid_to`, `period_selector_json`, `binding_id`, `selector_json`, and `targets`. Period-selector values are canonical JSON strings with model defaults and nulls retained. Selector values are serialized directly from the live validated selector `BaseModel`, retaining every declared typed field including unset defaults, default-equal values, and nulls; only loader-injected `source` discriminator metadata is excluded, and an unvalidated raw mapping is refused. JSON object-key/input order is semantically irrelevant and normalized by sorted keys. Each target is exactly `casilla_id` plus `section`, where section is the complete ordered tuple of path components. No direct target is represented by an empty target tuple, never an invented null casilla. Rows sort and de-duplicate by source/modelo/revision/binding; targets sort and de-duplicate by casilla/section. The serializer uses ASCII canonical JSON (`sort_keys`, compact separators), prefixes `cadrumo:ledger-registry-route-census:v1` plus NUL, and unsigned-8-byte-big-endian length frames the payload before SHA-256. Its source-set sibling prefixes `cadrumo:ledger-registry-source-set:v1` plus NUL and length frames each sorted source-root-relative POSIX path and raw body. Positive and adversarial tests pin both digests and reject source drift, missing/duplicate/reordered declarations, changed selector/applicability/target/section facts, malformed root/schema/row data, and loss or change of live typed selector defaults and nulls; they also prove irrelevant selector input order normalizes to the same digest. This is a projection and freshness detector over the live validated authority, not a second business registry.

#### Seven-family registration and ownership register

| Source family | Selector / validator | Production resolver | Declarations / sites | Current destination state |
| --- | --- | --- | --- | --- |
| `ledger_iva_aggregation` | `IvaLedgerSelector` / `validate_ledger_iva_aggregation_binding` | `LedgerIvaAggregationSourceResolver` | 498 / 18 | 467 registry-bound; 31 destinationless |
| `ledger_oss_aggregation` | `OssIossLedgerSelector` / `validate_ledger_oss_aggregation_binding` | `OssIossLedgerSourceResolver` | 5 / 3 | All five registry-bound |
| `ledger_renta_gastos_estimacion_directa_aggregation` | `RentaLedgerGastosEstimacionDirectaSelector` / `validate_ledger_renta_gastos_estimacion_directa_aggregation_binding` | `LedgerRentaGastosEstimacionDirectaAggregationSourceResolver` | 28 / 2 | All 28 registry-bound |
| `ledger_renta_income_aggregation` | `RentaLedgerIncomeSelector` / `validate_ledger_renta_income_aggregation_binding` | `LedgerRentaIncomeAggregationSourceResolver` | 10 / 7 | Seven registry-bound; one application-sidecar; two destinationless |
| `ledger_renta_gastos_pago_fraccionado_aggregation` | `RentaLedgerGastosPagoFraccionadoSelector` / `validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding` | `LedgerRentaGastosPagoFraccionadoAggregationSourceResolver` | 1 / 1 | Registry-bound to M130 casilla `02` |
| `ledger_impatriado_income_aggregation` | `ImpatriadoLedgerIncomeSelector` / `validate_ledger_impatriado_income_aggregation_binding` | `LedgerImpatriadoIncomeAggregationSourceResolver` | 2 / 2 | Both registry-bound |
| `ledger_irnr_income_aggregation` | `IrnrLedgerIncomeSelector` / `validate_ledger_irnr_income_aggregation_binding` | `LedgerIrnrIncomeAggregationSourceResolver` | 2 / 2 | Both application-sidecar routes; neither has a registry binding edge |

#### Complete family/revision route-site register

`Bindings / direct / sidecar / unresolved` is an exact partition for every site. `Direct` means a canonical `casillas_by_binding` edge. `Sidecar` means an explicit application mapping outside the registry target graph. Sections are taken from the target `CasillaDefinition`; `none` is a real absence, not an omitted observation. The route-census digest above additionally binds every declaration id, full typed selector, applicability interval and periods, target casilla ids, and target section paths.

| Family | Modelo / revision | Applicability and periods | Bindings / direct / sidecar / unresolved | Destination casillas and sections |
| --- | --- | --- | --- | --- |
| Renta expense | M100 / `2024` | 2024; `0A` | 14 / 14 / 0 / 0 | `0183, 0186, 0191, 0192, 0193, 0194, 0195, 0199, 0200, 0202, 0203, 0206, 0208, 0217`; `toma_datos_ampliada/reg_estima_directa/actividad_est_directa` |
| Renta income | M100 / `2024` | 2024; `0A` | 1 / 1 / 0 / 0 | `0171`; same section |
| Renta expense | M100 / `2025` | 2025; `0A` | 14 / 14 / 0 / 0 | same 14 ids; `rendimientos_actividades_economicas/estimacion_directa` |
| Renta income | M100 / `2025` | 2025; `0A` | 1 / 1 / 0 / 0 | `0171`; same section |
| M130 expense | M130 / `2019-y-siguientes` | 2019..open; `1T-4T` | 1 / 1 / 0 / 0 | `02`; `actividades_economicas_estimacion_directa` |
| Renta income | M130 / `2019-y-siguientes` | 2019..open; `1T-4T` | 4 / 1 / 1 / 2 | direct `01`; sidecar `06`; same section; two declarations have no destination |
| Renta income | M131 / `2019-2023` | 2019..2023; `1T-4T` | 1 / 1 / 0 / 0 | `05`; `actividades_agricolas_ganaderas_forestales` |
| Renta income | M131 / `2024` | 2024; `1T-4T` | 1 / 1 / 0 / 0 | `05`; same section |
| Renta income | M131 / `2025` | 2025; `1T-4T` | 1 / 1 / 0 / 0 | `05`; same section |
| Renta income | M131 / `2026` | 2026..open; `1T-4T` | 1 / 1 / 0 / 0 | `05`; same section |
| Impatriado income | M151 / `2015-2022` | 2015..2022; `0A` | 1 / 1 / 0 / 0 | `impatriado.base-liquidable-general`; `liquidacion/base` |
| Impatriado income | M151 / `2025-y-siguientes` | 2023..open; `0A` | 1 / 1 / 0 / 0 | same id and section |
| IRNR income | M210 / `2025` | 2025; `EVENT-N`, `0A` | 1 / 0 / 1 / 0 | sidecar `rendimientos_integros`; registry section absent from the binding edge |
| IRNR income | M210 / `2026-y-siguientes` | 2026..open; `EVENT-N`, `0A` | 1 / 0 / 1 / 0 | same sidecar |
| IVA | M303 / `2022` | 2022; `1T-4T` | 23 / 22 / 0 / 1 | 22 casillas across `iva/regimen_general/{deducible,devengado,inversion_sujeto_pasivo}` and `iva/resultado` |
| IVA | M303 / `2023` | 2023; quarterly and monthly | 28 / 28 / 0 / 0 | 28 casillas across the same four section branches |
| IVA | M303 / `2024-hasta-08-y-2t` | 2024-01-01..08-31; `1T`, `2T`, `01-08` | 30 / 29 / 0 / 1 | 29 casillas across the same four section branches |
| IVA | M303 / `2024-desde-09-y-3t` | 2024-09-01..12-31; `3T`, `4T`, `09-12` | 30 / 30 / 0 / 0 | 30 casillas, adding `iva/recargo_equivalencia/devengado` |
| IVA | M303 / `2025` | 2025; quarterly and monthly | 30 / 30 / 0 / 0 | same 30-casilla section set |
| IVA | M303 / `2026-y-siguientes` | 2026..open; quarterly and monthly | 30 / 30 / 0 / 0 | same 30-casilla section set |
| IVA | M309 / `2016-2017` | 2016..2017; `AD-HOC` | 2 / 2 / 0 / 0 | `iva.autorepercutido.intracomunitaria`, `iva.soportado.recargo-equivalencia`; `iva/no_periodica/{inversion_sujeto_pasivo,soportado}` |
| IVA | M309 / `2018-2022` | 2018..2022; `AD-HOC` | 2 / 2 / 0 / 0 | same destinations |
| IVA | M309 / `2023-y-siguientes` | 2023..open; `AD-HOC` | 2 / 2 / 0 / 0 | same destinations |
| IVA | M322 / `2008-2022` | effective 2022; monthly | 5 / 5 / 0 / 0 | `iva.autorepercutido.intracomunitaria`, `iva.repercutido.{general,reducido,super-reducido}`, `iva.soportado.interiores`; three `iva/regimen_general/*` branches |
| IVA | M322 / `2023` | 2023; monthly | 5 / 5 / 0 / 0 | same destinations |
| IVA | M322 / `2024-2025` | 2024..2025; monthly | 5 / 5 / 0 / 0 | same destinations |
| IVA | M322 / `2026-y-siguientes` | 2026..open; monthly | 5 / 5 / 0 / 0 | same destinations |
| IVA | M353 / `2021-2025` | 2021..2025; monthly | 5 / 5 / 0 / 0 | same five destinations and three section branches as M322 |
| OSS | M369 / `esquema-exterior` | 2021-07-01..open; `EXT-1T-EXT-4T` | 1 / 1 / 0 / 0 | `iva.exterior.de.services-cuota`; `iva/exterior/destino_de` |
| OSS | M369 / `esquema-importacion` | 2021-07-01..open; monthly | 1 / 1 / 0 / 0 | `iva.importacion.de.low-value-cuota`; `iva/importacion/destino_de` |
| OSS | M369 / `esquema-union` | 2021-07-01..open; `1T-4T` | 3 / 3 / 0 / 0 | `iva.union.de.goods-distance-cuota`, `iva.union.de.services-cuota`, `iva.union.fr.services-cuota`; `iva/union/{destino_de,destino_fr}` |
| IVA | M390 / `2022` | 2022; `0A` | 74 / 59 / 0 / 15 | 59 casillas across `iva/anual/{deducible,devengado,inversion_sujeto_pasivo,volumen_operaciones}` |
| IVA | M390 / `2023` | 2023; `0A` | 74 / 60 / 0 / 14 | 60 casillas across the same four branches |
| IVA | M390 / `2024` | 2024; `0A` | 74 / 74 / 0 / 0 | 74 casillas across the same four branches |
| IVA | M390 / `2025` | 2025; `0A` | 74 / 74 / 0 / 0 | 74 casillas across the same four branches |

#### Declarations without a registry destination

Three of the 36 declarations with no `casillas_by_binding` edge have an observed application-sidecar consumer. `LedgerRentaIncomeAggregationSourceResolver` maps `modelo-130-actividad-economica-retenciones-cumulative` to M130 casilla `06` through `_m130_retenciones_backend_inputs`; `LedgerIrnrIncomeAggregationSourceResolver` maps the single M210 binding in each revision to `rendimientos_integros` through `bound_inputs_by_casilla_id`. These routes work in live tests, but their output identity is not represented by the registry relationship and remains a `REGISTRY` gap for S100.

The other 33 declarations have no located calculation destination:

- M130 / `2019-y-siguientes`: `modelo-130-actividad-economica-ingresos-taxable-base-cumulative` and `modelo-130-actividad-economica-rendimiento-neto-cumulative`.
- M303 / `2022`: `modelo-303-recargo-equivalencia-super-reducido-cuota`.
- M303 / `2024-hasta-08-y-2t`: `modelo-303-iva-repercutido-super-reducido-transitorio-base`.
- M390 / `2022` (15): `modelo-390-iva-repercutido-tipo-7-5-{base,cuota}`, `modelo-390-iva-repercutido-tipo-2-{base,cuota}`, `modelo-390-iva-recargo-equivalencia-tipo-{1,0-62,0-26}-cuota`, and `modelo-390-iva-aic-{bienes,servicios}-tipo-{2,7-5}-{base,cuota}`.
- M390 / `2023` (14): the same set except `modelo-390-iva-recargo-equivalencia-tipo-0-62-cuota`.

These 33 selectors still participate in family matching. Until S100 either gives them a typed destination or proves an explicit excluded/not-applicable disposition that cannot suppress an unrouted fact, they remain unresolved rather than being called dormant, zero, or supported.

#### Calculation, verification, evidence, filing, and export consumers

| Route family / modelos | Production calculation evidence | Verification / filing-evidence / export evidence | Unresolved direct obligation |
| --- | --- | --- | --- |
| IVA / M303 | Nonzero persisted-ledger calculation in `test_e2e_ledger_m303_quarters_to_m390_annual.py`; deductible-evidence and drift tests exercise real stores | M303 verifies, captures snapshot/evidence, locally files, and correctly refuses export because its registry has no complete layout | Prove general non-OSS unrouted-observation refusal and resolve two destinationless historical declarations |
| IVA / M390 | Registry resolver tests exercise nonzero IVA selectors; production annual calculation and verification consume the M303 relation chain | M390 verifies and correctly refuses unavailable export layout; this proves the relation route, not every one of its 74 direct Ledger selectors | Add nonzero production-route coverage for representative direct M390 Ledger destinations; resolve 29 destinationless historical declarations |
| IVA / M309, M322, M353 | Selector, validator, and resolver tests exist | No live nonzero work-calculate→verify→evidence→export/file chain was located | Add per-Modelo positive, exclusion, zero-versus-missing, unrouted refusal, and finish-line proof |
| OSS / M369 | Nonzero issued-invoice-catalogue projection and production calculation are direct-tested | Successful calculate→verify→export exists; missing source and unrouted observation both refuse verify/export; genuine zero remains distinguishable | Preserve that this is invoice-catalogue-backed, not transaction-catalogue-backed; filing proof is still absent |
| Renta expense / M100 | Nonzero persisted-ledger M100 calculations cover direct-expense destinations and ratio/evidence rules | M100 verification succeeds; observed export refuses an undeclared mandatory Aux field | Complete successful export/file finish line after the layout product is complete |
| Renta income / M100 and M130 | Nonzero M130 c01/c06 and annual M100 calculations are direct-tested, including currency handling | M100 verification and ledger evidence are exercised; M100 export currently refuses its incomplete layout | Resolve the two destinationless M130 declarations and move c06 output identity into an honest typed registry route |
| Renta income / M131 | Registry declaration and resolver-level coverage exist | No live nonzero production work-calculate chain from Ledger through M131 was located | Add calculate→verify→evidence→export/file proof plus missing/deferred/zero and exclusion cases |
| M130 expense / c02 | Resolver/binding, currency, zero, and verification-shape tests exist | M130 workflow tests prove c02 is bound, but no explicit nonzero production-route c02 assertion was located | Add a nonzero persisted-ledger c02 calculation and finish-line proof |
| Impatriado income / M151 | Repository aggregation and real registry-binding resolution cover nonzero ES inclusion, foreign exclusion, ambiguity, and currency | No live M151 work-calculate→verify→evidence→export/file chain was located | Add the full production chain; keep the separate savings base manual until grounded |
| IRNR income / M210 | Nonzero secure-store calculation, selected-code separation, mutation, foreign exclusion, and manual/ledger authority exclusivity are direct-tested | Verification captures filing evidence without reclassifying gross income as manual | Move the sidecar output into an honest registry route and add export/file proof |

Unmatched nonzero observations become persisted `CalculationSourceIssue` values through `src/cadrumo/domain/calculations/registry/_ledger_binding_resolution.py:96` and `src/cadrumo/application/modelo/calculation_actions.py:1513`. Verification explicitly blocks OSS `unrouted_observation` at `src/cadrumo/application/modelo/verification_actions.py:1364`, but no general non-OSS source-issue gate was found. Export and filing require a sealed/verified revision and other evidence/precondition gates, but do not independently inspect those non-OSS source issues. This is a high-confidence filing-path gap: a non-OSS unmatched fact can remain only an advisory while the revision advances.

Ledger drift checking is otherwise strong at `src/cadrumo/application/modelo/_ledger_drift_gate.py:70`. Immutable filing evidence carries currency, FX rate, and EUR value without FX source/effective-date lineage at `src/cadrumo/domain/modelos/ledger_filing_snapshot.py:155`; S100 must close that provenance gap rather than treating the existing snapshot as complete.

Focused validation for this census exercises real selector/validator enrollment, production resolver ownership, source diagnostics, representative live calculation routes, evidence capture, and observed export/refusal paths. Those gates establish only the behavior they run; missing per-Modelo paths above remain `UNPROVEN`.

### Existing backend behavior must not be rebuilt

Transaction update; attach/detach; archive/stash/restore/exclude/remove/reset; manual split/merge; per-file import and FX; CSV/JSONL/XLSX export; bulk CSV classification; live rule apply; evidence CRUD; attachment metadata; evidence extraction/confirmation/batch; invoice view/update/remove; inventory; ratio eligibility/validation; participation; and low-level LLM suggest/saturate/split/apply already have application owners. Higher-level facades may compose them, but must not copy them.

### Valid CLI boundary

CLI may own argv syntax, token/date/decimal parsing, confirmations, resolution grammar, locale activation, rendering, redaction, envelope emission, and exit-code translation. Repository selection, joins, audit events, query semantics, provider/retry policy, multi-step effects, partial-success meaning, and regulated defaults belong behind application use cases.

### Migration order for ADR consideration

1. Query/read facades: list, review, check, status, history, track, invoice list, evidence review.
2. Mutation facades: create, allocate, classification, ratios, rule dry-run.
3. Multi-system workflows: LLM routing, Drive evidence, consent, directory import.
4. Adjacent registers: invoice orchestration, prorrata, bienes de inversión.
5. Missing capability services and export products.
6. Canonical outcome DTOs, CLI reprojection, removal of direct business orchestration.

This ordering is research evidence, not execution authorization. Backend completion remains the candidate hard gate before CLI completion, and CLI completion before TUI work.
