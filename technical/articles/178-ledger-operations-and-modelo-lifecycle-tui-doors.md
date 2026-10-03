# Ledger operations and Modelo lifecycle TUI doors

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-178` · **Topic:** [Installed runtime, terminal workbench, and agent harness](../topics/runtime-tui-and-agent-harness.md)

<!-- preserved:article -->
## Scope and limits

This report covers all 21 assigned files, 5,177 source lines, 226,457 bytes, and 47,223 measured `o200k_base` proxy tokens. Every declared slice was read across nine bounded pages. This is static inspection only: no UI, runtime, filesystem import/export, model reader, storage, or registered operation was executed. Test sources are absent from the supplied snapshot.

## Operator capabilities

Ledger import lets an operator select a bank statement or received/issued invoice book, choose an allowed parser, choose a file or folder, preview measured counts and diagnostics, then confirm application through the injected door. The preview distinguishes unknown write counts from zero and preserves duplicate/refusal/unmapped-column information (import screen (`src/cadrumo/entrypoints/tui/ledger/import_flow.py`), preview and submit (`src/cadrumo/entrypoints/tui/ledger/import_flow.py`)). Invoice entry supports either one base/rate or multiple typed invoice lines, collects dates, parties, currency, classifications and supplemental values, reviews a summary, and records only after explicit confirmation (invoice entry form (`src/cadrumo/entrypoints/tui/ledger/invoice_entry.py`), entry validation (`src/cadrumo/entrypoints/tui/ledger/invoice_entry.py`)). The TUI parses and shapes entered data; the source explicitly leaves date-sensitive legal and arithmetic validation to the writer (invoice input contract (`src/cadrumo/entrypoints/tui/ledger/models.py`)).

The local evidence flow registers a PDF or image, lists its filename and review state, checks reader readiness, extracts a draft, and lets the operator confirm the document as an invoice. Extraction is observational; confirmation is a separate write. The UI displays unread fields as unread, discrepancies, provenance, ambiguities, and any reader fallback reason (record actions (`src/cadrumo/entrypoints/tui/ledger/evidence_records.py`), evidence model (`src/cadrumo/entrypoints/tui/ledger/models.py`)). Transaction/invoice detail views support limited notes/description edits against the loaded baseline. Reconciliation is expressly local: it shows amount and counterparty comparisons, one-sided links, and affected declarations; an operator can explicitly confirm one suggested transaction/invoice pair (reconciliation (`src/cadrumo/entrypoints/tui/ledger/reconciliation.py`)).

The Modelo lifecycle door provides calculate, edit preflight/apply, verify, file, and export operations for a selected work unit. Edits are typed set/clear/restore intents and renew the baseline before applying. Verify and file require the selected calculation revision; file also requires a verification report. Export accepts an operator-selected path, refund/payment/domiciliation choices, replacement choice, and artefact type (lifecycle door (`src/cadrumo/entrypoints/tui/modelo/lifecycle.py`)). The export-result dialog labels artefact, output path, file size, completeness and software identity, and always warns that the output is not official AEAT filing evidence; a development identity or unverified completeness adds a further warning (export result warnings (`src/cadrumo/entrypoints/tui/modelo/export_result.py`)).

For applicable ordinary Modelo 303 periods, the M303 evidence modal requires an explicit joint-return answer, and only periods asking the Modelo 390 exemption show the attestation fields. The operator may identify existing evidence or enter an observed instant with an explicit UTC offset; the lifecycle door can instead create/admit an attestation through a registered runtime operation (M303 form (`src/cadrumo/entrypoints/tui/modelo/m303_evidence.py`), attestation admission (`src/cadrumo/entrypoints/tui/modelo/lifecycle.py`)).

## How operations are admitted and correlated

The Ledger flow state machine permits editing to move only to confirmation or cancellation, and confirmation to submission or cancellation. Once submitting, the flow must settle as success/failure; Back is refused while an operation is in flight (flow transitions (`src/cadrumo/entrypoints/tui/ledger/workspace_presentation.py`)). Invoice add uses the retained profile/session client and one registered operation. It correlates the result profile and invoice identity/fields against the request and requires the terminal receipt to show the matching effect/refusal before disclosing a result (runtime invoice door (`src/cadrumo/entrypoints/tui/ledger/runtime_invoice_add.py`)). Activity-asset runtime actions similarly bind one client, validate projection profile and authority provenance, correlate terminal condition/effect/refusal, and check that claim results reconstruct the exact supplied schedule claim (activity-asset runtime (`src/cadrumo/entrypoints/tui/ledger/runtime_actividad_asset.py`)).

Evidence confirmation has particularly strong local admission: extraction retains only profile, session, evidence ID, source digest and draft-review digest. Confirmation is one-shot, tied to the same exact session and evidence, sends both expected digests, and validates returned profile/source/draft and invoice kind/country before accepting the invoice result. The operation is expected to re-read the source and draft, so a changed document cannot silently inherit the previous review (evidence digests (`src/cadrumo/entrypoints/tui/ledger/runtime_evidence.py`), extract and confirm (`src/cadrumo/entrypoints/tui/ledger/runtime_evidence.py`)).

## Security and implementation assessment

The strongest implementation characteristics are explicit confirmation, typed immutable request/projection models, exact identity checks, session-bound operation doors, and clear separation between projections and effects. File import locks its form after preview and applies the same typed request; invoice entry locks fields after review and submits that frozen entry. A bounded follow-up question remains for import preview: the request retains a path, not a content snapshot or digest, and application occurs later. The application door may independently detect changes, but synthesis should inspect it before claiming the confirmed bytes are necessarily the previewed bytes (same-request import (`src/cadrumo/entrypoints/tui/ledger/import_flow.py`)). The browse root is derived from an operator-entered path or current directory; filesystem confinement must be established in the import service, outside this UI layer (browse root (`src/cadrumo/entrypoints/tui/ledger/import_flow.py`)).

The evidence runtime also maps every listed record to `UNMEASURED` status even though the screen displays a status column. Whether this reflects a deliberately unmeasured public contract or discards information needs checking against the operation projection; the code here does not justify reporting an awaiting/confirmed state from the underlying record (record projection mapping (`src/cadrumo/entrypoints/tui/ledger/runtime_evidence.py`)). This is a targeted data-contract question rather than a confirmed user-visible defect.

One product-path gap is confirmed in adjacent assigned code: Ledger review and evidence row selection post typed query requests, but the shared workspace handler responds with “destination pending” and documents that no production consumer executes those read queries yet (review screen (`src/cadrumo/entrypoints/tui/ledger/review.py`), pending handler (`src/cadrumo/entrypoints/tui/ledger/controller.py`)). Other flows such as classification, exclusion, evidence confirmation, invoice edits, and local link reconciliation do have injected submit doors. Synthesis should keep this query gap separate from the available mutation paths.

The M303 form rejects blank or offset-free attestation times and does not convert an unanswered joint-return selector into false. The export statement calls out the export’s evidentiary status and exposes digests only in an explicit technical view. No local sources establish current legal correctness, the full runtime authorization policy, filesystem confinement, or tests. Follow the registered operation definitions and composition code for those guarantees; this report records only the TUI-side checks.

## Dependencies for synthesis

Trace import preview/apply to its readers and persistence layer; invoice form/add to the canonical invoice writer; evidence list/extract/confirm to local secret/file custody and reader/model operations; and Modelo lifecycle/attestation/export results to their registered definitions and runtime host. Reconcile the evidence list status mapping with its public projection contract. Confirm whether the import service snapshots or revalidates source bytes after preview. These checks will establish the end-to-end boundaries that this screen layer cannot.

## Complete assigned-file coverage

All 21 source files and their complete manifest line ranges are covered above.

- ledger/evidence_records.py (`src/cadrumo/entrypoints/tui/ledger/evidence_records.py`) — 274 lines
- ledger/import_flow.py (`src/cadrumo/entrypoints/tui/ledger/import_flow.py`) — 323 lines
- ledger/invoice_entry.py (`src/cadrumo/entrypoints/tui/ledger/invoice_entry.py`) — 568 lines
- ledger/models.py (`src/cadrumo/entrypoints/tui/ledger/models.py`) — 594 lines
- ledger/models_actividad_asset.py (`src/cadrumo/entrypoints/tui/ledger/models_actividad_asset.py`) — 75 lines
- ledger/overview.py (`src/cadrumo/entrypoints/tui/ledger/overview.py`) — 93 lines
- ledger/reconciliation.py (`src/cadrumo/entrypoints/tui/ledger/reconciliation.py`) — 276 lines
- ledger/record_views.py (`src/cadrumo/entrypoints/tui/ledger/record_views.py`) — 238 lines
- ledger/review.py (`src/cadrumo/entrypoints/tui/ledger/review.py`) — 189 lines
- ledger/routes.py (`src/cadrumo/entrypoints/tui/ledger/routes.py`) — 218 lines
- ledger/runtime_actividad_asset.py (`src/cadrumo/entrypoints/tui/ledger/runtime_actividad_asset.py`) — 343 lines
- ledger/runtime_evidence.py (`src/cadrumo/entrypoints/tui/ledger/runtime_evidence.py`) — 364 lines
- ledger/runtime_invoice_add.py (`src/cadrumo/entrypoints/tui/ledger/runtime_invoice_add.py`) — 229 lines
- ledger/transaction_views.py (`src/cadrumo/entrypoints/tui/ledger/transaction_views.py`) — 143 lines
- ledger/workspace_injection.py (`src/cadrumo/entrypoints/tui/ledger/workspace_injection.py`) — 89 lines
- ledger/workspace_presentation.py (`src/cadrumo/entrypoints/tui/ledger/workspace_presentation.py`) — 114 lines
- modelo/__init__.py (`src/cadrumo/entrypoints/tui/modelo/__init__.py`) — 5 lines
- modelo/export_result.py (`src/cadrumo/entrypoints/tui/modelo/export_result.py`) — 221 lines
- modelo/lifecycle.py (`src/cadrumo/entrypoints/tui/modelo/lifecycle.py`) — 331 lines
- modelo/m303_evidence.py (`src/cadrumo/entrypoints/tui/modelo/m303_evidence.py`) — 196 lines
- modelo/runtime_lifecycle.py (`src/cadrumo/entrypoints/tui/modelo/runtime_lifecycle.py`) — 294 lines
<!-- /preserved:article -->
