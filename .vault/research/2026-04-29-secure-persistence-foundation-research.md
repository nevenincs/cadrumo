---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-28-secure-persistence-foundation-exec]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-adr]]"
  - "[[2026-04-27-secure-persistence-foundation-research]]"
---



# `secure-persistence-foundation` wave-3 research

## Origin

Wave 1 shipped the substrate; Wave 2 actioned every deferred Wave-1
finding and added the operator-facing primitives (materialise_secret
helpers, NIF / NIE / CIF validator, opaque-bearer redaction rule,
`aeat secrets` CLI) plus the read-through adapter pattern with
per-consumer migration helpers for the five plaintext-credential
canary targets. Wave 3 is the **financial-domain consumer** wave —
the wave that closes issue #216 by landing the bank-import Kent
moment under the substrate's governed persistence boundary.

This research artifact documents the financial-domain persistence
inventory, the migration shape per consumer, and the Wave-3 plan
seed. It also catches and queues any audit-gate findings emerging
from Wave-2's review pass.

## Wave-3 success criterion

Kent runs **one command** — `aeat financial ingest --persist
--provider <bank> --file <statement>` — and the tool:

1. Parses the bank statement file via the existing provider parser.
2. Normalises the rows into typed `RawTransaction` records.
3. Persists them through the governed boundary so:
   - Re-running the same file is idempotent (the existing
     `derive_transaction_id` SHA-256 hash already gives us this
     property).
   - Two parallel imports of the same file serialise via the
     substrate's `exclusive_file_lock`.
   - The persisted records are encrypted at rest at the FINANCIAL
     classification.
   - Every row carries an envelope with `schema_version` so future
     migrations are reviewable.
4. Returns a per-file summary in trilingual operator-language form
   (`imported N rows; skipped M duplicates; 0 errors`).

The summary is also emitted as a registered `--json` output schema
so machine consumers (downstream automation, Kent's eventual
dashboard) get a stable contract.

## Wave-3 candidate consumer surface

The audit's CRITICAL-2 finding called out broad plaintext financial
persistence. Wave 3's migration targets:

- `aeat.domain.financial.transactions` — the existing
  `TransactionCatalogue` (JSON-on-disk, atomic write via tempfile +
  `os.replace`, content-keyed by `derive_transaction_id`'s SHA-256
  hash). This is the load-bearing migration: the bank-import Kent
  moment lands here. Migration target: each `TransactionCatalogue`
  is wrapped in an `Envelope[TransactionCatalogue]` at FINANCIAL
  class; payload is the existing pydantic-v2 frozen
  `TransactionCatalogue` shape (no breaking change at the public
  surface).
- `aeat.domain.financial.invoices` — the invoice catalogue. Similar
  shape; FINANCIAL class.
- `aeat.domain.financial.attachments` — already content-addressable
  (`blobs/{sha256}` + manifest JSON). The substrate's
  `EncryptedBlobStore` is the natural home; migrate the existing
  blob layout under the substrate's blob-store API. FINANCIAL
  class for sensitive operator attachments; CORPUS for
  attachments backed by a public source (none today, but the
  classification primitive supports the distinction).
- `aeat.domain.financial.usage_ratios` — usage-ratio catalogue. Smaller;
  FINANCIAL class. Co-migrates with the invoices wave.

The substrate's existing primitives cover this surface without
new modules. Wave 3 ships **adapters**, not new substrate
primitives — the substrate is feature-complete after Wave 2.

## Wave-3 plan shape (preview)

The Wave-3 plan will run in approximately the following phases:

- Phase 0 — action any Wave-2 audit-gate findings that the
  reviewers raise and that have not yet been actioned. Inherits
  the standard Wave-N pattern of wave-entry-finding cleanup.
- Phase 1 — `aeat.domain.financial.transactions` migration adapter.
  - New `TransactionCatalogueRepository` under
    `aeat.domain.financial.transactions._repository` consuming the
    substrate's envelope + classification primitives.
  - The existing `load_transactions` / `save_transactions`
    helpers become read-through wrappers that consult the
    repository first and fall back to the legacy JSON path with
    a deprecation log.
  - Migration helper
    `migrate_transactions_to_governed_persistence(legacy_path)`
    reads the legacy catalogue and writes it via the
    repository.
- Phase 2 — `aeat.domain.financial.invoices` migration adapter; same
  pattern.
- Phase 3 — `aeat.domain.financial.usage_ratios` migration adapter.
- Phase 4 — `aeat.domain.financial.attachments` migration to the
  substrate's `EncryptedBlobStore`. The existing manifest layout
  is preserved (the substrate's manifest already carries the
  superset of fields).
- Phase 5 — bank-import persistence wiring. The existing
  `aeat financial ingest` command gains a `--persist` flag
  (default ON when stdout is a TTY, OFF when piped to keep the
  current `RawTransaction`-jsonl-to-stdout behaviour for pipe
  consumers). On `--persist`, the parsed rows are merged into
  the catalogue via the new repository's
  `merge_raw_transactions` method. Idempotency falls out of the
  existing `derive_transaction_id` SHA-256 design.
- Phase 6 — concurrency hardening for parallel imports.
  `merge_raw_transactions` acquires the substrate's
  `exclusive_file_lock` on the catalogue path; a second
  concurrent import waits or raises `LockAcquisitionError` with
  exit code 7 (LOCKED).
- Phase 7 — the bank-import Kent moment integration test. End-
  to-end: parser → repository → re-read returns the same rows;
  re-import → 0 new rows; concurrent import → one wins, other
  exits 7.
- Phase 8 — `docs/coverage/pipeline.md` flip. The TDP T1 row
  changes from `🚧 (no persist)` to `✅ persisted via aeat
  financial ingest --persist`.
- Phase 9 — Wave-3 audit gate (vaultspec-code-review + OWASP
  security audit + Gemini PR review).

## Standing constraints inherited from Waves 1 and 2

- The substrate's public API is `aeat.adapters.persistence.storage` only. Adapters
  consume the public surface; no internal-module access.
- Pydantic v2 strict frozen at every boundary.
- No mocks; tests use real cryptography, real on-disk
  persistence under `tmp_path`, real SQLAlchemy in-memory
  engines, real `multiprocessing.spawn` for cross-process tests.
- Read-through adapter pattern is non-negotiable — no flag-day
  cutovers; legacy JSON files remain readable until the
  operator runs the migration helper.
- Trilingual error envelope contract continues to apply.
- No new GH issues filed; #216 is the rolling tracker.
- Live AEAT submission permanently forbidden. Wave 3 does not
  touch live-submit territory.

## Out of scope for Wave 3

- Filing / submission / amendment / justificante migration
  (Wave 4).
- `.aeat/live-submit-audit.log` relocation (Wave 4).
- Observability + audit redaction discipline (Wave 5).
- Caches and corpora (Wave 6).
- Connector + export governance (Wave 7).
- Multi-currency handling (#103 territory; deferred per Wave-1
  research).
- PDF invoice ingest (#254 EPIC; deferred).
- Bulk classification rules (#217; deferred).
- T6 aggregation (#218; consumes Wave-3's persistence; deferred).

## Wave-3 entry-point findings (from Wave-2 audit gate)

The Wave-2 audit-gate reviewers are running concurrently with this
research artifact's drafting. Findings will be appended here once
the reviewers report. Per the wave contract, any HIGH or CRITICAL
emerging from Wave-2's review must close before Wave 3's
implementation phases begin; MEDIUM and LOW findings roll into
this artifact's backlog and get actioned in Wave-3 Phase 0.
