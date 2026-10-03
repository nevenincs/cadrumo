# Filing projections, workflow state, and JSON output contracts

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-114` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 33 core modules totaling 4,726 lines, 198,158 bytes, and 47,175 measured proxy tokens. I read all nine bounded pages in the chunk plan, including the complete 1,273-line filing projection contract and 731-line JSON output contract. The report describes the checked-in snapshot only. I did not import application code, run the application or tests, contact Google or AEAT, or verify external tax rules and portal behavior.

## Filing references and workflow state

The largest module defines typed projection references for fields that recur in Spanish filing forms. Its closed variants preserve the distinct row shapes of M303, M390, M200, and M296: simplified-regime activity cohorts and modules, prorrata and differentiated-deduction activities, corporate entity/representative rows, and withholding payees, payments, and certificates. A reference identifies where an already-known fact belongs; it is not itself a tax calculation or proof that a form is currently accepted. M303 and M390 use explicit cohort and activity indices where the forms repeat rows, while M296 occurrence context avoids inventing a fixed slot for its repeated annex records. These distinctions reduce the chance that a valid value is copied into a similarly named field for the wrong form or party. Filing projection variants (`src/cadrumo/core/filing_projection_ref.py`) M200 and M296 reference shapes (`src/cadrumo/core/filing_projection_ref.py`) M296 annex shapes (`src/cadrumo/core/filing_projection_ref.py`)

The module also provides a compiler and hydrator for serialized references. Compilation accepts only expected primitive wire values, normalizes supported enum values, checks integer and string fields, and validates through the union of typed models; hydration routes input back through that compiler rather than trusting an arbitrary mapping. A helper returns a casilla identifier only for references that actually carry one. This gives downstream filing code one validated representation while retaining the fact that some destinations are row or party references rather than casillas. Compiler and hydrator (`src/cadrumo/core/filing_projection_ref.py`) Casilla extraction (`src/cadrumo/core/filing_projection_ref.py`) Projection support (`src/cadrumo/core/filing_projection_ref_support.py`)

Related small registries constrain filing years to a bounded range and give foreign-asset obligation groups and filing codes a closed vocabulary; the listed Modelo 720 asset classes do not include the distinct 721 virtual-currency category. The flow contract describes input widget types, unanswered/invalid/stale/deferred states, create-versus-modify modes, and whether checkpoints are available. Copy references are limited to locale, schema-field, and terminology concepts, so a copied UI answer is not represented as reusable legal authority. These files define shared identities and state semantics; actual flow execution and form eligibility belong to their consumers. Filing-year bounds (`src/cadrumo/core/filing_year.py`) Foreign-asset registry (`src/cadrumo/core/foreign_asset_obligation.py`) Flow statuses and modes (`src/cadrumo/core/flows.py`) Copy-reference kinds (`src/cadrumo/core/flows.py`)

## Output contracts, integrity, and shared data

`json_contract.py` supplies typed JSON envelopes for command results, notices, and resolved action references. It derives envelope status from notices, uses strict schema models and JSON round trips to catch values that cannot survive serialization, and validates registered results and emitted documents. Notice descriptions/context are prose channels, while executable follow-up is represented through typed action fields; the contract is designed to prevent raw command text from being smuggled in as an action. Error envelopes follow a separate validation path. The output helper redacts the whole captured envelope in its observability path, which avoids selectively logging taxpayer fields, at the cost of losing field-level diagnostic detail. These are boundary guarantees of this module; consumers still have to register and use the contract correctly. Notice and action models (`src/cadrumo/core/json_contract.py`) Notice model (`src/cadrumo/core/json_contract.py`) Strict round trip and schema (`src/cadrumo/core/json_contract.py`) Success emission and capture (`src/cadrumo/core/json_contract.py`) Registered-result validation (`src/cadrumo/core/json_contract.py`)

The shared hashing utilities establish canonical UTF-8 JSON encoding with deterministic key order, compact separators, finite-number requirements, rejection of duplicate JSON members and nonstandard constants, and size-bounded canonicalization. They also provide file/content SHA-256 digests; the shorter BLAKE2b value is documented as a discriminator rather than proof. A digest only detects change relative to a trusted expected value; it does not establish who produced the payload. `keyed_digest.py` derives purpose-labeled keys with HKDF-SHA256 and creates HMAC-SHA256 values, but callers remain responsible for key custody and choosing what bytes represent the semantic message. Canonical encoding and bounds (`src/cadrumo/core/hashing.py`) Strict JSON parsing hooks (`src/cadrumo/core/hashing.py`) Content and file hashing (`src/cadrumo/core/hashing.py`) Label-derived HMAC (`src/cadrumo/core/keyed_digest.py`)

Other reusable data contracts include defensive immutable mappings, best-effort parent-directory fsync after file updates, strict external JSON shape checks, declared ledger sort axes, and lower-case hexadecimal/identifier grammars. The IBAN helpers normalize only spaces and hyphens, require an ASCII-shaped canonical value, and independently guard the mod-97 operation against malformed input. The image sniffer recognizes only supported PNG/JPEG/GIF/WebP signatures; identity-verification results distinguish valid, invalid, and unknown so a transport failure need not become a negative identity finding. These utilities refuse ambiguous shapes rather than inferring missing semantics. Frozen mapping (`src/cadrumo/core/frozen_mapping.py`) Directory sync (`src/cadrumo/core/fsync.py`) IBAN normalization and check (`src/cadrumo/core/iban.py`) Image media type (`src/cadrumo/core/image_media_type.py`) Identity verdicts (`src/cadrumo/core/identity_check_verdict.py`)

## External service, hardware, and workbook boundaries

The Google-related modules are boundary helpers, not a Google Drive client. They distinguish desktop OAuth from service-account impersonation, escape Drive query literals, parse file/folder IDs from accepted reference forms, and extract HTTP status and quota markers from structured errors. This supports callers in choosing credential and retry behavior, but these functions do not perform OAuth, establish a user's Drive authorization, or verify that a referenced object is accessible. Credential-source kinds (`src/cadrumo/core/google_credential_source.py`) Drive reference parsing (`src/cadrumo/core/google_drive_reference.py`) Structured HTTP/quota extraction (`src/cadrumo/core/google_http_error.py`)

Hardware capability types distinguish a measured lack of accelerator (`NONE`) from an unknown measurement (`UNKNOWN`) and expose free-memory tiering. The module documents that execution decisions should use measured bytes rather than treating a broad tier as a reservation; peer-process contention is separately represented from resident runtime use and unreadable measurements. This makes unknown resource state expressible without silently turning it into evidence of absence. Accelerator and contention states (`src/cadrumo/core/hardware.py`) Memory tier selection (`src/cadrumo/core/hardware.py`)

The legacy workbook reader handles BIFF8/OLE2 `.xls` data. Since a typical reader exposes a formula cell's cached result without indicating that the cell contains a formula, this adapter walks BIFF records and marks formula coordinates with the same type marker used by the workbook policy. It validates record/worksheet structure and refuses formats it cannot represent. This preserves the caller's ability to reject spreadsheet formulas rather than trusting stale recalculated values. The coverage remains deliberately limited to the legacy format it parses. Legacy reader contract (`src/cadrumo/core/legacy_workbook.py`) Workbook and formula scan (`src/cadrumo/core/legacy_workbook.py`) Formula-cell marking (`src/cadrumo/core/legacy_workbook.py`)

## Security, provenance, and concurrency

IVA category resolution separates evidence outcomes, including table classification, unsupported relief, contradiction, and a declared `RATE_INFERRED` outcome. The local contract notes that the rate-inferred distinction is not persisted/surfaced, so a downstream consumer cannot always tell a table result from one inferred from a rate. IVA compensation provenance names five supplying paths; only an AEAT capture can carry the official expediente reference, while operator seed/correction and reconstructed or app-filing states do not acquire official status merely by being represented in the same enum. These vocabularies are useful trust labels, but their effect depends on consumers preserving and checking them. IVA outcomes (`src/cadrumo/core/iva_category_resolution.py`) Rate-inferred outcome (`src/cadrumo/core/iva_category_resolution.py`) Compensation provenance states (`src/cadrumo/core/iva_compensation_provenance.py`)

Two locking mechanisms have intentionally different ownership models. `exclusive_file_lock` uses an OS-level sidecar lock (POSIX `flock`, Windows one-byte `msvcrt.locking`), retains the sidecar after release to avoid a delete/recreate race, and carries no PID or stale-recovery metadata. Its async twin shares the lock primitive and deadline but awaits between attempts, so it yields to the event loop and closes the descriptor on cancellation. Timeout and backoff defaults are resolved from live settings, and invalid caller-supplied budgets are refused. POSIX locking is advisory, so every cooperating writer must acquire the same lock. One quality concern is that both platform-specific `_try_lock` implementations treat any `OSError` as contention; permission or descriptor failures can therefore be reported later as a timeout instead of their original cause. OS lock implementation and budgets (`src/cadrumo/core/locks.py`) Synchronous and async contexts (`src/cadrumo/core/locks.py`) Async cancellation behavior (`src/cadrumo/core/locks.py`)

`unlink_lockfile` serves a different, recoverable PID-lock protocol: releasing a lock held by this process retries transient Windows sharing violations to a deadline, whereas stale-lock reclamation and best-effort cleanup can make a single attempt and poll again. It does not report a blocked unlink as success; non-contention permission errors propagate. The source records a cross-process contention case where 3 of 4 contenders stranded a live-PID lockfile before the retry policy was introduced, describing the resulting wedge. This gives a concrete reason for separating reliable holder release from lossy stale reclamation. `link_safety.py` separately detects symlink/junction-like paths; whether callers apply that check before opening data is outside these helpers. Unlink retry contract (`src/cadrumo/core/lockfile_unlink.py`) Unlink implementation (`src/cadrumo/core/lockfile_unlink.py`) Link-like path detection (`src/cadrumo/core/link_safety.py`) Lock error type (`src/cadrumo/core/locks_errors.py`)

## Assessment and follow-up

The strongest local capabilities are precise typed filing destinations, validated JSON command boundaries, deterministic and bounded hash inputs, formula-aware `.xls` admission, and an explicit split between OS locking and recoverable application lockfiles. The best-supported limitations are that a typed reference or provenance enum does not prove external legal or portal correctness; inferred-rate provenance is not fully surfaced; Google helpers do not authorize access; and the lock acquisition loop can mask non-contention `OSError`s as ordinary contention. Assessment of actual export completeness requires tracing projection references into producer/registry consumers. Assessment of privacy requires checking which command surfaces capture JSON and how they render the envelope. Tests are not part of this chunk, and no runtime behavior was verified here.

## Complete assigned-file coverage

- filing_projection_ref.py (`src/cadrumo/core/filing_projection_ref.py`) — lines 1–1,273
- filing_projection_ref_support.py (`src/cadrumo/core/filing_projection_ref_support.py`) — lines 1–23
- filing_year.py (`src/cadrumo/core/filing_year.py`) — lines 1–38
- flows.py (`src/cadrumo/core/flows.py`) — lines 1–119
- foreign_asset_obligation.py (`src/cadrumo/core/foreign_asset_obligation.py`) — lines 1–86
- frozen_mapping.py (`src/cadrumo/core/frozen_mapping.py`) — lines 1–108
- fsync.py (`src/cadrumo/core/fsync.py`) — lines 1–58
- fts_query.py (`src/cadrumo/core/fts_query.py`) — lines 1–23
- google_credential_source.py (`src/cadrumo/core/google_credential_source.py`) — lines 1–48
- google_drive_query.py (`src/cadrumo/core/google_drive_query.py`) — lines 1–22
- google_drive_reference.py (`src/cadrumo/core/google_drive_reference.py`) — lines 1–67
- google_http_error.py (`src/cadrumo/core/google_http_error.py`) — lines 1–85
- hardware.py (`src/cadrumo/core/hardware.py`) — lines 1–150
- hashing.py (`src/cadrumo/core/hashing.py`) — lines 1–269
- hex.py (`src/cadrumo/core/hex.py`) — lines 1–120
- iban.py (`src/cadrumo/core/iban.py`) — lines 1–97
- identifier_grammar.py (`src/cadrumo/core/identifier_grammar.py`) — lines 1–41
- identity_check_verdict.py (`src/cadrumo/core/identity_check_verdict.py`) — lines 1–48
- image_media_type.py (`src/cadrumo/core/image_media_type.py`) — lines 1–77
- invoice_link.py (`src/cadrumo/core/invoice_link.py`) — lines 1–40
- irnr.py (`src/cadrumo/core/irnr.py`) — lines 1–75
- iva_category_resolution.py (`src/cadrumo/core/iva_category_resolution.py`) — lines 1–122
- iva_compensation_provenance.py (`src/cadrumo/core/iva_compensation_provenance.py`) — lines 1–66
- iva_deduction_fact.py (`src/cadrumo/core/iva_deduction_fact.py`) — lines 1–23
- json_contract.py (`src/cadrumo/core/json_contract.py`) — lines 1–731
- json_shapes.py (`src/cadrumo/core/json_shapes.py`) — lines 1–64
- keyed_digest.py (`src/cadrumo/core/keyed_digest.py`) — lines 1–81
- ledger_sort.py (`src/cadrumo/core/ledger_sort.py`) — lines 1–84
- legacy_workbook.py (`src/cadrumo/core/legacy_workbook.py`) — lines 1–212
- link_safety.py (`src/cadrumo/core/link_safety.py`) — lines 1–35
- lockfile_unlink.py (`src/cadrumo/core/lockfile_unlink.py`) — lines 1–100
- locks.py (`src/cadrumo/core/locks.py`) — lines 1–311
- locks_errors.py (`src/cadrumo/core/locks_errors.py`) — lines 1–30
<!-- /preserved:article -->
