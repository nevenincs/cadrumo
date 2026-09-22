# Ledger and invoice lifecycle: preflight brief

Brief ID: LEDGER-01. Revision: 0.1. Date: 2026-09-21.
Session name: `ledger-core`. Goal: prove that issued/received invoice records, transactions and their evidence can be entered, reviewed, corrected and reused through CLI and TUI without lost meaning, duplicated amounts or broken tax provenance.
Provider, lead, cc number and UUID: pending user assignment. Provider-neutral; this brief does not launch an implementation session.
Required instructions: [session policy](session-policy.md) revision 1.8 and [ACCEPTANCE-01](acceptance-pattern.md) revision 1.7. Reuse bounded Luna Max discovery, one-writer ownership and the global verification reservation list.
Status: two bounded Luna Max reports (`ledger_core_map`, `ledger_frontend_map`), targeted coordinator source checks and official-domain grounding complete. No product changes, tests, runtime rendering, private-store reads or live calls performed. Adviser consultation could not start because of the session agent-thread limit; no adviser review or new architectural decision is claimed.

## Scope and non-duplication

Start with the same common-regime autonomo and synthetic input definitions as the active income/IVA briefs. Cover shared record lifecycle, not another set of tax engines. Recording an issued invoice is distinct from legally issuing/delivering a compliant invoice document; neither a catalogue row nor a PDF preview proves the latter. Inventory existing generation/export capabilities and label them accurately. New SII synchronization, VERI*FACTU or electronic-invoicing compliance is not authorized by this core ledger brief.

| Owner | Responsibility |
| --- | --- |
| LEDGER-01 | Shared invoice/transaction entry, imports, duplicate handling, revision/correction lineage, classification persistence, evidence custody, links, review and frontend continuation. Payment-link capabilities are investigated at the existing owner; do not invent a second payment ledger. |
| INCOME-01 / IVA-01 | Their liability/date/deduction semantics, aggregate completeness, periodic/annual reconciliation and official modelo exports. Ledger proves the persisted inputs and contributing record identities, then consumes their existing oracle/verification receipts. |
| RETENCIONES-01 | Withholding direction, payment-triggered inclusion, recipient/perception detail and periodic/annual obligations. Shared gross/base/withholding/net and payment facts must preserve its contract. |
| ASSETS-01 | Asset recognition, acquisition-cost treatment, schedules and amortization/IVA capital-goods rules. Ledger owns only its assigned acquisition/evidence linkage, not another inventory or depreciation engine. |
| PROFILE-01 / CALENDAR-01 | Selected taxpayer/profile facts and historical context / obligation and filing-evidence review. Changing a ledger record must not silently rewrite profile or filed-declaration history. |

Existing ownership takes precedence. Income is actively changing TUI invoice entry, ledger doors and related tests: do not assign these files to a second writer without a handoff. Read the [income checkpoint](handoffs/2026-09-21-income-tax-checkpoint.md), existing receipts and other owners' handoffs, and request a bounded delta before using older briefs' gap claims. The checkpoint reports installed invoice capture/linking and interim quarterly results alongside incomplete annual/continuation acceptance; do not promote an interim or failed overall receipt to a full pass. Shared improvements are delivered once and consumed across lanes.

## Domain distinctions and official grounding

Keep invoice identity, economic transaction, payment/settlement, attached evidence, tax-period observation and filed declaration as distinct objects even where the product links them. A payment is not necessarily a new expense; invoice plus payment must not count twice. Absence of a payment record is not proof an invoice is unpaid. Preserve gross/base, IVA, recargo, withholding, deductible allocation and net amounts without inferring one economic direction twice from both sign and a direction enum.

AEAT's issued-invoice book identifies invoice number/series, issue and distinct operation dates, recipient and tax decomposition, with rectifying invoices distinguished. Its received-invoice book also covers appropriate accounting/customs documents and deductible tax amounts. These are materially richer than a date/description/net-cash row. [AEAT issued-invoice register](https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/libros-registro-iva/libro-registro-facturas-expedidas.html), [AEAT received-invoice register](https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/libros-registro-iva/libro-registro-facturas-recibidas.html).

Invoice-content and rectification requirements are distinct from correcting an internal bookkeeping annotation. Article 15 generally describes a new rectifying invoice identifying the corrected invoice(s), subject to its specified exceptions; a local overwrite is not proof of that legal act. Ground each supported scenario in the law applicable to its date and circumstances, including how correction amounts are represented. Do not implement sign semantics or jurisdictional tax treatment from this prose. [BOE invoicing regulation, articles 6 and 15](https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696).

Invoice date, operation/accrual date, receipt/registration date, payment date and tax-deduction period must not be collapsed. The tax owners determine the applicable inclusion rule. Preserve the facts and diagnose an unsupported timing shape instead of silently substituting whichever date exists. Likewise, partial business use, IVA deductibility and income-tax deductibility are not one interchangeable percentage.

Live remains blocked. This brief authorizes no bank connection, AEAT login/submission, supplier/customer delivery, real payment, real invoice cancellation or destructive store operation. All execution acceptance is synthetic and isolated.

## Source map and priority checks

Source anchor observed: `c33e3e48f643d25ab77760e727057b1db8074ed6`, branch `tui/modelo`. Concurrent working-tree edits are material; the anchor is orientation, not proof of a frozen tree. Paths below are relative to `src/cadrumo/`. Recheck cited symbols rather than trusting line numbers after another session edits them.

| Canonical owner | Source evidence | Reuse and capability boundary |
| --- | --- | --- |
| Invoice record/catalogue | `domain/invoices/models.py:128`, `:274`, `:1111` | Strict immutable values and an ID-keyed catalogue; line/tax detail, payment-status/reference and transaction links exist. ID hashes direction, number, issue date, counterparty, currency and grand total. Hash identity is not automatically a business-key conflict policy. |
| Raw movement and classified transaction | `domain/transactions/raw_transaction.py:136`; `domain/transactions/models.py:207`, `:427`, `:1058` | Separate provider/bank row and classified transaction with direction, invoice/evidence references and edit lineage. Amount magnitude is non-negative. Invoice payment fields, cash movements and cash-accounting settlement evidence exist; a complete payment/allocation aggregate was not established by this audit. |
| Statement import | `adapters/inbound/financial/ledger_import.py:33`; `application/ledger/actions_import.py:146`, `:180`, `:395` | Existing provider adapters, content IDs, cross-format fingerprints, suspected-duplicate notices and row/event co-commit. Two same-signature movements in one statement may be genuine; do not indiscriminately deduplicate by date/amount. |
| Manual entry/edit | `application/ledger/actions_manual.py:115`, `:747`, `:884`, `_carry_forward_invoice_link` (observed at `:1552`) | Idempotency handling and new content-addressed replacement with edit lineage already exist. Inspect reciprocal links when an edit changes identity, not only same-ID classification. |
| Invoice creation/import/update | `application/invoices/bulk_import.py:767`; `catalogue_creation.py:540`; `catalogue_lifecycle.py:146`, `:254` | Guarded catalogue mutation, duplicate ID checks and identity-excluding patches preserve links. Invoice create/update save before separate event emission; report and test partial outcomes. Immutable Python values do not prove durable access to every previous invoice payload. |
| Secure transaction persistence | `adapters/persistence/profile/transactions.py:758`, `:1199` | Encrypted per-record rows and membership index, atomic batch writes. A separately committed date-routing cache exists; test cache staleness/rebuild/date-range correctness and verify its metadata classification rather than assuming every stored byte is encrypted. Do not broaden plaintext payload content. |
| Secure invoice persistence/linking | `adapters/persistence/profile/invoices.py:161`, `:233`; `application/invoices/transaction_linking.py:80` | Revision-guarded encrypted singleton catalogue. Explicit link co-commits both catalogues, with an extra-write port for related events. Reuse this mechanism; test other mutation paths separately. |
| IVA bridge | `application/aggregation/iva_ledger.py:417`, `:573`; `_modelo_bindings_invoice_iva.py:722`, `:901` | Active transaction classification drives ledger-owned tax amounts; invoices support screening and received-invoice deduction authority. Persisting an invoice alone does not prove it contributes automatically. IVA-01 owns the tax oracle. |
| Income bridge | `application/aggregation/_renta_income_evidence.py:75`; `application/aggregation/tests/test_income_sales_invoice_evidence.py:406`, `:431`, `:499` | Linked sales evidence provides base/IVA/withholding decomposition from persisted records. Tests distinguish one-sided/multi-transaction link refusal and cash behavior; do not equate that fallback with fully evidenced invoice-derived income. INCOME-01 owns acceptance of the tax result. |

Priority checks before new features:

1. **Identity-changing edit:** the link carry-forward helper retains `Transaction.invoice_id`; by itself it does not rewrite the invoice's transaction-ID list. Trace the caller/alias resolution and reproduce a date/amount/identity-changing edit followed by consistency and tax-source checks. Do not declare all linked edits broken: a same-ID classify path has existing coverage.
2. **Persisted record, failed event:** creation and update mutate the invoice store before emitting their audit event. Exercise event failure, visible partial outcome and retry without duplicate creation or lost audit history. Do not replace the established persistence architecture speculatively.
3. **Exact replay versus similar movements:** fingerprints intentionally distinguish replay from two genuine same-day/same-amount movements. Test changed parser/narrative/source format and changed invoice total under the same printed identity. Establish conflict behavior before replacing hash/dedup rules.
4. **Stored history versus current view:** edits can replace a current catalogue key. Verify which original facts and evidence remain reconstructable; a revision marker or event count alone does not prove an audit trail retains the old document content.
5. **Currency and allocation:** preserve original currency, conversion source/date and EUR value across unrelated edits. Missing FX must not silently become a one-to-one EUR amount. Partial/multiple payments and deduction allocations require actual supported contracts, not interpretation of a status field.

These are source-supported risks or coverage questions, not reproduced runtime defects.

### Current CLI/TUI capability and usability

| User operation | CLI source-observed capability | TUI source-observed capability / gap |
| --- | --- | --- |
| Record invoice | `aeat app ledger invoice add` / `wizard`, issued or received; richer category, operation metadata, withholding, recargo, class/series, correction target and lines. | Current entry supports issued/received, category, withholding, class, series and notes. It still carries one base/rate pair and lacks operation type/date, recargo, structured lines and correction-target number. Earlier IVA notes that category was absent are stale. |
| Import | `app ledger invoice import --file PATH --kind ...` plus statement import. | Statement and issued/received invoice import, preview/apply. Inspect format tokens/adapter equivalence, not only different labels; supported parser routes may differ. |
| Find and inspect | `invoice list`, `invoice view ID`; ledger list/filter/view. | Entries index and review/evidence routes exist. No dedicated invoice read/update or transaction-detail edit door was found in the installed ledger map. Some review/evidence row selections explicitly report `destination_pending`. |
| Change/correct | Ledger update; invoice update limited to metadata, not identity/totals/date/currency/tax ID. Rectification metadata is supplied on add/update, not a separate `rectify` verb. | Generic invoice update is not wired. Offering `rectificativa` without its original-invoice reference is an incomplete input path: verify refusal and remediation, not only the selector's presence. |
| Evidence and linkage | Existing evidence routes and transaction-invoice link operations. | Installed evidence add/list/extract/confirm and linking/classification doors exist; some row drilldowns remain pending. A working add door does not establish evidence-detail navigation. |
| Payment state | Payloads expose payment status/reference; no dedicated payment-mutation/search command was established in the bounded map. | No installed payment surface found. Investigate existing settlement owner before declaring a universal payment capability or building a new one. |
| Export | `aeat app ledger export --output PATH` with format selection exists. | No installed ledger export door found. Verify export security and actual format semantics; neither is established by command registration. |

CLI anchors: `entrypoints/cli/_app_ledger_invoice_intake_command_specs.py:32`, `:94`; `_app_ledger_invoice_lifecycle_command_specs.py:47`, `:117`, `:171`; `_ledger_business_invoice_cli.py:266`, `:582`, `:689`, `:773`; `app_ledger_invoice_common_command_parameters.py:100`; `_app_ledger_foundation_command_specs.py:61`; `_app_ledger_management_command_specs.py:65`, `:124`; `_app_ledger_operations_command_specs.py:168`; `_ledger_read_cli.py:510`.

TUI anchors: `entrypoints/tui/ledger/models.py:69`, `:284`; `ledger_doors.py:240`, `:289`; `ledger/invoice_entry.py:130`; `ledger/import_flow.py:22`, `:255`; `ledger/entries.py:184`; `ledger/controller.py:721`; installed composition `launcher.py:819`. Routes include overview, entries, review, import, classification, evidence and reconciliation. These are static findings, not a keyboard/rendering acceptance result. Verify both field capture and discoverable completion/recovery actions; a screen or route name does not establish an executable journey.

## Directed verification candidates — NOT RUN

Source paths/function names were checked; no collection or test execution was performed:

- `src/cadrumo/adapters/persistence/profile/tests/test_linking_atomicity.py::test_mid_batch_failure_rolls_back_both_catalogues`
- `src/cadrumo/adapters/persistence/profile/tests/test_linking_atomicity.py::test_link_roundtrips_every_populated_field_through_both_catalogues`
- `src/cadrumo/adapters/persistence/profile/tests/test_edit_keeps_invoice_link.py::test_classifying_a_linked_row_keeps_its_invoice_link` (not proof of an ID-changing edit).
- `src/cadrumo/adapters/persistence/profile/tests/test_invoices_concurrent_create.py::test_a_concurrent_create_does_not_discard_the_other_invoice`
- `src/cadrumo/adapters/persistence/profile/tests/test_co_commit_event_guard.py::test_a_concurrent_event_is_not_discarded_by_the_co_commit` (not proof invoice creation uses this co-commit path).
- `src/cadrumo/application/ledger/tests/test_import_path_diagnostic_parity.py::test_a_repeated_movement_signature_is_counted_the_same_by_both_paths`
- `src/cadrumo/application/aggregation/tests/test_income_sales_invoice_evidence.py::test_a_one_directional_link_is_refused` (coordinate with INCOME-01; consume an unchanged valid receipt instead of duplicating it).
- `src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_lifecycle.py::test_catalogue_create_accepts_every_regime_option_and_holds_the_totals_identity`
- `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_ingestion_surfaces.py::test_invoice_entry_preserves_explicit_iva_treatment_for_linked_income` (actively edited/owned by income; do not duplicate its reservation).
- `src/cadrumo/entrypoints/tui/tests/test_ledger_flow_state_machine.py::test_a_write_in_flight_cannot_be_abandoned` (flow-state contract only, not installed navigation proof).

The launch-time Luna delta identifies current markers and the few missing ID-edit/event-failure/field-parity cases. Reserve exact nodes and explicit marker selection; this list is not permission to run every suite. Existing installed runtime identities and setup belong to their owners; no installation was attempted here.

## Acceptance matrix

Use a small orthogonal fixture set, not all regimes multiplied by all operations. Resolve the supported year/authority once; parameterize dates, pin provenance and retain distinct record identities. Typical anchors are an issued invoice with own-sales withholding, a received professional invoice, a mixed-rate purchase, a partly business-use purchase and an asset-linked acquisition. Reuse the tax briefs' legal expectations; include unsupported cases as explicit refusals, not guessed conversions.

| ID | Scenario | Required proof |
| --- | --- | --- |
| LE1 | Entry and reopening | Enter issued and received invoices and the relevant transactions through each actual frontend. Fresh-process reopening preserves canonical dates, identities, currency, amounts, line decomposition, classification and evidence links. Direct repository seeding does not prove user entry. |
| LE2 | Field parity and validation | Build a bounded critical-field matrix: domain support, CLI writer/readback, TUI writer/readback, import preservation, consumer. Include multi-line/multi-rate, operation territory/regime, recargo, withholding, deductible allocations, operation date and correction references. Unknowns, zero, false and unset remain distinct; reject unsupported fields without silently dropping them. |
| LE3 | Imports and replay | Exercise supported structured/manual/batch paths, preview where implemented, malformed/unsupported data, exact replay, changed content under the same business identity and same bytes under a different filename. Report partial acceptance/refusal per item. Retrying after interruption must not duplicate accepted records. Format detection alone is not parser support. |
| LE4 | Identity and numbering | Distinguish internal UUID, issuer/recipient identity, invoice number/series and source identity. Same supplier number in another supplier/year/series/entity is not automatically a duplicate; confirm the existing canonical key. Conflicting reuse must not overwrite or mint a duplicate unnoticed. Validate numbering only where this product actually issues documents. |
| LE5 | Corrections and history | Distinguish local data repair, transaction classification revision, reversal and legally rectifying invoice. Original evidence/history remains recoverable under the existing contract; references, reason, correction amounts and inclusion are explicit. Test wrong/missing target, repeated correction, cross-period target and a correction after a calculation/export. No silent mutation of filed history. |
| LE6 | Payment and linking | Verify available invoice-to-transaction/payment relations, no payment, partial/multiple payments, refund/reversal and over-allocation. Where unsupported, show a clear capability limit. Base/IVA/withholding/net coherence and economic direction survive linking; invoice plus cash cannot double-count. A linked row alone is not settled-payment proof. |
| LE7 | Dates and periods | Distinct issue/operation/payment dates straddling a quarter/year; out-of-year and unrelated-entity controls. Demonstrate source facts reach the owning tax resolver unchanged. Do not impose one universal date rule on IVA, income and retenciones. |
| LE8 | Evidence custody | Attach/import synthetic bytes through the encrypted evidence boundary; reopen and verify integrity/provenance and correct entity/record association. Missing, altered, wrong-record or unreadable evidence remains explicit. A filename, path, URL or digest alone is not custody or document authenticity. |
| LE9 | Related writes and failures | Exercise failure between related invoice, transaction, evidence and observation writes; inspect committed state and retry behavior. Existing atomicity/idempotency rules govern. No phantom success, orphaned undisclosed records or silent replacement of unrelated observations; do not invent a new transaction coordinator without a defined contract. |
| LE10 | Tax lineage and deduplication | For each already-owned tax bridge, identify included/excluded persisted record IDs and evidence grade. Modify one fact through a supported correction and verify the expected source delta using the tax owner's oracle. Missing/unlinked evidence cannot be concealed by a cash-only fallback, manual casilla injection or double inclusion. |
| LE11 | Entity isolation and stale work | Two synthetic entities with overlapping business identifiers remain isolated across selection/restart. Concurrent/stale edits and TUI in-flight writes have safe outcomes. Previously calculated work is invalidated or marked stale through the existing generation contract, not silently presented as current. |
| LE12 | Review and export usability | Both frontends let users find an invoice/transaction, inspect decomposition and provenance, understand missing links/classification, follow revisions and know what changed. Show list/search/filter coverage honestly. If exporting, distinguish diagnostic list, ledger/book export, invoice document and modelo filing artifact; verify supported format meaning rather than file existence. |
| LE13 | Continuation and receipts | CLI-only/TUI-only independent stores, plus sequential CLI-to-TUI and TUI-to-CLI continuation stores. Compare canonical meaning, links, revisions, refusal codes and source contributions. Use central harness/environment/receipt owners; no new family-specific subprocess or secret plumbing. |

All cases report proven, failed, blocked or not exercised. Backend unit/contract checks, installed-frontend acceptance and live checks remain separate evidence grades. Synthetic capture or a row visible in both frontends does not prove both frontends can create it.

## Bounded implementation cadence

1. Consume the source map and active-session handoffs; Luna checks only relevant deltas. Return a capability/ownership table before edits. No shared file becomes available merely because it appears in this brief.
2. Trace one issued and one received business record through existing write, custody and consumer paths. Establish identity, correction and related-write contracts before frontend changes.
3. Reproduce the highest-risk gaps with narrow synthetic checks. Implement only defined changes at their canonical owner; do not add parallel ledger models, invoice catalogues, parsers, payment stores or tax aggregators.
4. Integrate shared changes before dependent CLI/TUI changes. Preserve each frontend's independence and route shared logic through existing application/composition contracts. Runtime src/ never imports dev/.
5. Reserve exact tests with applicable markers and `-n 0`. Reuse unchanged tax-lane receipts; one assigned owner runs affected ruff/ty/strict-type/import gates after integration. No duplicate full-lane runs or broad collection to select a few cases.
6. Report LE outcomes, exact commands/results, sanitized evidence references, unresolved contracts and affected downstream verification. Escalate undefined correction/payment/atomicity semantics as a compact decision packet; principal agents never define new architecture.

## Session roster and launch prompt

Record provider, lead, cc number, UUID, owned files, dependencies and LE IDs before launching `ledger-core`. Split a `ledger-surfaces` session only after shared contracts are stable and file ownership is disjoint; each actual session receives its own full named roster and one adviser.

- `ledger-discovery`: Luna Max, bounded source/test delta and audit reports, <=650 words with path:line, confidence limits and checks NOT RUN. No edits/tests/private reads/children.
- `ledger-principal`: Terra High (Codex) or Opus Medium (Claude), complex implementation/analysis of defined work only.
- `ledger-execution-*`: Terra Max or Sonnet High, assigned bounded edits, tool calls, monitoring or sanitization/reporting only; no architecture or children.
- `ledger-adviser`: exactly one Sol High or Fable 5.1 Medium; bounded architecture/session-optimization consultation, no coding, idle otherwise. Verify aliases and availability; Claude discovery uses the named coordinated Luna lane.

Every worker gets a clear goal, allowed files/actions, exclusions, dependencies, stop condition and reporting format. Retain compact checkpoints and source-map deltas; do not repeatedly load full subsystems or fork the full transcript.

> Session ledger-core. Goal: assigned LEDGER-01 shared lifecycle outcomes through both CLI and TUI. Read LEDGER-01 revision 0.1, session-policy 1.8 and ACCEPTANCE-01 1.7. Consume the source map and active tax-session handoffs, then assign one bounded Luna delta. Report existing capability, exact ownership and the smallest missing lifecycle checks before editing. Reuse canonical invoices, transactions, encrypted custody and tax bridges. Distinguish local correction, rectifying invoice and tax-return amendment; preserve unknowns, entity identity and provenance. No duplicate stores/calculators, live actions or silent unsupported conversion. Coordinate verification once and reuse tax-lane evidence. Escalate undefined contracts; report LE outcomes and checkpoint the next bounded action.
