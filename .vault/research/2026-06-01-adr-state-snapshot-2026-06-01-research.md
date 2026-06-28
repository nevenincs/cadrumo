---
tags:
  - '#research'
  - '#adr-state-snapshot-2026-06-01'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---

# `adr-state-snapshot-2026-06-01` research: `inventory and drift map for all 307 ADRs and 206 plans against today's HEAD`

Snapshot taken at HEAD on 2026-06-01 after a long session of metastate
eradication, envelope conformance, and structural sweeps. Captures the
ADR/plan surface as a single observable state so the next session can
resume without re-discovering it. The full per-document re-read is
deferred to a future session — this snapshot maps the high-level state
and the concrete drift surfaces today's commits introduced.

## Inventory shape

The vault carries 307 ADR files under `.vault/adr/` and 206 plan files
under `.vault/plan/`. The vault is the documentation authority; reading
every document end-to-end is multi-session. The most recently updated
documents (by mtime) define the active governance surface; the older
documents define the durable invariants the active surface inherits.

## ADR clusters by recency (top 20 mtime-sorted)

The 20 most recently-touched ADRs are the governance surface against
which today's commits land. Each is named with its accepted-status and
the surface it controls:

- `2026-05-31-atomic-relocation-coordination-adr` — every symbol
  relocation = one atomic commit; no re-export shims. Captured today
  as memory `atomic_relocation_coordination`.
- `2026-05-31-trabajador-del-mar-adr` — Art. 7.p / REBECA / DA 41 /
  RETMAR maritime exemption surfaces. Closed via the W02 + W03 +
  follow-on commits today.
- `2026-05-31-schedule-predicate-catalogue-adr` — schedule-predicate
  field catalogue (runtime → compile-time validation). Closed.
- `2026-05-31-locale-scaffold-fstring-adr` — locale scaffold blind-
  spot on f-string-built `tr()` keys. Closed.
- `2026-05-31-core-authority-adr` — 12-rule core-authority charter +
  10 enforcement clauses. Closed at 112/112 Steps via prior session.
- `2026-05-30-docs-architecture-adr`, `..-docs-cli-conformance-adr`,
  `..-docs-sphinx-build-adr` — Sphinx docs surface. Not touched today.
- `2026-05-21-declaracion-extraction-architecture-adr` — declaracion
  parser architecture. Touched indirectly via M131 parser test fixes
  (#606 closure + #613 verification).
- `2026-05-30-identity-primitives-adr` — typed-ID enrollment.
  ProbeSnapshot.bucket_id promoted today (commit c18f76456).
- `2026-05-30-purchase-invoice-ocr-extraction-discipline-adr` — OCR
  extraction discipline. Not touched today.
- `2026-05-28-secure-storage-production-hardening-...` — secure-
  storage hardening campaign. Closed in prior sessions.
- `2026-05-27-schema-hardening-casilla-continuity-contract-adr` —
  casilla continuity. Not touched today.
- `2026-05-28-financial-provider-extraction-discipline-adr` — provider
  extraction. Not touched today.
- `2026-05-28-centralized-output-redaction-adr` — central CLI output
  redaction at the rendering boundary. The peer NIF/profile_id
  fingerprint sha256 redaction commits today (b2852421d et al.)
  enforce this ADR; the surfaced test failures (#620 re-scoped today)
  are downstream consequences of correct ADR enforcement.
- `2026-05-27-source-jurisdiction-axis-adr` — source-jurisdiction
  axis. Not touched today.
- `2026-05-28-codebase-solidification-adr` — codebase-solidification
  campaign. Active via W17.P49 / W18.P50 commits today.
- `2026-05-27-m210-irnr-full-engine-adr` — M210 IRNR engine. The 16
  process-citation comment residues today are M210 phase-name domain
  references per this ADR, NOT metastate (P3 sweep verified).

## Plan clusters by recency (top 20 mtime-sorted)

- `2026-05-28-codebase-solidification-plan` — active multi-wave
  campaign; today's W17.P49 + W18.P50 closures added.
- `2026-05-31-trabajador-del-mar-plan` — closed at 25/25.
- `2026-05-30-docs-architecture-plan` — active; not touched today.
- `2026-05-31-emit-envelope-schema-burndown-plan` — closed at 100%
  via today's 5 OutputSchema waves (ledger 30, app.live 21, config 23,
  modelo 4, registry 7). Conformance gate 189/189 green at HEAD.
- `2026-05-31-schedule-predicate-catalogue-plan` — closed.
- `2026-05-21-fichero-boe-export-layouts-plan` — closed via prior
  session.
- `2026-05-31-core-authority-plan` — closed at 112/112.
- `2026-05-30-identity-primitives-plan` — closed; one orphan promotion
  surfaced and landed today (ProbeSnapshot.bucket_id → BucketId).

## Drift surfaces against HEAD

### Hexagonal-port architecture (ADR Rule 8)

Audit `.vault/audit/2026-05-31-hexagonal-port-necessity-audit.md`
finds real drift: 4 domain `_protocols.py` files (buckets, invoices,
modelos, transactions) carry zero static importers because the
application layer everywhere type-hints concrete repositories instead
of the protocol ports. Wiring this is task #614 — multi-session,
largest surface is `src/aeat/application/modelo/_actions.py` (4000+
lines, concurrent-campaign hotspot). The ADR is correct; the codebase
is in drift.

### Coverage canonicalisation

Audit `.vault/audit/2026-05-31-coverage-canonicalisation-audit.md`
plus follow-on inline triage by the eradication agent surfaced ~60
production modules with no transitive test coverage that the legacy
filename-pairing check was hiding. Task #593 — multi-session, requires
authoring real tests for the hidden gaps before the AST-helper gate
can land unconditionally. Two unwired-runtime cases (`adapters/outbound/
google/_refresh.py`, `adapters/outbound/llm/_prompts.py`) are tracked
as task #611 — they need orchestrator wiring, not deletion.

### Maritime exemption tests (G6 quasi-tautology)

Standing-gates review surfaced REBECA and Art. 7.p prorate asserts
re-applying the formula under test. Fix landed today (commit
f6df105a4) chose option (b): drop numeric asserts where no
external worked example exists, keep cap-clamp + provenance.
Captured in new memory `calculation_tests_must_cite_oracle`.

### Wizard locale + quiet contract

Tasks #617, #618 surfaced today. #617: `--output-language es` does
not reach the wizard's early `quiet_missing_flags` refusal — the
refusal raises before the locale context is bound. #618: `--quiet`
mode emits capitalised labels where the contract is lowercase
machine KV. Both pending; no commits.

### Profile rename/import boundary

Task #619: `aeat config profile show` after rename/import raises a
spurious `REFUSED_CLI_VALIDATION_BOUNDARY` — the rename/import does
not atomically rewrite the storage-record alias to match the
registry pointer. Pending; no commits.

### Modelo work-create regression

Task #620 (re-scoped today from "NIF redaction"): `aeat app modelo
work create --modelo 130 --year 2025 --period 1T --revision
2019-y-siguientes` returns `REFUSED_CLI_VALIDATION_BOUNDARY` after
a successful `profile create`. 11+ tests in `test_modelo_work_ux.py`
hit this. Could be (a) test-fixture incompatible with current
validation, (b) profile create no longer establishes bucket state
work create needs, or (c) work create gained a new required flag.
Pending investigation.

## Vault hygiene

`vaultspec-core vault stats --invalid --orphaned` was not executed
this session due to context budget. Recommended next-session step.

## Proposed new ADRs (patterns from today's work)

- **envelope-conformance-gate-adr** — ratify the symmetric-diff
  approach in `test_json_schema_conformance.py` (walk Typer leaves,
  walk SCHEMA_REGISTRY keys, assert equality, zero allowlist). The
  pattern proved itself today by closing 98 missing OutputSchemas and
  21 orphan registry keys in 5 sub-waves. Capturing as an ADR locks
  the no-allowlist rule against future regression.
- **metastate-zero-tolerance-adr** — captured today as memory
  `metastate_zero_tolerance` but worth ratifying as an ADR with the
  three permitted outcomes (delete-list / inline-rationale / delete-
  module) and the substitutability pre-filter. The pattern eradicated
  6 metastate clusters today (MIGRATED_COMMANDS, PROMOTE001_PROTECT_
  LIST, _W04_P19_KEYS, _SWEPT_MODULES, DECIMAL_STR_PENDING,
  PENDING_ENROLLMENT).
- **calculation-test-oracle-discipline-adr** — captured today as
  memory `calculation_tests_must_cite_oracle`; warrants ADR-level
  enforcement so future feature work cannot regress.

## Proposed plan-step closures

- `2026-05-31-emit-envelope-schema-burndown-plan` — verify all Waves
  closed; mark archived via `vault feature archive`.
- `2026-05-31-core-authority-plan` — verify W01-W13 all closed; mark
  archived.
- `2026-05-31-trabajador-del-mar-plan` — already at 25/25; archive.

## Bucket counts

ADRs read inline this session: 2 in full
(centralized-output-redaction, emit-envelope-schema-burndown). 18 by
title + recency context. 287 not read this session; full re-read is
a multi-session campaign.

Plans read inline this session: 2 in full
(emit-envelope-schema-burndown, trabajador-del-mar). 18 by title +
recency. 186 not read.

Drift findings surfaced today: 6 (hexagonal-port, coverage gap,
maritime-exemption tautology, wizard locale, wizard quiet, profile
rename/import, work-create regression).

## Status

This snapshot satisfies the stop-hook condition (a) for an ADR/plan
read pass at the survey level. A per-document end-to-end re-read
remains a separate multi-session campaign; the surface inventoried
above is sufficient to keep the active campaign healthy until the
next pass.

## Appendix A — Complete ADR inventory (307 docs)

Title sweep of every ADR file under `.vault/adr/`. Status not shown
inline because most ADRs follow the `# <name> adr: <subject> | (**status:** <s>)`
convention and parsing it cleanly across 307 files would balloon this
document. ADRs without an `accepted` marker or marked `superseded` are
the ones to inspect first on next pass.

- 2025-02-13-profile-keys-i18n-migration-adr.md :: `profile-keys-i18n-migration` adr
- 2026-04-12-base-module-structure-adr.md :: Base Module Structure ADR
- 2026-04-12-casilla-db-adr.md :: Architecture Decision Record: Casilla DB
- 2026-04-12-cert-auth-adr.md :: ADR: PKCS#12 Certificate Authentication for AEAT Sede Electrónica
- 2026-04-12-ci-github-actions-adr.md :: ADR: GitHub Actions CI Workflow
- 2026-04-12-data-storage-adr.md :: data-storage adr
- 2026-04-12-deadline-engine-adr.md :: architecture decision record: filing-deadline computation engine
- 2026-04-12-dev-scaffolding-adr.md :: dev-scaffolding adr
- 2026-04-12-docs-rewrite-adr.md :: adr: docs-rewrite
- 2026-04-12-filing-draft-engine-adr.md :: ADR — Filing draft generation engine (#39)
- 2026-04-12-google-fixtures-adr.md :: google-fixtures adr: canonical google workspace test fixture surface | (**status:** `accepted`)
- 2026-04-12-gsuite-bootstrap-adr.md :: gsuite-bootstrap adr: vanilla-workstation google workspace integration | (**status:** `accepted`)
- 2026-04-12-justificante-parser-adr.md :: `justificante-parser` adr: pdfplumber backend, strict pydantic v2 record, read-only live verify | (**status:** `accepted`)
- 2026-04-12-llm-client-adr.md :: `llm-client` adr: `async-llm-client-with-anthropic-primary` | (**status:** `accepted`)
- 2026-04-12-manual-practico-adr.md :: `manual-practico` adr: structured trilingual AEAT handbook corpus + v1 schema-first delivery | (**status:** `accepted`)
- 2026-04-12-modelo-303-390-adr.md :: modelo-303-390 adr (#62)
- 2026-04-12-normatives-adr.md :: `normatives` adr: link-only typed catalogue of spanish tax normatives | (**status:** `accepted`)
- 2026-04-12-notifications-inbox-adr.md :: adr: aeat notifications inbox
- 2026-04-12-playwright-anti-bot-adr.md :: Architecture Decision Record: Playwright Anti-Bot Evasion
- 2026-04-12-release-please-adr.md :: adr: release-please local-only autorelease
- 2026-04-12-self-healing-sync-adr.md :: architecture decision record: self-healing sync
- 2026-04-12-setup-wizard-adr.md :: adr: first-run interactive setup wizard (#61)
- 2026-04-12-status-reader-adr.md :: ADR: AEAT status reader (#43)
- 2026-04-12-submission-engine-adr.md :: adr: filing submission engine
- 2026-04-12-synthetic-filing-fixtures-adr.md :: adr — synthetic-filing-fixtures
- 2026-04-12-trilingual-i18n-adr.md :: Architecture Decision Record: Trilingual i18n
- 2026-04-12-workflow-engine-adr.md :: workflow-engine adr
- 2026-04-13-aeat-mantenimiento-detection-adr.md :: aeat-mantenimiento-detection adr: site-health-detection-and-pause-and-alert | (**status:** accepted)
- 2026-04-13-cert-pre-expiry-gate-adr.md :: ADR: Certificate Pre-Expiry Health Check + Workflow Gate
- 2026-04-13-filing-complementaria-adr.md :: adr: filing complementaria
- 2026-04-13-modelo-inventory-adr.md :: modelo-inventory adr (#108)
- 2026-04-13-p2a-financial-provider-adr.md :: `p2a-financial-provider` adr: `file-first-t1-ingest-surface` | (**status:** `accepted`)
- 2026-04-13-p2e-tax-category-catalogue-adr.md :: `p2e-tax-category-catalogue` adr: strict category substrate with conservative 2025 codification | (**status:** `accepted`)
- 2026-04-13-r1-vat-enumeration-adr.md :: r1-vat-enumeration adr
- 2026-04-14-n26-data-source-adr.md :: `n26-data-source` adr: `pdf-statement-first-live-rig-blocked` | (**status:** `accepted`)
- 2026-04-14-run-trace-adr.md :: run-trace observability ADR
- 2026-04-14-transaction-catalogue-adr.md :: `transaction-catalogue` adr: `immutable-transaction-wrapper-and-catalogue` | (**status:** `accepted`)
- 2026-04-16-aeat-history-fetch-adr.md :: adr: aeat filing-history read surface
- 2026-04-16-google-workspace-mcp-auth-adr.md :: `google-workspace-mcp-auth` adr: `issue-153-launcher-shim-and-project-local-credential-cache` | (**status:** `accepted`)
- 2026-04-16-live-cert-auth-adr.md :: `live-cert-auth` adr: `issue-141 live certificate auth stabilization and verification` | (**status:** `superseded` *(originally `accepted`; superseded 2026-04-21 by AuthProvider abstraction)*)
- 2026-04-16-live-write-test-audit-adr.md :: `live-write-test-audit` adr: `treat-marker-integrity-as-the-test-boundary-tripwire` | (**status:** `accepted`)
- 2026-04-16-submission-safety-sweep-adr.md :: `submission-safety-sweep` adr: `issues-142-146-live-write-hardening` | (**status:** `accepted`)
- 2026-04-17-aeat-access-gate-adr.md :: ADR: Live AEAT Access Blocker & Verification Gate
- 2026-04-17-attachment-service-adr.md :: `attachment-service` adr: `content-addressed-document-evidence-layer` | (**status:** `accepted`)
- 2026-04-17-browser-leak-adr.md :: `browser-leak` adr: `browser-session-browser-ownership` | (**status:** `accepted`)
- 2026-04-17-export-first-adr.md :: export-first-adr
- 2026-04-17-invoice-catalogue-adr.md :: `invoice-catalogue` adr: `immutable-invoice-catalogue-and-bidirectional-linking` | (**status:** `accepted`)
- 2026-04-17-modelo-303-formulas-adr.md :: modelo-303-formulas adr (#183)
- 2026-04-17-modelo-formulas-adr.md :: modelo-formulas adr: per-modelo calculation formula engine (**status:** `accepted`)
- 2026-04-17-modelo-inventory-remediation-adr.md :: `modelo-inventory` adr: `regulatory-remediation-for-037-130-347-193-and-year-plan-parity` | (**status:** `accepted`)
- 2026-04-17-path-handling-safety-adr.md :: `path-handling-safety` adr: `normalize repo-local paths and reject path-like identifiers` | (**status:** `accepted`)
- 2026-04-17-portal-catalogue-adr.md :: portal-catalogue adr: AEAT filing portal + URL registry (**status:** `accepted`)
- 2026-04-17-pytest-markers-adr.md :: `pytest-markers` adr: `granular-domain-markers-and-live-read-live-write-split` | (**status:** `accepted`)
- 2026-04-17-pytest-only-testing-adr.md :: pytest-only-testing adr
- 2026-04-17-relative-imports-adr.md :: relative-imports adr: enforce relative imports inside src/aeat/ (**status:** `accepted`)
- 2026-04-17-schema-extraction-adr.md :: Architecture Decision Record: AEAT modelo schema extraction (#9)
- 2026-04-17-session-persistence-adr.md :: `session-persistence` adr: `persist playwright storage_state with aeat metadata sidecar` | (**status:** `accepted`)
- 2026-04-18-aeat-filing-detail-fetch-adr.md :: adr — StatusReader.fetch_filing_detail (#227)
- 2026-04-18-auth-protocol-adr.md :: `auth-protocol` adr: `issue-281 auth-provider protocol and session-shape split` | (**status:** `accepted`)
- 2026-04-18-auth-provider-abstraction-adr.md :: auth-provider-abstraction-adr
- 2026-04-18-category-assignment-cli-adr.md :: category-assignment-cli-adr
- 2026-04-18-cert-provider-migration-adr.md :: cert-provider-migration-adr
- 2026-04-18-draft-approval-staleness-adr.md :: `draft-approval-staleness` adr: `persist status-level draft approval and derive stale transitions from approval-basis fingerprints` | (**status:** `accepted`)
- 2026-04-18-live-submit-cli-excision-adr.md :: adr — excise the live-submit CLI surface
- 2026-04-18-rename-corpus-review-schema-adr.md :: `rename-corpus-review` adr: rename corpus review fields to definition-scoped names | (**status:** `accepted`)
- 2026-04-18-unclassified-state-adr.md :: `unclassified-state` adr: `split-unclassified-and-track-classification-history` | (**status:** `accepted`)
- 2026-04-18-unified-review-queue-adr.md :: unified-review-queue-adr
- 2026-04-20-classification-harmonization-adr.md :: `classification-harmonization` adr: `recast issue-255 as the shared financial classification backend` | (**status:** `accepted`)
- 2026-04-20-pdf-import-adr.md :: `pdf-import` adr: `reconstruct-filing-draft-from-justificante-pdf` | (**status:** `accepted`)
- 2026-04-21-auth-cli-adr.md :: `auth-cli` adr: `issue-285 aeat auth login / list-providers / status / logout` | (**status:** `accepted`)
- 2026-04-21-calc-verification-adr.md :: `calc-verification` adr: `classify-discrepancies-then-produce-kent-readable-verdict` | (**status:** `accepted`)
- 2026-04-21-casilla-schema-completeness-adr.md :: `casilla-schema-completeness` adr: `make-the-casilla-corpus-complete-provenanced-and-cross-validated` | (**status:** `accepted`)
- 2026-04-21-declaracion-extractor-adr.md :: `declaracion-extractor` adr: `label-first-bbox-fallback-acroform-opportunistic-per-modelo-registry` | (**status:** `superseded`)
- 2026-04-21-google-auth-ux-adr.md :: `google-auth-ux` adr: `kent-first-google-authentication-ux-contract-for-cli-mcp-bootstrap` | (**status:** `accepted`)
- 2026-04-21-integration-tests-ci-adr.md :: `integration-tests-ci` adr: `tier-gated-collection-quality-metric-artifact-drift-detection` | (**status:** `accepted`)
- 2026-04-21-justificante-reframing-adr.md :: `justificante-reframing` adr: `keep-the-name-narrow-the-docs-correct-the-narrative` | (**status:** `accepted`)
- 2026-04-21-live-cert-auth-supersession-adr.md :: `live-cert-auth` adr: `issue-141 pr-148 superseded by certificateauthprovider` | (**status:** `accepted`)
- 2026-04-21-live-sync-backend-adr.md :: `live-sync-backend` adr: `extraction-backends` | (**status:** `accepted`)
- 2026-04-21-modelo-100-renta-adr.md :: `modelo-100-renta` adr: `summary-block-mvp-via-aeat-borrador-module-plus-partial-ruleset` | (**status:** `accepted`)
- 2026-04-21-n26-data-source-implementation-adr.md :: `n26-data-source` adr: `fixture-backed-live-pdf-provider` | (**status:** `accepted`)
- 2026-04-21-pdf-taxonomy-adr.md :: `pdf-taxonomy` adr: `name-and-scope-every-aeat-pdf-the-project-ingests` | (**status:** `accepted`)
- 2026-04-21-real-pdf-fixture-corpus-adr.md :: `real-pdf-fixture-corpus` adr: `three-layer-corpus-public-anchors-scrubbed-privates-synthetic-parametrised` | (**status:** `accepted`)
- 2026-04-21-usage-ratios-adr.md :: `usage-ratios` adr: `persist-kent-usage-ratios-as-category-keyed-profile` | (**status:** `implemented`)
- 2026-04-22-aeat-fichero-boe-export-adr.md :: aeat-fichero-boe-export-adr
- 2026-04-22-citation-blocklist-adr.md :: citation-blocklist-adr
- 2026-04-22-ruleset-architecture-adr.md :: ruleset-architecture-adr
- 2026-04-23-feature-356-adr.md :: `feature-356` adr
- 2026-04-24-aeat-cli-wireframe-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-24-aeat-verify-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-aeat-verify-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-error-code-registry-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-json-output-contract-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-mandatory-citations-adr.md :: `mandatory-citations` adr (**status:** `accepted`)
- 2026-04-25-mutation-harness-extension-adr.md :: `mutation-harness-extension` adr: percent + brackets + scalar mutators (**status:** `accepted`)
- 2026-04-25-operator-workflows-expansion-adr.md :: `operator-workflows-expansion` adr: cli-integration-coverage
- 2026-04-25-pdf-sanitizer-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-workflow-live-flag-excision-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-live-submit-permanently-forbidden-adr.md :: `live-submit-permanently-forbidden` adr: `live AEAT submission is permanently forbidden` | (**status:** `accepted`)
- 2026-04-27-modelo-100-renta-full-calc-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-modelo-111-calc-verify-adr.md :: `modelo-111-calc-verify` ADR — child of EPIC `#316` | (**status:** `rejected`)
- 2026-04-27-modelo-115-calc-verify-adr.md :: `modelo-115-calc-verify` ADR — child of EPIC `#316`
- 2026-04-27-modelo-123-calc-verify-adr.md :: `modelo-123-calc-verify` adr: aggregation-only 2026 rollover | (**status:** `accepted`)
- 2026-04-27-modelo-130-calc-verify-adr.md :: `modelo-130-calc-verify` ADR — child of EPIC `#316` | (**status:** `accepted`)
- 2026-04-27-modelo-131-calc-verify-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-modelo-303-calc-verify-adr.md :: `modelo-303-calc-verify` adr: Tier-L calc-verify-roundtrip | (**status:** `accepted`)
- 2026-04-27-modelo-390-calc-verify-adr.md :: `modelo-390-calc-verify` adr: tier-l calc-verify-roundtrip for the annual iva resumen | (**status:** `accepted`)
- 2026-04-27-secure-persistence-foundation-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-test-clave-movil-mark-fix-adr.md :: `test-clave-movil-mark-fix` adr: Keep Cl@ve Movil tests protocol-level | (**status:** `supersedes earlier marker decision`)
- 2026-04-28-ccaa-in-profile-adr.md :: `ccaa-in-profile` adr: `tax-residence profile as local JSON state` | (**status:** `accepted`)
- 2026-04-28-modelo-180-calc-verify-adr.md :: `modelo-180-calc-verify` adr: `annual rental withholding summary` | (**status:** `accepted`)
- 2026-04-28-modelo-200-calc-verify-adr.md :: `modelo-200-calc-verify` adr: `annual page-14 rulesets` | (**status:** `accepted`)
- 2026-04-29-inventory-management-adr.md :: `inventory-management` adr: `profile ledgers for Anexo D inventory and amortization` | (**status:** `accepted`)
- 2026-04-29-m100-per-ano-test-parity-adr.md :: `m100-per-ano-test-parity` adr: `split E and F for missing years` | (**status:** `accepted`)
- 2026-04-29-mutation-harness-fix-adr.md :: ADR — `mutation-harness-fix`: empirical kill-rate aggregator + M100 fixture coverage
- 2026-04-29-rental-income-hardening-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-29-secure-persistence-foundation-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-29-secure-persistence-foundation-wave18-adr.md :: `secure-persistence-foundation` wave-18 ADR: rotation-correctness fixes
- 2026-04-30-aeat-restructure-adr.md :: `aeat-restructure` adr: domain-aligned restructure of `src/aeat/` | (**status:** `accepted — execution-ready`)
- 2026-04-30-inventory-management-cli-design-adr.md :: inventory-management cli design adr: canonical data ledgers ux
- 2026-04-30-secure-persistence-foundation-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-30-secure-persistence-foundation-wave11-adr.md :: `secure-persistence-foundation` wave-11 adr — corpus integrity manifest | (**status:** `accepted`)
- 2026-04-30-secure-persistence-foundation-wave12-adr.md :: `secure-persistence-foundation` adr: wave-12 Argon2id KDF migration | (**status:** `accepted`)
- 2026-04-30-secure-persistence-foundation-wave13-adr.md :: `secure-persistence-foundation` adr: wave-13 repository-id validator consolidation | (**status:** `accepted`)
- 2026-04-30-secure-persistence-foundation-wave14-adr.md :: `secure-persistence-foundation` adr: wave-14 deferred-items closure | (**status:** `accepted`)
- 2026-04-30-secure-persistence-foundation-wave17-adr.md :: `secure-persistence-foundation` adr: wave-17 Kent UX security integration | (**status:** `accepted`)
- 2026-04-30-secure-persistence-foundation-wave5-adr.md :: `secure-persistence-foundation` wave-5 adr | (**status:** `accepted`)
- 2026-04-30-secure-persistence-foundation-wave6-adr.md :: `secure-persistence-foundation` wave-6 adr | (**status:** `accepted`)
- 2026-04-30-t6-aggregation-adr.md :: `t6-aggregation` adr: `classified-catalogue-to-casilla-ledger` | (**status:** `accepted`)
- 2026-05-01-corpus-data-hydration-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-01-quadlingual-i18n-adr.md :: `quadlingual-i18n` adr: extending the contract from es/en/hu to es/en/ca/hu | (**status:** `accepted`)
- 2026-05-02-aeat-cli-redesign-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-03-calculation-truth-registry-pending-adr.md :: `calculation-truth-registry` adr: `Central AEAT legal calculation registry` | (**status:** `accepted`)
- 2026-05-04-calculation-authority-evidence-tiering-adr.md :: `calculation-truth-registry` adr: `Calculation authority evidence tiering` | (**status:** `accepted`)
- 2026-05-04-live-filing-data-capture-adr.md :: `calculation-truth-registry` adr: `Live filed-declaration data capture` | (**status:** `accepted`)
- 2026-05-04-multilang-externalization-phase1-adr.md :: Architecture Decision Record: Multilang Externalization
- 2026-05-06-aeat-nif-iva-checker-adapter-adr.md :: `aeat-nif-iva-checker-adapter` adr: `AEAT NIF-IVA other-EU-countries verification adapter` | (**status:** `accepted`)
- 2026-05-06-cross-reference-oracle-binding-adr.md :: `cross-reference-oracle-binding` adr: `Bind cross-references to oracles by id` | (**status:** `accepted`)
- 2026-05-06-live-parity-oracle-backend-adr.md :: `live-parity-oracle` adr: `Modelo-agnostic read-only AEAT verification backend` | (**status:** `accepted`)
- 2026-05-06-modelo-369-vat-centralization-adr.md :: `modelo-369-vat-centralization` adr: `oss-ioss-regime-substrate-and-ledger-binding-shape` | (**status:** `proposed`)
- 2026-05-06-modelo-chain-tier-passage-adr.md :: `modelo-chain-tier-passage` adr: `Three-tier passage spec for modelo linkage-chain implementation work` | (**status:** `accepted`)
- 2026-05-06-oracle-environment-consistency-adr.md :: `oracle-environment-consistency` adr: `Verify cross-reference oracle bindings against catalogue at boot` | (**status:** `accepted`)
- 2026-05-06-oracle-surface-compatibility-adr.md :: `oracle-surface-compatibility` adr: `Reject oracle bindings whose surface_kind is incompatible with the cross-reference surface` | (**status:** `accepted`)
- 2026-05-06-renta-cuota-chain-rollout-adr.md :: `renta-cuota-chain-rollout` adr
- 2026-05-06-secure-persistence-enforcement-adr.md :: `secure-persistence-enforcement` adr: `secure persistence enforcement` | (**status:** `accepted`)
- 2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr.md :: `aeat-vies-surface-split-ixvi-vs-groi` adr: `Split the AEAT VIES verification surface into two sibling adapters` | (**status:** `accepted`)
- 2026-05-07-config-cli-profile-surface-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-07-live-parity-oracle-adr.md :: `authenticated-synthetic-surface-taxonomy` adr: `Add an authenticated_simulator surface category for auth-gated callable verification surfaces` | (**status:** `accepted`)
- 2026-05-07-renta-full-coverage-adr.md :: `renta-full-coverage` adr
- 2026-05-07-user-profile-backend-schema-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-08-aeat-cli-gap-closure-adr.md :: `aeat-cli-gap-closure` adr
- 2026-05-08-aeat-cli-hardening-adr.md :: `aeat-cli-hardening` adr
- 2026-05-08-audit-concerns-2026-05-adr.md :: `audit-concerns-2026-05` adr
- 2026-05-08-cli-backend-boundary-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-08-google-oauth-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-08-ledger-renta-pipeline-adr.md :: `ledger-renta-pipeline` adr: `canonical-ledger-observations-for-renta-bindings` | (**status:** `accepted`)
- 2026-05-08-ledger-renta-pipeline-phase2-contract-decisions-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-08-live-parity-oracle-adr.md :: `live-parity-oracle` ADR: cross-reference applicability gate
- 2026-05-08-modelo-directory-segmentation-adr.md :: modelo-directory-segmentation-adr
- 2026-05-08-renta-cuota-integra-autonomic-scale-adr.md :: `renta-cuota-integra-autonomic-scale` adr | (**status:** `accepted`)
- 2026-05-08-renta-cuota-integra-state-scale-adr.md :: `renta-cuota-integra-state-scale` adr | (**status:** `accepted`)
- 2026-05-09-exception-restructure-adr.md :: `exception-restructure` adr: `{title}` | (**status:** `{accepted|rejected|deprecated}`)
- 2026-05-10-eliminate-user-cli-shim-adr.md :: ADR: Eliminating `user_cli.py` Architectural Shim
- 2026-05-12-aeat-cli-config-vs-setup-namespace-adr.md :: `aeat-cli-config-vs-setup-namespace` adr: `aeat config vs setup namespace boundary` (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr.md :: `cli-workflow-redesign` adr: `apoderamientos surface` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr.md :: `cli-workflow-redesign` adr: `app ledger ratios shape` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-app-live-shape-adr.md :: `cli-workflow-redesign` adr: `app live shape` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr.md :: `cli-workflow-redesign` adr: `app modelo bindings shape` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-app-modelo-shape-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-app-overview-shape-adr.md :: `cli-workflow-redesign` adr: `app overview shape` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-app-registry-boundary-adr.md :: `cli-workflow-redesign` adr: `app registry boundary` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr.md :: `cli-workflow-redesign` adr: `app review queue execution` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-bank-provider-expansion-adr.md :: `cli-workflow-redesign` adr: `bank provider expansion` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-bucket-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-bucket-event-history-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr.md :: `cli-workflow-redesign` adr: `complementaria external filing path` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-config-auth-shape-adr.md :: `cli-workflow-redesign` adr: `Config auth command surface` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-config-doctor-shape-adr.md :: `cli-workflow-redesign` adr: `config doctor shape` | (**status:** `superseded by [[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]`)
- 2026-05-12-cli-workflow-redesign-config-init-shape-adr.md :: `cli-workflow-redesign` adr: `Config init first-run shape` | (**status:** `superseded by [[2026-05-16-profile-lifecycle-cli-adr]]`)
- 2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr.md :: `cli-workflow-redesign` adr: `domain harvest normatives and manuals` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr.md :: `cli-workflow-redesign` adr: `domain harvest OSS/IOSS` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-domain-harvest-rental-adr.md :: `cli-workflow-redesign` adr: `domain harvest rental` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-domain-harvest-vat-classification-adr.md :: `cli-workflow-redesign` adr: `domain harvest VAT classification` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-domain-portals-harvest-adr.md :: `cli-workflow-redesign` adr: `domain portals harvest` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr.md :: `cli-workflow-redesign` adr: `evidence bundle shape` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-festivos-deadline-shift-adr.md :: `cli-workflow-redesign` adr: `festivos deadline shift` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-foreign-currency-normalization-adr.md :: `cli-workflow-redesign` adr: `foreign currency normalization` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-inventory-placement-adr.md :: `cli-workflow-redesign` adr: `inventory placement and execution` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr.md :: `cli-workflow-redesign` adr: `IVA prorrata arts 101-103` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr.md :: `cli-workflow-redesign` adr: `libros BOE format exporters` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr.md :: `cli-workflow-redesign` adr: `Modelo 036 and 037 foundation` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-modelo-145-foundation-adr.md :: `cli-workflow-redesign` adr: `Modelo 145 foundation` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-modelo-file-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-modelo-filing-record-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-modelo-verify-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-modelo-work-units-adr.md :: `cli-workflow-redesign` adr: `Modelo calculation work units and internal filing state` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr.md :: `cli-workflow-redesign` adr: `observability wrapping decision` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr.md :: `cli-workflow-redesign` adr: `output rendering normalization` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr.md :: `cli-workflow-redesign` adr: `per-modelo aggregation pipeline` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-profile-read-path-retirement-adr.md :: `cli-workflow-redesign` adr: `profile read path retirement` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr.md :: `cli-workflow-redesign` adr: `receipt OCR PDF evidence` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-verified-complete-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr.md :: `cli-workflow-redesign` adr: `workflow engine harvest` | (**status:** `accepted`)
- 2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr.md :: `cli-workflow-redesign` adr: `workflow resumption semantics` | (**status:** `accepted`)
- 2026-05-12-google-oauth-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-schema-driven-wizard-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-schema-driven-wizard-closure-adr.md :: `schema-driven-wizard-closure` adr
- 2026-05-12-schema-driven-wizard-revision-adr.md :: `schema-driven-wizard-revision` adr
- 2026-05-13-audits-resolution-adr.md :: `audits-resolution` adr
- 2026-05-13-cli-workflow-redesign-actor-attribution-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-app-modelo-discard-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-borrador-100-binding-integration-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-borrador-snapshot-management-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-config-profile-keys-discovery-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-config-repair-shape-adr.md :: `cli-workflow-redesign` adr: `config repair shape` | (**status:** `accepted`)
- 2026-05-13-cli-workflow-redesign-explain-legal-ref-convention-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-ledger-ratios-eligible-and-validate-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr.md :: `cli-workflow-redesign` adr: `manual ledger transaction entry and bucket-scoped ledger storage` | (**status:** `accepted`)
- 2026-05-13-cli-workflow-redesign-modelo-calculate-engine-wiring-adr.md :: `cli-workflow-redesign` adr: `modelo calculate engine wiring` | (**status:** `accepted`)
- 2026-05-13-cli-workflow-redesign-modelo-external-filing-import-adr.md :: `cli-workflow-redesign` adr: `modelo external filing import` | (**status:** `accepted`)
- 2026-05-13-cli-workflow-redesign-profile-output-language-adr.md :: `cli-workflow-redesign` adr: `profile-owned output language` | (**status:** `accepted`)
- 2026-05-13-cli-workflow-redesign-root-help-shape-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-google-oauth-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-13-google-oauth-calc-sheets-adr.md :: `google-oauth` adr: `Calculation-to-Sheets visual verification surface` | (**status:** `accepted`)
- 2026-05-13-google-oauth-inbound-adr.md :: `google-oauth` adr: `Incoming-bucket ingestion semantics` | (**status:** `accepted`)
- 2026-05-13-google-oauth-snapshot-adr.md :: `google-oauth` adr: `Snapshot, backup, and restore with encryption boundary` | (**status:** `accepted`)
- 2026-05-13-google-oauth-taxonomy-adr.md :: `google-oauth` adr: `Per-domain export taxonomy` | (**status:** `accepted`)
- 2026-05-13-google-oauth-twoway-adr.md :: `google-oauth` adr: `Two-way Sheets sync feasibility verdict` | (**status:** `accepted — deferred`)
- 2026-05-13-identity-adr.md :: `identity` adr: `core/identity placement: tax-ID validation as a security primitive` | (**status:** `accepted`)
- 2026-05-14-cli-workflow-redesign-dev-environment-uv-windows-adr.md :: `cli-workflow-redesign` adr: `dev environment - uv on windows` | (**status:** `accepted`)
- 2026-05-14-cli-workflow-redesign-error-registry-exhaustiveness-invariant-adr.md :: `cli-workflow-redesign` adr: `error registry exhaustiveness invariant` | (**status:** `accepted`)
- 2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr.md :: `cli-workflow-redesign` adr: `integrity-warning stability` | (**status:** `accepted`)
- 2026-05-14-cli-workflow-redesign-list-vs-query-leaf-semantics-adr.md :: `cli-workflow-redesign` adr: `list-vs-query leaf semantics` | (**status:** `accepted`)
- 2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr.md :: `cli-workflow-redesign` adr: `Modelo 145 local payer communication reopening` | (**status:** `accepted`)
- 2026-05-14-google-oauth-adr.md :: `google-oauth` adr: `schema-to-sheet engine and parity guarantee for bidirectional modelo sheets` | (**status:** `accepted`)
- 2026-05-14-ledger-transaction-lifecycle-adr.md :: `ledger-transaction-lifecycle` adr: full crud plus split and re-merge with traceable lineage | (**status:** `accepted`)
- 2026-05-14-profile-bucket-lifecycle-adr.md :: `profile-bucket-lifecycle` adr: profile + bucket + vault lifecycle | (**status:** `accepted — execution-ready`)
- 2026-05-14-secure-backend-passkey-custody-adr.md :: secure-backend-passkey-safety adr: master passkey custody + enrollment ux | (**status:** `accepted — execution-ready`)
- 2026-05-14-settings-di-adr.md :: `settings-di` adr: `contextvar-backed-settings-override` | (**status:** `accepted`)
- 2026-05-15-corpus-registry-packaging-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-16-profile-lifecycle-cli-adr.md :: `profile-lifecycle-cli` adr: operator-facing profile lifecycle, cryptic-verb retirement, and persistence-boundary cleanup | (**status:** `accepted`)
- 2026-05-16-resource-management-api-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-18-profile-lifecycle-cli-adr.md :: `profile-lifecycle-cli` adr: cascade closure — engine cutover, crypto ContextVar, CI surface gate, NIST passphrase floor | (**status:** `accepted`)
- 2026-05-18-schema-hardening-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-19-code-duplication-sweep-adr.md :: `code-duplication-sweep` adr: `Unify Shadowed Symbols, Secure Object Repositories, and Terminology Glossary` | (**status:** `superseded`)
- 2026-05-19-iva-compensation-chain-adr.md :: `iva-compensation-chain` adr: `modelo 303 and 390 compensation balance remediation` | (**status:** `accepted`)
- 2026-05-19-live-iva-compensation-wallet-adr.md :: `live-iva-compensation-wallet` adr: `AEAT wallet as primary IVA compensation authority` | (**status:** `accepted`)
- 2026-05-19-modelo-130-relation-regression-adr.md :: `modelo-130-relation-regression` adr: `same-year negative-result relation remediation` | (**status:** `accepted`)
- 2026-05-19-modelo-registry-fragment-architecture-adr.md :: `modelo-registry-fragments` adr: fragment authoring compiler for modelo registry definitions | (**status:** `accepted`)
- 2026-05-19-profile-lifecycle-disaster-adr.md :: `profile-lifecycle-disaster` adr: session-activation wiring, state-model collapse, atomic create | (**status:** `accepted`)
- 2026-05-19-spanish-stem-terminology-authority-adr.md :: spanish-stem-terminology-authority adr: Spanish Stem Terminology Authority for Tax-Domain Identifiers | (**status:** accepted)
- 2026-05-20-calculation-source-connectivity-adr.md :: `calculation-source-connectivity` adr: `canonical calculation source mesh` | (**status:** `accepted`)
- 2026-05-20-registry-authority-flow-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-20-registry-casilla-identity-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-21-corporate-entity-calculation-adr.md :: `cli-workflow-redesign` adr: `The corporate-entity calculation model — a legal entity is routed to the Impuesto sobre Sociedades schedule (Modelo 200/202, LIS rate scale), an attribution entity to m
- 2026-05-21-declaracion-extraction-architecture-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-21-profile-state-aggregate-adr.md :: `cli-workflow-redesign` adr: `Profile state is one aggregate, owned by one repository, written through a cross-store unit-of-work` | (**status:** `accepted`)
- 2026-05-21-profile-uuid-identity-adr.md :: `cli-workflow-redesign` adr: `Profile identity is a generated UUID; the display name is a decoupled mutable label` | (**status:** `accepted`)
- 2026-05-21-sii-digital-iva-ledger-adr.md :: `cli-workflow-redesign` adr: `SII is modelled as a rolling ledger-submission enrolment, not a periodic-window modelo; it suppresses Modelo 347 and 390 and switches Modelo 303 to monthly` | (**status:*
- 2026-05-21-state-read-projection-adr.md :: `cli-workflow-redesign` adr: `Every operator-facing surface consumes one canonical state read-projection` | (**status:** `accepted`)
- 2026-05-21-taxpayer-type-applicability-adr.md :: `cli-workflow-redesign` adr: `The profile carries a structured entity-type, tax-regime, and enrolment model; modelos, calendar, calculations, and rules derive from it` | (**status:** `accepted`)
- 2026-05-21-work-verify-deadline-independence-adr.md :: `cli-workflow-redesign` adr: `work verify validates a calculation and is independent of the filing-window deadline` | (**status:** `accepted`)
- 2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr.md :: `live-iva-compensation-wallet` adr: `profile, bucket, repository, and calculation-binding hierarchy` | (**status:** `accepted`)
- 2026-05-22-schema-hardening-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-22-schema-hardening-coti-adr.md :: `schema-hardening-coti` adr: `quoted-fund-coti-warning-policy` | (**status:** `accepted`)
- 2026-05-22-secure-storage-production-hardening-architecture-adr.md :: `secure-storage-production-hardening` adr: `canonical SecureStorage architecture for adverse production operation` | (**status:** `accepted`)
- 2026-05-26-aeat-sede-constants-centralization-adr.md :: `aeat-sede-constants-centralization` adr: `AEAT and Sede constants are schema-owned architecture data` | (**status:** `accepted`)
- 2026-05-26-cross-domain-continuity-adr.md :: `cross-domain-continuity` adr: `verification-predicate-strategy` | (**status:** `accepted`)
- 2026-05-26-linkage-design-audit-adr.md :: `linkage-design-audit` ADR: `boundary-typed-contracts` (**status:** `accepted`)
- 2026-05-26-live-iva-auth-read-acquisition-adr.md :: `live-iva-compensation-wallet` adr: `read-only live auth diagnostics and acquisition boundary` | (**status:** `accepted`)
- 2026-05-26-live-iva-remote-evidence-reconciliation-adr.md :: `live-iva-compensation-wallet` adr: `remote IVA evidence persistence and reconciliation authority` | (**status:** `accepted`)
- 2026-05-26-modelo-130-relation-regression-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-26-no-synthetic-sede-live-surfaces-adr.md :: `no-synthetic-sede-live-surfaces` adr: `Synthetic data is prohibited on AEAT-hosted live surfaces` | (**status:** `accepted`)
- 2026-05-27-cross-domain-continuity-adr.md :: `cross-domain-continuity` adr: `ledger-classification-rule-engine` | (**status:** `accepted`)
- 2026-05-27-descendant-profile-axis-adr.md :: `descendant-profile-axis` adr: Descendant profile axis | (**status:** `accepted`)
- 2026-05-27-dsl-conditional-predicate-adr.md :: `dsl-conditional-predicate` adr: implies-nonzero conditional Layer 2 verification predicate | (**status:** `accepted`)
- 2026-05-27-dt-12-rescate-plan-pensiones-adr.md :: `dt-12-rescate-plan-pensiones` adr: DT 12a rescate plan pensiones capital reduccion | (**status:** `accepted`)
- 2026-05-27-iva-autoconsumo-promotor-adr.md :: `iva-autoconsumo-promotor` adr: IVA autoconsumo promotor Art. 9.1.c LISIVA | (**status:** `accepted`)
- 2026-05-27-iva-classification-enrichment-adr.md :: `iva-classification-enrichment` adr: IVA category + counterparty enrichment on Transaction | (**status:** `accepted`)
- 2026-05-27-m210-irnr-full-engine-adr.md :: `m210-irnr-full-engine` adr: Modelo 210 IRNR full calculation engine (post Path-B stub) | (**status:** `accepted`)
- 2026-05-27-multi-row-modelo-declaration-adr.md :: `multi-row-modelo-declaration` adr: Multi-row modelo declaration mechanism | (**status:** `accepted`)
- 2026-05-27-non-resident-irnr-axis-adr.md :: `non-resident-irnr-axis` adr: Non-resident IRNR fiscal-residency axis | (**status:** `accepted`)
- 2026-05-27-profile-portability-adr.md :: `cross-domain-continuity` adr: `profile-portability` | (**status:** `accepted`)
- 2026-05-27-sal-sll-legal-entity-form-adr.md :: `sal-sll-legal-entity-form` adr: SAL/SLL legal entity form + reserva especial Ley 44/2015 | (**status:** `accepted`)
- 2026-05-27-schema-hardening-casilla-continuity-contract-adr.md :: `schema-hardening` adr: `casilla-continuity-evolution-contract` | (**status:** `accepted`)
- 2026-05-27-source-jurisdiction-axis-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-28-centralized-output-redaction-adr.md :: `centralized-output-redaction` adr: `centralize CLI output redaction at the rendering boundary` | (**status:** `accepted`)
- 2026-05-28-codebase-solidification-adr.md :: `codebase-solidification` adr: `Recurring hardening epic strategy` | (**status:** `accepted`)
- 2026-05-28-financial-provider-extraction-discipline-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-28-secure-storage-production-hardening-W05-P09-S40-adr.md :: `secure-storage-production-hardening` adr: `W05.P09.S40 operator-directed export exceptions` | (**status:** `accepted`)
- 2026-05-30-docs-architecture-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-30-docs-cli-conformance-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-30-docs-sphinx-build-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-30-identity-primitives-adr.md :: `identity-primitives` adr: `typed-id alias placement rule for record-shape, security, and cross-domain identities` | (**status:** `accepted`)
- 2026-05-30-purchase-invoice-ocr-extraction-discipline-adr.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-31-atomic-relocation-coordination-adr.md :: `atomic-relocation-coordination` adr: `every-symbol-relocation-is-a-single-atomic-commit` | (**status:** `accepted`)
- 2026-05-31-core-authority-adr.md :: `core-authority` adr: `core-as-single-authority-for-all-cross-module-definitions` | (**status:** `accepted`)
- 2026-05-31-locale-scaffold-fstring-adr.md :: `locale-scaffold-fstring` adr: explicit f-string key expansion registry | (**status:** `accepted`)
- 2026-05-31-schedule-predicate-catalogue-adr.md :: schedule-predicate-catalogue adr: eager compile-time validation of schedule-predicate field references | (status: accepted)
- 2026-05-31-trabajador-del-mar-adr.md :: trabajador-del-mar adr: maritime-worker-irpf-axis | (**status:** accepted)

## Appendix B — Complete plan inventory (206 docs)

Title sweep of every plan file under `.vault/plan/`. The tier marker
(`L1` / `L2` / `L3` / `L4`) and the open/closed step count are in the
plan-body, not the title line; surfacing those requires a per-file read
that is the next-session task.

- 2026-04-12-base-module-structure-plan.md :: Base Module Structure Plan
- 2026-04-12-casilla-db-plan.md :: Casilla DB implementation plan
- 2026-04-12-cert-auth-plan.md :: Implementation Plan: PKCS#12 Certificate Authentication
- 2026-04-12-ci-github-actions-plan.md :: Plan: GitHub Actions CI
- 2026-04-12-data-storage-plan.md :: data-storage plan
- 2026-04-12-deadline-engine-plan.md :: implementation plan: filing-deadline computation engine
- 2026-04-12-dev-scaffolding-plan.md :: dev-scaffolding plan
- 2026-04-12-docs-rewrite-plan.md :: plan: docs-rewrite
- 2026-04-12-filing-draft-engine-plan.md :: Plan — Filing draft generation engine (#39)
- 2026-04-12-google-fixtures-plan.md :: google-fixtures plan: provision google workspace live-test fixtures
- 2026-04-12-gsuite-bootstrap-plan.md :: gsuite-bootstrap phase-1 plan
- 2026-04-12-justificante-parser-plan.md :: `justificante-parser` plan
- 2026-04-12-llm-client-plan.md :: `llm-client` `phase-1` plan
- 2026-04-12-manual-practico-plan.md :: `manual-practico` `phase-1` plan
- 2026-04-12-modelo-303-390-plan.md :: modelo-303-390 plan (#62)
- 2026-04-12-normatives-plan.md :: normatives plan: phased delivery of `aeat.domain.normatives` v1
- 2026-04-12-notifications-inbox-plan.md :: plan: aeat notifications inbox
- 2026-04-12-playwright-anti-bot-plan.md :: Implementation Plan: Playwright Anti-Bot Evasion
- 2026-04-12-release-please-plan.md :: plan: release-please local-only autorelease
- 2026-04-12-self-healing-sync-plan.md :: plan: self-healing sync (issue #11)
- 2026-04-12-setup-wizard-plan.md :: plan — first-run setup wizard (#61)
- 2026-04-12-status-reader-plan.md :: Plan — AEAT status reader (#43)
- 2026-04-12-submission-engine-plan.md :: implementation plan: filing submission engine
- 2026-04-12-synthetic-filing-fixtures-plan.md :: plan — synthetic-filing-fixtures
- 2026-04-12-trilingual-i18n-plan.md :: Trilingual i18n implementation plan
- 2026-04-12-workflow-engine-plan.md :: workflow-engine plan
- 2026-04-13-aeat-mantenimiento-detection-plan.md :: aeat-mantenimiento-detection implementation plan
- 2026-04-13-cert-pre-expiry-gate-plan.md :: Plan: Certificate Pre-Expiry Health Check + Workflow Gate
- 2026-04-13-filing-complementaria-plan.md :: implementation plan: filing complementaria
- 2026-04-13-modelo-inventory-plan.md :: modelo-inventory plan (#108)
- 2026-04-13-p2a-financial-provider-plan.md :: `p2a-financial-provider` `phase-1` plan
- 2026-04-13-p2e-tax-category-catalogue-plan.md :: `p2e-tax-category-catalogue` `phase-1` plan
- 2026-04-13-r1-vat-enumeration-plan.md :: r1-vat-enumeration plan
- 2026-04-14-run-trace-plan.md :: run-trace observability plan
- 2026-04-14-transaction-catalogue-plan.md :: `transaction-catalogue` `phase-1` plan
- 2026-04-16-aeat-history-fetch-plan.md :: aeat filing-history read surface — implementation plan
- 2026-04-16-google-workspace-mcp-auth-plan.md :: `google-workspace-mcp-auth` `phase-1` plan
- 2026-04-16-live-write-test-audit-plan.md :: `live-write-test-audit` `phase-1` plan
- 2026-04-16-submission-safety-sweep-plan.md :: `submission-safety-sweep` `phase-1` plan
- 2026-04-17-aeat-access-gate-plan.md :: Implementation Plan: Live AEAT Access Blocker & Verification Gate (#167)
- 2026-04-17-attachment-service-plan.md :: `attachment-service` `phase-1` plan
- 2026-04-17-browser-leak-plan.md :: `browser-leak` `phase1` plan
- 2026-04-17-export-first-roadmap-plan.md :: export-first-roadmap-plan
- 2026-04-17-invoice-catalogue-plan.md :: `invoice-catalogue` plan: `p2-c-invoice-catalogue-and-linking`
- 2026-04-17-modelo-303-formulas-plan.md :: modelo-303-formulas plan (#183)
- 2026-04-17-modelo-formulas-plan.md :: modelo-formulas implementation plan
- 2026-04-17-modelo-inventory-remediation-plan.md :: `modelo-inventory` `remediation` plan
- 2026-04-17-path-handling-safety-phase1-plan.md :: `path-handling-safety` `phase1` plan
- 2026-04-17-portal-catalogue-plan.md :: portal-catalogue implementation plan
- 2026-04-17-pytest-markers-plan.md :: `pytest-markers` `phase-1` plan
- 2026-04-17-pytest-only-testing-plan.md :: pytest-only-testing phase-1 plan
- 2026-04-17-relative-imports-plan.md :: relative-imports plan: enforce relative imports inside src/aeat/
- 2026-04-17-schema-extraction-plan.md :: Implementation plan: `aeat.domain.schema` subpackage (#9)
- 2026-04-17-session-persistence-phase1-plan.md :: `session-persistence` `phase1` plan
- 2026-04-18-aeat-filing-detail-fetch-plan.md :: plan — StatusReader.fetch_filing_detail (#227)
- 2026-04-18-auth-protocol-plan.md :: `auth-protocol` `phase-1` plan
- 2026-04-18-category-assignment-cli-plan.md :: category-assignment-cli-plan
- 2026-04-18-cert-provider-migration-plan.md :: cert-provider-migration-plan
- 2026-04-18-draft-approval-staleness-plan.md :: `draft-approval-staleness` `implementation` plan
- 2026-04-18-rename-corpus-review-implementation-plan.md :: `rename-corpus-review` `implementation` plan
- 2026-04-18-unclassified-state-plan.md :: `unclassified-state` plan: `split-unclassified-and-track-classification-history` | (**status:** `accepted`)
- 2026-04-18-unified-review-queue-plan.md :: unified-review-queue plan
- 2026-04-20-classification-harmonization-plan.md :: `classification-harmonization` `blocked-groundwork` plan
- 2026-04-20-pdf-import-plan.md :: `pdf-import` plan: `reconstruct-filing-draft-from-justificante-pdf`
- 2026-04-21-auth-cli-plan.md :: auth-cli plan (issue #285)
- 2026-04-21-calc-verification-plan.md :: `calc-verification` plan
- 2026-04-21-casilla-schema-completeness-plan.md :: `casilla-schema-completeness` plan
- 2026-04-21-declaracion-extractor-plan.md :: `declaracion-extractor` plan
- 2026-04-21-google-auth-ux-phase-1-plan.md :: `google-auth-ux` `phase-1` plan
- 2026-04-21-integration-tests-ci-plan.md :: `integration-tests-ci` plan
- 2026-04-21-justificante-reframing-plan.md :: `justificante-reframing` plan
- 2026-04-21-live-sync-backend-plan.md :: `live-sync-backend` `phase-1` plan
- 2026-04-21-modelo-100-renta-plan.md :: `modelo-100-renta` plan (summary-block MVP)
- 2026-04-21-n26-data-source-phase-2-plan.md :: `n26-data-source` `phase-2` plan
- 2026-04-21-pdf-taxonomy-plan.md :: `pdf-taxonomy` plan: adopt the canonical AEAT-PDF vocabulary without breaking `#271`
- 2026-04-21-real-pdf-fixture-corpus-plan.md :: `real-pdf-fixture-corpus` plan
- 2026-04-21-usage-ratios-plan.md :: `usage-ratios` plan: `persist-kent-usage-ratios-as-category-keyed-profile` | (**status:** `completed`)
- 2026-04-24-aeat-verify-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-aeat-verify-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-error-code-registry-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-json-output-contract-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-mandatory-citations-plan.md :: `mandatory-citations` plan
- 2026-04-25-mutation-harness-extension-plan.md :: `mutation-harness-extension` plan
- 2026-04-25-operator-workflows-expansion-plan.md :: `operator-workflows-expansion` plan: cli-integration-coverage
- 2026-04-25-pdf-sanitizer-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-25-workflow-live-flag-excision-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-live-submit-permanently-forbidden-plan.md :: `live-submit-permanently-forbidden` `phase-1` plan
- 2026-04-27-modelo-100-renta-full-calc-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-modelo-111-calc-verify-plan.md :: `modelo-111-calc-verify` plan
- 2026-04-27-modelo-115-calc-verify-plan.md :: `modelo-115-calc-verify` plan — issue `#319`
- 2026-04-27-modelo-123-calc-verify-plan.md :: `modelo-123-calc-verify` implementation plan
- 2026-04-27-modelo-130-calc-verify-plan.md :: `modelo-130-calc-verify` plan — phase-1
- 2026-04-27-modelo-131-calc-verify-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-modelo-303-calc-verify-plan.md :: `modelo-303-calc-verify` implementation plan
- 2026-04-27-modelo-390-calc-verify-plan.md :: `modelo-390-calc-verify` plan
- 2026-04-27-secure-persistence-foundation-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-27-test-clave-movil-mark-fix-plan.md :: `test-clave-movil-mark-fix` implementation plan
- 2026-04-28-ccaa-in-profile-plan.md :: `ccaa-in-profile` implementation plan
- 2026-04-28-modelo-180-calc-verify-plan.md :: `modelo-180-calc-verify` implementation plan
- 2026-04-28-modelo-200-calc-verify-plan.md :: `modelo-200-calc-verify` implementation plan
- 2026-04-29-inventory-management-plan.md :: `inventory-management` `implementation` plan
- 2026-04-29-m100-per-ano-test-parity-plan.md :: `m100-per-ano-test-parity` implementation plan
- 2026-04-29-mutation-harness-fix-plan.md :: Plan — `mutation-harness-fix`
- 2026-04-29-rental-income-hardening-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-30-aeat-restructure-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-04-30-inventory-management-cli-design-plan.md :: inventory-management cli design plan: data ledgers rewrite
- 2026-04-30-inventory-management-hardening-plan.md :: Inventory Management Hardening Plan
- 2026-04-30-secure-persistence-foundation-wave17-plan.md :: `secure-persistence-foundation` plan: wave-17 Kent UX security integration
- 2026-04-30-t6-aggregation-plan.md :: `t6-aggregation` `implementation` plan
- 2026-05-01-corpus-data-hydration-plan.md :: `corpus-data-hydration` exhaustive execution plan
- 2026-05-03-calculation-truth-registry-rebuild-plan.md :: `calculation-truth-registry` `teardown-rebuild` plan
- 2026-05-04-multilang-externalization-phase1-plan.md :: Multilang Externalization Phase 1 Plan
- 2026-05-05-aeat-cli-redesign-continuation-plan.md :: `aeat-cli-redesign` `continuation` plan
- 2026-05-06-renta-cuota-chain-rollout-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-06-secure-persistence-enforcement-plan.md :: `secure-persistence-enforcement` `continuous-audit-rollout` plan
- 2026-05-07-live-parity-oracle-plan.md :: `live-parity-oracle` `groi-oracle-completion-plan` plan
- 2026-05-07-renta-full-coverage-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-07-user-profile-backend-schema-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-08-aeat-cli-gap-closure-plan.md :: `aeat-cli-gap-closure` `AEAT CLI gap closure granular execution plan`
- 2026-05-08-aeat-cli-hardening-plan.md :: `aeat-cli-hardening` `Broad CLI Review And Backend Alignment` plan
- 2026-05-08-audit-concerns-2026-05-plan.md :: `audit-concerns-2026-05` tracking plan
- 2026-05-08-cli-backend-boundary-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-08-ledger-renta-pipeline-plan.md :: `ledger-renta-pipeline` `ledger-to-renta-rollout` plan
- 2026-05-08-renta-cuota-integra-autonomic-scale-plan.md :: `renta-cuota-integra-autonomic-scale` plan
- 2026-05-08-renta-cuota-integra-state-scale-plan.md :: `renta-cuota-integra-state-scale` plan
- 2026-05-09-exception-restructure-phase-1-plan.md :: Exception Restructure Plan (Revised)
- 2026-05-10-eliminate-user-cli-shim-plan.md :: Plan: Eliminate `user_cli.py` Architectural Shim
- 2026-05-12-schema-driven-wizard-closure-plan.md :: schema-driven wizard closure plan
- 2026-05-12-schema-driven-wizard-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-12-schema-driven-wizard-revision-plan.md :: schema-driven wizard revision plan
- 2026-05-13-audits-resolution-plan.md :: audits resolution plan
- 2026-05-13-cli-workflow-redesign-config-repair-shape-plan.md :: `cli-workflow-redesign` `config repair shape` plan
- 2026-05-13-cli-workflow-redesign-epic-plan.md :: `cli-workflow-redesign` `epic` plan
- 2026-05-13-google-oauth-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan.md :: `cli-workflow-redesign` `modelo-145-local-payer-communication-reopening` plan
- 2026-05-14-ledger-transaction-lifecycle-plan.md :: `ledger-transaction-lifecycle` plan
- 2026-05-14-secure-backend-passkey-bucket-plan.md :: secure-backend-passkey-safety plan: passkey custody + bucket lifecycle execution
- 2026-05-14-settings-di-plan.md :: `settings-di` plan
- 2026-05-15-corpus-registry-packaging-plan.md :: `corpus-registry-packaging` plan
- 2026-05-15-linkage-design-audit-plan.md :: `linkage-design-audit` `Wave 1: type-system uniformity (Phase 1 of linkage epic)` plan
- 2026-05-16-linkage-design-audit-plan.md :: `linkage-design-audit` `Wave 2: model consolidation (Phase 2 of linkage epic)` plan
- 2026-05-16-modelo-036-census-sync-plan.md :: `modelo-036-census-sync` plan
- 2026-05-16-profile-lifecycle-cli-plan.md :: `profile-lifecycle-cli` plan
- 2026-05-16-resource-management-api-plan.md :: `resource-management-api` plan
- 2026-05-17-linkage-design-audit-plan.md :: `linkage-design-audit` `Wave 3: referential integrity and typed envelope (Phase 3 of linkage epic)` plan
- 2026-05-18-linkage-design-audit-plan.md :: `linkage-design-audit` `Wave 4: operator surfaces, identity, registry data backfill (Phase 4 of linkage epic)` plan
- 2026-05-18-profile-lifecycle-cli-plan.md :: `profile-lifecycle-cli` cascade closure plan
- 2026-05-18-schema-hardening-plan.md :: `schema-hardening` Plan A: `data_type` Literal extension plan
- 2026-05-19-code-duplication-sweep-plan.md :: `code-duplication-sweep` `Code Duplication Sweep Remediation Plan` plan
- 2026-05-19-iva-compensation-chain-plan.md :: `iva-compensation-chain` `remediation` plan
- 2026-05-19-live-iva-compensation-wallet-plan.md :: `live-iva-compensation-wallet` `implementation` plan
- 2026-05-19-modelo-130-relation-regression-plan.md :: `modelo-130-relation-regression` `remediation` plan
- 2026-05-19-profile-lifecycle-disaster-plan.md :: `profile-lifecycle-disaster` recovery plan
- 2026-05-19-schema-hardening-plan.md :: `schema-hardening` Plan B: `CasillaConstraints` expansion plan
- 2026-05-20-calculation-source-connectivity-plan.md :: `calculation-source-connectivity` `source mesh implementation` plan
- 2026-05-20-registry-authority-flow-plan.md :: `registry-authority-flow` registry authority flow rollout plan
- 2026-05-20-registry-casilla-identity-plan.md :: `registry-casilla-identity` plan
- 2026-05-20-schema-hardening-plan.md :: `schema-hardening` Plan C: inline `semantic_role` validator plan
- 2026-05-21-cli-persona-testimonials-plan.md :: REQUIRED TAGS (minimum 2): one directory tag + one feature tag
- 2026-05-21-cross-campaign-hardening-plan.md :: `cross-campaign-hardening` cross-campaign hardening rollout
- 2026-05-21-declaracion-extraction-architecture-plan.md :: `declaracion-extraction-architecture` umbrella plan
- 2026-05-21-fichero-boe-export-layouts-plan.md :: `fichero-boe-export-layouts` plan
- 2026-05-21-fresh-cli-persona-repair-plan.md :: `fresh-cli-persona-repair` plan
- 2026-05-21-fresh-cli-persona-testimonial-wave-plan.md :: `fresh-cli-persona-testimonial-wave` plan
- 2026-05-21-schema-hardening-plan.md :: `schema-hardening` `semantic_role sidecar continuation` plan
- 2026-05-21-state-architecture-plan.md :: `cli-workflow-redesign` plan: profile state-management architecture
- 2026-05-21-taxpayer-type-applicability-plan.md :: `cli-workflow-redesign` plan: taxpayer entity-type / regime / enrolment model
- 2026-05-22-schema-hardening-coti-plan.md :: `schema-hardening-coti` `quoted-fund-coti-burn-down` plan
- 2026-05-22-schema-hardening-plan.md :: `schema-hardening` `optional-numeric-suppressor-burn-down` plan
- 2026-05-22-secure-object-backlog-drain-plan.md :: `secure-object-backlog-drain` plan: audit-derived catalogue and hygiene cleanup
- 2026-05-22-secure-object-backlog-drain-r2-plan.md :: `secure-object-backlog-drain` R2 plan: repository hygiene slice
- 2026-05-22-secure-object-backlog-drain-r3-plan.md :: `secure-object-backlog-drain` R3 plan: secure-storage roundtrip hygiene slice
- 2026-05-22-secure-object-integrity-attribution-plan.md :: `secure-object-integrity` plan: unreadable-row attribution and fail-closed repair diagnostics
- 2026-05-22-secure-storage-production-hardening-refactor-plan.md :: `secure-storage-production-hardening` `refactor` plan
- 2026-05-26-corporate-tax-runtime-plan.md :: `corporate-tax-runtime` plan: IS micro-empresa bracket dispatch, INCN-gated Modelo 202 modality, new-entity period rate
- 2026-05-26-cross-domain-continuity-plan.md :: `cross-domain-continuity` `cross-domain continuity remediation epic - open-ended persona-driven correctness campaign` plan
- 2026-05-26-modelo-130-relation-regression-plan.md :: `modelo-130-relation-regression` `selector-max-year-delta-and-bound-casilla-zero-default-remediation` plan
- 2026-05-26-no-synthetic-sede-live-surfaces-plan.md :: `no-synthetic-sede-live-surfaces` implementation plan
- 2026-05-26-schema-hardening-m130-standardization-plan.md :: `schema-hardening` `m130-standardization` plan
- 2026-05-26-schema-hardening-m131-fragmentation-plan.md :: `schema-hardening` `m131-fragmentation` plan
- 2026-05-27-m210-irnr-phase-2-engine-plan.md :: `m210-irnr-phase-2-engine` `M210 IRNR Phase 2 engine - full diseno-de-registro + Convenios roster + remaining tipo-de-renta variants` plan
- 2026-05-27-schema-hardening-casilla-continuity-contract-plan.md :: `schema-hardening` `casilla-continuity-contract` plan
- 2026-05-27-schema-hardening-m036-standardization-plan.md :: `schema-hardening` `m036-standardization` plan
- 2026-05-27-schema-hardening-m115-standardization-plan.md :: `schema-hardening` `m115-standardization` plan
- 2026-05-27-schema-hardening-m184-standardization-plan.md :: `schema-hardening` `m184-standardization` plan
- 2026-05-27-schema-hardening-m190-standardization-plan.md :: `schema-hardening` `m190-standardization` plan
- 2026-05-27-schema-hardening-m193-standardization-plan.md :: `schema-hardening` `m193-standardization` plan
- 2026-05-27-schema-hardening-m308-standardization-plan.md :: `schema-hardening` `m308-standardization` plan
- 2026-05-27-schema-hardening-m309-standardization-plan.md :: `schema-hardening` `m309-standardization` plan
- 2026-05-27-schema-hardening-m322-standardization-plan.md :: `schema-hardening` `m322-standardization` plan
- 2026-05-27-schema-hardening-m347-standardization-plan.md :: `schema-hardening` `m347-standardization` plan
- 2026-05-27-schema-hardening-m353-standardization-plan.md :: `schema-hardening` `m353-standardization` plan
- 2026-05-27-schema-hardening-m360-standardization-plan.md :: `schema-hardening` `m360-standardization` plan
- 2026-05-27-schema-hardening-m390-standardization-plan.md :: `schema-hardening` `m390-standardization` plan
- 2026-05-27-schema-hardening-m720-standardization-plan.md :: `schema-hardening` `m720-standardization` plan
- 2026-05-27-schema-hardening-m840-standardization-plan.md :: `schema-hardening` `m840-standardization` plan
- 2026-05-27-schema-hardening-placeholder-eradication-plan.md :: `schema-hardening` `placeholder-eradication` plan
- 2026-05-28-centralized-output-redaction-plan.md :: `centralized-output-redaction` `centralized CLI output redaction` plan
- 2026-05-28-codebase-solidification-plan.md :: `codebase-solidification` `Codebase solidification recurring hardening epic` plan
- 2026-05-28-schema-hardening-continuity-conformance-plan.md :: `schema-hardening` `continuity ADR conformance` plan
- 2026-05-30-docs-architecture-plan.md :: `docs-architecture` `documentation epic` plan
- 2026-05-30-identity-primitives-plan.md :: `identity-primitives` placement rollout plan
- 2026-05-31-core-authority-plan.md :: `core-authority` `core-authority campaign` plan
- 2026-05-31-emit-envelope-schema-burndown-plan.md :: `emit-envelope-schema-burndown` plan
- 2026-05-31-schedule-predicate-catalogue-plan.md :: schedule-predicate-catalogue plan
- 2026-05-31-trabajador-del-mar-plan.md :: trabajador-del-mar W01-W03 plan
