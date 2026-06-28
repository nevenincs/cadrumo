---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-snapshot-adr]]"
  - "[[2026-05-13-google-oauth-inbound-adr]]"
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
---

# `google-oauth` adr: `Per-domain export taxonomy` | (**status:** `accepted`)

## Problem Statement

ADR-1 / ADR-2 / ADR-3 establish HOW data crosses the storage boundary. ADR-5 establishes WHICH domains cross it and WHAT they look like on the other side. Per-domain decisions: export direction (out-only / two-way / never), serialisation format (binary ciphertext / CSV / JSON / Sheets), editability profile, reverse-flow capability, and what new substrate hooks each domain requires.

## Considerations

- Research stream R7 produced a comprehensive per-domain matrix (codebase-grounded audit of every domain in `src/aeat/domain/` and `src/aeat/application/`).
- The cli-workflow-redesign invoice-domain-decoupling ADR mandates four canonical source kinds — `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice` — and forbids the bare `invoice` term. Every Tier-1 / Tier-2 / never-export classification in this ADR honors that taxonomy. The legacy `domain/invoices/` and `application/invoices/` paths are refactored per that ADR's mandate before the substrate hooks named here can land; ADR-5 references the post-refactor file paths.
- ADR-7 will close the two-way sync feasibility question; ADR-5 enumerates which domains would participate IF two-way were enabled, not whether it ships.
- ADR-2's `NamespaceLabelDeriver` requires per-domain registrations; ADR-5 catalogues them.
- The substrate currently lacks enumeration on several domains (R8 flagged `iter_namespaces`, `iter_all_records_raw`; R7 flagged enumeration gaps on the three invoice-domain repositories — `PurchaseInvoiceEvidenceRepository`, `PayableInvoiceRepository`, `CollectibleInvoiceRepository` — plus `WorkflowResultRepository` and transactions reverse-merge); ADR-5 specifies which hooks each tier requires.

## Constraints

- **Pydantic v2 strict** for export-record payloads.
- **No partial implementations.** Each domain in scope ships its export end-to-end (out + reverse if applicable) or stays out of scope until a future amendment.
- **No backwards-compat.** No legacy export readers.
- **Never-export domains are hard-refused.** Code-level refusal in the sync coordinator; audit-logged if attempted.

## Implementation

### 1. Tier-1 v1 domains — full export, two-way reverse-flow

These ship complete in v1: outbound mirror + Sheets visualisation (per ADR-6) + reverse-merge service for editable fields invoked by the v1 CLI edit and CSV-corrections commands (per ADR-7).

#### 1.1 `transactions`

- **Storage:** encrypted SQL via `SecureObjectRepository`, single catalogue object per NIF.
- **Sync export:** ciphertext per-row mirror (ADR-2 / ADR-3); each transaction = one Drive file.
- **Reverse-flow editable fields:** `business_classification`, `business_pct`, `category_id`, `notes`. `raw`, `transaction_id`, amount, date are immutable.
- **Substrate hooks needed:** `application/transactions/_reverse_merge.py` — accepts an operator-edited record subset, validates editable-only invariant, merges into the catalogue.
- **Label deriver:** `transactions/<period>-<descriptor>` (period = year-quarter or year-month derived from transaction date; descriptor = `_raw_transaction.descriptor` truncated to 40 chars and slugified).

#### 1.2 `purchase_invoice_evidence`

A `purchase_invoice_evidence` is a receipt/invoice the operator received that SUPPORTS the deductible-expense treatment of an existing `ledger_transaction`. It is not itself an expense; it is the evidence that justifies one. Double-counting must not occur (a `purchase_invoice_evidence` paired with a `ledger_transaction` does not create a second expense row).

- **Storage:** encrypted SQL via `SecureObjectRepository`; one record per evidence document.
- **Sync export:** ciphertext per-row mirror.
- **Reverse-flow editable fields:** `notes`, `attached_to_transaction_id` (re-linking to a different supporting ledger transaction). Identity (`evidence_id`, `received_at`, document hash) immutable.
- **Substrate hooks needed:** `PurchaseInvoiceEvidenceRepository.iter_evidence()`; `application/purchase_invoice_evidence/_reverse_merge.py`.
- **Label deriver:** `purchase-invoice-evidence/<period>-<vendor>-<short_id>`.

#### 1.3 `payable_invoice`

A `payable_invoice` is a business-operation invoice the autónomo RECEIVED from a vendor; money the autónomo owes. Distinct from `purchase_invoice_evidence` (which is ledger-side proof for a deductible expense). A `payable_invoice` may eventually be paired with a `ledger_transaction` when payment occurs, but it exists as a tax entity independently.

- **Storage:** encrypted SQL via `SecureObjectRepository`; one record per `payable_invoice` source-kind record.
- **Sync export:** ciphertext per-row mirror.
- **Reverse-flow editable fields:** `payment_status`, `notes`, `linked_transaction_ids`, `payment_id`. Identity (`payable_invoice_id`, `invoice_number`, `issued_at`, amounts, vendor identity) immutable.
- **Substrate hooks needed:** `PayableInvoiceRepository.iter_invoices()`; `application/payable_invoice/_reverse_merge.py`.
- **Label deriver:** `payable-invoice/<period>-<vendor>-<invoice_number>`.

#### 1.4 `collectible_invoice`

A `collectible_invoice` is a business-operation invoice the autónomo ISSUED to a customer; money owed to the autónomo. Distinct from `payable_invoice` (direction of liability differs). Tax entity independent of ledger movements.

- **Storage:** encrypted SQL via `SecureObjectRepository`; one record per `collectible_invoice` source-kind record.
- **Sync export:** ciphertext per-row mirror.
- **Reverse-flow editable fields:** `payment_status`, `notes`, `linked_transaction_ids`, `payment_id`. Identity (`collectible_invoice_id`, `invoice_number`, `issued_at`, amounts, customer identity) immutable.
- **Substrate hooks needed:** `CollectibleInvoiceRepository.iter_invoices()`; `application/collectible_invoice/_reverse_merge.py`.
- **Label deriver:** `collectible-invoice/<period>-<customer>-<invoice_number>`.

#### 1.5 `rental`

- **Storage:** SQL ORM (5 relational tables): `rental_fincas`, `rental_contracts`, `rental_income_records`, `rental_expenses`, `rental_amortization_ledger`.
- **Sync export:** ciphertext per-row mirror for each table; one Drive folder per table under `aeat-vault/rental-<table>/`.
- **Reverse-flow editable fields:**
  - `rental_income_records`: amounts, dias_alquilados, notes.
  - `rental_expenses`: amounts, descriptions, allocation_pct.
  - `rental_amortization_ledger`: notes only.
  - `rental_fincas`, `rental_contracts`: structural; CLI-only edits (refused via Sheets reverse-flow because foreign-key integrity risk).
- **Substrate hooks needed:** Each rental repository already exposes `list_all()` / `list_for_finca()` / `list_for_period()`. Sufficient.
- **Label deriver per table:** `rental-<table>/<entity_pk>-<descriptor>`.

### 2. Tier-2 v1 domains — outbound mirror only, no reverse-flow

These ship outbound export (continuous Drive mirror via ADR-2) but no operator-edit reverse path. Calc-to-Sheets visualisation per ADR-6 if applicable.

| Domain | Export format | Substrate hook added | Notes |
|---|---|---|---|
| `filing/` (drafts) | ciphertext mirror + JSON snapshot per draft | `application/filing/_export_snapshot.py` (new use-case wrapping `iter_drafts`) | Local fichero-BOE export already exists; Drive backup of draft JSON is the addition. |
| `justificante/` | ciphertext mirror | `iter_justificantes()` already exists | Filing-receipt audit log. |
| `submission/` | ciphertext mirror | `iter_submissions()` already exists | Submission history log. AEAT is write-locked; reverse permanently forbidden. |
| `profile/` (operator profile) | ciphertext mirror + JSON snapshot | none | Small record; cross-machine migration utility. |
| `usage_ratios/` | ciphertext mirror | none | Small record. |
| `attachments/` (manifests only) | ciphertext mirror of manifests | `iter_manifests()` already exists | **Manifest only — bytes never exported.** Bytes are content-addressed in encrypted blob store; manifest references them. |
| `deadlines/` (computed schedules) | JSON or iCal snapshot on-demand | new `engine.export_schedule()` | Stateless — computed from registry + profile. iCal format chosen for calendar-app interop. |
| `workflow/` (run audit log) | JSON append-log mirror | new `WorkflowResultRepository` | `WorkflowResult` is currently transient; ADR-5 mandates a persistence layer. |

### 3. Never-export domains

Code-level refusal. The sync coordinator's namespace allow-list does NOT include these. Attempts (operator passes `--namespace <forbidden>`) are refused with `NeverExportError` and audit-logged.

| Domain | Reason |
|---|---|
| `application/auth/` (Sede session tokens) | Session secrets; Drive export would weaken the AEAT-side auth boundary. |
| `calculations/registry/` (TOML files) | Version-controlled source code, not user data. Operator-as-data treatment would corrupt the audit chain. |
| `manuals/` | Project corpus shipped with the source code. Not per-operator state. |
| `normatives/` | Same as manuals. |
| `vat/` | Static tax-law corpus. |
| `categories/` | Compiled-in taxonomy. |
| `portals/` | Static URL registry. |
| `modelos/` | Static value-object catalogue. |
| Master KEK / recovery key / envelope DEKs | Governed by `MasterKeyProvider` per `secure-persistence-enforcement-adr`. ADR-3 handles cross-machine KEK escrow via explicit operator passphrase only. |

The allow-list is enforced in the coordinator's namespace resolver:

```python
class NamespaceAllowList:
    """Allow-list of exportable namespaces."""

    EXPORTABLE: ClassVar[frozenset[str]] = frozenset({
        "transactions",
        "purchase-invoice-evidence",
        "payable-invoice",
        "collectible-invoice",
        "rental-fincas", "rental-contracts", "rental-income-records",
        "rental-expenses", "rental-amortization-ledger",
        "filing-drafts", "justificantes", "submissions",
        "profile", "usage-ratios", "attachments-manifests",
        "deadlines", "workflow-runs",
    })
```

### 4. New substrate hooks required by ADR-5

Consolidated list of substrate amendments triggered by tier assignments:

- `SecureObjectRepository.iter_namespaces()` and `iter_all_records_raw()` (R8-mandated; foundational for sync).
- `PurchaseInvoiceEvidenceRepository.iter_evidence()` (per 1.2).
- `PayableInvoiceRepository.iter_invoices()` (per 1.3).
- `CollectibleInvoiceRepository.iter_invoices()` (per 1.4).
- `application/transactions/_reverse_merge.py` (per 1.1).
- `application/purchase_invoice_evidence/_reverse_merge.py` (per 1.2).
- `application/payable_invoice/_reverse_merge.py` (per 1.3).
- `application/collectible_invoice/_reverse_merge.py` (per 1.4).
- `application/filing/_export_snapshot.py` (per Tier-2 filing).
- `WorkflowResultRepository` — new persistence layer for `application/workflow/` results (per Tier-2 workflow). Overlap-check required against the cli-workflow-redesign EPIC's evidence-bundle ADR before P06 implementation; the two artefacts may share a backing record or the bundle may consume the repository as its source — implementation should not duplicate the audit trail.
- `application/deadlines/_export.py::export_schedule(format: Literal["json", "ical"])` (per Tier-2 deadlines).

Each is a small focused addition under the substrate's existing patterns. None require schema changes to existing tables. The new `WorkflowResultRepository` adds one new table via migration.

### 5. Per-domain `NamespaceLabelDeriver` registrations

Each Tier-1/Tier-2 domain registers its deriver during package import. Concrete derivers:

```python
# transactions
def label_for_transaction(*, namespace: str, decrypted_payload: bytes) -> str:
    record = Transaction.model_validate_json(decrypted_payload)
    return f"{record.date.strftime('%Y-%m')}-{slug(record.descriptor)[:40]}"
```

And similar per Tier. Every allow-listed namespace MUST register a deriver during package import. A namespace lacking a registered deriver raises `UnregisteredNamespaceLabelDeriverError` at startup — no silent fallback, no permissive default. Future allow-listed namespace additions land alongside their deriver registration in the same ADR amendment.

### 6. Reverse-merge service — fully active in v1

The reverse-merge use-cases (`_reverse_merge.py` per source kind) are fully active in v1. They are called by:

- the v1 CLI edit commands per ADR-7 (e.g. `aeat app ledger transaction edit`, `aeat app ledger payable-invoice edit`, `aeat app ledger rental income edit`), and
- the v1 CSV-corrections import commands per ADR-7 (`aeat app ledger {transaction|purchase-invoice-evidence|payable-invoice|collectible-invoice} corrections import-csv`).

Each reverse-merge service validates the editable-only field invariant for its source kind, applies record subsets to the substrate via the existing repository APIs, and emits both an audit row and a `ledger.<source-kind>.correction.applied` bucket event per the cli-workflow-redesign bucket-event-history ADR. The service has no settings flag and no inert code path.

ADR-7's deferral applies to the Sheets-pull CLI entry-point only (the future command that would read `/aeat-vault/_workspace/` Sheets and feed record subsets into this service). That command does not exist in v1 source code. The reverse-merge service ships fully active without it; the future amendment adds the command alongside its own ADR.

### 7. Out of scope (deferred)

- New domains added after v1 (e.g. a future banking-connector domain) — separate ADR amendments.
- Multi-format export per domain (e.g. transactions to CSV AND Sheets simultaneously) — v1 ships one canonical export format per domain.
- Domain-internal versioning beyond the substrate's `schema_version` field — handled by domain ADRs as they emerge.

## Rationale

**Tier 1 = `ledger_transaction` + `purchase_invoice_evidence` + `payable_invoice` + `collectible_invoice` + `rental`.** Highest operator-touch domains; full export + reverse-flow delivers the most v1 value. Their schemas are stable, their editable-vs-immutable boundaries are clear, their substrate hooks (or required additions) are small. The four-way invoice-domain split mandated by the cli-workflow-redesign invoice-domain-decoupling ADR is honored throughout: a `purchase_invoice_evidence` supports a `ledger_transaction`'s deductibility and never creates a second expense; `payable_invoice` and `collectible_invoice` are independent business-operation tax entities.

**Tier 2 = audit-trail and snapshot domains.** Outbound mirror gives the operator off-machine resilience without taking on the two-way complexity. Filing drafts and justificantes are reference data; reverse-editing them would corrupt audit chains.

**Never-export covers source code + session secrets.** Registry TOML files are code, not user data. Manuals / normatives / vat / categories / portals / modelos are shipped corpus. Sede session tokens are security boundaries that Drive must not see. The hard refusal is enforced in the coordinator's allow-list, not just by convention.

**Substrate hooks added per-domain rather than wholesale.** Each hook is a focused use-case (e.g. `iter_evidence`, `iter_invoices` on `PayableInvoiceRepository`, `WorkflowResultRepository`, `export_schedule`). Wholesale substrate amendments (e.g. "add an `iter_anything` God-method") risk overgrowing the substrate's API; per-domain hooks stay scoped to each domain's actual needs. The three invoice-domain repositories (`PurchaseInvoiceEvidenceRepository`, `PayableInvoiceRepository`, `CollectibleInvoiceRepository`) replace the legacy `InvoiceCatalogueRepository` per the invoice-domain-decoupling ADR's refactor mandate.

**Reverse-merge service is the v1 backend for CLI edit + CSV-corrections import; no settings gate.** ADR-5 defines the field-level editability matrix; ADR-7 closes the feasibility verdict for a future Sheets-pull entry-point. The reverse-merge service itself is fully active in v1 because v1 ships the CLI edit and CSV-corrections callers; there is no inert code and no flag to flip later. The future Sheets-pull amendment adds a new CLI command that consumes the same service — it is an addition, not a re-activation.

## Consequences

**Positive.**

- Clear matrix: every domain in the codebase has an explicit tier assignment + rationale.
- Reverse-flow editability is per-field, not per-record — matches the operator's real workflow (edit category, leave amount).
- Allow-list prevents accidental never-export domain exfiltration.
- Substrate hooks are small focused additions; total LOC across all hooks ≤500.

**Negative.**

- Eight new substrate hooks to implement and test before Tier-1/Tier-2 features can ship.
- Per-domain label derivers add a new abstraction surface (one Protocol implementation per exportable domain).
- Operators with edge-case workflows (e.g. needing to bulk-recategorise rental fincas via Sheets) are blocked because the structural rental tables are CLI-only.

**Neutral.**

- The tier system is amendable: a domain can graduate from Tier-2 to Tier-1 via amendment once reverse-flow demand is established.
- Never-export is a hard boundary; weakening it requires an ADR amendment with security justification.

## References

External:
- iCal RFC 5545 — `https://datatracker.ietf.org/doc/html/rfc5545`

Internal:
- `[[2026-05-13-google-oauth-adr]]` — bucket layout.
- `[[2026-05-13-google-oauth-snapshot-adr]]` — encryption boundary.
- `[[2026-05-13-google-oauth-inbound-adr]]` — inbound bucket semantics.
- `[[2026-05-12-google-oauth-adr]]` — provider abstraction.
- `[[2026-05-06-google-oauth-research]]` — R7 per-domain taxonomy.
