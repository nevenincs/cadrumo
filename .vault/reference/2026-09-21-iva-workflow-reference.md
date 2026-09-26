---
tags:
  - '#reference'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:b50145d6d3f5e502c9578949f51a5b161e44d4a7bb35cb1cbfe48008fbeac0c1'
related: []
---

# `iva-workflow` reference: `IVA CLI and TUI capability map`

This reference audits the live implementation against IVA-01 revision 0.5 and
ACCEPTANCE-01 revision 1.0. It covers invoice entry and persistence, the IVA
ledger-to-modelo projection, Modelo 303 and 390 authority/export support, filed
history and compensation-wallet reconciliation, SII boundaries, and the
available acceptance harness. The audited source revision is
`ce2c87ce4ceafbbe912c5a15500c8ec06be1979e` on branch `tui/modelo`.

## Summary

### Canonical invoice and operator entry surfaces

The canonical aggregate is substantially richer than either frontend.
`InvoiceLine` carries quantity, unit price, subtotal, IVA rate and IVA amount at
`src/cadrumo/domain/invoices/models.py:168`; `Invoice` carries the tuple of lines
and the wider legal, party, payment, IVA-category, operation, recargo,
retention, rectification and FX facts at
`src/cadrumo/domain/invoices/models.py:272`. `build_catalogue_invoice` accepts an
explicit sequence of lines at
`src/cadrumo/application/invoices/catalogue_creation.py:358`, while its scalar
base/rate lane synthesises one line.

The CLI manual add route starts at
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:244`. It exposes one
taxable base and one rate, plus operation type/date, invoice class, series,
rectification target, recargo, IVA category, retention and notes. It therefore
cannot manually enter a mixed-rate invoice despite the domain model supporting
one. Its structured catalogue payload is assembled at
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:146`; the payload
model includes recargo and operation type at
`src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py:74`, but the
wire contract is not a complete serialization of every canonical invoice fact.

The bulk importer is also one-row/one-base/one-rate. Its row contract begins at
`src/cadrumo/application/invoices/bulk_import.py:124` and hands the scalar base
and rate to `build_catalogue_invoice` at
`src/cadrumo/application/invoices/bulk_import.py:733`. It provides partial
success and field-attributed refusals, but is not a mixed-line invoice import
surface. Neither the canonical invoice nor the creation event retains an
import source-file/source-row locator; timestamps are not source provenance.

The TUI invoice form's complete field list is at
`src/cadrumo/entrypoints/tui/ledger/invoice_entry.py:20`; its entry model is at
`src/cadrumo/entrypoints/tui/ledger/models.py:289`, and the persistence door calls
the shared catalogue creator at `src/cadrumo/entrypoints/tui/ledger_doors.py:244`.
The TUI supports one base/rate, invoice class, series and retention. It does not
expose IVA category, operation type/date, rectification target, recargo or
multiple lines. The two frontends therefore do not have equivalent invoice
entry coverage. Its workspace injection also has add/import doors but no
canonical invoice read/list/view door, so its fake-door tests cannot prove
fresh-session persisted readback.

### Ledger ownership of Modelo 303 facts

The invoice catalogue is supporting evidence, not the domestic Modelo 303
calculation source. That boundary is explicit at
`src/cadrumo/application/aggregation/modelo_bindings.py:1`. The resolver loads
the transaction catalogue and projects IVA ledger observations at
`src/cadrumo/application/aggregation/modelo_bindings.py:249`; invoice checks are
a silence screen rather than a second amount source.

The projection in `src/cadrumo/application/aggregation/_iva_transaction.py:1`
requires active business transactions with explicit taxable base, IVA amount,
rate and category. Received/deductible flows additionally require deduction
fact kind and immutable provenance; cash accounting, prorrata, business-use
percentage, recargo and rectification are handled there. Missing, stale or
unsupported facts produce issues rather than inferred zeroes.

Linking an invoice and transaction only updates their reciprocal identifiers in
`src/cadrumo/application/invoices/transaction_linking.py:1`; it does not copy tax
amounts or classification into the ledger. The CLI manual transaction command
can supply the required tax substrate in
`src/cadrumo/entrypoints/cli/_ledger.py:1`. The TUI classification screen at
`src/cadrumo/entrypoints/tui/ledger/classification.py:1` can only select business,
personal or reviewed-excluded classification and exposes no transaction IVA
facts. Consequently, invoice entry by itself cannot feed Modelo 303, and the
current TUI cannot complete that bridge without a separately prepared ledger.

The ownership split is intentional rather than an absent copy operation. Invoice
identity, lines, totals, correction metadata and document payment status live in
`src/cadrumo/domain/invoices/models.py:272`; transaction money, IVA classification
and deduction facts live in `src/cadrumo/domain/transactions/models.py:427`.
One invoice may accumulate several transaction links, while a transaction has one
invoice reference; split cash-accounting payments are transaction evidence parts.
The public shared operations can create the invoice, create/update the transaction,
attach immutable purchase evidence and link the two without establishing silent
precedence.

The Phase-2 delta confirms that the shared catalogue writer already accepts an
ordered `Sequence[InvoiceLine]` at
`src/cadrumo/application/invoices/catalogue_creation.py:358`, and the encrypted
catalogue repository reopens those lines at
`src/cadrumo/adapters/persistence/profile/invoices.py:161`. The public CLI still
projects only scalar base/rate facts at
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:244`, while its JSON
payload omits line details and canonical invoice class, operation, category and
rectification facts at
`src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py:57`.

Bulk import retains a one-based row during parsing but does not attach immutable
source identity to the accepted invoice at
`src/cadrumo/application/invoices/bulk_import.py:87`. The existing canonical
provenance precedent is basename, SHA-256 and one-based row in
`src/cadrumo/domain/transactions/raw_transaction.py:50`; secure attachment
storage separately retains content digest and artifact identity in
`src/cadrumo/domain/attachments/models.py:101`. Filename-only provenance is not
sufficient, and neither the original path nor raw imported row belongs in the
accepted invoice record.

Phase-2 implementation closes those capture gaps. The catalogue writer now
derives totals from supplied ordered lines and refuses scalar/structured mixing
at `src/cadrumo/application/invoices/catalogue_creation.py:357`. The CLI parses
each repeatable `--line` occurrence through the canonical line model at
`src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:169`, and the typed
readback owns required line projections at
`src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py:42`.

Accepted invoices now carry optional canonical provenance at
`src/cadrumo/domain/invoices/models.py:403`. Bulk import reads and hashes the
source once at `src/cadrumo/application/invoices/bulk_import.py:706` and attaches
the immutable per-row identity to the accepted invoice at
`src/cadrumo/application/invoices/bulk_import.py:853`. Focused tests prove CSV,
TSV and XLSX identity, one source read, exact encrypted import-to-reopen
association, and absence of absolute paths or raw row payloads.

The selected-scope completeness gap found during this audit is now closed. Missing or contradictory
transaction IVA facts produce typed aggregation issues and no observation at
`src/cadrumo/application/aggregation/iva_ledger.py:603`. The Modelo binding resolver
classifies the approved evidence-failure reasons as the typed
`iva_selected_scope_evidence_failure` diagnostic at
`src/cadrumo/application/aggregation/modelo_bindings.py:156`. Calculation persists
that diagnostic as a sanitized `CalculationSourceIssue` carrying only a stable
`transaction:<id>` reference at
`src/cadrumo/application/modelo/calculation_actions.py:1523`. Verification emits a
blocking finding at `src/cadrumo/application/modelo/verification_actions.py:1344`,
and export refuses the unresolved issue at
`src/cadrumo/application/modelo/export.py:498`. Reviewed-excluded rows, rows outside
the selected profile/period, ambiguous authority/classification reasons and the
observation-preserving prorrata diagnostic remain outside this blocking set.

### Settlement, filed history and wallet reconciliation

Read-only remote capture is separated from calculation. Filed Modelo 303
history and the compensation wallet are fetched independently, retaining
independent success/failure outcomes and acquisition provenance in
`src/cadrumo/application/live/iva_remote_state.py:1`. The Sede wallet adapter is
read-only at
`src/cadrumo/adapters/outbound/aeat/sede/iva_compensation_wallet.py:1`, and
observations are persisted through the secure bound repository at
`src/cadrumo/adapters/outbound/aeat/sede/observation_store.py:1`.

Casilla 110 reconciliation is a typed, fail-closed decision in
`src/cadrumo/domain/iva_compensation/reconciliation.py:1`. It validates taxpayer,
year and period; distinguishes fresh, stale, missing and conflicting wallet
evidence; and permits an explicit, evidenced taxpayer override. Carry-forward
lots, applications, remaining balances, expiry and refund election are modeled
in `src/cadrumo/domain/iva_compensation/carry_forward.py:1`. A wallet snapshot
is evidence of pending availability, while filed period states remain the
source for original movements. This supports the brief's distinction among
declared/payment state, generated/applied/remaining credits and requested versus
evidenced refunds at the arithmetic level, but the persisted IVA history does
not model payment evidenced/unknown or refund requested/approved/paid lifecycle
states. Its period projection is latest-state keyed and amendment-aware
selection remains open; missing intermediate filings also have no explicit
missing-period state.

The generic filing catalogue already owns origin, AEAT confirmation,
supersession and amendment links at
`src/cadrumo/domain/modelos/filing_record.py:136`. It preserves superseded
records and exposes current and latest-confirmed selection independently. The
IVA compensation history remains the latest secure period-keyed carry source at
`src/cadrumo/application/calculations/iva_compensation_history.py:66`, while
`src/cadrumo/domain/iva_compensation/carry_forward.py:171` owns generated,
applied and remaining credit arithmetic. Payment/refund elections in
`src/cadrumo/application/modelo/filing_actions.py:186` are intent, not evidence
of settlement.

No existing durable value records declared liability separately from evidenced
payment, or refund requested/approved/paid with evidence references. Those
states must attach to the existing immutable filing chain without becoming a
second carry history. Calculation or export cannot imply any confirmation,
payment, approval or refund outcome.

### Authority and export coverage

The registry contains a Modelo 303 `2026-y-siguientes` revision with
`year_from = 2026` at
`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/revision.toml:54`
and a generated export layout at
`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2026-y-siguientes/export/0000-export-layout.toml:1`.
Modelo 390's latest authored annual revision is explicitly limited to year 2025
at `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/revision.toml:41`,
with its export layout at
`src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/export/0000-export-layout.toml:1`.
The latest shared complete exercise is therefore 2025; 2026 periodic 303 support
does not imply a 2026 annual 390 authority.

The 390 annual compensation partition emits source issues and unresolved
bindings for missing or stale 303 observations, but no dedicated verify/export
refusal for that partition was found. Latest 303 and 390 revision attestations
also explicitly disclaim human countersignature, fresh-render reproduction and
AEAT figure-correctness validation. Local export receipts are evidence of local
rendering, not AEAT filing acceptance.

No published `authority.current.json` exists at the default authority root in
this worktree. Runtime calculation, rendering and export tests that call the
bundled indexed authority fail with `AuthorityDescriptorUnavailableError`.
Publishing an authority was not performed because it is a separate governed
registry publication action, not a test fixture repair.

### SII and acceptance-runner boundary

SII XML families are recognized by the document shape detector, but
`XML_AEAT_SII` is deliberately excluded from structured single-invoice shapes
at `src/cadrumo/core/document_shape.py:1`. The single-invoice parser supports
CII, UBL and Facturae and refuses other shapes at
`src/cadrumo/adapters/inbound/einvoice/parsers.py:932`. The refusal contract is
tested in
`src/cadrumo/adapters/inbound/einvoice/tests/test_aeat_batch_shape_refusal.py:1`.
No SII batch importer or live-books synchronization implementation was found.

There is no IVA acceptance runner under `dev/acceptance`; only the income-tax
harness exists. The required isolated CLI/TUI seeded-store parity and fresh
process continuation workflow is therefore not implemented.

### Verification evidence and blockers

The installed TUI screen test passed with six integration tests:
`src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_ingestion_surfaces.py:1`.
This test injects a door and proves screen behavior; it does not prove installed
frontend persistence or Modelo continuation. The authority-independent IVA
carry/refund and SII refusal selection passed eleven unit tests across
`src/cadrumo/domain/iva_compensation/tests/test_refunded_carry_forward.py:1` and
`src/cadrumo/adapters/inbound/einvoice/tests/test_aeat_batch_shape_refusal.py:1`.
Additional focused annual/carry selections passed eleven tests, and the 390
registry predicates/compensation binding selection passed eight tests.

Authority-dependent focused runs failed before their assertions because the
published authority descriptor is absent: the invoice/aggregation/frontend
selection produced 10 failures, 40 errors and 7 passes; the wallet,
carry-forward and secure observation-store selection produced 28 errors and 7
passes. These are environment/precondition failures and must not be reported as
behavioral disprovals of the individual contracts.

The locked workspace installation also cannot currently produce the installed
`aeat` executable. `uv sync --frozen` fails while building the local
`cadrumo-data-manuals` package because
`packaging/cadrumo_data_manuals/hatch_build.py:86` subscripts a Hatchling
`BuilderConfig` that is not subscriptable in the locked build environment.
Dependency-only sync succeeds and permits source-based pytest via the configured
`src` python path, but cannot satisfy the brief's installed-entrypoint evidence.

### Acceptance disposition

V1 is partial: shared secure catalogue persistence exists and injected TUI form
behavior passes, but installed fresh-process readback is unproved, source-row
provenance is absent and the TUI field set is narrower. V2 is partial because
the CLI can separately populate transaction tax facts, while invoice linkage
itself does not project them and the TUI cannot supply them. Selected-scope
missing or contradictory transaction IVA evidence now persists and blocks
verification/export, closing the silent-completeness defect found in Phase 1.
V3 and V4 are
partial: the domain and transaction aggregation support the important regimes
and fail-closed evidence rules, while the entry surfaces do not expose the full
canonical or transaction substrate. V5, V6 and V7 are partial: structural and
domain coverage passes, but runtime calculation/export is blocked by the absent
authority and installed executable, official correctness is unattested, and
the annual compensation source gap is not dedicatedly fail-closed. V8 and V9
are partial: the source contracts and authority-independent tests pass, but
settlement lifecycle, supersession and missing-period representation are
incomplete and secure runtime reconciliation is blocked by authority setup.
V10 fails because parity/continuation tooling and TUI canonical readback are
absent. V11 fails because no IVA acceptance runner exists.

Before an implementation session begins, the session identity fields required
by ACCEPTANCE-01 remain to be assigned: provider, acceptance lead, CC list,
session UUID, artifact root and writable branch. They must not be invented.
