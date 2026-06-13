---
tags:
  - '#research'
  - '#secure-object-database-drift'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `secure-object-database-drift` research: `cross-application encrypted persistence integrity`

This research investigated whether persisted application state is reliably written and reloaded across the encrypted storage substrate. The trigger was live IVA wallet/history work that depended on durable AEAT-filed observations, IVA compensation history, local calculation observations, and wallet reconciliation decisions. The scope expanded to the complete application because the same `secure_objects` table backs ledger, invoices, Modelo work units, filing drafts, justificantes, submissions, workflow state, auth sessions, profile state, and live remote-state snapshots.

The investigation was read-only for live/profile data. No private payloads, taxpayer identifiers, wallet amounts, filing identifiers, or decrypted live rows were recorded here.

## Findings

### Storage architecture

- The central encrypted object store is `secure_objects`, mapped by `src/aeat/adapters/persistence/storage/sql/_orm.py` and accessed through `SecureObjectRepository` in `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- Secure object natural keys are stored as HMAC lookup digests. Payloads are encrypted BLOBs. That means code must not infer domain identity from raw `object_key` bytes, and raw-row scans cannot prefix-match natural keys.
- `SecureBoundRepository` in `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py` is the common envelope abstraction for many domain repositories.
- Relational SQL state also exists outside `secure_objects`, notably registry/catalog and rental/finca tables declared in `src/aeat/adapters/persistence/storage/sql/_orm.py`. Secure-object diagnostics do not currently validate those relational schema/table contracts.

### Routing model

- When `AEAT_DATABASE_URL` / `aeat_database_url` is explicit, it wins. Otherwise settings derive a per-bucket SQLite URL under `<storage-root>/buckets/<bucket-id>/db/aeat.db` from active profile resolution. Without an active profile, settings can derive a root fallback DB.
- Active bucket ID resolution flows through `src/aeat/core/_bucket_pointer_io.py`: explicit environment/settings override first, then plaintext active-profile pointer.
- The CLI opens the active bucket master-key session before normal profile-bound commands. Storage encryption and decryption resolve the current `BucketSession` through a `ContextVar` in `src/aeat/adapters/persistence/storage/master_key/_active_session.py`.
- Profile lifecycle has special cross-bucket routing helpers so profile records can be read from the target bucket DB rather than whichever DB the current process engine happens to point at.

### Active profile integrity probe

The active profile's manifest and profile record are coherent and readable. `aeat config repair profile` reported the active pointer as registered, the encrypted profile record present, and status ready.

`aeat config repair integrity objects` reported 74 readable secure-object rows and 374 unreadable rows. The unreadable rows are concentrated in state-critical namespaces:

- `aeat.domain.buckets.event_history`: 234 unreadable, 1 readable.
- `aeat.domain.filing.drafts`: 9 unreadable, 0 readable.
- `aeat.domain.invoices`: 32 unreadable, 0 readable.
- `aeat.domain.justificante.metadata`: 7 unreadable, 0 readable.
- `aeat.domain.modelos.calculation_revisions`: 9 unreadable, 0 readable.
- `aeat.domain.modelos.work_units`: 18 unreadable, 0 readable.
- `aeat.domain.transactions.bucket`: 18 unreadable, 0 readable.
- `aeat.outbound.aeat.auth.sessions`: 6 unreadable, 2 readable.
- `aeat.outbound.aeat.sede.filed_declaration.artefacts`: 14 unreadable, 24 readable.
- `aeat.outbound.aeat.sede.filed_declaration.observations`: 27 unreadable, 8 readable.

The live IVA compensation namespaces currently needed by the wallet calculation chain are readable:

- `aeat.calculations.iva_compensation.history`: 8 readable, 0 unreadable.
- `aeat.calculations.observations`: 8 readable, 0 unreadable.
- `aeat.calculations.iva_wallet.reconciliation_decisions`: 1 readable, 0 unreadable.
- `aeat.calculations.iva_wallet.reconciliation_decision_events`: 3 readable, 0 unreadable.
- `aeat.outbound.aeat.sede.iva_compensation_wallet.observations`: 3 readable, 0 unreadable.

This proves the successful live IVA capture is persisted and reloadable now, but it does not make the broader application state healthy.

### Root-cause class confirmed

Several tests opened `EphemeralMasterKeyProvider` while failing to isolate `AEAT_DATABASE_URL`. Repositories constructed without an injected engine then used the process default settings and could write encrypted test data into the active profile DB under a throwaway key. Those rows then appear as valid rows that cannot decrypt under the real profile key.

Concrete contaminated surfaces matched this pattern:

- Invoice and transaction repository tests used ephemeral keys with default repositories.
- Invoice reconciliation tests used ephemeral keys with default invoice/transaction repositories.
- Complementaria tests used ephemeral keys while only moving legacy draft/submission directories, not the SQL DB.
- Sede declaration observation tests used `FiledDeclaracionObservationStore` with an ephemeral master key provider, while the store's internal `SecureObjectRepository()` still resolved the default active DB.

The implemented mitigation isolated those test files to `tmp_path` databases and disposed cached engines before and after the tests.

### Calculation-chain bug confirmed

`CalculationObservationRepository.iter_modelo()` attempted to iterate raw secure-object rows and prefix-match raw object keys as though they were plaintext `(modelo, year, period)` strings. That cannot work because secure object keys are HMAC digests and payloads are ciphertext at the raw-row layer.

The implemented fix makes `iter_modelo()` enumerate decrypted repository records and filter on `payload.observation.modelo`. A regression test now saves observations for two modelos and proves the scan returns only the requested modelo.

### Silent partial enumeration risk

The generic `SecureBoundRepository.iter_ids()` previously used `SecureObjectRepository.list_records()`. That lower-level method skips unreadable rows and only logs a warning. For complete application state, this is unsafe: a calculation, filing, live snapshot, submission, or ledger scan could continue with partial data and look correct from the caller's perspective.

The implemented fix changes `SecureBoundRepository.iter_ids()` to use `iter_records_with_failures()` and raise `SecureObjectUnreadableError` when any row in the namespace is unreadable. This makes generic secure-bound enumeration fail closed instead of silently hiding persisted rows.

### Remaining gaps

- Existing active-profile unreadable rows are not repaired. They must not be quarantined blindly. The next step is row-level classification and origin attribution.
- `repair list` currently reports namespace, row id, digest, classification, schema version, timestamp, and decryptability. It does not yet infer likely owner profile, active bucket relation, expected singleton key, or probable test-contamination signature.
- Explicit `AEAT_DATABASE_URL` can still bypass per-bucket routing. This is valid for controlled tests and diagnostics but dangerous for profile-bound CLI commands unless guarded.
- Root fallback DB can still receive writes if a command misses its active-profile guard.
- `probe_namespace_integrity()` validates AES-GCM decryptability only. Rows can decrypt but still fail domain envelope classification/schema compatibility.
- Relational SQL drift is outside the secure-object integrity report and needs its own schema/table validation.
- Namespace classification in `repair_integrity.py` still omits some active namespaces such as profile inventory/assets/amortization, attachments, usage ratios, Google OAuth/Drive config, and LLM cache/usage.

## Decisions already implemented in this pass

- Fixed `CalculationObservationRepository.iter_modelo()` to scan decrypted repository records.
- Added a non-tautological regression test proving `iter_modelo()` returns saved matching observations.
- Added a fail-closed regression test proving prior-filing scans raise `SecureObjectUnreadableError` when rows exist but were sealed under another key.
- Changed `SecureBoundRepository.iter_ids()` / `iter_records()` behavior to fail closed on unreadable rows.
- Isolated the discovered ephemeral-key tests to temporary SQLite databases and disposed cached engines around them.

## Recommended next implementation wave

1. Add a non-destructive secure-object attribution report that groups unreadable rows by namespace, row timestamp range, classification, expected singleton-vs-multirow semantics, and likely origin.
2. Add a test hygiene guard that fails when a test file opens `EphemeralMasterKeyProvider` and constructs default SQL-backed repositories without isolating `AEAT_DATABASE_URL` or injecting an engine.
3. Add active-profile command guards that refuse profile-bound writes when settings resolve to the root fallback DB.
4. Extend repair namespace classification to every active namespace discovered by `list_namespaces()`.
5. Add domain-envelope integrity mode: decrypt readable rows and validate the owning repository's envelope classification/schema contract without printing payloads.
6. Add relational SQL integrity diagnostics for non-secure-object tables.
