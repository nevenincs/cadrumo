---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave7-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave6-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-audit]]"
---



# `secure-persistence-foundation` final security audit | (**status:** `revision required`)

## Scope

End-to-end security audit of the secure-persistence-foundation feature
covering Wave 1 substrate through Wave 10 master-key rotation. The
audit walks the codebase looking for at-rest crypto correctness, AEAD
binding, master-key rotation invariants, HKDF context discipline,
redaction discipline, identity-bearing data leak canaries, CLI input
validation, test discipline, json-pipe-safety, live-submit forbidden
discipline, and dead/legacy code residue.

Verification commands:

- `uv run --no-sync ruff check src/aeat`: **all checks passed**.
- `uv run --no-sync ty check src/aeat`: **all checks passed**.
- `uv run --no-sync python -m pytest src/aeat/storage src/aeat/entrypoints/cli/test_security.py src/aeat/entrypoints/cli/test_json_pipe_safety.py src/aeat/observability src/aeat/llm src/aeat/financial src/aeat/filing src/aeat/submission src/aeat/justificante src/aeat/workflow -q`: **1463 passed, 9 skipped, 5 deselected, 26 warnings**.

## Findings

### CRYPTO-CORRECTNESS - PASS

The substrate primitives (`src/aeat/adapters/persistence/storage/_crypto.py`,
`src/aeat/adapters/persistence/storage/_envelope.py`, `src/aeat/adapters/persistence/storage/_master_key.py`)
implement AES-256-GCM with 12-byte random nonces and 16-byte tags via
`cryptography.hazmat.primitives.ciphers.aead.AESGCM`. HKDF-SHA256
derives per-consumer keys from the project master key. `encrypt_record`
and `decrypt_record` correctly thread the AAD parameter into the AEAD
operation. Key length is verified up-front. The `EncryptedBlob` model
carries `nonce || ciphertext_with_tag` with `min_length` invariants.
`derive_key` defends against zero-length output.

The cipher envelope's `_build_aad` helper authenticates both the
sensitivity classification and the consumer's HKDF context. The
binding is `aeat.envelope.cipher.v1::CLASS::HKDF`. Cross-consumer
ciphertext substitution and class-relabel attacks both fail with
`DecryptionError` (verified by 8 substrate tests in
`_test_envelope_ciphertext.py` plus per-repository
`test_foreign_class_envelope_refused`). `load_encrypted_envelope`
validates the AAD on the cipher envelope BEFORE consulting the master
key (defense in depth). The inner-envelope classification is re-checked
after decryption.

The master-key acquisition stack (`KeyringMasterKeyProvider`,
`FileFallbackMasterKeyProvider`) is well-engineered: scrypt KDF with
N=2^17 (OWASP-aligned), 32-byte master key wrapped under an AAD-bound
AES-256-GCM envelope, secure file-write via `os.open(..., O_NOINHERIT
| O_CLOEXEC, mode=0o600)` (TOCTOU-safe; no post-write chmod),
passphrase popped from environment after read so child processes do
not inherit it, atexit cache zeroisation, and explicit refusal of
the no-op `fail.Keyring` / `null.Keyring` backends.

### MASTER-KEY ROTATION - PASS

`src/aeat/adapters/persistence/storage/_rotation.py` and the `aeat security
rotate-master-key` CLI implement a content-preserving rotation:

- The rotation operates at the bytes level - it never parses the
  inner `Envelope` payload. That keeps the rotation contract
  decoupled from per-consumer payload schemas.
- Each cipher envelope is re-written via `tempfile + os.replace`
  so a crash mid-rotation leaves either the old or the new ciphertext
  on disk, never a torn state.
- Resume-idempotency: rotation tries the new master key first; if it
  decrypts, the file is already rotated and is skipped. Falls back to
  the old key on AEAD-tag failure.
- AAD binding survives rotation: the AAD is rebuilt for both
  decrypt-old and encrypt-new with the consumer's `hkdf_context`
  and the cipher envelope's `classification`.
- The same-key guard in the CLI prevents accidental no-op rotation.
- `RotationSummary` (rotated / skipped / errors) provides a transparent
  partial-success ground state; the CLI exits non-zero on
  `errors > 0`.

`test_rotation.py` covers the round-trip, resume idempotency,
wrong hkdf-context after rotation, distinct-context fan-out,
AAD-mismatch refusal, and torn-write recovery. `aeat security
rotate-master-key` is exercised end-to-end with a NIF canary in
`test_security.py`.

### HKDF CONTEXT DISCIPLINE - PASS

Catalogued every consumer's HKDF context byte-string:

| Consumer | HKDF context |
| --- | --- |
| Transaction catalogue (Wave 3 repo) | `aeat.domain.financial.transactions.catalogue.v1` |
| Filing draft (Wave 4 repo) | `aeat.application.filing.draft.v1` |
| Filing amendment (Wave 4 repo) | `aeat.application.filing.amendment.v1` |
| Filing history (Wave 4 repo) | `aeat.application.filing.history.v1` |
| Justificante metadata (Wave 4 repo) | `aeat.domain.justificante.metadata.v1` |
| Submission (Wave 4 repo) | `aeat.adapters.outbound.aeat.export.filing.v1` |
| Workflow run (Wave 7) | `aeat.application.workflow.run.v1` |
| Envelope-payload HKDF salt | `aeat.envelope.payload.v1` |
| Cipher-envelope AAD prefix | `aeat.envelope.cipher.v1::` |
| Encrypted columns lookup | `aeat.column.hashed_lookup.v1` |
| Secret-store lookup | `aeat.secret_store.lookup.v1` |
| Master-key wrap AAD | `aeat.master-key.v1` |
| Blob payload AAD | `aeat.blob.payload.v1` |
| Blob DEK wrap AAD | `aeat.blob.dek-wrap.v1` |

No collisions; all `*.v1`-versioned for clean future migrations.

`default_rotation_plan(settings)` lists eight `RotationPlanEntry`
records covering every governance consumer. The `amendment-results/`
subdirectory of `aeat_submissions_dir` and the `amendments/`
subdirectory share the `aeat.application.filing.amendment.v1` HKDF context -
this is correct because both directories are bound to the same
`FilingAmendmentRepository` consumer identity (the engine binds
the amendment-results store to the same repository class via
`_amendment_repository()` with a sibling store_dir). See LOW-002
below for a comment-only follow-up.

### REDACTION DISCIPLINE - PASS for in-scope sinks

`JsonlRunSink.emit` (DIAGNOSTIC, hot path on every CLI run),
`LLMCache.write` (DIAGNOSTIC), and `UsageRecorder.record`
(DIAGNOSTIC) all route through `redact_structured` with the
`default_rules_for_class(SensitivityClass.DIAGNOSTIC)` rule set
before write. The redaction is recursive (walks dicts, lists, tuples,
model dumps) and idempotent on already-redacted output (the NIF
SHA-256-prefix output `sha256:abcd1234` does not match the NIF
pattern, so re-reads stay stable).

`LLMCache.read` deliberately returns redacted text via
`CachedEntry.model_validate_json` of the redacted JSON. This is
the correct DIAGNOSTIC posture - the cache is lossy by design when
the alternative is plaintext-on-disk leak.

See finding TRACE-001 below for `save_trace` /
`save_events_append` plaintext writers under
`src/aeat/core/observability/_store.py`.

### CLI INPUT VALIDATION - PASS

Every id-shaped CLI argument is validated against path-traversal
patterns BEFORE composition into filenames:

- `_validate_draft_id` rejects empty, slash, backslash, dot, and
  leading-dot tokens (`src/aeat/application/filing/_repository.py`).
- `_validate_amendment_id`
  (`src/aeat/application/filing/_complementaria_repository.py`).
- `_validate_csv` (`src/aeat/domain/justificante/_repository.py`).
- `_validate_submission_id` (`src/aeat/adapters/outbound/aeat/export/_repository.py`).
- `_validate_modelo` in filing-history repository.
- `_validate_run_id` rejects non-`[0-9a-f]{16}` shapes
  (`src/aeat/core/observability/_store.py`).
- `resolve_record_json_path` (`src/aeat/core/paths.py`) is the
  centralised path-containment guard used by workflow and divergence
  repositories.

### TEST DISCIPLINE - PASS

Storage tests use real on-disk persistence with
`EphemeralMasterKeyProvider`. Crypto tests cover failure modes:
wrong key, wrong AAD, malformed input, version gate, classification
gate, foreign-class refusal, foreign-hkdf-context refusal, torn-write
recovery, resume-idempotency. Tests in
`src/aeat/adapters/persistence/storage/_test_master_key.py` use `monkeypatch` to
swap out the third-party `keyring` package's `get_password` /
`set_password` - the only sanctioned mock surface (the OS keychain
is not testable on CI).

Per-repository tests (filing draft, filing amendment, filing history,
justificante, submission, transaction catalogue, workflow) all
include a `test_foreign_class_envelope_refused` and a
`test_foreign_hkdf_context_refused` (or equivalent canary) that
exercise the full crypto stack on real disk.

### JSON-PIPE-SAFETY - PASS

`uv run --no-sync python -m pytest src/aeat/entrypoints/cli/test_json_pipe_safety.py`
passes 7/7. Storage imports remain deferred behind subcommand bodies
in `cli/secrets.py`, `cli/security.py`,
`observability/_sink.py`, `llm/_cache.py`, `llm/_usage.py`,
`workflow/_persistence.py`, and the financial-ingest CLI.
Non-storage CLI commands do not pay the Alembic plugin discovery
cost.

### LIVE-SUBMIT FORBIDDEN DISCIPLINE - PASS

`src/aeat/adapters/outbound/aeat/export/test_live_submit_permanently_forbidden.py`
passes 7/7. The wave-7 merge from main excised the now-obsolete
`GovernedLiveSubmitAuditSink` and the legacy `_audit`
deprecation wrapper as the wave-7 audit gate noted. No active code
path performs a live AEAT write.

### Cross-cutting design checks - PASS

- **AAD binding** - every cipher envelope authenticates both its
  sensitivity class and its consumer's HKDF context. Cross-consumer
  ciphertext substitution and class-relabel attacks both fail with
  `DecryptionError`. AAD survives master-key rotation.
- **Per-consumer key derivation** - distinct HKDF contexts catalogued
  above, no collisions, all `.v1` versioned.
- **Test discipline** - `EphemeralMasterKeyProvider` backs every
  storage test; `override_master_key_provider()` discipline shared
  with `_resolve_master_key_provider()` in encrypted columns.
- **Idempotent re-saves** - verified across all six core repositories
  in the wave-7 audit gate.
- **Per-record locking** - `exclusive_file_lock` guards every
  repository's `save` / `merge` / `delete` path.
- **Live-submit forbidden** - no active code path performs a live
  AEAT write.

## HIGH findings (REVISION REQUIRED)

### LEAK-001 | HIGH | `aeat financial txs` CLI bypasses `TransactionCatalogueRepository`

The `aeat financial txs build`, `aeat financial txs classify`,
and `aeat financial txs classify-llm` subcommands in
`src/aeat/entrypoints/cli/financial/txs.py` (lines 139, 261, 453) all call
`save_transactions(catalogue, target)` from
`src/aeat/domain/financial/transactions/_service.py:51`, which atomically
writes `catalogue.model_dump_json(indent=2)` to PLAINTEXT on disk
at `aeat_financial_txs_dir/transactions.json` (the
`DEFAULT_CATALOGUE_FILENAME` resolved by
`src/aeat/entrypoints/cli/financial/_catalogue.py:21`).

The catalogue is the wave-3-defined consumer of
`TransactionCatalogueRepository` - at FINANCIAL classification,
with HKDF context `aeat.domain.financial.transactions.catalogue.v1`.
Wave 9 (commit `822154e`) claims hard cutover with no legacy
plaintext fallback, but only filing / submission / amendment /
justificante / workflow were closed. The transaction CLI was never
migrated.

Concrete leak: every `RawTransaction` row in the catalogue
carries the counter-party `description`, `amount`,
`currency`, optional `payee`, and the
`derive_transaction_id` SHA-256 over those fields. Any operator
running `aeat financial txs build path/to/statement.csv` lands a
plaintext FINANCIAL-class catalogue on disk with full transaction
descriptions that may carry merchant names, beneficiary NIFs in
payment memos, etc.

The directory layout is also inconsistent - `aeat financial ingest
--persist` writes the encrypted envelope to
`transactions.envelope.json` while `aeat financial txs ...`
writes the plaintext catalogue to `transactions.json` in the SAME
directory. An operator who alternates between the two paths gets two
desynced catalogues with no warning.

Resolution requires: (a) removing `save_transactions` /
`load_transactions` plaintext helpers; (b) routing every `aeat
financial txs` subcommand through
`TransactionCatalogueRepository`; (c) deleting the
`DEFAULT_CATALOGUE_FILENAME` constant; (d) removing the legacy
fallback in the wave-3 docstring at
`src/aeat/domain/financial/transactions/_repository.py:10-16`. This is a
non-trivial refactor (the CLI surface for txs has many subcommands
and downstream review/invoice consumers), so flagging for user
judgement rather than mechanical fix.

### LEAK-002 | HIGH | `aeat financial invoices` writes plaintext catalogue

`src/aeat/domain/financial/invoices/_service.py:97` `save_invoices`
is the mirror image of `save_transactions`: writes plaintext
`InvoiceCatalogue.model_dump_json(indent=2)` to disk via
`tempfile + os.replace`. Invoice records carry counter-party
NIFs, amounts, and free-text descriptions - FINANCIAL class. No
invoice repository was created in waves 3-9; the entire invoice
catalogue remains a plaintext writer.

This was never in scope for waves 3-9 (the wave-1 ADR enumerated
transactions, drafts, submissions, amendments, justificantes, filing
history, and workflow runs as in-scope, with invoices implicitly
deferred). Worth opening as the next backlog item.

### LEAK-003 | HIGH | `aeat financial attachments` manifest writer plaintext

`src/aeat/domain/financial/attachments/_store.py:281` `write_manifest`
writes `attachment.model_dump_json(indent=2)` plaintext via
`_atomic_write_text`. The `Attachment` manifest model carries
`source_reference`, `linked_transaction_ids`,
`linked_invoice_ids`, `metadata` (free-form key/value), and
`notes` (free-form text) - FINANCIAL-class data tying
identity-bearing transaction IDs to arbitrary file blobs. The blob
bytes themselves go through `EncryptedBlobStore` correctly, but
the manifest sidecar leaks the linkage.

Out of scope for waves 3-9; flagging for the invoice-and-attachment
follow-on track.

### LEAK-004 | HIGH | Setup wizard writes operator NIF plaintext

`src/aeat/application/setup/_env_writer.py:152` `write_profile_file`
writes `profile.model_dump_json(indent=2)` to disk without
encryption. `AutonomoProfile.tax_id` is the operator's NIF. The
first-run setup wizard runs ahead of the secret store, so the profile
JSON is the authoritative carrier of the operator's identity record.
Per the default policy table, IDENTITY class requires
`CIPHERTEXT_REQUIRED` at rest.

Out of scope for waves 3-9 (the setup wizard predates feature 216),
but flagging because the project's track-A bidirectional sync and
track-B unidirectional pipeline model implies the setup wizard's
profile output is intended to be a long-lived identity record.

## MEDIUM findings

### TRACE-001 | MEDIUM | `save_trace` / `save_events_append` write `RunTrace` plaintext

`src/aeat/core/observability/_store.py:70-114` exposes `save_trace`
and `save_events_append`, both of which write
`RunTrace.model_dump_json` and `RunEvent.model_dump_json`
directly to disk with no redaction. `save_trace` is invoked at
every `run_context` exit (`_context.py:266`), so on every CLI
invocation an unredacted trace lands on disk at
`runs_dir/RUN_ID/trace.json`. The trace's `arguments` tuple
is run through name-side redaction in `build_arguments`
(`cli/_observability.py`) - flags whose name matches
`password` / `secret` / `token` / `api_key` /
`passphrase` / `credential` are replaced with three asterisks -
but value-side redaction is NOT performed (audit finding S6 from a
prior round). An operator who passes a NIF or a justificante CSV in
the value position of an otherwise innocent flag has the literal
value written into `trace.json`.

The `JsonlRunSink.emit` path on `events.jsonl` DOES route
through `redact_structured` correctly. The asymmetry between the
two writers is the gap.

This pre-dates feature 216 (it ships from the run-trace observability
feature) and is documented as a known carry-forward in
`cli/_observability.py:21-29`. Per the default policy table,
AUDIT class is `CIPHERTEXT_REQUIRED`. The fix path is: (a) route
`save_trace` through `redact_structured` like
`JsonlRunSink.emit` already does; (b) consider migrating
`save_trace` to the encrypted-envelope substrate since AUDIT-class
records belong there; (c) at minimum extend
`_REDACT_NAME_SUBSTRINGS` with NIF-shaped value detection.
Flagging for user judgement on the migration scope.

### LEAK-005 | MEDIUM | Sync divergence repository writes plaintext JSON

`src/aeat/application/sync/_repository.py:69`
`JsonFileDivergenceRepository.save` writes
`record.model_dump_json(indent=2)` plaintext for each
`DivergenceRecord`. Per the default policy table, divergence
records are AUDIT class (`CIPHERTEXT_REQUIRED`). The records do
NOT carry operator-identity-bearing data (no NIF / casilla VALUE /
CSV / token); they track schema deltas between local and live AEAT
modelo definitions. The discipline gap is: the AUDIT-class default
policy says ciphertext-at-rest, but this repository writes plaintext.

Recommend either (a) escalate divergence records through an encrypted
envelope, or (b) add a per-record sensitivity override that
explicitly declares divergence records as OPERATIONAL or CORPUS class
(plaintext-acceptable per the policy table). Flagging for user
judgement.

### USAGE-001 | MEDIUM | `UsageRatioProfile` writer plaintext

`src/aeat/domain/financial/usage_ratios/_service.py:97` writes
`profile.model_dump_json(indent=2)` plaintext.
`UsageRatioProfile` carries business / personal split percentages
- less identity-bearing than transaction descriptions but still
FINANCIAL classification per default policy. Out of scope for waves
3-9; flagging for the follow-on financial-input encryption sweep.

### DOCSTRING-001 | MEDIUM | Stale legacy-fallback docstring after wave-9 hard cutover

`src/aeat/domain/financial/transactions/_repository.py:10-16` and
`src/aeat/application/filing/_repository.py:9-13` both still describe a legacy
entry point and a read-through-and-fallback adapter. Wave-9 hard
cutover commit `822154e` removed the fallback in filing,
submission, amendment, etc. but left the docstrings stale. For the
filing draft repository this is purely a docstring defect; for the
transactions docstring it is both stale prose AND it is still TRUE
because LEAK-001 above (the transactions CLI surface still bypasses
the repository).

Mechanical fix: update the filing draft repository docstring to
remove the legacy and fallback language. The transactions docstring
should be updated only after LEAK-001 is closed.

## LOW findings

### LOW-001 | LOW | `_validate_*_id` helpers duplicated across repositories

Each repository defines its own `_validate_*_id` near-identical
helper. `_paths.resolve_record_json_path` is a centralised
version used by workflow and divergence; consider migrating every
repository to call it instead. Pure code-quality concern; no security
impact.

### LOW-002 | LOW | Rotation plan duplicates `aeat.application.filing.amendment.v1` for two store dirs

`src/aeat/adapters/persistence/storage/_rotation.py:283,287` lists two distinct
`RotationPlanEntry` records both bound to the same HKDF context
(`aeat.application.filing.amendment.v1`), one for
`aeat_submissions_dir/amendment-results` and one for
`aeat_submissions_dir/amendments`. This is correct per design
(one `FilingAmendmentRepository` consumer identity, two store
dirs), but deserves an inline comment explaining why so a future
maintainer does not deduplicate the plan and break rotation for one
of the directories. Mechanical fix is a comment-only change.

## Decision

**Status: REVISION REQUIRED.**

The substrate (Wave 1, Wave 7), the rotation helper (Wave 10), the
secret store, and the per-repository governance writers (transactions
repo, filing draft, filing amendment, filing history, justificante,
submission, workflow) are all sound and pass every crypto-correctness,
AAD-binding, classification-gate, and rotation-invariant check. AEAD
is correctly bound to (classification, hkdf_context). Master-key
rotation preserves payload bytes, is per-file atomic, resume-
idempotent, and AAD binding survives rotation.

The wave-9 hard-cutover claim (no legacy plaintext fallback anywhere)
is false for `aeat financial txs` (LEAK-001). The CLI surface
for transaction classification still writes a plaintext FINANCIAL-class
catalogue to disk via `save_transactions` parallel to the
encrypted `transactions.envelope.json` written by `aeat
financial ingest --persist`. This is the dominant finding and
requires revision before the feature can claim hard-cutover
end-to-end.

The remaining HIGH findings (invoices catalogue, attachment
manifests, setup-wizard profile) are out of the wave-1 ADR enumerated
scope but are part of the broader discipline that every persistence
consumer that writes identity-bearing data must use the
encrypted-envelope path, which the secure-persistence-foundation
feature establishes. They should be captured as the next backlog
items rather than blocked on this audit gate.

The TRACE-001 finding (`save_trace` plaintext writer) is a
pre-existing carry-forward from the run-trace observability feature
and is documented in source as a known limitation. It should either
be closed by routing `save_trace` through `redact_structured`
at minimum, or escalated to the encrypted-envelope substrate as part
of the AUDIT-class discipline.

No mechanical fixes were applied - every HIGH finding requires user
judgement on scope and timing. Flagging for the next wave or a
follow-up bug.
