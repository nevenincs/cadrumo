---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-snapshot-adr]]"
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-08-google-oauth-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
---

# `google-oauth` adr: `Incoming-bucket ingestion semantics` | (**status:** `accepted`)

## Problem Statement

ADR-2 reserved `/aeat-vault/_inbound/` with three subfolders (`pending/`, `processed/`, `rejected/`) for operator-prepared, undigested data. ADR-4 closes the concrete ingestion model: the acknowledgement protocol (how the app signals "I've ingested this file"), deduplication, schema validation gates, operator-prepared metadata conventions, and the rejection UX with error sidecars.

## Considerations

- ADR-2 established the folder layout. ADR-4 fills in the semantics.
- The cli-workflow-redesign invoice-domain-decoupling ADR mandates four source kinds (`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`). Every inbound filename prefix and parser routing rule honors that taxonomy; bare `invoice` is forbidden.
- Research stream R6 surveyed Hazel, fswatch, n8n, Shoeboxed, Receipt Bank for inbox ingestion patterns.
- The existing inbound providers (`adapters/inbound/financial/providers/_csv.py`, `_ofx.py`, `_xlsx.py`, `_pdf_n26.py`, declaración parser, justificante parser) are path-only; a Drive-fetcher must materialise to tempfile before invoking them.
- The `_inbound/` bucket is the only place where operator+accountant collaboration is plausibly bidirectional (operator drops files; app processes; operator inspects results).

## Constraints

- **Pydantic v2 strict** for every record.
- **No partial implementations.** Triple dedup, validation, rejection sidecars all land complete.
- **No backwards-compat.** No migration from any prior inbox shape.
- **Inbound bucket only.** ADR-4 does not amend the substrate-mirror or `_workspace/` buckets.
- **Files are materialised to a local tempfile before invoking existing inbound providers.** No provider amendments required; the fetcher is a thin adapter.

## Implementation

### 1. Bucket layout

```
/aeat-vault/_inbound/
  README.md                      ← operator instructions (folder description in Drive UI too)
  pending/                       ← operator drops files here
  processed/                     ← app moves files here on successful ingestion
  rejected/                      ← app moves files here on validation failure
    <file>.error.txt             ← sidecar with plaintext rejection reason
```

The `README.md` is operator-facing instructions: naming conventions, expected file types, what happens to processed files, what to do with rejected files.

### 2. Acknowledgement — move to `processed/`

When `aeat config google sync pull --include-inbound` (or its successor) processes a file from `pending/`:

1. Coordinator downloads the file via `provider.get_object`.
2. Materialises to local tempfile under `var/inbound-staging/<random>.<ext>`.
3. Invokes the appropriate inbound provider (financial CSV/OFX/XLSX/PDF/justificante/declaración) based on filename convention + content sniffing.
4. On success, moves the Drive file to `processed/` via `files().patch(parents: [processed_folder_id])`.
5. Cleans up the tempfile.

Drive `files().patch` for parent change is metadata-only and atomic; the file ID stays stable. The operator sees the file relocated from `pending/` to `processed/`, confirming ingestion.

### 3. Triple deduplication

Three layers, evaluated in order:

1. **Drive file ID dedup.** Local `inbound_ingested_files` table records every file ID the app has already processed. Re-listing the same Drive file ID skips immediately.

2. **Content hash dedup.** Drive metadata's `md5Checksum` field. If a file with the same MD5 has been processed (even under a different name / file ID — operator re-uploaded a copy), skip with a log entry indicating the prior file ID.

3. **Parse-level dedup.** After successful parse, the resulting domain records (ledger transactions, purchase invoice evidence, payable invoices, collectible invoices, etc.) are merged via existing deterministic SHA-256-keyed merge logic in `application/transactions/_import.py` and the per-source-kind importers introduced by the invoice-domain-decoupling refactor. Duplicate domain records are silently absorbed by the merge; no double-counting. The `purchase_invoice_evidence` parser additionally guards against creating a second expense when an evidence record is attached to an already-counted `ledger_transaction`.

Sidecar table introduced by migration `0006_inbound_ingested_files.py`:

```sql
CREATE TABLE inbound_ingested_files (
    profile_id           TEXT NOT NULL,
    drive_file_id        TEXT NOT NULL,
    content_md5          BLOB NOT NULL,
    drive_filename       TEXT NOT NULL,
    drive_mime_type      TEXT NOT NULL,
    drive_size_bytes     INTEGER NOT NULL,
    ingested_at          DATETIME NOT NULL,
    target_provider      TEXT NOT NULL,  -- e.g. 'financial.csv', 'justificante', 'declaracion'
    ingestion_summary    TEXT NOT NULL,  -- short human-readable result
    PRIMARY KEY (profile_id, drive_file_id)
);
CREATE INDEX idx_inbound_content_md5 ON inbound_ingested_files(content_md5);
```

### 4. Schema validation gates

Per-file validation in two stages:

**Stage 1 — type detection (cheap):**

- MIME type from Drive metadata (`mimeType` field).
- Filename extension and convention prefix (`justificante-`, `bank-statement-`, `purchase-invoice-evidence-`, `payable-invoice-`, `collectible-invoice-`, etc.). The four invoice-domain source kinds from the cli-workflow-redesign invoice-domain-decoupling ADR each get a distinct prefix; bare `invoice-` is forbidden.
- Magic bytes inspection during download (catches MIME spoofing).

**Stage 2 — parse-level validation (expensive):**

- Invoke the appropriate provider's parser; catch its typed exceptions.
- If parse succeeds, validate the produced records against the domain schema.
- If parse fails OR validation fails, reject (§5).

The provider-selection rules per filename prefix:

| Prefix | Provider |
|---|---|
| `justificante-*` | `adapters/inbound/justificante/_parser.parse_justificante` |
| `declaracion-*` | `adapters/inbound/declaracion/_parser.parse_declaracion` |
| `bank-statement-*` | financial provider, type-sniffed from extension |
| `purchase-invoice-evidence-*` | purchase-invoice-evidence importer (ledger-side expense evidence; supports an existing `ledger_transaction`, never creates a separate expense row) |
| `payable-invoice-*` | payable-invoice importer (vendor invoice; money the autónomo owes; business-operation entity) |
| `collectible-invoice-*` | collectible-invoice importer (customer invoice; money owed to the autónomo; business-operation entity) |
| `*.csv` / `*.ofx` / `*.xlsx` (no prefix) | financial provider, type-sniffed |
| Anything else | reject (no inferable target) |

### 5. Rejection UX — sidecar `.error.txt`

When validation fails:

1. Coordinator moves the Drive file to `_inbound/rejected/`.
2. Writes a sibling file `<original_filename>.error.txt` with content:

```
Rejection reason: <short reason>
Detected file type: <mime_type>
Detected extension: <ext>
Attempted parser: <provider name>
Validation error: <typed exception message>
File ID: <drive_file_id>
Rejected at: <iso8601 timestamp>

What to do:
- <actionable suggestion>
```

Sidecar is plaintext (no encryption). Drive UI shows the text preview on click. Operator reads, decides: re-upload corrected, manually fix, delete the rejected file.

The error sidecar contains NO sensitive content from the source file (no decoded NIFs, no parsed amounts) — only metadata about why parsing failed.

### 6. Operator-prepared metadata — filename convention

Primary metadata channel is the filename itself. Naming convention:

```
<type>-<period>-<source>-<random>.<ext>
```

Examples:

- `justificante-2026q2-modelo-303-a1b2c3.pdf`
- `bank-statement-2026-04-iban-es12-a1b2.csv`
- `purchase-invoice-evidence-2026-04-vendor-amazon-a1b2.pdf` (operator-supplied receipt; supports a deductible-expense ledger transaction)
- `payable-invoice-2026-04-vendor-supplier-a1b2.pdf` (vendor invoice the autónomo received and owes)
- `collectible-invoice-2026-04-client-acme-a1b2.pdf` (invoice the autónomo issued to a client; awaiting payment)
- `declaracion-2025-irpf-a1b2.pdf`

Parsed by the ingestion coordinator into `(type, period_hint, source_hint, suffix)`. Type drives parser selection; period and source flow into domain-record provenance fields.

Optional supplementary channels:

- **Drive's `description` field** (operator-editable in Drive UI) — recorded into the ingested file's audit log if present; not parsed for routing.
- **Sidecar `<file>.meta.json`** — if operator drops a sidecar JSON alongside their data file with the same basename, the coordinator parses it for additional metadata (period override, account hint, attachment links). Strict pydantic schema; malformed sidecar → file rejected with a clear error.

### 7. Polling cadence

Inbound ingestion runs on operator demand:

```
aeat config google sync inbound          [--profile <id>] [--batch] [--dry-run]
aeat config google sync inbound --reject [--profile <id>] [--file-id <id>]      # operator-manually-rejects a stuck file
aeat config google sync inbound --replay [--profile <id>] [--file-id <id>]      # re-runs ingestion on a processed file (forces dedup bypass)
```

No daemon. No `_inbound/` polling on `sync push`/`sync pull`. Operator schedules via OS cron / Task Scheduler / launchd if they want continuous ingestion.

### 8. Out of scope (deferred)

- Drive push notifications / webhooks (deferred for the same reasons ADR-2 deferred them — webhooks require a public HTTPS endpoint).
- Email-to-Drive ingestion (Gmail → Drive bridge). Not in v1; operators upload to Drive themselves.
- OCR for image-only PDFs. Existing parsers handle text-extractable PDFs only.
- Multi-attachment composite ingestion (e.g. a payable-invoice PDF + its purchase-invoice-evidence receipt JPG arriving together). Not in v1.

## Rationale

**Move-to-processed acknowledgement over rename / trash / app-side-only.** Move-to-processed gives the operator visual confirmation: they see the file relocated. Rename-with-prefix pollutes the `pending/` folder. Trash removes the file from operator visibility (recovery via Drive trash is awkward). App-side-only dedup leaves the operator wondering whether ingestion happened.

**Triple deduplication over single-layer.** File-ID alone misses re-uploads (operator duplicates a file). Content-hash alone misses Drive's modifiedTime semantics on re-uploads. Parse-level alone runs the expensive parser before realising it's a dup. Layered approach short-circuits at the cheapest layer that catches the dup.

**Sidecar `.error.txt` over in-app error log.** Operator drops files in Drive UI, not in CLI. Errors must surface in Drive UI for the operator to act on them. Sidecar is plaintext, Drive-previewable, requires no special tooling. The app's observability sink still records the structured error for postmortem.

**Filename convention over Drive `description` or `appProperties` for routing.** Filenames are operator-typeable in Drive UI without entering metadata fields they don't know about. The prefix convention is short, learnable, documented in `_inbound/README.md`. `appProperties` is app-private (operator-invisible); `description` is free-form and inconsistent.

**Operator-demand polling over scheduled.** Same rationale as ADR-2: no daemon, no in-process schedule, operator owns cadence via `--batch` + OS scheduler. Inbound ingestion is operator-initiated by definition (they're dropping files); the ingestion run is similarly explicit.

## Consequences

**Positive.**

- Operator's mental model: drop, wait, check `processed/`. No CLI back-and-forth required.
- Triple dedup gives idempotency at three layers — robust against operator re-uploads.
- Rejection sidecars are operator-readable in Drive UI without leaving the inbox folder.
- No provider amendments — existing inbound parsers work unchanged behind the tempfile materialisation step.
- Operator-prepared sidecar `.meta.json` admits domain-rich metadata when filename convention is insufficient.

**Negative.**

- Operator must learn the filename prefix convention. Mitigated by the in-bucket README.
- Files without recognisable prefix go to `rejected/` immediately. Surprising to operators who expect "drop anything, app figures it out." Documented; the rejection sidecar names the issue.
- `processed/` and `rejected/` folders accumulate over time. v1 does not auto-prune. Operator can manually delete or move to a long-term archive folder.
- Sidecar `.error.txt` files contain a small amount of telemetry (file type, parser name, error class). Operator must understand this is plaintext and shareable.

**Neutral.**

- The `inbound_ingested_files` table size grows linearly with ingestion volume. At v1 scale (≤500 files per operator per year), table stays small (<100 KB).
- A future amendment may add scheduled polling, OCR, or composite ingestion; the v1 design does not preclude these.

## References

External:
- Hazel folder rule engine — `https://www.noodlesoft.com/`
- n8n Watch Folder workflow node — `https://n8n.io/integrations/google-drive/`
- Shoeboxed receipt ingestion — `https://www.shoeboxed.com/`
- Sidecar files (DAM convention) — `https://en.wikipedia.org/wiki/Sidecar_file`

Internal:
- `[[2026-05-13-google-oauth-adr]]` — bucket layout (ADR-2).
- `[[2026-05-13-google-oauth-snapshot-adr]]` — encryption boundary (ADR-3).
- `[[2026-05-12-google-oauth-adr]]` — provider abstraction.
- `[[2026-05-08-google-oauth-adr]]` — OAuth + per-profile session.
- `[[2026-05-06-google-oauth-research]]` — R6 ingestion patterns.
