---
tags:
  - '#reference'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:6385ab0fb4e7a06c0d799f63becf70986a557153c30d91d62fb3493f508a0638'
related:
  - "[[2026-07-14-google-oauth-audit]]"
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-06-30-bucket-custody-completeness-adr]]"
  - "[[2026-06-10-ledger-evidence-enforcement-adr]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]"
---

# `google-optional-adapter-boundary` reference: `implemented Google adapter boundaries`

This reference records the implementation that constrains the Google scope
reconciliation. The clean scoped files were confirmed against commit
`52352c8d61444b16f966aad6c4c3211996a5c005`. The concurrently modified custody
service was inspected as working-tree blob
`1f59a5ef26f8b561575344bad4a5f5428df1e5a5`; its diff changes prose only, not the
archive behavior cited below.

## Summary

### Authentication and provider composition already exist

The Google CLI exposes register, login, status, and logout at
`file:src/cadrumo/entrypoints/cli/_config/_google.py:191-380`.
`run_login_flow` owns the desktop OAuth exchange at
`file:src/cadrumo/adapters/outbound/google/_oauth_flow.py:219`, while encrypted
client, token, metadata, Drive configuration, and credential-source records use
the existing secure repository at
`file:src/cadrumo/adapters/outbound/google/_session_store.py:65-271`.
The per-profile `GoogleCredentialSourceSelection` chooses OAuth Desktop or
service-account impersonation at
`file:src/cadrumo/adapters/outbound/google/_session_store.py:216-257`, and
`build_google_credentials` resolves that choice at
`file:src/cadrumo/adapters/outbound/storage/_factory.py:75-114`.
The selection record is not an impersonated credential: the factory derives an
access token for each use and does not persist that token.
`StorageProvider` is the generic port and the local and Google backends are its
existing implementations at
`file:src/cadrumo/adapters/outbound/storage/_protocol.py:25`,
`file:src/cadrumo/adapters/outbound/storage/_local.py:101`, and
`file:src/cadrumo/adapters/outbound/storage/_google_drive.py:175`; the factory
selects them at `file:src/cadrumo/adapters/outbound/storage/_factory.py:202`.
Another authentication, session, or provider layer would duplicate shipped
code.

### Drive is a ciphertext mirror with integrity reads, not restore authority

The source repository exposes deterministic on-wire rows through
`iter_all_records_raw` at
`file:src/cadrumo/adapters/persistence/storage/sql/secure_objects.py:303`.
`google sync push` uploads those ciphertext payloads and explicitly keeps the
master key local at
`file:src/cadrumo/entrypoints/cli/_config/_google.py:797-858`.
Remote manifests are built, persisted, read, and compared by the existing
helpers at `file:src/cadrumo/adapters/outbound/storage/_mirror_manifest.py:38-307`.
Those reads detect missing objects, stale revisions, divergent lineage, and
ciphertext corruption. They do not install remote rows into the local secure
repository. The correct boundary is therefore “no restore or key authority,”
not “Google is push-only.”

### Provider-neutral custody already owns complete recovery

The archive CLI delegates export and import to `BucketMaintenanceService` at
`file:src/cadrumo/entrypoints/cli/_config/_bucket_archive.py:84-274`.
The service writes a sealed full-custody archive, optionally wrapped under an
operator recovery passphrase, and restores it through the canonical bundle and
profile paths at
`file:src/cadrumo/application/bucket_maintenance/_service.py:613-844`.
Google-specific KEK escrow, per-row restoration, or a second recovery format
would duplicate this recovery mechanism.

### Drive evidence acquisition already reuses canonical byte custody

`resolve_document_link` fetches reachable Drive media as bytes and refuses
Gmail, arbitrary URLs, and out-of-scope Drive files at
`file:src/cadrumo/adapters/outbound/google/_document_link_resolver.py:155-239`.
`ledger doclink` sends those bytes through `add_attachment_bytes` and the
canonical ledger evidence linker at
`file:src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py:194-299`.
`ledger pull-folder` explicitly lists a selected Drive folder and reuses the
same resolver and attachment primitive for every eligible child at
`file:src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py:328-458`.
`add_attachment_bytes` delegates blob and manifest storage to `AttachmentStore`
at `file:src/cadrumo/domain/attachments/_service.py:126-188`.

An exact source search at the audited revision found no
`KekEscrowEnvelope`, `inbound_ingested_files`, `sync inbound`, `google escrow`,
or `google restore` implementation. No watched `_inbound` scanner, filename
router, plaintext staging path, or rejection-sidecar pipeline exists. The ADR
must preserve the two explicit byte-bearing commands and retire only the
unimplemented watched-inbox design.

### Calculation Sheets is a non-authoritative round trip

The CLI implements `calc export`, `verify`, `pull`, and `compute` at
`file:src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py:124-606`.
`PullResult` carries strict operator, binding, relation, and row-set edits at
`file:src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py:278-301`;
`pull_operator_edits` validates ownership and registry/layout metadata before
returning them at
`file:src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py:520-628`.
`compute_from_pull` delegates directly to `calculate_registry_snapshot` at
`file:src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py:1121-1181`, and
the CLI states and implements that the command persists nothing at
`file:src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py:510-606`.

Targeted confirmation found no `WorkUnit`, `ModeloWorkUnit`,
`CalculationRevision`, `CalculationRevisionCatalogueRepository`, or domain
writer import in the Google adapter or Google calc CLI. Sheet readback is real;
Sheet-to-local calculation persistence is not.

### Ledger correction already has one writer

`aeat app ledger update` builds a typed patch and calls
`update_manual_transaction_fields` at
`file:src/cadrumo/entrypoints/cli/_ledger.py:545-610`. That application service
delegates to the existing manual transaction update path, including lineage and
bucket events, at
`file:src/cadrumo/application/ledger/_actions_manual.py:618-872`.
Exact search found no Google transaction-edit command, generic CSV-corrections
surface, or production reverse-merge writer. Adding those under Google would
duplicate or bypass the canonical ledger lifecycle.

### Required wording corrections

- Remote integrity verification reads Drive; the mirror is non-authoritative,
  not write-only.
- Calculation Sheets has typed readback and non-persistent computation; it is
  not merely a one-way export.
- Explicit `doclink` and `pull-folder` flows intentionally persist encrypted
  evidence through canonical services; they are not parallel Google writers.
- No new Google escrow, watched inbound pipeline, calculation persistence, or
  ledger reverse merge is required by the current implementation.
