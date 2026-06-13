---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-security-storage-audit-audit]]"
  - "[[2026-04-12-data-storage-research]]"
  - "[[2026-04-12-data-storage-adr]]"
  - "[[2026-04-17-path-handling-safety-review-audit]]"
  - "[[2026-04-17-session-persistence-review-audit]]"
  - "[[2026-04-21-run-trace-rolling-audit]]"
---



# `secure-persistence-foundation` research: `secure-persistence-foundation-research`

## Origin and scope

This research grounds the secure-persistence-foundation feature, the
authoritative universe of work tracked under PR #216. The feature absorbs the
remediation arc of the 2026-04-27 security storage audit and supersedes the
narrower bank-import-persistence framing originally scoped to issue #216. The
PR is long-lived; it accumulates wave-by-wave deliverables; per-wave merges
do not happen — the PR body is the rolling tracker.

The audit found that the project's persistence surface is fragmented across
roughly twenty-five domain-specific writers, no shared classification or
governance contract exists, sensitive secrets and session-bearing material
are persisted as plaintext in repo-local files, and the formal storage layer
in `src/aeat/storage` covers only three catalogue tables (`modelos`,
`portals`, `corpus_artifacts`). The decision question this research is
written to answer is: how does the project install one governed persistence
boundary, with safe-default extension semantics, that subsumes every domain
without breaking the existing CLI surface, the existing pydantic v2 contract,
or the existing Alembic discipline?

The standing data-storage ADR (2026-04-12) deliberately scoped the storage
layer narrow ("First-cut tables ... exactly the scope of issue #10") but
explicitly anticipated expansion ("Populating tables — handled by #6, #7,
#9, #17, #23"). Wave 1 of this feature continues that ADR's intent: the
persistence boundary already exists conceptually; this work generalises it
into the project-wide governed surface the prior ADR foreshadowed and the
audit found missing.

The feature's wave count is unbounded by design. Each wave is a full
vaultspec pipeline loop (research → ADR → plan → execute → review → audit
gate). Audit gates are blocking: no wave handover until every CRITICAL and
HIGH finding raised by the gate's `vaultspec-code-review` pass and Codex
security re-audit is exhausted. Findings roll forward into the next wave's
research artifact when not closeable in the current wave.

## Standards baseline

The audit anchors its severity assessments to four primary standards. This
research adopts the same anchors:

- OWASP Secrets Management Cheat Sheet — central, auditable, lifecycle-
  managed secret handling with least privilege.
- OWASP Logging Cheat Sheet — exclusion or sanitisation of session
  identifiers, access tokens, government identifiers, and payment-related
  data from log artifacts.
- OWASP Cryptographic Storage Cheat Sheet — minimisation of stored
  sensitive data, separation of secret material from ordinary state,
  restrictive permissions on configuration, avoidance of source-adjacent
  key material.
- NIST SP 800-111 (Guide to Storage Encryption Technologies) — at-rest
  protection appropriate to content sensitivity; SP 800-52r2 covers
  transport which is only partially in scope here.

The `cryptography` package (>=47.0.0) is already a direct project
dependency. Fernet (AES-128-CBC + HMAC-SHA256), AES-GCM, ChaCha20Poly1305,
PBKDF2, and scrypt are available without new dependencies. Argon2id,
SQLCipher, OS-keychain abstraction, and cross-platform file-locking
primitives are not currently pinned and would be new dependencies if
selected.

## Persistence-surface inventory (synthesis)

The project's persistence surface decomposes into the following domains.
Each domain entry lists its writer modules, on-disk roots (referenced by
their settings name where applicable), format, write semantics, sensitivity
class, and current redaction posture.

### Centralised SQL storage (the existing governed surface)

- Writers: `src/aeat/adapters/persistence/storage/engine.py`, `session.py`, `repository.py`,
  `migrations_api.py`, `_orm.py`, `records.py`.
- Root: `aeat_database_url` (default `sqlite:///<project>/var/aeat.db`).
- Format: SQLite via SQLAlchemy 2.x; Alembic migrations under
  `migrations/versions/`.
- Tables today: `modelos`, `portals`, `corpus_artifacts`.
- Sensitivity: identity / audit (catalogue metadata, no secret material).
- Pattern: pydantic v2 records on the public surface; ORM rows
  internal-only; repositories translate at every boundary.
- Tests: `_test_engine.py`, `_test_session.py`, `_test_repository.py`,
  `_test_migrations.py`, `_test_records.py`, `_test_constraints.py`.

### Secret material and session-bearing state (CRITICAL)

- Writers: `src/aeat/application/setup/_env_writer.py`, `src/aeat/entrypoints/cli/oauth.py`,
  `src/aeat/entrypoints/cli/auth/__init__.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- Roots: `env/.env` (KEY=VALUE plaintext including Cl@ve identity and
  Google resource IDs), `env/oauth-client.json` (OAuth client credentials,
  hardcoded `PROJECT_ROOT / "env"`), `env/service-account.json` (Google
  service-account credentials, hardcoded `PROJECT_ROOT / "env"`),
  `env/workspace-mcp-credentials`, `aeat_token_dir` (default `.tokens/`)
  containing `google_oauth_token.json` (OAuth access + refresh tokens),
  `<profile>-storage.json` (Playwright `storage_state`),
  `<profile>-storage.json.meta.json` (AEAT session metadata sidecar with
  identity NIF, certificate thumbprint, schema version, SHA-256, TTL).
- Format: KEY=VALUE plaintext, JSON, JSONL.
- Write semantics: env file rewritten in place preserving comments and
  ordering (`env_io.py`); tokens written via `path.write_text()`;
  storage-state captured by Playwright; metadata sidecars written
  atomically via `tempfile.NamedTemporaryFile(delete=False)` + capture.
- Hardening today: prior session-persistence audit landed Windows ACL
  hardening via `icacls.exe` and POSIX `chmod 0o600`; eager invalidation
  on probe failure; SHA-256-keyed integrity gates; certificate-thumbprint
  binding; idempotent browser teardown.
- Gap: the data-at-rest is plaintext on disk regardless of OS-level ACL.
  Workstation-backup leak, accidental commit, or support-bundle capture
  exposes reusable authentication material.

### Financial / accounting state (CRITICAL)

- Writers: `src/aeat/domain/financial/transactions/_service.py`,
  `src/aeat/domain/financial/invoices/_service.py`,
  `src/aeat/domain/financial/usage_ratios/_service.py`,
  `src/aeat/domain/financial/attachments/_store.py`.
- Roots: `aeat_financial_txs_dir` (transactions catalogue JSON),
  `aeat_invoices_dir` (invoice catalogue JSON, NOT path-normalised),
  `aeat_usage_ratios_path`, `aeat_attachments_dir` (NOT path-normalised;
  contains content-addressable blob store under `blobs/{sha256}` and
  manifest JSON under `manifests/{sha256}.json`).
- Format: JSON for catalogues, opaque binary for attachment blobs, JSON
  manifests.
- Write semantics: atomic write via `tempfile.NamedTemporaryFile` +
  `os.replace()` (transactions); content-addressable write-once for
  blobs; mutable rewrite for manifests as link state evolves.
- Sensitivity: financial / identity-bearing.
- Gap: no encryption, no classification, no retention policy. Two of the
  three roots not covered by repo-relative path normalisation.

### Filing / submission / amendment / justificante state (CRITICAL)

- Writers: `src/aeat/entrypoints/cli/filing/__init__.py`,
  `src/aeat/entrypoints/cli/review/__init__.py`,
  `src/aeat/application/filing/_complementaria.py`,
  `src/aeat/adapters/outbound/aeat/export/_engine.py`,
  `src/aeat/adapters/outbound/aeat/export/_audit.py`,
  `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py`.
- Roots: `aeat_drafts_dir`, `aeat_submissions_dir`,
  `aeat_filing_history_dir`, `aeat_justificantes_dir`,
  `aeat_submission_browser_trace_dir`, plus the hard-coded
  `.aeat/live-submit-audit.log` (HIGH: outside any configured root,
  contains taxpayer NIF, draft checksum, justificante CSV identifier,
  submission URL, environment state, process arguments).
- Format: JSON for draft / submission / amendment records; PDF for
  justificantes; JSONL for live-submit audit; binary trace zips and
  screenshots for browser captures.
- Sensitivity: identity-bearing, audit-class for submission records;
  CRITICAL for live-submit audit content.

### Workflow / sync / observability (HIGH)

- Writers: `src/aeat/application/workflow/_persistence.py`,
  `src/aeat/application/sync/_repository.py`,
  `src/aeat/core/observability/_store.py`, `_sink.py`, `_context.py`,
  `_fingerprint.py`, `_replay.py`.
- Roots: `aeat_workflow_runs_dir`, `aeat_sync_divergence_file_dir`,
  `aeat_runs_dir` (per-run subdirectories with `trace.json` and
  `events.jsonl`; NOT covered by repo-relative path normalisation but
  protected by a regex check on `run_id` shape inside
  `observability/_store.py`).
- Format: JSON for workflow / divergence records, JSON for run trace,
  JSONL for run events.
- Write semantics: atomic JSON write, append-only JSONL with flush +
  fsync after every emit. Argument redaction is denylist-substring,
  name-side only — does not catch values that resemble secrets but bear
  innocuous keys.
- Hardening today: prior run-trace audit closed all blocking findings —
  contextvar binding order, timezone-aware datetimes, replay-mode
  marker, ASCII-safe ellipsis, drift-evasion hash inclusion of
  `env/.env` bytes.

### Caches and corpora (MEDIUM)

- Writers: `src/aeat/adapters/outbound/llm/_cache.py`, `src/aeat/adapters/outbound/llm/_usage.py`,
  `src/aeat/domain/schema/_fetch.py`, `src/aeat/domain/schema/_cache.py`,
  `src/aeat/status/_cache.py`, `src/aeat/domain/manuals/_fetch.py`,
  `src/aeat/domain/manuals/_loader.py`, `src/aeat/domain/normatives/_loader.py`,
  `src/aeat/domain/casillas/catalogue.py`, `src/aeat/inbox/`.
- Roots: `aeat_llm_cache_dir`, `aeat_llm_usage_dir`,
  `aeat_schema_cache_dir`, `aeat_status_cache_dir`,
  `aeat_manuals_root`, `aeat_normatives_root`, `aeat_casillas_root`,
  `aeat_inbox_dir`, `aeat_inbox_pdf_dir`.
- Format: JSON for response and schema cache, JSONL daily-rotated for
  LLM usage, PDFs and JSON for fetched corpus material.
- Sensitivity: cache (LLM responses may contain echoed-back NIFs and
  account fragments — operationally sensitive even though nominally
  cache-class), corpus (public reference material, low sensitivity).

### Connectors and exports (MEDIUM)

- Writers: `src/aeat/entrypoints/cli/bootstrap.py`, `src/aeat/entrypoints/cli/drive.py`,
  `src/aeat/entrypoints/cli/docs.py`, `src/aeat/entrypoints/cli/sheets.py`,
  `src/aeat/entrypoints/mcp/launch_google_workspace.py`, `src/aeat/entrypoints/cli/sede/`,
  `scratch/` family (sede-discovery, clave-diag, recon-* outputs from
  ad-hoc diagnostic CLIs).
- Format: heterogeneous (PDF, PNG, HTML, JSON, ZIP, depending on
  capture tool).
- Sensitivity: variable — `scratch/clave-diag` may include URL fragments
  with session tokens, screenshots may capture identity-bearing form
  state.

### Path-normalisation coverage gap

Twenty-five settings are funnelled through `_normalize_repo_relative_paths`
in `src/aeat/config.py`. Three are skipped:
`aeat_invoices_dir` (financial invoices), `aeat_attachments_dir` (financial
attachment blob store), and `aeat_runs_dir` (observability run capture).
The audit grades this MEDIUM-HIGH because path normalisation is one of the
few defence-in-depth controls keeping local writes inside expected roots.
The fix is mechanical (add three names to the validator tuple) and is the
canonical Wave-1 Phase-0 quick-win.

## Threat model and sensitivity classes

The substrate must serve at least the following content classes, each with
its own retention, redaction, and at-rest treatment:

- secret — long-lived authentication material (OAuth client secret,
  service-account private key, certificate passphrase, refresh tokens).
  Threat: workstation backup, accidental commit, support-bundle capture.
  Treatment target: ciphertext at rest with key separated from ciphertext;
  never logged; never echoed; deletion verifiable.
- session — short-lived bearer state (Playwright `storage_state`, OAuth
  access token cache, AEAT session sidecars). Threat: replay; lifetime
  longer than necessary increases blast radius. Treatment target:
  ciphertext at rest with TTL enforced at read; integrity-bound to
  the providing factor (certificate thumbprint, NIF).
- identity — taxpayer- and operator-linked records (NIF, full name,
  contact email, business profile, bank-account fragments). Threat:
  re-identification on leak; regulatory exposure (GDPR / Spanish LOPD).
  Treatment target: ciphertext at rest where the field is not needed for
  query; audit log on every read; never logged at INFO or above.
- financial — bank transaction rows, invoice records, attachment binary
  blobs, usage ratios, draft and submission payloads, amendment
  records. Threat: re-identification, financial fraud, regulatory
  exposure. Treatment target: ciphertext at rest by default; redaction
  rules for log echo; retention policy aligned to fiscal year + statute
  of limitations.
- audit — submission audit log, run trace, divergence record, workflow
  run record. Threat: leak of identity / session / secret context the
  audit captured. Treatment target: redaction at write time (NIF →
  hashed, URL → host-only, token → fingerprint), ciphertext at rest for
  the underlying record, retention policy aligned to compliance
  obligations.
- cache — LLM response cache, schema cache, status cache, manuals,
  normatives, casillas, BOE PDFs. Threat: low for public reference data;
  medium for LLM cache where responses may echo identity-bearing input.
  Treatment target: plaintext is acceptable for public corpora;
  identity-bearing cache (LLM) treated as identity-class.
- operational — env-file configuration, settings, build manifests.
  Threat: low for literal values; high if the file silently accumulates
  secret-class material (the audit's CRITICAL is precisely this drift).
  Treatment target: split — secret-class material moves to the secret
  store; operational-class settings remain in plaintext config.
- diagnostic — `scratch/` outputs, browser traces, screenshots, network
  captures. Threat: routinely exfiltrates identity, session, and audit
  context as collateral. Treatment target: governed retention default
  (e.g. seven-day TTL); explicit redaction; opt-in capture; sanitised
  on write; never enabled by default in non-developer environments.

## Tech-stack survey for the substrate

The substrate must compose along three axes — secret store, at-rest
crypto for tabular records, at-rest crypto for opaque blobs — plus a
governance layer (classification, retention, redaction, schema/version)
and a path-governance fix.

### Secret store

The audit specifies "dedicated secret store or OS-backed secure storage
boundary" without prescribing a mechanism. Three credible candidates:

- OS keychain via the `keyring` package (Windows Credential Manager,
  macOS Keychain, Linux Secret Service via libsecret). Strength:
  per-OS native confidentiality boundary, no key management problem,
  zero-prompt for the operator. Weakness: requires `keyring` and on
  Linux `secretstorage`+`jeepney` runtime dependencies; CI / headless
  execution requires a backend shim; portability across container
  runtimes is fragile; cross-platform behaviour requires explicit
  testing per backend.
- Passphrase-derived KEK + encrypted secret file. The operator provides
  a passphrase once per session (or via OS keychain bootstrap); the
  KEK is derived via Argon2id (preferred) or scrypt (already in
  `cryptography`); each secret is wrapped with AES-GCM or ChaCha20-Poly1305
  per-record. Strength: portable, deterministic, testable, no
  platform-specific code. Weakness: introduces a passphrase prompt /
  cache; passphrase loss is unrecoverable; argon2-cffi is a new
  dependency unless we accept scrypt.
- Hybrid — OS keychain stores the long-lived KEK; secrets remain in an
  encrypted file. Strength: combines the keychain's confidentiality
  boundary with the file's portability; KEK rotation is bounded.
  Weakness: now both code paths must work on every supported OS.

The favoured direction for the ADR phase is the hybrid pattern: OS
keychain when available (operator UX), encrypted-file fallback with a
passphrase-derived KEK when the keychain is unavailable (CI, headless,
disabled keychain). Both backends speak the same `SecretStore` protocol
on the public surface.

### At-rest crypto for tabular records

Three credible patterns:

- SQLCipher (whole-database encryption, transparent to SQLAlchemy via a
  custom dialect). Strength: every byte at rest is ciphertext; trivial
  for the consumer. Weakness: requires a non-stdlib SQLite build
  (`pysqlcipher3` or vendored binary); friction on Windows; no
  per-column granularity.
- Column-level encryption via SQLAlchemy `TypeDecorator`. Strength:
  granular — only sensitive columns pay the encryption cost; works on
  stock SQLite; auditable per-field. Weakness: query-by-encrypted-value
  becomes infeasible (deterministic encryption is rejected because of
  ECB-equivalent leakage); developer must mark sensitive columns
  explicitly.
- Application-level envelope on the pydantic record — encrypt the
  whole record body, store ciphertext in a single column, keep
  searchable fields plaintext. Strength: minimal SQL surface impact.
  Weakness: gives up SQL search semantics on most fields.

The favoured direction is column-level encryption with a small set of
sensitive `TypeDecorator`s plus searchable plaintext metadata columns
where queries need them. SQLCipher is rejected for now on portability
grounds; a future ADR may revisit.

### At-rest crypto for opaque blobs

The financial attachments store and the schema-cache PDF cache hold
opaque material today. Two patterns:

- Encrypted blob store: blobs written as ciphertext; manifest carries
  the (per-blob) data-encryption key wrapped with the substrate's
  master key. Read path decrypts at access.
- Hybrid sensitivity: public-corpus blobs (manuals, normatives, BOE
  PDFs) remain plaintext; identity-bearing blobs (operator
  attachments) are ciphertext. Sensitivity class drives the path.

The favoured direction is the hybrid: classification at write time
selects whether the blob is encrypted; manifest carries the
classification and (when applicable) the wrapped DEK.

### Schema / version contract for file-backed domains

The data-storage ADR adopted Alembic for SQL schema. File-backed
domains today evolve via the natural pydantic-v2 strict-validation
boundary — incompatible payloads raise on load — but no explicit version
field, no formal migration routine, no compatibility matrix. The
substrate must give file-backed domains the same evolution discipline.
A modest `EnvelopeV1` shape with `schema_version`, `payload`, and
`written_at` (plus optional ciphertext metadata) is sufficient; per-
domain migrators consume the version field on load. Pure-pydantic
existing payloads can adopt the envelope by wrapping; a one-shot
migration reads the legacy form and writes the envelope form.

### Cross-platform file locking

Two domains (transaction-catalogue write, secret-store update) need
exclusive write locks on opening. Stdlib `fcntl` (POSIX) and `msvcrt`
(Windows) cover the bases without a new dependency. `portalocker` and
`filelock` are alternatives with cleaner APIs but introduce a
runtime dependency. The favoured direction is a small in-tree lock
helper using stdlib only.

### Audit-sink redesign

`.aeat/live-submit-audit.log` is the highest-immediate-leverage
HIGH finding. The fix is structural — the audit sink relocates under
the governed substrate (`aeat_audit_dir`, normalised), the schema is
explicit (envelope + redacted payload), and the writer participates in
the substrate's classification and retention contract. Existing log
file is migrated forward by the canary consumer in Wave 2 (or
documented as out-of-scope for Wave 1 if it adds unrelated risk).

## Wave roadmap (initial; expands as audits roll forward)

The roadmap below is the initial decomposition. The audit gate at the end
of each wave can extend or split waves; the PR body always carries the
current roadmap.

- Wave 1 — substrate, no domain migration. Deliver the governed
  persistence boundary (the `aeat.persistence` public surface or
  generalisation of `aeat.adapters.persistence.storage`), the classification and retention
  contract, the secret store with two backends (OS keychain + encrypted-
  file fallback), the at-rest crypto primitives (column-level
  `TypeDecorator` set; envelope helper for file-backed domains), the
  cross-platform file-lock helper, the schema-version envelope helper,
  the path-normalisation fix for the three skipped settings, and the new
  error codes registered in `aeat.core.errors._registry`. Substrate ships with
  exhaustive unit + integration tests. No domain consumer is migrated.
  The audit gate's output extends Wave 2 or opens new waves.
- Wave 2 — secret canary consumer. Migrate `env/oauth-client.json`,
  `env/service-account.json`, OAuth token cache, and (where compatible)
  Playwright `storage_state` from plaintext to the secret store. Audit-
  sink relocation may co-deliver here if scope permits.
- Wave 3 — financial domain. Bring transactions, invoices, attachments,
  usage ratios under the governed boundary. Issue #216's
  bank-import-persistence Kent moment lands here as the demonstration
  consumer.
- Wave 4 — filing / submission / amendment / justificante. Includes
  the live-submit audit relocation if not co-delivered in Wave 2.
- Wave 5 — observability and audit redaction discipline. Run-trace and
  workflow records pass through redaction rules at write time; browser
  traces and screenshots inherit explicit retention defaults.
- Wave 6 — caches and corpora. LLM cache (identity-class) migrates to
  ciphertext; public corpora remain plaintext under the governed
  boundary.
- Wave 7 — connector and export governance. Approved roots, retention
  defaults, sanitisation rules for Drive, Docs, Sheets, sede captures,
  and `scratch/`.

The wave count is not bounded. Findings discovered by audit gates that
are not closeable in the current wave open new waves. The PR body
reflects the live state.

## Decisions deferred to the Wave-1 ADR phase

The ADR resolves at minimum:

- The public name and import path of the substrate (`aeat.persistence`
  as a new subpackage that absorbs `aeat.adapters.persistence.storage`, or extension of
  `aeat.adapters.persistence.storage` itself; the practical difference is the migration
  burden on existing callers vs the conceptual cleanliness of a new
  name).
- Final selection between keyring-only, file-fallback-only, and hybrid
  for the secret store; the dependency footprint that adds.
- Final selection between column-level `TypeDecorator` and envelope
  encryption for sensitive SQL columns.
- Whether the schema-version envelope wraps existing pydantic payloads
  or replaces them.
- Whether Argon2id (new dependency: `argon2-cffi`) is mandatory for the
  passphrase KEK or scrypt (no new dependency) is sufficient.
- Whether file locking uses stdlib helpers or `portalocker`.
- The error-code identifiers and stable runbook IDs registered for
  every new error class introduced by the substrate.
- The CLI surface for operator-facing secret-store operations (`aeat
  secrets list`, `aeat secrets put`, `aeat secrets rm`, `aeat secrets
  rotate`) — required for the canary consumer in Wave 2.
- The redaction rule set adopted by the audit-sink redesign and how it
  composes with the existing argument-redaction in the run-trace path.

## References to live code

The persistence-surface inventory above and its sensitivity assignments
were derived from a code-research sweep of the modules listed under each
domain heading. The standing data-storage ADR fixes SQLAlchemy 2.x +
Alembic as the SQL discipline, and that decision is preserved here. The
prior path-handling, session-persistence, auth-protocol, live-sync
backend, and run-trace audits resolved their original-scope findings and
are treated as floor — Wave 1 must not regress any of them.

## Open audit-finding inventory at the start of Wave 1

The below findings are the live work queue at Wave 1 entry. Each is
referenced by the 2026-04-27 security audit's labelling.

- CRIT-1 — plaintext secret and credential persistence in `env/`,
  `.tokens/`, OAuth and service-account JSON, browser `storage_state`.
  Expected resolution: substrate (Wave 1) + canary migration (Wave 2).
- CRIT-2 — broad plaintext financial / filing / session / observability
  persistence without classification or unified protection. Expected
  resolution: substrate (Wave 1) + per-domain migrations (Waves 3..6).
- HIGH-1 — narrow centralised storage; most domains bypass it. Expected
  resolution: substrate (Wave 1) generalises the contract; per-domain
  consumers migrate in subsequent waves.
- HIGH-2 — `.aeat/live-submit-audit.log` outside configured roots, plus
  high-risk observability artifacts. Expected resolution: substrate
  (Wave 1) provides the governed audit sink; relocation in Wave 2 or
  Wave 4.
- HIGH-3 — profile / config CLI surfaces persist identity to plaintext.
  Expected resolution: substrate (Wave 1) provides the secret store
  and identity-class container; setup CLI migration in Wave 2.
- MED-HIGH path-normalisation drift on three settings. Expected
  resolution: Wave 1 Phase 0 quick-fix.
- MED schema-evolution fragmentation. Expected resolution: substrate
  (Wave 1) ships the schema-version envelope; per-domain adoption in
  Waves 3..7.
- MED connector / export uncontrolled writes. Expected resolution:
  Wave 7.
- LOW-MED `AEAT_LIVE_SUBMIT_ENABLED` documentation drift. Expected
  resolution: opportunistic Wave-1 cleanup if the env-file substrate
  touches the example file; otherwise deferred.

The audit gate at end-of-Wave-1 is responsible for verifying every
HIGH finding tagged "Wave 1 substrate" is structurally addressed and
for raising any new finding the substrate work introduces. The next
ADR document is the immediate downstream consumer of this research.
