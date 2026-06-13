---
tags:
  - '#research'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-side-store-inventory-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s36-review-audit]]'
  - '[[2026-05-27-secure-storage-hierarchy-namespace-inventory-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s37-review-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s38-review-audit]]'
  - '[[2026-05-28-secure-storage-production-hardening-w05-p09-s39-review-audit]]'
---

# `secure-storage-production-hardening` research: `W05.P09.S40 retained export and side-store exceptions`

This research determines whether `W05.P09.S40` needs exception ADR work after the
`W05.P09.S37`, `W05.P09.S38`, and `W05.P09.S39` migrations. The scope is the
retained explicit export or operational side-store surfaces visible in the
named plan, side-store inventory, reviews, hierarchy inventory, and current
code and policy evidence.

## Findings

### 1. S40 should produce an exception ADR for retained operator-directed exports

`W05.P09.S40` should not be closed as no-op. At least one retained explicit
export surface remains after the sensitive JSON and JSONL migration work:
`EvidenceBundleService.export` in `src/aeat/application/evidence/_service.py`.
The S36 inventory explicitly singled out the evidence bundle ZIP export as an
operator-selected export path that should be covered by S40 if retained. The
current code still retains it: the service verifies the bundle, refuses failed
verification, requires `force_incomplete` for incomplete bundles, writes record
payloads into a ZIP at the caller-provided path, and writes `manifest.json`
last.

The ledger transaction export in `src/aeat/application/ledger/_actions.py` also
qualifies for the same class of ADR coverage. The S36 review identifies the
ledger command export path as an operator-selected output rather than a
production bucket-local JSON or JSONL side store. Current policy evidence
classifies `export_ledger_transactions` as an explicit operator-directed ledger
transaction export to a caller-chosen path. Current code writes serialized
ledger rows only when `LedgerExportCommand.output_path` is provided, then emits
a ledger export event containing format, row count, byte size, digest, and
bounded transaction identifiers.

One ADR can cover both surfaces if it defines the exception class as
operator-directed plaintext exports from already-governed secure state. Separate
ADRs are only useful if the project wants different retention or operating
rules for audit bundle ZIP files versus ledger CSV or JSONL exports.

### 2. No retained W05 operational side-store exception is justified now

The S36 inventory did not find a retained application-side operational side
store that needs an immediate S40 ADR after the S37-S39 migrations. The
candidate bucket-local stores were evidence manifests, purchase invoice
evidence JSONL, business-operation invoice JSONL, inventory ledgers, live verify
observations, live expedientes snapshots, and live notification snapshots.

The evidence manifest store is migrated by S37 into the registered
`application_evidence_bundles` secure-object namespace. The inventory ledger is
migrated by S38 into the registered `profile_inventory_ledger` secure-object
namespace. The live verify, expedientes, and notifications stores are migrated
by S39 into registered secure-object namespaces through runtime-created
repositories. These no longer qualify as retained plaintext side-store
exceptions.

Short-lived secret materialisation and other storage-infrastructure temporary
file exceptions appear in the current sensitive-persistence policy allowlist,
but they are not W05.P09.S36 application side-store findings. They are better
handled by their existing storage-infrastructure and W12 plaintext-exception
tracking unless a later observation-pool pass deliberately consolidates all
plaintext exception classes into a broader ADR.

### 3. The two remaining ledger JSONL stores are pending migration, not S40 exceptions

`src/aeat/application/ledger/_evidence.py` still persists purchase invoice
evidence through a per-bucket JSONL file under
`Settings.aeat_purchase_invoice_evidence_dir`. `src/aeat/application/ledger/_business_operation_invoice.py`
still persists payable and collectible business-operation invoice records
through per-bucket JSONL files under `Settings.aeat_invoices_dir`.

These are real production bucket-local JSONL side stores, but they should not
receive S40 exception ADRs now. The S36 review recorded the original ownership
gap and its resolution: the plan now assigns purchase invoice evidence migration
to `W17.P37.S424` and business-operation invoice migration to `W17.P37.S425`.
The W17 plan text says those stores should migrate behind runtime-created
secure-object repositories, or receive explicit exception ADR coverage only if
migration is rejected after implementation research. Current code and policy
evidence therefore support a pending-migration disposition, not an accepted
exception disposition.

### 4. Already secure live and filed-declaration surfaces do not need S40 ADRs

The S36 inventory named several suspected live or filed-declaration surfaces
that are already secure-object backed. Current hierarchy evidence registers
the filed-declaration artefact, filed-declaration observation, IVA wallet
observation, IVA remote-state acquisition, Borrador 100 snapshot, census
snapshot, live expedientes snapshot, live notifications snapshot, and live
verify observation namespaces. Current live code uses runtime-created
secure-object repositories for migrated live snapshots and verify observations.

These surfaces may still have follow-up quality findings, such as S39's note
about list paths silently filtering bucket-mismatched decrypted rows, but that
is a secure-object semantics issue. It is not a retained plaintext export or
operational side-store exception for S40.

### 5. Wider explicit exports exist, but they are outside the W05.P09.S40 closeout scope

The current sensitive-persistence policy also identifies explicit
user-directed declaration export in `src/aeat/application/filing/_export.py`
and explicit operator-directed profile export in
`src/aeat/entrypoints/cli/_config/__init__.py`. The secure-persistence
enforcement ADR already distinguishes explicit user-directed exports from
normal repository persistence, and the broader W12/W16 tracking exists for
plaintext-exception inventory work.

Those wider exports should not block S40 unless the project intentionally
expands S40 from W05 side-store closeout into a global export exception ADR.
For the requested scope, S40 should cover the retained exports discovered by
the W05 side-store pass: evidence bundle ZIP export and ledger transaction
export.

## Recommendation

Create one S40 ADR now for retained operator-directed export exceptions. The
ADR should cover `EvidenceBundleService.export` and `export_ledger_transactions`
as explicit caller-path boundary crossings, not repository persistence. It
should state classification, threat model, retention responsibility, export
intent, refusal rules, audit or digest requirements, and the rule that these
exports do not authorize bucket-local plaintext repositories.

Do not create S40 exception ADRs for the migrated evidence, inventory, or live
stores. Do not create S40 exception ADRs for purchase invoice evidence JSONL or
business-operation invoice JSONL unless `W17.P37.S424` or `W17.P37.S425`
research rejects migration. Do not treat already secure filed-declaration,
wallet, Borrador, census, remote-state acquisition, live snapshot, or live
verify repositories as S40 exceptions.
