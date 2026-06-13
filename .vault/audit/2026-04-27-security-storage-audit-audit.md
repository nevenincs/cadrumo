---
tags:
  - '#audit'
  - '#security-storage-audit'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-12-data-storage-research]]"
  - "[[2026-04-17-path-handling-safety-review-audit]]"
  - "[[2026-04-17-session-persistence-review-audit]]"
  - "[[2026-04-18-auth-protocol-review-audit]]"
  - "[[2026-04-21-live-sync-backend-code-review-audit]]"
  - "[[2026-04-21-run-trace-rolling-audit]]"
---



# `security-storage-audit` audit: security-storage-posture

## Scope

This audit covers persisted local state, secret handling, session persistence,
financial data storage, connector side effects, local cache and export
surfaces, and path governance on current `main`.

The audited surfaces include:

- the formal storage layer in `src/aeat/storage`
- repo-configured roots under `var/`, `.tokens`, `env/`, and `.aeat/`
- profile and configuration CLI flows, including `aeat auth configure`
  and persisted `AutonomoProfile` data
- financial ingest, review, draft, submission, justificante, workflow,
  sync, observability, schema, manuals, inbox, and LLM persistence
- Google, AEAT, BOE, manual, and financial-provider connector flows that
  augment local state
- scratch, temp, trace, and operator-selected export paths that create
  secondary sensitive artifacts

Direct answer to the architecture question:

Future implementers cannot currently securely and easily extend centralized
persisted data structures. The repository does have a formal persistence
boundary, but it is narrow, it does not govern most operational domains, and
it does not provide one shared path for data classification, secret handling,
path governance, retention, redaction, and schema evolution.

## Standards baseline

Modern expectations are not met for secret handling or protected local state.

OWASP Secrets Management guidance expects secrets to be centralized,
standardized, lifecycle-managed, auditable, and protected with least
privilege and TLS in transit. This codebase instead persists live credentials,
tokens, and session-bearing state as repo-local plaintext files across
`env/`, `.tokens`, and browser persistence outputs.

OWASP Logging guidance expects session identifiers, access tokens, government
identifiers, and payment-related data to be excluded from logs or transformed
through sanitization, hashing, masking, or encryption. Persisted audit, debug,
trace, and submission-adjacent artifacts still retain identity-bearing and
session-adjacent data in readable form.

OWASP Cryptographic Storage guidance expects minimization of sensitive stored
data, separation of secrets from ordinary data, restrictive permissions on
config files, and avoidance of source-adjacent key material. Current practice
keeps secrets, session state, and business records close to ordinary repo-local
state without systematic encryption or one uniform permissions model.

NIST transport guidance such as SP 800-52 Rev. 2 is only partially relevant
here because some connection-security controls exist. The primary gap is at
rest. NIST at-rest expectations such as SP 800-111 and SC-28 are not met
because sensitive local data lacks consistent storage encryption and
authenticated protection appropriate to its content and threat model.

## Physical storage map

Important physical roots and their current contents:

- `var/aeat.db`
  central SQLite database for the narrow `src/aeat/storage` layer only
- `.tokens`
  plaintext OAuth token cache, AEAT `storage_state` JSON, and `.meta.json`
  sidecars for certificate and Cl@ve providers
- `env/.env`
  mutable plaintext operator and runtime configuration, including Cl@ve
  identity data and Google resource IDs
- `env/oauth-client.json`
  plaintext OAuth client credentials
- `env/service-account.json`
  plaintext Google service-account credentials
- `env/workspace-mcp-credentials`
  local connector credential cache for workspace MCP usage
- `var/financial/transactions`
  normalized transaction catalogue JSON
- `var/financial/invoices`
  invoice JSON records
- `var/financial/attachments`
  attachment blob store and JSON manifests
- `var/financial/usage-ratios.json`
  configurable financial profile and business classification ratios
- `var/drafts`
  filing draft JSON, approval state, and taxpayer-linked draft data
- `var/submissions`
  submission JSON, amendments, and amendment-result records
- `var/justificantes`
  justificante PDFs and parsed justificante-related downstream records
- `var/filing-history`
  historical filing state and optional archived detail-page HTML
- `var/workflow-runs`
  workflow result JSON
- `var/runs`
  observability `trace.json` and `events.jsonl`
- `var/browser-traces`
  browser screenshots, trace zips, and form/debug artifacts
- `var/divergences`
  sync divergence JSON repository
- `var/inbox` and `var/inbox/pdfs`
  imported inbound document state
- `var/status-cache`
  cached remote AEAT status state
- `var/schema-cache`
  BOE PDFs and extracted schema JSON
- `var/llm-cache`
  cached LLM responses
- `var/llm-usage`
  daily LLM usage JSONL
- `corpus/manuals`
  fetched AEAT manual PDFs, manifests, and structured extracted JSON
- `corpus/casillas`
  canonical casilla catalogue JSON
- `corpus/normatives`
  normative JSON corpus
- `.aeat/live-submit-audit.log`
  hard-coded live submission audit JSONL outside configured roots
- `scratch/sede-discovery`
  AEAT justificante capture PDFs and discovery reports
- `scratch/clave-diag`
  Cl@ve diagnostic HTML, PNG, and URL artifacts
- `scratch/recon-*`
  authenticated page dumps, screenshots, and network-debug artifacts
- `.cache/l1_anchors`
  cached public PDF anchor artifacts
- `var/exports` and operator-selected output paths
  fixed-width BOE exports, Drive downloads, and other ad hoc output files
- OS temp directories
  transient `.tmp`, `.part`, `NamedTemporaryFile`, and `TemporaryDirectory`
  writes used by multiple persistence modules

## Storage domains and owning modules

Centralized storage:

- `src/aeat/adapters/persistence/storage/_orm.py`, `repository.py`, `engine.py`, `session.py`,
  `migrations_api.py`
  own the formal DB-backed layer for `modelos`, `portals`, and
  `corpus_artifacts`

Financial and accounting state:

- `src/aeat/domain/financial/transactions/_service.py`
  stores `transactions.json`
- `src/aeat/domain/financial/invoices/_service.py`
  stores `invoices.json` and can also rewrite linked transaction state
- `src/aeat/domain/financial/usage_ratios/_service.py`
  stores usage-ratio JSON
- `src/aeat/domain/financial/attachments/_store.py`
  stores raw blobs and manifest JSON

Profile, config, and identity state:

- `src/aeat/env_io.py`
  reads and rewrites flat `KEY=VALUE` env files
- `src/aeat/application/setup/_env_writer.py`
  writes `env/.env` and persisted `AutonomoProfile` JSON
- `src/aeat/entrypoints/cli/oauth.py`
  copies OAuth client JSON and updates `env/.env`
- `src/aeat/entrypoints/cli/auth/__init__.py`
  copies OAuth and service-account JSON, rewrites `env/.env`, and manages
  auth-path selection
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`
  persists `google_oauth_token.json`
- `src/aeat/entrypoints/cli/auth/_paths.py`, `src/aeat/entrypoints/cli/auth/_session.py`
  define, read, and delete persisted session files
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
  persist AEAT browser session state and metadata sidecars

Filing and submission state:

- `src/aeat/entrypoints/cli/filing/__init__.py`
  writes drafts and imported submission-linked records
- `src/aeat/entrypoints/cli/review/__init__.py`
  rewrites draft approval state
- `src/aeat/application/filing/_complementaria.py`
  writes amendments and reads original draft state
- `src/aeat/adapters/outbound/aeat/export/_engine.py`
  writes submission and amendment-result JSON
- `src/aeat/adapters/outbound/aeat/export/_audit.py`
  appends live-submit audit JSONL

Workflow, sync, and observability:

- `src/aeat/application/workflow/_persistence.py`
  writes workflow result JSON
- `src/aeat/application/sync/_repository.py`
  writes divergence JSON
- `src/aeat/core/observability/_store.py`,
  `src/aeat/core/observability/_sink.py`,
  `src/aeat/core/observability/_context.py`
  write `trace.json` and `events.jsonl`

Reference, schema, and corpus state:

- `src/aeat/domain/casillas/catalogue.py`
  writes canonical casilla JSON and temp draft JSON
- `src/aeat/domain/manuals/_fetch.py`
  writes fetched manual PDFs and manifests
- `src/aeat/domain/manuals/_loader.py`
  reads structured extracted manual JSON
- `src/aeat/domain/normatives/_loader.py`
  reads normative JSON corpus
- `src/aeat/domain/schema/_fetch.py`
  caches BOE PDFs
- `src/aeat/domain/schema/_cache.py`
  caches extracted schema JSON

LLM state:

- `src/aeat/adapters/outbound/llm/_cache.py`
  stores cached completion JSON
- `src/aeat/adapters/outbound/llm/_usage.py`
  stores daily usage JSONL

## Connector, export, and local-state augmentation map

Google and Workspace connectors:

- `src/aeat/entrypoints/cli/bootstrap.py`
  creates or inspects Drive, Sheet, and Doc resources and writes resulting IDs
  into `env/.env`
- `src/aeat/entrypoints/cli/drive.py`
  downloads remote Drive content into operator-chosen local paths and uploads
  local files to Drive
- `src/aeat/entrypoints/cli/docs.py`
  mutates remote Docs state without local persistence of the document body
- `src/aeat/entrypoints/cli/sheets.py`
  mutates remote Sheets state without a local sheet cache
- `src/aeat/entrypoints/mcp/launch_google_workspace.py`
  provisions and uses `env/workspace-mcp-credentials`

AEAT connectors and local augmentation:

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`
  captures AEAT browser sessions into `storage_state` JSON and sidecars
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
  captures Cl@ve-backed session state and diagnostics
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/_walker.py`
  walks authenticated AEAT state and yields justificante captures
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/_notifications.py`
  fetches remote AEAT notification state
- `src/aeat/entrypoints/cli/sede/__init__.py`
  persists fetched justificante PDFs and discovery reports
- `src/aeat/application/workflow/_engine.py`
  augments local workflow state from AEAT notifications and expedientes
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py`
  writes browser trace artifacts during live submission
- `src/aeat/adapters/outbound/aeat/export/_engine.py`
  turns remote submission responses into local submission records

BOE and manual connectors:

- `src/aeat/domain/schema/_fetch.py`
  fetches or reads BOE PDFs and caches them locally
- `src/aeat/domain/schema/_cache.py`
  persists extracted schema JSON
- `src/aeat/domain/manuals/_fetch.py`
  downloads AEAT manual PDFs and writes manifests

Financial import connectors:

- `src/aeat/domain/financial/providers/_csv.py`
  parses CSV and TXT statements
- `src/aeat/domain/financial/providers/_xlsx.py`
  parses XLSX statements
- `src/aeat/domain/financial/providers/_ofx.py`
  parses OFX and QFX statements
- `src/aeat/domain/financial/providers/_pdf_n26.py`
  parses N26 PDFs
- `src/aeat/entrypoints/cli/financial/txs.py`
  persists normalized imported state into `transactions.json`
- `src/aeat/entrypoints/cli/financial/ingest.py`
  emits parsed provider transactions as NDJSON or JSON to stdout

LLM-backed augmentation:

- `src/aeat/adapters/outbound/llm/_client.py`
  reads cache, calls remote provider APIs, and writes cache and usage records
- `src/aeat/entrypoints/cli/financial/txs.py`
  writes LLM-derived classification back into the transaction catalogue

## Findings

### Critical: plaintext repo-local secret and credential persistence

The highest-risk issue is widespread plaintext persistence of credentials and
session-bearing material in repo-local, human-readable files. This includes
`env/.env`, `env/oauth-client.json`, `env/service-account.json`,
`.tokens/google_oauth_token.json`, persisted browser `storage_state` JSON, and
provider or session sidecars.

This design fails the basic expectation that secrets, tokens, cookies, and
client credentials should be centrally governed and separated from ordinary
operational data. A local compromise, accidental commit, workstation backup
leak, or support bundle capture can expose reusable authentication material.
The problem is systemic rather than isolated because multiple CLI and
connector surfaces write directly to file-backed plaintext stores.

### Critical: broad plaintext persistence of sensitive financial, identity,
and session-adjacent business records

Sensitive operational state is stored across JSON, JSONL, PDF, SQLite,
browser-state JSON, attachments, traces, and debug artifacts without a single
protection boundary or classification model. The affected domains include
transactions, invoices, usage ratios, drafts, submissions, amendments,
amendment results, justificantes, workflow runs, run traces, divergence
outputs, inbox documents, LLM cache and usage, and browser/session artifacts.

The risk is not only confidentiality loss. Because these records are spread
across heterogeneous file formats and roots, there is no consistent integrity
control, no unified retention policy, and no single extension point where
future implementers can inherit safe defaults.

### High: centralized persistence exists but does not govern the evolving
business domains

The formal storage package is currently limited to `modelos`, `portals`, and
`corpus_artifacts`. Most business state bypasses it entirely. As a result, the
system has no single persistence contract for financial records, filing state,
submissions, workflow state, audit artifacts, or session material.

This is the core reason future implementers cannot securely and easily extend
centralized persisted data structures. They can add new local persistence
quickly, but they do so without inheriting schema migration, versioning rules,
data classification, access control boundaries, redaction policy, or path
governance. The architecture therefore encourages drift instead of safe
extension.

### High: audit, log, and debug artifacts persist sensitive submission and
session context outside controlled roots

`.aeat/live-submit-audit.log` is outside the configured storage roots and
records taxpayer NIF, draft checksum, justificante CSV, submission URL,
environment state, and process arguments. Browser traces, screenshots,
network captures, and trace zips also create high-risk observability artifacts
that can expose sensitive submission context, session state, and operator
behavior.

This directly conflicts with modern logging guidance. Auditability is
necessary, but current persistence captures too much sensitive context and
does so in uncontrolled locations.

### High: profile and config CLI surfaces write identity and financial profile
state directly to plaintext local files

Profile and configuration flows are materially in scope. `aeat auth
configure` writes Cl@ve identity values into `env/.env`. The default
`AutonomoProfile` JSON persists financial or user profile state directly.
Browser authentication and AEAT automation also persist `storage_state` plus
sidecar metadata.

This means operators do not merely hold secrets locally; they also accumulate
identity-linked business configuration and session state in easy-to-read
files. The ambiguity of the term `profile` increases operational risk because
browser profile state, user financial profile state, and `profile_tax_id`
references are semantically different but all persistence-adjacent.

### Medium-High: path-governance drift weakens containment guarantees

Physical-path governance is inconsistent because `aeat_invoices_dir`,
`aeat_attachments_dir`, and `aeat_runs_dir` are omitted from
`_normalize_repo_relative_paths`. That drift matters because path
normalization is one of the few available controls for keeping local writes
inside expected roots.

When some storage surfaces are normalized and others are not, future code
cannot reliably assume consistent containment, portability, or auditability.
This increases the chance of silent writes to unintended locations and makes
later hardening more difficult.

### Medium: schema and version evolution are fragmented by domain

Alembic governs only the narrow database-backed storage layer. Drafts,
sidecars, schema cache, rulesets, declaration parsers, and other file-backed
domains evolve independently or without a formal version contract.

This fragmentation increases the long-term cost of safe extension. New
persisted data structures do not have one migration model, one compatibility
policy, or one rollback story. It also makes forensic interpretation and
incident response harder because storage semantics are dispersed across
domain-specific code.

### Medium: connector and export surfaces allow uncontrolled local writes

Google connectors, remote fetch and export paths, manual BOE fetches,
financial imports, and operator-chosen downloads can write to user-selected
locations or `scratch/` with limited retention, sanitization, or naming
policy. This broadens the effective storage surface well beyond the nominal
repo roots.

The consequence is that even if core roots were hardened later, sensitive
derived artifacts could still escape into unmanaged locations through export
and debug workflows.

### Low-Medium: configuration documentation drift around
`AEAT_LIVE_SUBMIT_ENABLED`

`env/.env.example` contains contradictory guidance around
`AEAT_LIVE_SUBMIT_ENABLED`. This is lower severity than the storage flaws
above, but it still matters because ambiguous operator guidance around live
submission can produce unsafe runtime assumptions and inconsistent audit
expectations.

## Recommendations

Overall assessment:

The codebase does not currently have a secure, centralized persisted-data
model. It has a narrow centralized database layer surrounded by a much larger
file-backed persistence surface for secrets, sessions, financial records,
filing state, caches, and observability artifacts. That mismatch is the main
architectural problem.

Implementers cannot currently extend centralized persisted data structures
securely and easily because the shared extension point is incomplete. To make
extension safe, the project needs one governed persistence strategy that
covers business data, session data, secrets, audit artifacts, path
normalization, schema evolution, and retention and redaction rules.

Prioritized remediation plan:

1. Remove plaintext secret and session persistence from repo-local ordinary
   files. Move credentials, tokens, and browser session state to a dedicated
   secret store or OS-backed secure storage boundary, and stop treating
   `env/.env`, credential JSON, token JSON, and `storage_state` JSON as
   acceptable long-term secret stores.
2. Establish a formal data-classification model for persisted state. At
   minimum separate secrets, session state, identity-bearing records,
   financial records, observability artifacts, and low-sensitivity cache data,
   then assign required controls for each class.
3. Expand the centralized persistence architecture beyond `modelos`,
   `portals`, and `corpus_artifacts`. New operational domains should only
   persist through a governed API that enforces location, schema and
   versioning, retention, and redaction rules by default.
4. Eliminate or redesign high-risk audit and debug persistence. Replace
   `.aeat/live-submit-audit.log` with a governed audit sink inside configured
   roots, remove direct capture of NIFs, URLs, tokens, and session-adjacent
   fields unless strictly required, and define explicit redaction rules for
   traces and screenshots.
5. Bring profile and config CLI surfaces under the same governance model.
   `aeat auth configure`, `AutonomoProfile` persistence, and browser and
   session setup should write through the same classified storage boundary
   instead of directly to plaintext config files.
6. Fix path-governance drift immediately. Include `aeat_invoices_dir`,
   `aeat_attachments_dir`, and `aeat_runs_dir` in repo-relative normalization
   and enforce consistent storage-root validation for all configured write
   locations.
7. Define one schema and versioning contract for all persisted domains.
   File-backed domains need explicit version fields, migration routines,
   compatibility rules, and deprecation handling comparable to the existing
   Alembic discipline.
8. Constrain export and connector write behavior. Require approved roots,
   retention defaults, and sanitization for downloads, manual fetches,
   `scratch/` outputs, and remote-export surfaces.
9. Correct `AEAT_LIVE_SUBMIT_ENABLED` documentation drift so operator guidance
   matches actual runtime behavior and security expectations.
10. After the architectural controls above exist, migrate existing
    high-sensitivity stores first: secrets and tokens, browser session state,
    live-submit audit logs, submission artifacts, and financial records."}}
