---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:03dad8c9021b030306b76acd98204d940e80de73476f4b1821eac9bd732b74b7'
related: []
---
# `mcp-parity` reference: `closed operations`

## Summary

Every locator in this record is relative to the root of this repository, on branch `feature/tui` at commit `85f84a2680`, read on 2026-10-10 by static analysis with nothing executed. The tree had uncommitted changes by another session; none of the source files cited here is among them. This record lists the 143 registered Cadrumo operations that do not list the MCP frontend in their permitted frontends: 72 admit the command line and the terminal interface, and 71 admit the command line only. It states facts only. It decides nothing, recommends nothing, and does not say whether any exclusion was intended.

### How the list was built

Three merged matrices of the registered operations were reconciled by `definition_id`: the ledger side (92 rows), the modelo and filing side (120 rows) and the profile, access and platform side (79 rows). That is 291 rows. They overlap at their edges: 22 ids appear in more than one matrix (14 in the modelo and platform matrices, 5 in the ledger and modelo matrices, 3 in all three). The union is 291 minus 14 minus 5 minus 2 times 3, which is 266 registered operations. By frontend set the 266 split as CTM 119, CT 72, C 71, CM 1 and M 3. The 123 that list MCP (CTM, CM and M) are not in this record. The remaining 143 are the closed operations: CT 72 plus C 71.

For each of the 143, the line that sets its permitted frontends was opened in the working tree and read. All 143 lists contain the command line, none contains MCP, and the terminal interface is present exactly in the 72 marked CT. The gap classes and the needs column are carried from the matrices, which are static readings; the host-path claims were checked against about twenty request models (`output_path`, `source_path`, `files`, `target`, `certificate_path` and similar fields). On gap class the matrices agree for every repeated id except `export.google-review` (G4 and G2 in two matrices, G4 alone in the third); the table gives G4, G2. The three matrices agree on the frontend code of every repeated id.

### Boundary facts

`AeatAccessGate.require_live_write` always raises (`src/cadrumo/core/access_gate/gate.py:96-107`). Its only production call site is `refuse_declared_live_write` in command-line dispatch (`src/cadrumo/entrypoints/cli/_command_runtime.py:331-346`), a search of `src/cadrumo_harness` finds no reference to the gate, and no command declares a live write. A tool call does not pass through that gate; on that path the boundary holds because no registered operation submits anything. `modelo.work.file` in the table below writes a local record and submits nothing. The two `live.borrador.100` definitions in this list read or import local snapshots; every other `live.*` definition lists MCP and is not in this record.

### Legend

Frontend codes: `CT` is command line plus terminal interface; `C` is command line only. Gap classes, each as the audit defines it (a row may carry more than one):

- G1: a registered operation exists; MCP is excluded only by the permitted-frontends list; the code states no reason; no secret, no host file path and no confirmation that lives outside the operation.
- G2: as G1, but the command line or terminal interface enforces a confirmation or gate outside the operation (a `--yes` flag, a dialog, a filing gate, a wizard, a programmatic `decide` callback).
- G3: the operation takes or writes a host file path, or needs document bytes.
- G4: closed to automation by stated design (a `requires_human` policy, a human-only comment or docstring, an accepted decision record, a secret that only the command line or terminal interface may submit, anything that grants or widens access).
- G5: the runtime supports it but the MCP adapter has no tool or wiring for what it needs; in this list, the financial operand submit.
- G6: a capability implemented in-process with no registered operation. No row in this list carries it, because every row is a registered operation.
- G7: local machine, installation or terminal administration that a client of a running runtime has no reason to perform.
- G8: declared but not usable, such as a definition that lists MCP without an access resolver. No closed operation carries it; the seven such definitions are in their own section below.

Needs column: `secret` (a declared ephemeral secret), `host path` (the request reads or writes a path on the runtime host), `human session` (the access policy sets `requires_human`), `client-side guard` (a confirmation or gate that lives in the command line or terminal interface, per the matrices), `financial operand` (a transient financial operand), or `none`.

## Closed operations

The deciding locator is the line where that definition sets its permitted frontends. Families that share one builder share one locator and say so in the note under the heading.

### Ledger entries and classification

Each definition sets its frontends in its own module, except the rule group, the ratios group and the attach and detach pair, which share one builder each. `ledger.classify.bulk` also refuses any frontend but the command line in its access resolver (`src/cadrumo/application/ledger/bulk_classify_operation.py:248`).

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `ledger.add` | add one manual transaction | C | G1 | none | `src/cadrumo/application/ledger/add_operation.py:179` |
| `ledger.update` | correct a transaction's editable facts | C | G1 | none | `src/cadrumo/application/ledger/update_operation.py:344` |
| `ledger.classify.single` | classify one transaction manually | C | G1 | none | `src/cadrumo/application/ledger/classify_operation.py:169` |
| `ledger.classify.bulk` | classify transactions from CSV text | C | G1 | none | `src/cadrumo/application/ledger/bulk_classify_operation.py:237` |
| `ledger.allocate` | record business and private split | C | G1 | none | `src/cadrumo/application/ledger/allocate_operation.py:164` |
| `ledger.split.manual` | split a transaction into children | C | G2 | client-side guard | `src/cadrumo/application/ledger/split_operation.py:411` |
| `ledger.merge` | merge a complete split cohort | C | G2 | client-side guard | `src/cadrumo/application/ledger/merge_operation.py:319` |
| `ledger.attach` | attach stored evidence to transaction | C | G1 | none | `src/cadrumo/application/ledger/attachment_mutation_operation.py:525` |
| `ledger.detach` | detach evidence from transaction | C | G1 | none | `src/cadrumo/application/ledger/attachment_mutation_operation.py:525` |
| `ledger.rule.add` | add or update a rule | C | G1 | none | `src/cadrumo/application/ledger/rule_operation.py:521` |
| `ledger.rule.list` | list stored rules | C | G1 | none | `src/cadrumo/application/ledger/rule_operation.py:521` |
| `ledger.rule.apply` | apply rules to unclassified rows | C | G1 | none | `src/cadrumo/application/ledger/rule_operation.py:521` |
| `ledger.ratios.list` | list usage-ratio overrides | C | G1 | none | `src/cadrumo/application/ledger/ratios_operation.py:430` |
| `ledger.ratios.set` | set a usage ratio | C | G1 | none | `src/cadrumo/application/ledger/ratios_operation.py:430` |
| `ledger.ratios.unset` | remove a usage ratio | C | G1 | none | `src/cadrumo/application/ledger/ratios_operation.py:430` |
| `ledger.ratios.eligible` | list ratio-eligible categories | C | G1 | none | `src/cadrumo/application/ledger/ratios_operation.py:430` |
| `ledger.ratios.validate` | validate ratios against bounds | C | G1 | none | `src/cadrumo/application/ledger/ratios_operation.py:430` |

### Ledger lifecycle and removal

`ledger.archive`, `ledger.stash`, `ledger.restore` and `ledger.exclude` share one builder, so one locator.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `ledger.archive` | archive a transaction | C | G2 | client-side guard | `src/cadrumo/application/ledger/lifecycle_mutation_operation.py:380` |
| `ledger.stash` | stash a transaction | C | G2 | client-side guard | `src/cadrumo/application/ledger/lifecycle_mutation_operation.py:380` |
| `ledger.restore` | restore a stashed transaction | C | G2 | client-side guard | `src/cadrumo/application/ledger/lifecycle_mutation_operation.py:380` |
| `ledger.exclude` | exclude a transaction from filing | C | G2 | client-side guard | `src/cadrumo/application/ledger/lifecycle_mutation_operation.py:380` |
| `ledger.remove` | remove one transaction | C | G2 | client-side guard | `src/cadrumo/application/ledger/remove_operation.py:204` |
| `ledger.reset` | reset the ledger catalogue | C | G2 | client-side guard | `src/cadrumo/application/ledger/reset_operation.py:212` |
| `ledger.participation.rebuild` | rebuild derived participation index | CT | G1 | none | `src/cadrumo/application/ledger/participation_rebuild_operation.py:109` |

### Statement import and export

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `ledger.import` | import bank statement files | CT | G3, G2 | host path, client-side guard | `src/cadrumo/application/ledger/import_operation.py:662` |
| `ledger.export` | export ledger rows to a file | CT | G3, G4 | host path, human session | `src/cadrumo/application/ledger/export_operation.py:254` |

### Evidence and invoice intake

`ledger.invoice.import` and `ledger.invoice.wizard` share one builder. `ledger.evidence.batch` also refuses any frontend but the command line in its access resolver (`src/cadrumo/application/ledger/evidence_ingestion_operation.py:269`).

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `ledger.evidence.add` | register an invoice evidence file | CT | G3 | host path | `src/cadrumo/application/ledger/evidence_add_operation.py:389` |
| `ledger.evidence.batch` | ingest a directory of invoices | C | G3, G4 | host path, human session | `src/cadrumo/application/ledger/evidence_ingestion_operation.py:310` |
| `ledger.evidence.update` | update an evidence record | C | G1 | none | `src/cadrumo/application/ledger/evidence_mutation_operation.py:564` |
| `ledger.evidence.remove` | delete an evidence record | C | G2 | client-side guard | `src/cadrumo/application/ledger/evidence_mutation_operation.py:564` |
| `ledger.evidence.extract` | extract a draft invoice | CT | G1 | none | `src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:249` |
| `ledger.evidence.confirm` | confirm a reviewed draft invoice | CT | G2 | client-side guard | `src/cadrumo/application/ledger/invoice_evidence_confirm_operation.py:258` |
| `ledger.invoice.import` | bulk-create invoices from file | C | G3 | host path | `src/cadrumo/application/invoices/catalogue_intake_operation.py:43` |
| `ledger.invoice.wizard` | create an invoice from arguments | C | G1 | none | `src/cadrumo/application/invoices/catalogue_intake_operation.py:43` |

### Ledger reads closed to MCP

The five evidence follow-up reads (`attachment_queue`, `attachment_view`, `consent.list`, `review.list`, `review.view`) share one builder.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `ledger.evidence.list` | list registered evidence | CT | G1 | none | `src/cadrumo/application/ledger/evidence_read_operation.py:489` |
| `ledger.evidence.view` | view one evidence record | CT | G1 | none | `src/cadrumo/application/ledger/evidence_read_operation.py:489` |
| `ledger.evidence.reader-readiness` | measure the local document reader | CT | G1 | none | `src/cadrumo/application/ledger/invoice_evidence_readiness_operation.py:206` |
| `ledger.evidence.attachment_queue` | list attachments awaiting review | CT | G1 | none | `src/cadrumo/application/ledger/evidence_followup_registration.py:67` |
| `ledger.evidence.attachment_view` | view one attachment manifest | CT | G1 | none | `src/cadrumo/application/ledger/evidence_followup_registration.py:67` |
| `ledger.evidence.consent.list` | list off-host consent history | CT | G1 | none | `src/cadrumo/application/ledger/evidence_followup_registration.py:67` |
| `ledger.evidence.review.list` | list pending extraction drafts | CT | G1 | none | `src/cadrumo/application/ledger/evidence_followup_registration.py:67` |
| `ledger.evidence.review.view` | view one pending draft | CT | G1 | none | `src/cadrumo/application/ledger/evidence_followup_registration.py:67` |

### Declaration work units and their reads

`modelo.bindings.resolve` and `modelo.readiness` name no frontends in their own builders (`src/cadrumo/application/modelo/query_read_operation.py:482-492` and `:506-515`) and take the default of the shared read builder, `{CLI, TUI}`.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `modelo.work.create` | create or reuse a work unit | CT | G2 | client-side guard | `src/cadrumo/application/modelo/work_create_operation.py:365` |
| `modelo.work.list` | list work units | CT | G1 | none | `src/cadrumo/application/modelo/work_inventory_operation.py:109` |
| `modelo.work.metadata` | read work unit metadata | CT | G1 | none | `src/cadrumo/application/modelo/metadata_read_operation.py:135` |
| `modelo.work.review` | read compact work unit snapshot | CT | G1 | none | `src/cadrumo/application/modelo/work_review_operation.py:104` |
| `modelo.work.history` | read work unit event history | CT | G1 | none | `src/cadrumo/application/modelo/history_operation.py:172` |
| `modelo.history` | read one modelo's event history | CT | G1 | none | `src/cadrumo/application/modelo/lifecycle_history_operation.py:124` |
| `modelo.work.dependencies` | inspect cross-period dependencies | CT | G1 | none | `src/cadrumo/application/modelo/dependency_operation.py:241` |
| `modelo.work.revisions` | list calculation revisions | CT | G1 | none | `src/cadrumo/application/modelo/revision_inventory_operation.py:160` |
| `modelo.work.revision` | select one calculation revision | CT | G1 | none | `src/cadrumo/application/modelo/revision_selection_operation.py:329` |
| `modelo.work.revision_snapshot` | inspect one revision snapshot | CT | G1 | none | `src/cadrumo/application/modelo/revision_snapshot_operation.py:120` |
| `modelo.bindings.resolve` | preview unsaved binding overrides | CT | G1 | none | `src/cadrumo/application/modelo/query_read_operation.py:454-456` |
| `modelo.readiness` | read modelo readiness for profile | CT | G1 | none | `src/cadrumo/application/modelo/query_read_operation.py:454-456` |
| `modelo.work.compare_taxation` | compare individual and joint taxation | C | G1 | none | `src/cadrumo/application/modelo/taxation_comparison_operation.py:173` |
| `modelo.work.wizard_context` | read remaining wizard inputs | CT | G2 | client-side guard | `src/cadrumo/application/modelo/wizard_context_operation.py:131` |
| `modelo.work.wizard_attempt` | record a wizard calculation attempt | CT | G2 | client-side guard | `src/cadrumo/application/modelo/wizard_attempt_operation.py:232` |
| `modelo.work.m303_attestation` | admit Modelo 303 evidence attestation | CT | G1 | none | `src/cadrumo/application/modelo/m303_attestation_operation.py:239` |

### Declaration lifecycle

The eight lifecycle writers sit in one module, each with its own frontend line; the eighth, `modelo.edit.apply`, is listed under casilla edits. The local filed record is a local record only. `modelo.work.verify` reads through the certificate backend; see Not verified.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `modelo.work.calculate` | calculate a work unit | CT | G2 | client-side guard | `src/cadrumo/application/modelo/operation_definitions.py:569` |
| `modelo.work.verify` | verify revision, persist report | CT | G1 | none | `src/cadrumo/application/modelo/operation_definitions.py:929` |
| `modelo.work.file` | record revision as locally filed | CT | G2 | client-side guard | `src/cadrumo/application/modelo/operation_definitions.py:1109` |
| `modelo.export` | export filing file or report | CT | G2, G3 | host path, client-side guard | `src/cadrumo/application/modelo/operation_definitions.py:1408` |
| `modelo.work.amend` | start an amendment record | CT | G1 | none | `src/cadrumo/application/modelo/operation_definitions.py:1545` |
| `modelo.work.discard` | discard a work unit | CT | G2 | client-side guard | `src/cadrumo/application/modelo/operation_definitions.py:699` |
| `modelo.work.rename` | rename a work unit | CT | G1 | none | `src/cadrumo/application/modelo/operation_definitions.py:1792` |
| `modelo.work.amendment_context` | read context for an amendment | CT | G1 | none | `src/cadrumo/application/modelo/amendment_context_operation.py:205` |
| `modelo.work.filing_record` | read one filing record by selection | CT | G1 | none | `src/cadrumo/application/modelo/filing_selection_operation.py:119` |
| `modelo.filing_record.list` | list filing histories | C | G1 | none | `src/cadrumo/application/modelo/filing_record_list_operation.py:142` |
| `modelo.filing_record.view` | view a filing record | CT | G1 | none | `src/cadrumo/application/modelo/filing_record_view_operation.py:304` |
| `modelo.filing_record.import` | import external filing evidence locally | C | G3, G1 | host path | `src/cadrumo/application/modelo/filing_record_import_operation.py:296` |
| `modelo.observation.local` | record local casilla observation | C | G1 | none | `src/cadrumo/application/modelo/local_observation_operation.py:197` |

### Casilla edits and workbench reads

The five workbench reads (`modelo.work.form`, `modelo.work.casilla_help`, `modelo.edit.renew`, `modelo.edit.preflight`, `modelo.edit.apply_prerequisite`) share one builder and one constant, `_HUMAN_FRONTENDS`, defined at `src/cadrumo/application/modelo/workbench_operations.py:479`. `modelo.edit.apply` and `modelo.edit.preflight` declare a transient financial operand (`src/cadrumo/application/modelo/operation_definitions.py:1729`, `src/cadrumo/application/modelo/workbench_operations.py:513`); a search for "financial" under `src/cadrumo_harness/mcp/` returns no match.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `workbench.generation` | read one workbench generation | CT | G4 | human session | `src/cadrumo/application/workbench_generation_operation.py:142` |
| `modelo.work.form` | read whole editor form | CT | G4 | human session | `src/cadrumo/application/modelo/workbench_operations.py:516` |
| `modelo.work.casilla_help` | read casilla help card | CT | G4 | human session | `src/cadrumo/application/modelo/workbench_operations.py:516` |
| `modelo.edit.renew` | renew the edit baseline | CT | G4 | human session | `src/cadrumo/application/modelo/workbench_operations.py:516` |
| `modelo.edit.preflight` | preflight staged casilla edits | CT | G4, G5 | human session, financial operand | `src/cadrumo/application/modelo/workbench_operations.py:516` |
| `modelo.edit.apply` | apply staged casilla edits | CT | G5, G2 | financial operand, client-side guard | `src/cadrumo/application/modelo/operation_definitions.py:1728` |
| `modelo.edit.apply_prerequisite` | read source casilla of refusal | CT | G4 | human session | `src/cadrumo/application/modelo/workbench_operations.py:516` |

### Review packages, audit, verification reports and quickfile

The six review-package exchange definitions share one builder; their constant `_FRONTENDS` is defined at `src/cadrumo/application/modelo/review_package_exchange_operation.py:90`. `modelo.audit.read` and `modelo.audit.export` take `_HUMAN_FRONTENDS` (`{CLI}`, defined at `src/cadrumo/application/modelo/audit_operation.py:75`). `modelo.quickfile` also refuses any frontend but the command line in its access resolver (`src/cadrumo/application/modelo/quickfile_operation.py:354`).

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `modelo.verification_report.list` | list persisted verification reports | C | G1 | none | `src/cadrumo/application/modelo/verification_report_read_operation.py:140` |
| `modelo.verification_report.view` | view one verification report | C | G1 | none | `src/cadrumo/application/modelo/verification_report_read_operation.py:140` |
| `modelo.work.report_verify` | verify a summary PDF signature | CT | G3 | host path | `src/cadrumo/application/modelo/calculation_report_verification_operation.py:265` |
| `modelo.quickfile` | run the five-stage filing chain | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/quickfile_operation.py:314` |
| `modelo.audit.read` | read an audit evidence bundle | C | G4 | human session | `src/cadrumo/application/modelo/audit_operation.py:548` |
| `modelo.audit.export` | export audit bundle as ZIP | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/audit_operation.py:559` |
| `modelo.review_package.build` | build a local review package | CT | G3 | host path | `src/cadrumo/application/modelo/review_package_operation.py:370` |
| `modelo.review_package.sign` | sign a review package | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/review_package_exchange_operation.py:577` |
| `modelo.review_package.counter_sign` | counter-sign a signature envelope | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/review_package_exchange_operation.py:577` |
| `modelo.review_package.encrypt_for_recipient` | encrypt a package for recipient | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/review_package_exchange_operation.py:577` |
| `modelo.review_package.decrypt` | decrypt a recipient package | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/review_package_exchange_operation.py:577` |
| `modelo.review_package.encrypt_feedback` | encrypt feedback to originator | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/review_package_exchange_operation.py:577` |
| `modelo.review_package.import_feedback` | import a recipient feedback envelope | C | G4, G3 | human session, host path | `src/cadrumo/application/modelo/review_package_exchange_operation.py:577` |

### Modelo-specific families

Sub-families: Modelo 036 (`_HUMAN_FRONTENDS` defined at `src/cadrumo/application/modelo/m036_operation.py:78`, `_RECORD_FRONTENDS` at `:79`); Modelo 145 (one builder for five ids); IVA wallet (one module per id); maritime preview; spreadsheet and review workbooks; reconcile export. `export.google-review` publishes to Google, not to AEAT.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `modelo.036.read` | read recorded Modelo 036 declarations | CT | G4 | human session | `src/cadrumo/application/modelo/m036_operation.py:476` |
| `modelo.036.record` | record externally filed Modelo 036 | C | G4 | human session | `src/cadrumo/application/modelo/m036_operation.py:487` |
| `modelo.m145.create` | create a Modelo 145 record | C | G1 | none | `src/cadrumo/application/modelo/m145_communication_operation.py:161` |
| `modelo.m145.validate` | validate a Modelo 145 record | C | G1 | none | `src/cadrumo/application/modelo/m145_communication_operation.py:161` |
| `modelo.m145.export` | export a Modelo 145 as text | C | G1 | none | `src/cadrumo/application/modelo/m145_communication_operation.py:161` |
| `modelo.m145.mark_delivered_to_payer` | mark Modelo 145 delivered to payer | C | G1 | none | `src/cadrumo/application/modelo/m145_communication_operation.py:161` |
| `modelo.m145.mark_locally_completed` | mark Modelo 145 locally completed | C | G1 | none | `src/cadrumo/application/modelo/m145_communication_operation.py:161` |
| `modelo.iva-wallet.balance` | read IVA wallet balance | C | G1 | none | `src/cadrumo/application/modelo/iva_wallet_balance_operation.py:213` |
| `modelo.iva-wallet.seed` | seed an IVA wallet period | C | G2 | client-side guard | `src/cadrumo/application/modelo/iva_wallet_seed_operation.py:245` |
| `modelo.iva-wallet.correct` | correct an IVA wallet period | C | G2 | client-side guard | `src/cadrumo/application/modelo/iva_wallet_correction_operation.py:248` |
| `modelo.iva-wallet.override` | override an IVA wallet period | C | G2 | client-side guard | `src/cadrumo/application/modelo/iva_wallet_override_operation.py:274` |
| `modelo.work.preview_maritime_exemption` | preview the maritime income exemption | C | G1 | none | `src/cadrumo/application/modelo/maritime_preview_operation.py:239` |
| `modelo.spreadsheet.export` | export calculation surface to XLSX | C | G3 | host path | `src/cadrumo/application/modelo/modelo_spreadsheet_operation.py:57` |
| `export.calculation-review-xlsx` | write saved calculation as XLSX | CT | G3 | host path | `src/cadrumo/application/export/calculation_review_xlsx_operation.py:216` |
| `export.google-review` | publish saved calculation to Google Sheets | CT | G4, G2 | human session, client-side guard | `src/cadrumo/application/export/google_review_operation.py:175` |
| `modelo.reconcile.export-xlsx` | export reconciliation differences as XLSX | CT | G3 | host path | `src/cadrumo/application/modelo/reconciliation_export_operation.py:224` |

### Live captures and reads that are closed

Every other `live.*` definition lists MCP and is not in this record. The two below are built together; `_HUMAN_FRONTENDS` is defined at `src/cadrumo/application/live/borrador_100_operation.py:80` and `_IMPORT_FRONTENDS` at `:81`.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `live.borrador.100.read` | read Modelo 100 borrador snapshots | CT | G4 | human session | `src/cadrumo/application/live/borrador_100_operation.py:419` |
| `live.borrador.100.import` | import local borrador PDF snapshot | C | G4, G3 | human session, host path | `src/cadrumo/application/live/borrador_100_operation.py:435` |

### Authentication to AEAT and providers

Where an access resolver names a human session for these ids: `src/cadrumo/application/auth/apoderado_operation.py:157`, `src/cadrumo/application/auth/provider_configure_operation_access.py:87`, `src/cadrumo/application/auth/session_acquire_operation_access.py:50`, `src/cadrumo/application/auth/diagnostic_report_operation.py:247`.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `auth.apoderado.configure` | set represented NIF and scopes | CT | G4 | secret, human session | `src/cadrumo/application/auth/apoderado_operation.py:200` |
| `auth.apoderado.clear` | clear the apoderado setup | CT | G4 | human session | `src/cadrumo/application/auth/apoderado_operation.py:200` |
| `auth.provider.configure` | configure provider authentication route | CT | G4, G3 | human session, host path | `src/cadrumo/application/auth/operation_definitions.py:517` |
| `auth.session.acquire` | acquire or verify provider session | CT | G4 | human session | `src/cadrumo/application/auth/operation_definitions.py:527` |
| `auth.diagnostics.phone-state-report` | record observed Clave phone state | CT | G4 | human session | `src/cadrumo/application/auth/diagnostic_report_operation.py:272` |

### Certificates

The five certificate source definitions share one builder (`_HUMAN_FRONTENDS` defined at `src/cadrumo/application/auth/certificate_source_operation.py:77`; human session at `:222`); the two certificate secret definitions share another (`_FRONTENDS` defined at `src/cadrumo/application/auth/certificate_secret_operation.py:51`; the passphrase secret is declared except when removing, at `:213`).

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `auth.certificate.secret.set` | bind or rotate certificate passphrase | CT | G4 | secret, human session | `src/cadrumo/application/auth/certificate_secret_operation.py:212` |
| `auth.certificate.secret.remove` | remove stored certificate passphrase | CT | G4 | human session | `src/cadrumo/application/auth/certificate_secret_operation.py:212` |
| `auth.certificate.source.register` | register a certificate source file | CT | G3, G4 | human session, host path | `src/cadrumo/application/auth/certificate_source_operation.py:135` |
| `auth.certificate.source.list` | list certificate sources | CT | G4 | human session | `src/cadrumo/application/auth/certificate_source_operation.py:135` |
| `auth.certificate.source.select` | select the active certificate source | CT | G4 | human session | `src/cadrumo/application/auth/certificate_source_operation.py:135` |
| `auth.certificate.source.remove` | remove a certificate source | CT | G4 | human session | `src/cadrumo/application/auth/certificate_source_operation.py:135` |
| `auth.certificate.source.check` | check certificate source expiry | CT | G4 | human session | `src/cadrumo/application/auth/certificate_source_operation.py:135` |

### Automation access administration

The seven automation definitions share one builder. The three below take `{CLI, TUI}` because they are in `_HUMAN_DEFINITIONS` (`src/cadrumo/application/user_profile/automation_operations.py:77-82`); the four proposal definitions that are not in that set list MCP and appear under Listed for MCP and not runnable. `user-profile.automation-approve` declares the secret kind `automation.password` (`src/cadrumo/application/user_profile/automation_operations.py:390-395`).

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `user-profile.automation-approve` | approve an automation grant | CT | G4 | secret, human session | `src/cadrumo/application/user_profile/automation_operations.py:413-417` |
| `user-profile.automation-decline` | decline an automation request | CT | G4 | human session | `src/cadrumo/application/user_profile/automation_operations.py:413-417` |
| `user-profile.automation-inventory` | list grants, keys and requests | CT | G4 | human session | `src/cadrumo/application/user_profile/automation_operations.py:413-417` |

### Profile lifecycle, archive and history

The three archive definitions share one constant, `_FRONTENDS`, defined at `src/cadrumo/application/user_profile/archive_operation.py:73`. For `user-profile.censo-file-import` the request carries parsed facts, not a path; see Not verified.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `auth.profile.passphrase-rotate` | rotate the profile passphrase | CT | G4 | secret, human session | `src/cadrumo/application/auth/operation_definitions.py:560` |
| `user-profile.censo-file-import` | enrol facts from censal certificate | C | G3 | none | `src/cadrumo/application/user_profile/censal_file_import_operation.py:261` |
| `profile.history` | browse profile event history | C | G1 | none | `src/cadrumo/application/user_profile/history_operation.py:146` |
| `profile.archive.export` | export a sealed profile archive | C | G3, G4 | human session, host path | `src/cadrumo/application/user_profile/archive_operation.py:527` |
| `profile.archive.push` | push profile mirror to Drive | C | G4 | human session | `src/cadrumo/application/user_profile/archive_operation.py:540` |
| `profile.archive.reconcile` | reconcile interrupted archive exports | C | G4, G7 | human session | `src/cadrumo/application/user_profile/archive_operation.py:549` |

### Google and collaboration configuration

The six `config.google.*` definitions share one builder (human session at `src/cadrumo/application/user_profile/google_configuration_operation.py:101`); the three `config.collab.recipient.*` definitions share another.

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `config.google.status` | read Google configuration status | C | G4 | human session | `src/cadrumo/application/user_profile/google_configuration_operation.py:143` |
| `config.google.probe` | probe Drive synchronisation | C | G4 | human session | `src/cadrumo/application/user_profile/google_configuration_operation.py:143` |
| `config.google.login` | Google consent and login | C | G4 | human session | `src/cadrumo/application/user_profile/google_configuration_operation.py:143` |
| `config.google.logout` | revoke stored Google tokens | C | G4 | human session | `src/cadrumo/application/user_profile/google_configuration_operation.py:143` |
| `config.google.folder.view` | view the Drive root folder | C | G4 | human session | `src/cadrumo/application/user_profile/google_configuration_operation.py:143` |
| `config.google.folder.organize` | move the Drive root folder | C | G4 | human session | `src/cadrumo/application/user_profile/google_configuration_operation.py:143` |
| `config.collab.recipient.add` | register trusted review recipient key | C | G1 | none | `src/cadrumo/application/modelo/review_package_recipient_operations.py:540` |
| `config.collab.recipient.list` | list trusted recipients | C | G1 | none | `src/cadrumo/application/modelo/review_package_recipient_operations.py:540` |
| `config.collab.recipient.remove` | remove a trusted recipient | C | G1 | none | `src/cadrumo/application/modelo/review_package_recipient_operations.py:540` |

### Workflow

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `workflow.run.read` | read one workflow run | CT | G1 | none | `src/cadrumo/application/workflow/run_read_operation.py:260` |
| `workflow.run.list` | list workflow runs | CT | G1 | none | `src/cadrumo/application/workflow/run_read_operation.py:273` |
| `workflow.resume.context` | capture resume context | CT | G1 | none | `src/cadrumo/application/workflow/resume_operation.py:258` |

### Diagnostics and the rest

`diagnostics.workstation.check` also refuses any frontend but the command line in its access resolver (`src/cadrumo/application/workstation_check_operation.py:302`).

| definition_id | what it does | frontends | gap class(es) | needs | deciding locator |
|---|---|---|---|---|---|
| `diagnostics.workstation.check` | workstation health report | C | G7 | none | `src/cadrumo/application/workstation_check_operation.py:290` |

## Stated reasons in code

The families below have a sentence in the definition, its module docstring or a nearby comment that names a human or CLI audience for them. Each sentence is quoted with its locator. The `src/cadrumo/application/` prefix is written out in full.

| family | quoted sentence | locator |
|---|---|---|
| Workbench owner reads (`modelo.work.form`, `modelo.work.casilla_help`, `modelo.edit.renew`, `modelo.edit.preflight`, `modelo.edit.apply_prerequisite`) | "Owner reads for a human at a password-authenticated CLI or TUI; never an agent or off-host destination." | `src/cadrumo/application/modelo/workbench_operations.py:478` |
| Workbench owner reads (same five) | "The workbench form is an owner read model: a password-authenticated human CLI or TUI session may receive it through the verified local transport, and no agent or off-host destination may." | `src/cadrumo/application/modelo/workbench_projection.py:3-5` |
| `workbench.generation` | "Human-only registered read of one immutable workbench generation." | `src/cadrumo/application/workbench_generation_operation.py:1` |
| Human Google publication (`export.google-review`) | "Register human-only Google publication with exact disclosure and settlement." | `src/cadrumo/application/export/google_review_operation.py:1` |
| Human Google publication (`export.google-review`) | "Hold an immutable review through a durable, human-only response checkpoint." | `src/cadrumo/application/export/google_review_operation_executor.py:137` |
| Profile archive (`profile.archive.export`, `.push`, `.reconcile`) | "Register the complete existing human archive family without agent escalation." | `src/cadrumo/application/user_profile/archive_operation.py:516` |
| Profile archive (same three) | "Neither portable recovery nor mirror output grants renewed automation authority." | `src/cadrumo/application/user_profile/archive_operation.py:5` |
| Automation inventory, approval and decline | "Inventory is human-only private metadata in the existing encrypted result store; observing an operation never grants new authority." (a code comment, about the inventory result) | `src/cadrumo/application/user_profile/automation_operations.py:293-294` |
| Passphrase rotation (`auth.profile.passphrase-rotate`) | "Human-only authority and settled projection for registered password rotation." | `src/cadrumo/application/auth/passphrase_operation_access.py:1` |
| Provider session acquisition (`auth.session.acquire`) | "Exact-profile human authority for provider login and its bounded result." | `src/cadrumo/application/auth/session_acquire_operation_access.py:1` |
| Provider session acquisition (`auth.session.acquire`) | "Require human authority separately at execution, publication and release." | `src/cadrumo/application/auth/session_acquire_operation_access.py:42` |
| Certificate sources (five ids) | "Require exact-profile human authority and fresh result disclosure." | `src/cadrumo/application/auth/certificate_source_operation.py:197` |
| Human evidence ingestion (`ledger.evidence.batch`) | "Human evidence ingestion through one exact-profile worker authority." | `src/cadrumo/application/ledger/evidence_ingestion_operation.py:1` |
| Human evidence ingestion (`ledger.evidence.batch`) | "Require human CLI, all-period scope and exact dual-category disclosure." | `src/cadrumo/application/ledger/evidence_ingestion_operation.py:263` |
| Google configuration (six `config.google.*` ids) | "Register and resolve human Google configuration operations." | `src/cadrumo/application/user_profile/google_configuration_operation.py:1` |
| Review package exchange (six ids) | "Registered human review-package exchange using canonical crypto and custody." | `src/cadrumo/application/modelo/review_package_exchange_operation.py:1` |
| Review package exchange (six ids) | "Enroll the complete six-route family, retaining explicit human authority." | `src/cadrumo/application/modelo/review_package_exchange_operation.py:567` |
| Named access profiles with a `HUMAN_` prefix (used by the certificate secrets, passphrase rotation, provider configuration, session acquisition, borrador, audit, Modelo 036, review package exchange and profile archive resolvers) | "HUMAN_: only a human session may act." | `src/cadrumo/application/operations/access_resolution.py:372` |
| Secrets (`auth.apoderado.configure`, `auth.certificate.secret.set`, `auth.profile.passphrase-rotate`, `user-profile.automation-approve` declare one) | "Consume a CLI/TUI secret through its exact operation's protected handoff." The same method raises a frontend refusal for any frontend but the command line and terminal interface; the runtime repeats the check. | `src/cadrumo/adapters/local_runtime/frontend_client.py:313-316`, `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:89-90` |
| Secrets and grant approval (accepted decision record, status `accepted`) | "Passwords, keys, recovery values and unlock material never enter MCP arguments/results, elicitation forms, chat, ordinary JSON/text output, argv, environment values, clipboard defaults, logs or plaintext temporary files." | `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:90` |
| Automation grant approval (same accepted record) | "The user opens either trusted CLI or TUI, inspects that request and proves the profile password through the dedicated secret channel." | `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:84` |

### Wording that names an audience or the setting without giving a reason

| id or family | sentence | locator |
|---|---|---|
| `ledger.export` | "Registered exact-profile human ledger export using the canonical serializer." The access resolver sets `requires_human` at `:241`. | `src/cadrumo/application/ledger/export_operation.py:1` |
| `modelo.quickfile` | "Register the existing local human chain with encrypted inputs and full effect settlement." The access resolver sets `requires_human` at `:399`. | `src/cadrumo/application/modelo/quickfile_operation.py:292` |
| `modelo.audit.read`, `modelo.audit.export` | "Registered exact-profile audit reads and explicit human ZIP export." | `src/cadrumo/application/modelo/audit_operation.py:1` |
| `live.borrador.100.read`, `.import` | "Declare full human reads, safe agent queries and human local PDF import." | `src/cadrumo/application/live/borrador_100_operation.py:407` |
| `modelo.036.read`, `modelo.036.record` | "Registered local Modelo 036 recording and separately authorized reads." | `src/cadrumo/application/modelo/m036_operation.py:1` |
| `ledger.rule.add`, `.list`, `.apply` | "Declare one CLI-only, exact-profile recorded rule operation." | `src/cadrumo/application/ledger/rule_operation.py:501` |
| `profile.history` | "Declare a CLI-only read of all periods without COMMIT or provider effects." | `src/cadrumo/application/user_profile/history_operation.py:138` |

### Families for which the code states nothing

For these families the definition, the module docstring and the lines around the frontend declaration say nothing about why the family is closed to MCP, and a search of `src/cadrumo/application` for phrases such as "human-only", "CLI-only", "never an agent" and "without agent" found no sentence about them:

- ledger entries and classification (except the CLI-only wording of the rule family above), ledger lifecycle and removal, statement import, the ledger reads closed to MCP, and the evidence and invoice intake ids other than `ledger.evidence.batch`;
- declaration work units and their reads, and the declaration lifecycle (all thirteen ids);
- verification reports, the review package build, Modelo 145, the IVA wallet, the maritime preview, the spreadsheet and review workbooks, and the reconcile export;
- `auth.apoderado.configure`, `auth.apoderado.clear`, `auth.provider.configure` and `auth.diagnostics.phone-state-report`, which require a human session in their resolvers (`src/cadrumo/application/auth/apoderado_operation.py:157`, `src/cadrumo/application/auth/provider_configure_operation_access.py:87`, `src/cadrumo/application/auth/diagnostic_report_operation.py:247`) without a sentence about it;
- `user-profile.censo-file-import` and `config.collab.recipient.*`;
- workflow, and `diagnostics.workstation.check`.

## Listed for MCP and not runnable

Seven definitions list MCP in their permitted frontends and cannot complete through the MCP path. They are not among the 143. Six are registered without an access resolver, so resolving access raises `OPERATION_UNAVAILABLE` (`src/cadrumo/application/operations/access_resolution.py:484-490`); the seventh has a resolver and declares a secret.

| definition_id | frontends set at | reason | locator |
|---|---|---|---|
| `user-profile.automation-request` | `src/cadrumo/application/user_profile/automation_operations.py:413-417` (all frontends unless the id is in `_HUMAN_DEFINITIONS`) | registered with `access_resolver=None`; the resolver is attached only to the human definitions | `src/cadrumo/application/user_profile/automation_operations.py:450` |
| `user-profile.automation-rotate` | same | same | same |
| `user-profile.automation-renew` | same | same | same |
| `user-profile.automation-scope` | same | same | same |
| `export.google-sheets` | `src/cadrumo/application/export/google_operation.py:556` | registration composed without an access resolver; the command line still submits it | `src/cadrumo/application/export/google_operation.py:578-591`, `src/cadrumo/entrypoints/cli/runtime_modelo_spreadsheet_push.py:65` |
| `local-reader.provision` | `src/cadrumo/application/local_reader_operation.py:111` | registration composed without an access resolver | `src/cadrumo/application/local_reader_operation.py:119-132` |
| `user-profile.bundle-export` | `src/cadrumo/application/user_profile/operations.py:149` | has a resolver (`:315`) and declares an ephemeral secret (`:225-228`); secret submission is refused for any frontend but the command line and terminal interface, and the MCP execute path starts an operation only when the receipt has no secret requirement | `src/cadrumo/adapters/local_runtime/frontend_client.py:315-316`, `src/cadrumo_harness/mcp/admitted_operations.py:120-121` |

The four automation proposal ids travel through a separate enrollment path in the MCP harness (`src/cadrumo_harness/mcp/runtime_adapter.py:273-291`), not through the generic operation tools.

## Counts

Computed from the table above. The two frontend totals are CT 72 and C 71, 143 in all.

### Per family

| family | ids | CT | C |
|---|---|---|---|
| Ledger entries and classification | 17 | 0 | 17 |
| Ledger lifecycle and removal | 7 | 1 | 6 |
| Statement import and export | 2 | 2 | 0 |
| Evidence and invoice intake | 8 | 3 | 5 |
| Ledger reads closed to MCP | 8 | 8 | 0 |
| Declaration work units and their reads | 16 | 15 | 1 |
| Declaration lifecycle | 13 | 10 | 3 |
| Casilla edits and workbench reads | 7 | 7 | 0 |
| Review packages, audit, verification reports and quickfile | 13 | 2 | 11 |
| Modelo-specific families | 16 | 4 | 12 |
| Live captures and reads that are closed | 2 | 1 | 1 |
| Authentication to AEAT and providers | 5 | 5 | 0 |
| Certificates | 7 | 7 | 0 |
| Automation access administration | 3 | 3 | 0 |
| Profile lifecycle, archive and history | 6 | 1 | 5 |
| Google and collaboration configuration | 9 | 0 | 9 |
| Workflow | 3 | 3 | 0 |
| Diagnostics and the rest | 1 | 0 | 1 |
| total | 143 | 72 | 71 |

### Per gap class

An id counts under each class it carries, so the column sums exceed 143.

| gap class | ids | CT | C |
|---|---|---|---|
| G1 | 65 | 31 | 34 |
| G2 | 23 | 11 | 12 |
| G3 | 25 | 10 | 15 |
| G4 | 47 | 26 | 21 |
| G5 | 2 | 2 | 0 |
| G7 | 2 | 0 | 2 |

Combinations of classes are not tabulated separately. G6 and G8 do not occur among the closed operations.

### Per need

| need | ids | CT | C |
|---|---|---|---|
| none | 66 | 31 | 35 |
| host path | 24 | 10 | 14 |
| human session | 47 | 26 | 21 |
| client-side guard | 23 | 11 | 12 |
| secret | 4 | 4 | 0 |
| financial operand | 2 | 2 | 0 |

### Frontend totals

| frontends | ids |
|---|---|
| CT (command line and terminal interface) | 72 |
| C (command line only) | 71 |
| closed in all | 143 |

## Not verified

- The gap classes and needs entries are carried from the matrices. Only the deciding locators, the stated-reason sentences and the host-path request fields were opened in this record. The client-side guards (`--yes` flags, dialogs, filing gates, wizards) were not re-opened, and whether each operation repeats the validation the command line performs before submitting was not checked.
- The registered total of 266 was reconciled from the ids of the three matrices. It was not re-derived here from the composition of the production registry, so an operation absent from all three matrices would be absent from this list. No difference from 143 (72 plus 71) arose in the reconciliation.
- `user-profile.censo-file-import` carries G3 in the matrices because the command line parses a certificate file before submitting. Its request model carries parsed facts and no path (`src/cadrumo/application/user_profile/censal_file_import_operation.py:104,115-117`), so the needs column says none. Whether the parse step is the only place a file is read was not checked.
- `modelo.work.verify` reads through the certificate backend. Whether that needs an interactive sign-in to AEAT was not established.
- The permitted-frontends line is one of two frontend gates on a definition. Access resolvers also check the frontend in places (`src/cadrumo/application/ledger/bulk_classify_operation.py:248`, `src/cadrumo/application/ledger/evidence_ingestion_operation.py:269`, `src/cadrumo/application/modelo/quickfile_operation.py:354`, `src/cadrumo/application/workstation_check_operation.py:302`); the resolvers of the other definitions were not enumerated.
- The search for stated reasons covered `src/cadrumo/application` by phrase. Comments in the command line, terminal interface and runtime code, in documentation, and in version history were not searched for reasons.
- The "what it does" column is a short paraphrase from the definition and the matrices; it was not checked against each executor.
- The files cited were read from the working tree, which holds uncommitted changes by another session. None of the cited source files is among the modified paths, but the tree may have changed since.
