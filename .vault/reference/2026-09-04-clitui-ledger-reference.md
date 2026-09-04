---
tags:
  - '#reference'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:a73c0833ea6ddd24287badb66f0449ca1ddee10fb3c38439a5fb7618799f1bbc'
related:
  - "[[2026-09-04-clitui-ledger-research]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---
# `clitui-ledger` reference: `CLI to backend capability authority census`

This reference maps the first semantic-search-led census of Ledger behavior owned by the CLI to existing or proposed frontend-neutral application homes. It is an initial denominator, not an exhaustive command-graph classification. Every implementation step must refresh affected rows against the live tree.

## Summary

### Campaign matrix publication

This document is the authoritative human-readable publication surface for the `LedgerCapabilityMatrixV1` campaign contract in `dev/quality/clitui_ledger_capability_matrix.py`. The S04 CLI stream is now an exact, fail-closed projection, but the publication remains a **provisional baseline** rather than a serialized accepted matrix: S05-S08 have not produced and adjudicated the complete live union census, S09 has not recorded the cross-plan hold control, and S12-S14 have not reviewed and accepted the frozen denominator. The contract therefore requires the publication to fail closed instead of inventing a denominator digest, matrix digest, evidence attestation, or G0 closure.

| Publication field | Current value |
| --- | --- |
| Contract / schema | `LedgerCapabilityMatrixV1` / `3` |
| Publication revision | `s04-cli-census-2` |
| Observation timestamp | `2026-09-04T19:55:53.8412508Z` |
| Source revision | `c2fd4b4c5e040d2c5e9814e3319ff0c911b741c8` |
| Contract source digest | `sha256:c2998c8ff958ae820b59fa7055a36d83117bb35282fe2679761032fab7a15a10` |
| Accepted plan owner | `clitui-ledger` |
| Denominator revision / digest | Not issued: the mandatory S04-S08 live census and adjudication are open |
| Matrix digest | Not issued: a digest-bound `LedgerCapabilityMatrixV1` cannot exist before the complete denominator and current evidence subjects exist |
| Acceptance attestation | Absent by design: only S14 may record an independent `ACCEPT` ruling bound to the frozen digest |
| TUI hold | Campaign sequencing bars Ledger TUI implementation; the cross-plan recorded control remains open until S09 and row-level applicability/hold classification remains open until S07, S08, and S11 |

#### Mandatory source-stream landscape

Every stream below must become one complete, readable, unambiguous, digest-bound `CensusStreamObservationV1`. A known count is baseline evidence only; it is not a declaration that the stream census is complete.

| Source stream | S03 observation | Readiness | Closure owner |
| --- | --- | --- | --- |
| `cli_endpoint` | 78 invocable endpoints: 77 leaves and executable `participation`; each has an exact path, handler, schema, TUI declaration, and ownership annotation | Complete current CLI stream; not a union-denominator attestation | S04 complete |
| `cli_suboperation` | 50 explicit behavior-distinct sub-operations across ten overloaded endpoints | Complete current CLI stream; not a union-denominator attestation | S04 complete |
| `backend_only` | Existing backend primitives and composite gaps are catalogued below | Partial: exhaustive backend-only operation and direct-proof census remains open | S05 |
| `missing_product` | The baseline missing product and provenance families are published below | Partial: union review and canonical row admission remain open | S05 and S08 |
| `registry_route` | Seven Ledger binding families and 546 declarations are established below | Partial: every route, calculation consumer, filing consumer, and proof obligation remains open | S06 |
| `artifact_product` | Flat CSV/JSONL/XLSX exists; review package, Google transport, and restore archive remain distinct missing products | Partial: product identities and artifact proof remain open | S05, S06, and S08 |
| `supported_surface` | CLI enrollment and TUI component existence/installed reachability are known to be distinct | Partial: exhaustive component and navigation reachability census remains open | S07 |

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
| `ledger.registry.iva` | `REGISTRY` | registry binding/resolution and calculation route; exact route contract in S06/S100 | `registry`, `proof`; nonzero M309/M322/M353 route proof open |
| `ledger.registry.oss` | `REGISTRY` | registry binding/resolution and M369 route; exact route contract in S06/S100 | Preserve issued-invoice-catalogue distinction; proof bounded below |
| `ledger.registry.renta_expense` | `REGISTRY` | registry binding/resolution and M100 route; exact route contract in S06/S100 | Preserve evidence and deduction-ratio requirements |
| `ledger.registry.renta_income` | `REGISTRY` | registry binding/resolution and M100/M130/M131 routes; exact route contract in S06/S100 | `registry`, `proof`; M131 live path and M130 c06 hardcoded projection open |
| `ledger.registry.m130_expense` | `REGISTRY` | registry binding/resolution and M130 c02 route; exact route contract in S06/S100 | `registry`, `proof`; explicit nonzero c02 route assertion open |
| `ledger.registry.impatriado_income` | `REGISTRY` | registry binding/resolution and M151 route; exact route contract in S06/S100 | `registry`, `proof`; calculate-to-export proof and manual savings base open |
| `ledger.registry.irnr_income` | `REGISTRY` | registry binding/resolution and M210 route; exact route contract in S06/S100 | Preserve explicit classification and mutual exclusion; proof bounded below |

#### Evidence-coordinate register

These coordinates bind the S03 claims to the current observation revision. They are publication locators, not contract `EvidenceCoordinateV1` objects yet; S08/S12 must assign row/axis roles and current subject snapshots before admission.

| Coordinate | Locator | Subject digest | Claim boundary |
| --- | --- | --- | --- |
| `evidence.baseline.matrix_contract` | `dev/quality/clitui_ledger_capability_matrix.py:22` | `sha256:c2998c8ff958ae820b59fa7055a36d83117bb35282fe2679761032fab7a15a10` | Schema 3, eight axes, source kinds, gaps, controls, evidence currentness, and G0-G4 predicates |
| `evidence.s04.cli_command_census` | `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:51` | `sha256:2cd8e21e2b8602e5e18338c22350301f2bc76f580873af51b1154d5364e6769b` | Exact current CLI stream: 78 invocables, 50 supplemental behavior-distinct sub-operations across ten overloaded endpoints, derived path/handler/schema/TUI facts, and fail-closed ownership annotations |
| `evidence.baseline.cli_authority` | `2026-09-04-clitui-ledger-reference`, CLI-to-backend disposition matrix | Bound by this document's CLI-maintained `body_hash` after publication | Initial authority families and candidate application homes |
| `evidence.baseline.backend_behavior` | `2026-09-04-clitui-ledger-reference`, Direct backend behavior gate | Bound by this document's CLI-maintained `body_hash` after publication | Existing direct-proof boundaries and missing facades |
| `evidence.baseline.missing_products` | `2026-09-04-clitui-ledger-reference`, Missing capability and reuse map | Bound by this document's CLI-maintained `body_hash` after publication | Explicit product/artifact/provenance gaps |
| `evidence.baseline.registry_routes` | `src/cadrumo/domain/calculations/registry/bindings.py:926` | `sha256:957fca756cca97d606a42d34ec0b4d9fc074454a1b3d4bff08953e9408333252` | Seven family enrollment baseline; route-level S06 proof census is open |
| `evidence.baseline.cli_boundary` | `2026-09-04-clitui-ledger-reference`, Valid CLI boundary | Bound by this document's CLI-maintained `body_hash` after publication | Allowed adapter concerns and forbidden business ownership |

#### Gate summary

| Gate | State at S03 | Blocking facts |
| --- | --- | --- |
| G0 denominator and ownership freeze | **OPEN** | S04 is complete, but S05-S08 union census/adjudication, S09/S11 hold records, S12 row review, S13 reopening detector, and S14 digest-bound independent `ACCEPT` remain outstanding |
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

The canonical `BindingSourceKind` taxonomy and `LEDGER_BINDING_SOURCE_KINDS` define seven ledger families at `src/cadrumo/core/aggregation.py:233,512`. All seven enroll through selector registration and validator dispatch at `src/cadrumo/domain/calculations/registry/bindings.py:926,1023`, and the application calculation route validates unique total production ownership at `src/cadrumo/application/modelo/calculation_route.py:112,154`. Exact registry census found 546 declarations across the seven families.

| Binding family | Declared consumers | Production proof | Open proof or authority gap |
| --- | --- | --- | --- |
| Ledger IVA | M303/M309/M322/M353/M390 | Strong M303→M390 and deductible-evidence paths | No located live nonzero Ledger calculate proof for M309/M322/M353 |
| Ledger OSS | M369 | Strong calculate→verify/export tests | Uses issued-invoice catalogue rather than transaction catalogue; distinction must remain explicit |
| Renta direct-estimation expenses | M100 | Strong M100 and M130→M100 annual chain | Preserve invoice evidence and deduction-ratio requirements |
| Renta income | M100/M130/M131 | Strong M130/M100 and currency proof | M131 lacks located production work-calculate proof; M130 c06 uses hardcoded application projection outside honest registry targeting |
| M130 fractional-payment expenses | M130 c02 | Strong aggregate/binding and currency tests | No located explicit nonzero production-route c02 assertion |
| Impatriado income | M151 | Repository, registry-binding and currency tests | No located calculate→verify/export proof; savings base remains manual |
| IRNR income | M210 | Strong live calculate, mutation, exclusion and evidence-bundle tests | Preserve explicit M210 classification and mutual-exclusion authority |

Unmatched nonzero observations become persisted `CalculationSourceIssue` values through `src/cadrumo/domain/calculations/registry/ledger_binding_resolution.py:96` and `src/cadrumo/application/modelo/calculation_actions.py:1513`. Verification explicitly blocks the OSS `unrouted_observation`, but no general non-OSS verification gate was found at `src/cadrumo/application/modelo/verification_actions.py:1386`; this is a high-confidence filing-path gap. Ledger drift checking is otherwise strong at `src/cadrumo/application/modelo/ledger_drift_gate.py:70`, but immutable filing evidence carries currency, FX rate, and EUR value without FX source/date at `src/cadrumo/domain/modelos/ledger_filing_snapshot.py:155`.

Focused registry/calculation verification for this census passed 133 tests. Registration/dispatch tests prove enrollment, while the missing per-Modelo live paths above remain unproven rather than being inferred from generic resolver coverage.

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
