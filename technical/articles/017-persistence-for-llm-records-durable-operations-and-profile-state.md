# Persistence for LLM records, durable operations, and profile state

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-017` · **Topic:** [Persistence and secure storage](../topics/persistence-and-secure-storage.md)

<!-- preserved:article -->
## Scope

This chunk covers 25 persistence files for the encrypted LLM stores, operation journal and lease lifecycle, secure operands, and profile-owned calculation records. I read all assigned ranges across nine bounded pages: 5,391 lines and 47,244 measured `o200k_base` proxy tokens. This is static analysis only; I did not execute the application or tests.

## LLM cache, usage, telemetry, and consent history

`LLMCache` derives a key from the effective provider/model, system and user prompt, request controls, and image content addresses. It stores only the address of each image, not base64 image bytes. Encrypted secure objects partition records by the configured logical cache root. On read, the cache verifies that the decrypted entry derives the requested object key, preventing a valid but misfiled row from answering another request. It evicts old entries carrying redaction placeholders rather than replaying changed tax identifiers. On write, it applies DIAGNOSTIC redaction and skips persistence if redaction altered the model response, preserving the response that was actually returned to the caller. Age and count caps bound retention. Key derivation and cache read (`src/cadrumo/adapters/persistence/llm/cache.py`) Response redaction and write (`src/cadrumo/adapters/persistence/llm/cache.py`) Retention (`src/cadrumo/adapters/persistence/llm/cache.py`)

`UsageRecorder` persists response text and accounting fields after DIAGNOSTIC redaction in the encrypted store; it does not persist prompts or image payloads. Its read path checks that each decrypted record and saved random suffix reconstruct the actual secure-object key, then filters by date and sorts. Cost summaries preserve uncertainty: any unpriced row makes total estimated cost `None`, with a separate count of unpriced entries. The local run-telemetry store contains run ID, caller/provider/model, duration, success, error class, and start time, not prompt or response text; it uses the same logical-root partition and validates the reconstructed row key. Both diagnostic stores have age and count retention. Redacted usage writes (`src/cadrumo/adapters/persistence/llm/usage.py`) Usage identity check and summary (`src/cadrumo/adapters/persistence/llm/usage.py`) Local run telemetry (`src/cadrumo/adapters/persistence/llm/run_telemetry.py`) Telemetry key validation (`src/cadrumo/adapters/persistence/llm/run_telemetry.py`)

The evidence-consent ledger is treated differently from regenerable diagnostics. It records the evidence content address, resolved provider/model, acknowledgement surface, and time, but never the bytes, prompt, or response. The dispatch path must append successfully before it can proceed, and a missing active bucket or failed secure-object write refuses dispatch. There is no pruning path: other application flows use the complete history to find artefacts affected by consent withdrawal. Append-only consent history (`src/cadrumo/adapters/persistence/llm/consent_ledger.py`) Fail-closed append (`src/cadrumo/adapters/persistence/llm/consent_ledger.py`)

## Durable operation state

The filesystem operation journal stores a credential-free current snapshot alongside its ordered event history. Validation enforces stable operation identity, contiguous sequence numbers, nondecreasing timestamps, ordered revisions, terminal-event position, and agreement between snapshot and history tail. Repository methods provide bounded replay and inventory pages, read observations from one locked journal record, resolve idempotency claims under the same root lock, and commit only with the exact live lease. Settlement commits the terminal snapshot and clears its scope lease while holding that lock; a crash between its two file writes can leave a terminal record beside a stale lease, which the code says submission and reconciliation recover. History invariants (`src/cadrumo/adapters/persistence/operations/_journal_validation.py`) Bounded journal observations and inventory (`src/cadrumo/adapters/persistence/operations/journal.py`) Create and compare-and-swap commit (`src/cadrumo/adapters/persistence/operations/journal.py`) Terminal settlement (`src/cadrumo/adapters/persistence/operations/journal.py`)

The lease adapter stores one versioned record per conflict scope. It validates the scope and operation against both filename and payload, uses a shared exclusive lock with journal transitions, and distinguishes acquire, conflict, expiry, renewal/takeover, and lost ownership. Writes require the exact current lease and caller-supplied observation time; this keeps expiry decisions tied to a consistent operation clock. Durable operation operands are separate content-addressed secure objects: their namespace must be version 1, keyed by `{content_digest}`, use an allowed sensitivity, and require ciphertext at rest. `resolve` re-hashes payload bytes before strict model validation. Lease record and identity checks (`src/cadrumo/adapters/persistence/operations/lease.py`) Exact live-lease requirement (`src/cadrumo/adapters/persistence/operations/lease.py`) Lease state transitions (`src/cadrumo/adapters/persistence/operations/lease.py`) Secure operand boundary (`src/cadrumo/adapters/persistence/operations/secure_references.py`)

Financial-operand custody persists only a per-interaction checkpoint, not the amount buffer itself. It rejects path-shaped interaction IDs and uses lock-protected compare-and-swap transitions so two supervisors cannot settle the same wait from the same predecessor. However, its `open` and `advance` methods write JSON directly with `Path.write_text`, rather than the journal's atomic repository writer. A process or machine failure during an in-place write could leave an invalid checkpoint that restart reconciliation cannot parse; power-loss behavior was not exercised. Checkpoint path and state transitions (`src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`) Direct checkpoint writes (`src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`)

## Profile persistence and calculation history

Two shared persistence kernels handle distinct existing formats: bare strict-model JSON and an `Envelope` that duplicates classification, schema version, and timestamp inside the encrypted payload as well as in row metadata. The enveloped kernel checks both layers on load; both expose read revisions, prepare co-commit writes, and offer guarded mutation that retries only revision conflicts with a pure callback. This guards singleton updates against lost writes, but callers preparing a co-commit must carry the revision read; the low-level write API leaves the revision optional for callers that truly have no read predecessor. Envelope validation and revision reads (`src/cadrumo/adapters/persistence/profile/_secure_enveloped_document.py`) Optional revision on co-commit write (`src/cadrumo/adapters/persistence/profile/_secure_enveloped_document.py`) Guarded singleton mutation (`src/cadrumo/adapters/persistence/profile/_secure_model_document.py`)

Concrete adapters store authority-bearing profile state such as apoderado configuration, capital-goods registers, activity-asset history, and bucket-event history. They bind data to a profile bucket and registry-owned namespace, translate storage failures at the application boundary, and use revision guards for append operations where concurrent writes could otherwise silently drop entries. The calculation observation repository keeps official and pending-local layers separate, binds keys to modelo/year/period/member coordinates, and validates incoming observations against the pinned bundled registry revision and Modelo 303 carry rules. The IVA wallet adapter writes latest state and immutable history in one encrypted-store batch and rechecks registry coordinates when loading. These are value and audit stores; the bundled registry is the source for matching technical coordinates, while this review does not validate current law. Capital-register guarded add (`src/cadrumo/adapters/persistence/profile/bienes_inversion.py`) Append-only bucket history CAS (`src/cadrumo/adapters/persistence/profile/buckets.py`) Observation preparation and registry checks (`src/cadrumo/adapters/persistence/profile/calculation_observations.py`) Official/pending layer transitions (`src/cadrumo/adapters/persistence/profile/calculation_observations.py`) Atomic latest-state and history write (`src/cadrumo/adapters/persistence/profile/calculation_observations.py`)

The calculation-revision migration maps retired relation override keys onto current binding IDs using a frozen join plus the selected authority snapshot. It recomputes content-addressed revision IDs, leaves already-current entries unchanged, refuses unknown keys and conflicting many-to-one folds, and logs identifiers without taxpayer figure values. Both the direct migration and the prepared migration plan write through a compare-and-swap against the catalogue revision, so a concurrent calculation does not get overwritten by migration. Key classification and refusal (`src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`) Deterministic rekeying (`src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`) Revision-guarded persistence (`src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`)

## Assessment and limits

This chunk has strong identity and concurrency controls: cache, usage, and telemetry reads validate row/key correspondence; secure operands are content-addressed and re-hashed; singleton mutations use compare-and-swap; journal history and ownership are validated as one state machine; and consent-audit failure blocks the corresponding dispatch. The clearest durability question is the custody repository's in-place checkpoint writes. A second caller-facing invariant is that any manually composed singleton co-commit must supply the revision it read. Static review does not establish crash consistency on real filesystems, transaction behavior of the SQL backend, operator recovery usability, or that every caller follows the intended revision discipline. No tests were executed.

## Complete source coverage

All 25 assigned files were read in full; pages 1–9 covered every manifest line.

- persistence/__init__.py (22 lines) (`src/cadrumo/adapters/persistence/__init__.py`)
- llm/__init__.py (1 line) (`src/cadrumo/adapters/persistence/llm/__init__.py`)
- llm/cache.py (516 lines) (`src/cadrumo/adapters/persistence/llm/cache.py`)
- llm/consent_ledger.py (179 lines) (`src/cadrumo/adapters/persistence/llm/consent_ledger.py`)
- llm/run_telemetry.py (410 lines) (`src/cadrumo/adapters/persistence/llm/run_telemetry.py`)
- llm/usage.py (308 lines) (`src/cadrumo/adapters/persistence/llm/usage.py`)
- operations/__init__.py (3 lines) (`src/cadrumo/adapters/persistence/operations/__init__.py`)
- operations/_journal_validation.py (245 lines) (`src/cadrumo/adapters/persistence/operations/_journal_validation.py`)
- operations/financial_operand_custody.py (112 lines) (`src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`)
- operations/journal.py (475 lines) (`src/cadrumo/adapters/persistence/operations/journal.py`)
- operations/lease.py (358 lines) (`src/cadrumo/adapters/persistence/operations/lease.py`)
- operations/secure_references.py (154 lines) (`src/cadrumo/adapters/persistence/operations/secure_references.py`)
- profile/__init__.py (27 lines) (`src/cadrumo/adapters/persistence/profile/__init__.py`)
- profile/_filing_runtime.py (35 lines) (`src/cadrumo/adapters/persistence/profile/_filing_runtime.py`)
- profile/_review_package_keypair.py (91 lines) (`src/cadrumo/adapters/persistence/profile/_review_package_keypair.py`)
- profile/_revision_guarded_singleton_mutation.py (53 lines) (`src/cadrumo/adapters/persistence/profile/_revision_guarded_singleton_mutation.py`)
- profile/_secure_enveloped_document.py (295 lines) (`src/cadrumo/adapters/persistence/profile/_secure_enveloped_document.py`)
- profile/_secure_model_document.py (231 lines) (`src/cadrumo/adapters/persistence/profile/_secure_model_document.py`)
- profile/actividad_asset.py (112 lines) (`src/cadrumo/adapters/persistence/profile/actividad_asset.py`)
- profile/apoderado.py (140 lines) (`src/cadrumo/adapters/persistence/profile/apoderado.py`)
- profile/auth_diagnostics.py (81 lines) (`src/cadrumo/adapters/persistence/profile/auth_diagnostics.py`)
- profile/bienes_inversion.py (172 lines) (`src/cadrumo/adapters/persistence/profile/bienes_inversion.py`)
- profile/buckets.py (322 lines) (`src/cadrumo/adapters/persistence/profile/buckets.py`)
- profile/calculation_observations.py (596 lines) (`src/cadrumo/adapters/persistence/profile/calculation_observations.py`)
- profile/calculation_revision_override_migration.py (453 lines) (`src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py`)
<!-- /preserved:article -->
