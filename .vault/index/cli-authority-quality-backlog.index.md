---
generated: true
tags:
  - '#index'
  - '#cli-authority-quality-backlog'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:9b53e275484edaddfde794f057f6fc9b4d60ab8a1665be778fb448edd3eb0fbf'
related:
  - '[[2026-07-17-cli-authority-quality-backlog-adr]]'
  - '[[2026-07-17-cli-authority-quality-backlog-plan]]'
  - '[[2026-07-18-cli-authority-quality-backlog-adr]]'
  - '[[2026-07-18-cli-authority-quality-backlog-research]]'
  - '[[2026-07-22-cli-authority-quality-backlog-close-honesty-review-audit]]'
---

# `cli-authority-quality-backlog` feature index

Auto-generated index of all documents tagged with `#cli-authority-quality-backlog`.

## Documents

### adr

- `2026-07-17-cli-authority-quality-backlog-adr` - `cli-authority-quality-backlog` adr: `cli-authority-quality-backlog rescope grounding` | (**status:** `accepted`)
- `2026-07-18-cli-authority-quality-backlog-adr` - `cli-authority-quality-backlog` adr: `S27 clave-diagnostics namespace authority: storage registry is canonical` | (**status:** `accepted`)

### audit

- `2026-07-22-cli-authority-quality-backlog-close-honesty-review-audit` - `cli-authority-quality-backlog` audit: `Close honesty review`

### exec

- `2026-07-17-cli-authority-quality-backlog-P01-S01` - Make every accepted as_of argument participate in revision validity selection or reject it explicitly instead of silently ignoring it
- `2026-07-17-cli-authority-quality-backlog-P01-S02` - Reject an as_of argument on the unscoped registry discovery path with an instructive refusal naming the scoped form that honours it
- `2026-07-17-cli-authority-quality-backlog-P01-S03` - Prove historical as-of boundaries are honoured on the scoped path and refused explicitly on the unscoped path rather than silently ignored
- `2026-07-17-cli-authority-quality-backlog-P02-S04` - Add an AST recurrence gate that rejects new reducible production SHA-256 constructor and one-shot hexdigest bodies while allowing streaming, HMAC, HKDF, X509, and digest-byte uses
- `2026-07-17-cli-authority-quality-backlog-P02-S05` - Prove the recurrence gate rejects a new reducible one-shot body and accepts every legitimate cryptographic use it must not block
- `2026-07-17-cli-authority-quality-backlog-P03-S06` - Correct namespace registry metadata drift and make each namespace definition the sole authority for identifier, schema version, sensitivity, default object key, key grammar, owner, and custody
- `2026-07-17-cli-authority-quality-backlog-P03-S07` - Remove duplicate namespace, version, sensitivity, catalogue-key, and custody literals from transaction, invoice, modelo participation, and bucket persistence consumers and bind them to registry definitions
- `2026-07-17-cli-authority-quality-backlog-P04-S11` - Make filed observation persistence the sole owner of latest-record selection, deterministic history ordering, metadata enrollment, and calculation-observation writes and remove the duplicate selector and persistence loop from capture orchestration
- `2026-07-17-cli-authority-quality-backlog-P04-S12` - Introduce one typed filed-capture finalizer and failure accumulator used by single, bulk, and source capture with explicit fail-fast single and source policy and best-effort bulk policy
- `2026-07-17-cli-authority-quality-backlog-P04-S13` - Prove identical latest selection and history ordering across all capture routes, their distinct failure policies, and preservation of the separate strict IVA compensation persistence path
- `2026-07-17-cli-authority-quality-backlog-P05-S14` - Define typed LLM review requests, decisions, results, and mandatory invocation origins without an application-layer default CLI source command
- `2026-07-17-cli-authority-quality-backlog-P05-S15` - Implement one application review workflow for suggest, saturate, review, apply, reject, evidence no-split, and evidence split while composing existing canonical persistence primitives
- `2026-07-17-cli-authority-quality-backlog-P07-S20` - Decide the profile-create prompted-question inventory contract: fix the exact set and count of questions the wizard surfaces on the payload and record the rationale as an ADR-lite decision note in the plan
- `2026-07-17-cli-authority-quality-backlog-P07-S21` - Implement and assert the exact profile-create question count against the decided inventory so an added or dropped question fails the test loudly
- `2026-07-17-cli-authority-quality-backlog-P08-S22` - Give the acceptance-wall meta-test a per-worker unique temp root via tmp_path_factory so concurrent pytest workers no longer share a PID-keyed directory and race
- `2026-07-17-cli-authority-quality-backlog-P09-S23` - Audit the roughly forty select_revision callers and prove every production calculation, verification, filing, export, and projection path resolves through the law-determined canonical resolver and only asserts a stored revision_id equal, never injects it
- `2026-07-17-cli-authority-quality-backlog-P09-S24` - Assert binding validator-dispatch completeness: every BindingSourceKind member has a dispatch entry in the validator registry or a documented mesh-only deferral, so a new source kind cannot ship unvalidated
- `2026-07-17-cli-authority-quality-backlog-P11-S26` - Add a structural no-build/no-publish assertion to the publish-workflow guardrail test: denylist-scan every step run and uses in the validate job (or pin the full step allowlist) so a differently-spelled build or publish command cannot slip past the exact-substring guards, gated on the guardrail test failing if any validate-job step invokes a build or publish tool
- `2026-07-17-cli-authority-quality-backlog-P03-S08` - Remove duplicate namespace metadata from profile, calculation, aggregation, and filed-observation repositories and bind repository construction to registry definitions
- `2026-07-17-cli-authority-quality-backlog-P03-S10` - Replace literal-membership namespace checks with a non-vacuous production-root adoption gate that recognizes cadrumo-prefixed declarations, detects local metadata declarations, and proves each storage binding consumes the registered definition
- `2026-07-17-cli-authority-quality-backlog-P03-S27` - NEEDS ADJUDICATION and prerequisite for P03.S09: resolve the split namespace authority where clave-diagnostics namespace values are duplicated across core.external_constants (CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE, used by _clave_movil_support.py), a raw literal in _clave_permanente_support.py line 49 (no CLAVE_PERMANENTE core symbol, asymmetric), and the adapters storage registry (CLAVE_MOVIL and PERMANENTE_DIAGNOSTICS_NAMESPACE whose .namespace values are themselves raw literals duplicating core), plus raw classification SensitivityClass.SESSION and schema_version 1 at _clave_movil_page_flow.py lines 460-461 duplicating the registry namespace .sensitivity and .schema_version. Decide the single authority (core.external_constants versus the adapters storage registry) and whether registry values source from core, then single-source all consumers, gated on one authority with no duplicated namespace literal across core, registry, and consumer
- `2026-07-17-cli-authority-quality-backlog-P05-S16` - Route classify --auto-split and split --llm through the typed review workflow with distinct invocation origins and remove CLI-owned review branching and application source-command defaults
- `2026-07-17-cli-authority-quality-backlog-P05-S17` - Prove suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and CLI-route parity against real persistence and model subprocess boundaries
- `2026-07-17-cli-authority-quality-backlog-P06-S18` - GATED (blocked until the mcp-call-latency plan completes): make the MCP server direct dispatch path call gate_refusal() once so a refused call is not composed twice into the envelope
- `2026-07-17-cli-authority-quality-backlog-P06-S19` - GATED (blocked until the mcp-call-latency plan completes): add a per-verb CLI-versus-MCP schema-parity diff proving every operator verb exposes the same request and response schema across both surfaces
- `2026-07-17-cli-authority-quality-backlog-P10-S25` - Triage the two low-severity entrypoints structural duplications the duplication-authority audit surfaced (repeated iterator shapes and thin synchronous wrappers): confirm each on the current tree by exact declaration, caller, and writer-path inspection, then either record a disposition note classifying it as intentionally distinct incidental similarity or consolidate it behind one shared abstraction proven substitutable against every consumer contract, so no duplicated policy, state ownership, or persistence behavior survives unclassified
- `2026-07-17-cli-authority-quality-backlog-P03-S09` - DEFERRED pending (a) protected-browser S08 closure and (b) resolution of the namespace-authority-split adjudication in P03.S27: remove duplicate namespace and custody declarations from Clave, LLM cache and usage, bundle, attachment, and secure-storage consumers without conflating certificate custody with master-key keyring custody. The auth zone is the S08 quiescence surface and in active auth-cert churn, so editing clave and certificate lifecycle now risks colliding with or reopening behavioral work
- `2026-07-17-cli-authority-quality-backlog-P09-S28` - Measure the legitimate population of direct create_work_unit callers and then close the filing-year gap that the select_revision caller audit structurally could not see, because create_work_unit is not itself a select_revision caller and so fell outside that audit's denominator entirely. It validates a supplied revision_id only for existence and for period-token membership, never against the filing year, so create_work_unit for modelo 303 filing_year 2026 carrying revision_id 2023-y-siguientes succeeds silently and builds a 2026 work unit under the 2023 revision's norms even though that revision's compiled period selector is capped at year_to 2025 and the authority resolves those coordinates to 2026-y-siguientes. Production is safe today only because every production caller resolves through resolve_registry_revision_for_work_target first, so the exposure is a FUTURE caller that does not, and the starting hypothesis to DISPROVE is a static gate constraining production call sites rather than a runtime refusal at the shared door, because whether a revision_id was law-resolved or hand-supplied is not visible in the arguments at all and a runtime predicate therefore cannot discriminate a fixture seeding a work unit from a production path that resolved correctly. Roughly ninety modules call create_work_unit directly, so the population must be measured before the mechanism is chosen

### plan

- `2026-07-17-cli-authority-quality-backlog-plan` - `cli-authority-quality-backlog` plan

### research

- `2026-07-18-cli-authority-quality-backlog-research` - `cli-authority-quality-backlog` research: `S27 clave-diagnostics namespace authority grounding`
