---
tags:
  - '#reference'
  - '#core-authority-action-tracker-v2'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-types-v2-reference]]"
  - "[[2026-05-31-core-authority-constants-v2-reference]]"
  - "[[2026-05-31-core-authority-indirections-v2-reference]]"
  - "[[2026-05-31-core-authority-duplicates-v2-reference]]"
  - "[[2026-05-31-core-authority-imports-v2-reference]]"
  - "[[2026-05-31-core-authority-semantic-v2-reference]]"
---

# core-authority-action-tracker-v2 reference: unified action tracker

## 1. Campaign Summary

The core-as-authority campaign establishes src/aeat/core/ as the single authoritative
source for all cross-layer shared types, constants, protocols, and error hierarchies across
the hexagonal architecture. No layer below core/ may declare a symbol consumed by another
layer at the same or higher level; no layer above core/ may re-declare a symbol already
expressible through a core/ abstraction. This tracker consolidates the full surface
identified by six independent v2 mechanical audits (AST-level types, constants, indirections,
duplicates, imports, and GPU-accelerated semantic search) plus two latent runtime bugs
surfaced during synthesis. Every action row is a concrete, independently executable fix.
The tracker supersedes any v0 or v1 action lists, which were based on incomplete first-pass
data undercounting violations by one to two orders of magnitude. The ADR-amendment pipeline:
(a) confirm each action against the live code, (b) determine whether an existing ADR rule
covers it or an amendment is required (marked (amend) in the table), (c) execute as a
standalone commit with a verification test, (d) close the row.

---

## 2. Action Table

Actions grouped by category, ordered by risk descending within each category.
Columns: Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug.

### FIX actions (latent bugs -- execute first)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| FIX-001 | FIX | core/errors/_registry.py -- two classes registered as ExportFormatError: application/export/_errors.py (hierarchy CoreError) and adapters/outbound/aeat/export/_errors.py (hierarchy ExportError, ValueError) | Rename adapter class to AeatExportFormatError; keep application class canonical | 4 | `2026-05-31-core-authority-semantic-v2-reference` `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries Rule 3 | high | yes |
| FIX-002 | FIX | domain/calculations/registry/_export_parse.py:402 -- call _parse_decimal(field, raw) arg order reversed vs every other call site using _parse_decimal(raw, field) | Swap arguments at line 402; add regression test asserting correct decimal extracted | 1 | `2026-05-31-core-authority-semantic-v2-reference` | aeat-calculation-grounding | high | yes |

### RELOC actions (symbol in wrong layer -- move to authoritative layer)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| RELOC-001 | RELOC | core/i18n/_render.py:27 -- OUTPUT_LANGUAGE_ENV_VAR | core/external_constants.py | 3 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-002 | RELOC | core/i18n/_render.py:28 -- DEFAULT_OUTPUT_LANGUAGE | core/external_constants.py | 2 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-003 | RELOC | core/i18n/_render.py:29 -- SUPPORTED_OUTPUT_LANGUAGES | core/external_constants.py | 12 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-004 | RELOC | domain/calculations/registry/_groi_oracle.py:64 -- AEAT_GROI_URL | Must be consumed via Settings.external_constants() at call site | 5 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-005 | RELOC | domain/calculations/registry/_aeat_nif_iva_oracle.py:44 -- AEAT_NIF_IVA_VERIFICATION_URL | Must be consumed via Settings.external_constants() at call site | 3 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-006 | RELOC | domain/calculations/registry/_aeat_nif_iva_oracle.py:50 -- AEAT_NIF_IVA_ENTRY_URL | Must be consumed via Settings.external_constants() at call site | 3 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-007 | RELOC | domain/calculations/registry/_renta_web_open_oracle.py:24 -- RENTA_WEB_OPEN_LANDING_URL | Must be consumed via Settings.external_constants() at call site | 2 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-008 | RELOC | domain/calculations/registry/_renta_web_open_oracle.py:25 -- RENTA_WEB_OPEN_APP_URL | Must be consumed via Settings.external_constants() at call site | 3 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-009 | RELOC | application/workflow/_events.py:27 -- SYSTEM_BUCKET_ID (0 consumers, dead) | DELETE (see DELETE-001) | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| RELOC-010 | RELOC | application/workflow/_events.py:28 -- WORKFLOW_STATE_OBJECT_ID (0 consumers, dead) | DELETE (see DELETE-002) | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| RELOC-011 | RELOC | domain/fincas/_amortization_ledger.py:33 -- DAYS_PER_YEAR (0 consumers, dead) | DELETE (see DELETE-003) | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| RELOC-012 | RELOC | application/aggregation/_counterpart.py:311 -- THRESHOLD_347_EUR = Decimal("3005.06") | Merge with M347_THRESHOLD_EUR in domain/modelos; see MERGE-001 | 1 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | high | no |
| RELOC-013 | RELOC | application/aggregation/_foreign_assets.py:153 -- THRESHOLD_720_EUR_PER_CLASS = Decimal("50000.0") | Move to core/external_constants.py as MODELO_720_REPORTING_THRESHOLD_EUR | 1 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | medium | no |
| RELOC-014 | RELOC | application/aggregation/_shared_issue_reasons.py:27-31 -- UNSUPPORTED_DIRECTION, UNSUPPORTED_CURRENCY, UNCLASSIFIED_BUSINESS_STATE, PERSONAL_TRANSACTION, OUTSIDE_PERIOD (all 0 consumers) | DELETE if dead; verify 0 consumers before removing | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| RELOC-015 | RELOC | application/filing/_runtime_repository.py:5 -- imports from adapters layer | Break by introducing domain-layer repository protocol; adapter implements it | 1 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-016 | RELOC | application/auth/_sessions.py:15 -- imports from adapters layer | Introduce application-layer protocol; move adapter dependency to DI boundary | 1 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-017 | RELOC | application/calculations/_iva_compensation_history.py:13 -- imports from adapters layer | Introduce application-layer port interface | 1 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-018 | RELOC | application/live/_errors.py:8,13 -- imports from adapters layer | Move shared error base to core/errors/ | 2 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-019 | RELOC | application/filing/_export.py:36 -- imports from adapters layer | Extract shared export contract to application/export/_contracts.py | 1 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | medium | no |
| RELOC-020 | RELOC | application/ledger/_actions.py:21 -- imports from adapters layer | Extract repository protocol to application/ledger/_protocols.py | 1 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | medium | no |
| RELOC-021 | RELOC | domain/profile/_ccaa.py:56 -- CCAA Enum | CCAA is geographic; evaluate promotion to core/geography.py | 8 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | low | no |
| RELOC-022 | RELOC | domain/deadlines/_festivos.py:59 -- CalendarCCAA Enum | Merge with CCAA (100% geographic duplicate); see MERGE-002 | 6 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| RELOC-023 | RELOC | application/overview/_explain.py:35 -- _ProfileFactValue TypeAlias | domain/calculations/registry/_schema.py:944 ProfileFactValue canonical; alias application variant | 1 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | low | no |
| RELOC-024 | RELOC | domain/user_profile/_values.py:48 -- ProfileFactValue TypeAlias | domain/calculations/registry/_schema.py:944 ProfileFactValue canonical; see MERGE-003 | 3 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | medium | no |
| RELOC-025 | RELOC | core/ -- 36 edges importing from domain/ (illegal direction) | For each: move symbol to core/ or remove the core-layer import | 36 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 1 | high | no |
| RELOC-026 | RELOC | core/ -- 13 edges importing from application/ (illegal direction) | Same as RELOC-025; introduce protocol or move symbol | 13 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 1 | high | no |
| RELOC-027 | RELOC | core/ -- 4 edges importing from adapters/ (illegal direction) | Same as RELOC-025 | 4 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 1 | high | no |
| RELOC-028 | RELOC | domain/* -- 119 edges importing from adapters/ (89 from _repository.py files importing persistence shapes) | For each _repository.py: extract protocol to domain layer; adapter implements; remove inbound import | 119 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-029 | RELOC | domain/* -- 7 edges importing from application/ (illegal upward direction) | For each: move shared type to domain/ or core/ | 7 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-030 | RELOC | domain/* -- 5 edges importing from entrypoints/ (illegal direction) | Remove; no domain module may reference entrypoints | 5 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| RELOC-031 | RELOC | adapters/outbound/aeat/export/_errors.py -- ExportError (second ExportFormatError registration after FIX-001) | Rename to AeatExportFormatError and update all 4 call sites | 4 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries Rule 3 | high | no |
| RELOC-032 | RELOC | adapters/* -- 52 edges importing from application/ (17 bi-directional cycle edges in auth + Google adapters) | Break each cycle: extract shared interface to application/; adapter depends inward only | 52 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 3 | high | no |
| RELOC-033 | RELOC | application/aggregation/_renta_ledger.py:34 -- LedgerTransactionDirection alias | Remove alias; use TransactionDirection directly | 1 | `2026-05-31-core-authority-indirections-v2-reference` | architecture-boundaries | low | no |
| RELOC-034 | RELOC | application/aggregation/_renta_income_ledger.py:36 -- LedgerTransactionDirection alias | Remove alias; use TransactionDirection directly | 1 | `2026-05-31-core-authority-indirections-v2-reference` | architecture-boundaries | low | no |
| RELOC-035 | RELOC | application/aggregation/_iva_ledger.py:~39 -- LedgerTransactionDirection alias | Remove alias; use TransactionDirection directly | 1 | `2026-05-31-core-authority-indirections-v2-reference` | architecture-boundaries | low | no |
| RELOC-036 | RELOC | application/aggregation/test_renta_ledger_helpers.py:26 -- LedgerTransactionDirection alias | Remove alias in test; use TransactionDirection directly | 1 | `2026-05-31-core-authority-indirections-v2-reference` | architecture-boundaries | low | no |
| RELOC-037 | RELOC | BundleId declared in application/ instead of core/identity/ | Move to core/identity/__init__.py; update all callers | varies | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | medium | no |
| RELOC-038 | RELOC | EvidenceId declared in application/ instead of core/identity/ | Move to core/identity/__init__.py alongside other identity primitives; update callers | varies | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | medium | no |
| RELOC-039 | RELOC | domain/calculations/registry/__init__.py passthrough for 6 symbols (borderline shim) | Direct ~5 callers using domain.calculations short path to domain.calculations.registry.* directly | 5 | `2026-05-31-core-authority-indirections-v2-reference` | architecture-boundaries | low | no |
| RELOC-040 | RELOC | application/live/_snapshot_base.py:86 -- SnapshotRepository Protocol not formally implemented by 3 concrete repos | Add explicit Protocol registration or make repos structurally conform; add test | 3 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |

### MERGE actions (semantic duplicates -- consolidate to single canonical)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| MERGE-001 | MERGE | domain/modelos/_row_models.py:276 M347_THRESHOLD_EUR = Decimal("3005.06") AND application/aggregation/_counterpart.py:311 THRESHOLD_347_EUR = Decimal("3005.06") | Move canonical to core/external_constants.py as M347_THRESHOLD_EUR; delete application copy; migrate 4 callers | 4 | `2026-05-31-core-authority-constants-v2-reference` `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | high | no |
| MERGE-002 | MERGE | domain/deadlines/_festivos.py:59 CalendarCCAA AND domain/profile/_ccaa.py:56 CCAA (100% geographic duplicate per semantic audit) | Consolidate to CCAA in domain/profile/_ccaa.py; delete CalendarCCAA; migrate 6 callers in deadlines | 6 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| MERGE-003 | MERGE | domain/calculations/registry/_schema.py:944 ProfileFactValue AND domain/user_profile/_values.py:48 ProfileFactValue (same name, different definition) | Consolidate to single canonical in domain/calculations/registry/_schema.py; alias in user_profile if needed | 4 | `2026-05-31-core-authority-types-v2-reference` `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries | medium | no |
| MERGE-004 | MERGE | application/filing/reconciliation/_schema.py:34 ReconciliationStatus AND domain/submission/_models.py:22 SubmissionStatus (50% semantic overlap) | Audit whether ReconciliationStatus states are a subset of SubmissionStatus; document explicit divergence if not | 3 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| MERGE-005 | MERGE | domain/renta/_ledger_expenses.py:61 RentaReconciliationStatus AND application/filing/reconciliation/_kind.py ReconciliationStatus AND application/modelo/_reconcile.py ModeloReconciliationVerdict (100% semantic: Spanish/English split) | Unify under single core reconciliation status type; eliminate Spanish/English split | 5 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| MERGE-006 | MERGE | core/identity/_documents.py _hash_file AND domain/calculations/registry/_workbook_parity.py _hash_file AND application/ledger/_actions.py _hash_file (3 identical copies) | Move canonical to core/hashing.py; delete 2 copies; migrate callers | 3 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| MERGE-007 | MERGE | 5 independent SHA-256 one-liner hashlib calls across domain/ and application/ | Introduce core.hashing.sha256_file(path) helper; migrate 5 call sites | 5 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | low | no |
| MERGE-008 | MERGE | application/filing/_normalise_period (copy 1) AND application/filing/reconciliation/_normalise_period (copy 2) | Extract to application/filing/_period_utils.py; delete 2 copies | 4 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | low | no |
| MERGE-009 | MERGE | core/identity/validate_identity AND domain/calculations/registry/_normalise_tax_identity (validate_identity silently accepts malformed NIFs that _normalise_tax_identity would reject) | Consolidate validation logic in core/identity/; make domain call core; add test for malformed NIF rejection | 2 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | high | no |
| MERGE-010 | MERGE | 3 independent ValidatedRegistryAuthority.load() call sites with duplicate initialization boilerplate | Introduce factory helper in domain/calculations/registry/_authority.py; eliminate 2 duplicate call sites | 3 | `2026-05-31-core-authority-semantic-v2-reference` | aeat-registry-authority-flow | low | no |
| MERGE-011 | MERGE | core/errors/__init__.py ValidationError, domain/filing/_errors.py ValidationError, application/*.py ValidationError (2 more), adapters/_errors.py ValidationError (5 classes, no shared base) | Introduce core/errors/_validation.py CoreValidationError base; make all 5 descend from it | 5 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| MERGE-012 | MERGE | core/errors/_not_found.py NotFoundError AND domain/*/_not_found.py NotFoundError (2 more, 3 classes total) | Consolidate under core/errors/_not_found.py CoreNotFoundError; make domain subclasses explicit | 3 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | medium | no |
| MERGE-013 | MERGE | domain/iva/_classification.py _IVA_RATE_TO_VAT_KIND (3 entries) vs application/calculations/ similar mapping (5 entries) -- coverage hole | Consolidate to single authoritative IVA rate mapping in domain/iva/; document 2 missing entries; add coverage test | 4 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | high | no |
| MERGE-014 | MERGE | _STRICT_FROZEN annotated constant declared 10x across codebase (sig-collision -- differing values in some modules) | Consolidate to single canonical definition in core/ if values are identical; disambiguate with module-specific names if values differ | 10 | `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries | medium | no |
| MERGE-015 | MERGE | _ActorLabel declared 5x across domain/buckets and domain/modelos (name-collision) | Rename to domain-specific labels (BucketActorLabel, ModeloActorLabel etc.); eliminate collision | 5 | `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries | low | no |

### DELETE actions (dead code with 0 consumers)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| DELETE-001 | DELETE | application/workflow/_events.py:27 -- SYSTEM_BUCKET_ID = "system" (0 consumers) | Delete constant; no callers | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-002 | DELETE | application/workflow/_events.py:28 -- WORKFLOW_STATE_OBJECT_ID (0 consumers) | Delete constant; no callers | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-003 | DELETE | domain/fincas/_amortization_ledger.py:33 -- DAYS_PER_YEAR = Decimal("365") (0 consumers) | Delete constant; no callers | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-004 | DELETE | core/external_constants.py:301 -- LATIN_1_ENCODING (0 consumers) | Delete; encoding string is either inlined or covered by SEDE_BODY_ENCODING in adapter | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-005 | DELETE | core/external_constants.py -- PROVENANCE_SOURCE_MANUAL_CLI (0 consumers) | Delete constant; no callers | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-006 | DELETE | core/external_constants.py -- PDF_MIME_TYPE (0 consumers) | Delete; BINARY_MIME_TYPE covers the use case | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-007 | DELETE | adapters/persistence/storage/profile/assets.py -- ASSETS_AMORTIZATION_LEDGER_FILENAME (0 consumers) | Delete constant | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| DELETE-008 | DELETE | adapters/persistence/storage/profile/assets.py -- ASSETS_LEDGER_FILENAME (0 consumers) AND adapters/persistence/storage/profile/inventory.py INVENTORY_LEDGER_FILENAME (0 consumers) | Delete both constants; inline in namespace definition if still needed | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |

### RENAME actions (name collision or disambiguation)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| RENAME-001 | RENAME | adapters/outbound/aeat/export/_errors.py ExportFormatError (name collides with application/export/_errors.py ExportFormatError -- both registered in core/errors/_registry.py) | Rename to AeatExportFormatError; already covered by FIX-001 | 4 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries | high | no |
| RENAME-002 | RENAME | domain/calculations/registry/_schema.py:549 ModeloCapability (Literal alias) vs domain/transactions/_model_tier.py:50 ModelCapability (Enum) -- near-identical names, different kinds | Rename registry Literal to ModeloFilingCapability to eliminate confusion | 3 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | medium | no |
| RENAME-003 | RENAME | domain/calculations/registry/_workbook_parity.py:57 ParityStatus AND domain/calculations/registry/_parity_tapes.py:26 ParityStatus -- same name, two definitions | Consolidate to one definition in _parity_tapes.py; import in _workbook_parity.py; delete duplicate | 2 | `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries | medium | no |
| RENAME-004 | RENAME | domain/calculations/registry/_workbook_parity.py:58 EvidenceTier AND domain/calculations/registry/_schema.py:564 EvidenceTier -- same name, two Literal aliases | Consolidate to single definition in _schema.py; import in _workbook_parity.py | 2 | `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries | medium | no |
| RENAME-005 | RENAME | entrypoints/cli/_app_live.py:29 _VerifyVerdict AND application/live/_verify.py:42 VerifyVerdict -- near-identical Literal aliases, private vs public | Remove entrypoints duplicate; import VerifyVerdict from application layer | 1 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | low | no |
| RENAME-006 | RENAME | application/aggregation/_shared_issue_reasons.py UNSUPPORTED_DIRECTION, UNSUPPORTED_CURRENCY, UNCLASSIFIED_BUSINESS_STATE, PERSONAL_TRANSACTION, OUTSIDE_PERIOD (all 0 consumers) | Verify 0 consumers via grep; delete all 5 if confirmed dead | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| RENAME-007 | RENAME | domain/profile/assets/__init__.py:20 SCHEMA_VERSION = "1" AND domain/profile/inventory/__init__.py:34 SCHEMA_VERSION = "1" -- same name, both in domain/profile subpackages | Rename to ASSETS_SCHEMA_VERSION and INVENTORY_SCHEMA_VERSION respectively | 2 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | low | no |
| RENAME-008 | RENAME | adapters/outbound/aeat/auth/test_authenticator.py:60 SECRET_PASSPHRASE AND adapters/outbound/aeat/auth/test_certificate.py:41 SECRET_PASSPHRASE -- duplicate test constant | Extract to shared test fixture or deduplicate via conftest | 0 | `2026-05-31-core-authority-constants-v2-reference` | aeat-source-hygiene | low | no |
| RENAME-009 | RENAME | application/aggregation/_service.py:56 ERROR_CODES AND application/operator_surface/_contract.py:332 ERROR_CODES -- same name, different values | Rename to specific names: AggregationErrorCodes and OperatorSurfaceErrorCodes | 4 | `2026-05-31-core-authority-duplicates-v2-reference` | architecture-boundaries | medium | no |
| RENAME-010 | RENAME | adapters/outbound/aeat/_playwright.py:7,8 PlaywrightError and PlaywrightTimeoutError -- third-party boundary localisation aliases | No action -- correct pattern per indirections audit | 0 | `2026-05-31-core-authority-indirections-v2-reference` | architecture-boundaries | none | no |
| RENAME-011 | RENAME | domain/calculations/registry/_applicability.py:118 ApplicabilityVerdict -- evaluate whether this Enum belongs in core/errors/ as a shared verdict type | Audit consumers; if multi-layer, promote to core/ | varies | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | low | no |
| RENAME-012 | RENAME | adapters/persistence/storage/_namespace_registry.py SECURE_OBJECT_CATALOGUE_KEY, SECURE_OBJECT_DEFAULT_KEY, SECURE_OBJECT_WORKFLOW_STATE_KEY (2 consumers each) | Review whether these belong in domain/buckets/ or application/workflow/ per ownership | 2 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | low | no |
| RENAME-013 | RENAME | domain/calculations/registry/_censo_modelos.py CENSUS_MODELO_SERVICE_OWNER (string constant for service ownership, crosses layers) | Move to core/external_constants.py or core/service_registry.py | 2 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | low | no |
| RENAME-014 | RENAME | adapters/outbound/aeat/auth/_clave_movil.py:83 CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE (string, 4 consumers) -- lives in adapters but identifies a cross-layer diagnostic namespace | Move to core/external_constants.py or keep in adapters with documented rationale | 4 | `2026-05-31-core-authority-constants-v2-reference` | architecture-boundaries | low | no |

### MIGRATE actions (import-direction violations requiring structural move)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| MIGRATE-001 | MIGRATE | application/auth/_sessions.py -- imports adapters/ auth session shapes directly; 17 bi-directional adapter<->application edges in auth cluster | Extract AuthSessionProtocol to application/auth/_protocols.py; adapter implements; eliminate circular import | 17 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| MIGRATE-002 | MIGRATE | adapters/outbound/google/ -- 17 bi-directional cycle edges with application/calculations/ | Extract IvaCompensationRepositoryProtocol to application/calculations/_ports.py; Google adapter implements; break cycle | 17 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| MIGRATE-003 | MIGRATE | All domain/_repository.py files importing from adapters/persistence/ shapes (89 edges) | For each: extract StorageRecord protocol to domain layer; persistence adapter imports domain protocol and provides implementation | 89 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| MIGRATE-004 | MIGRATE | domain/* 5 edges importing from entrypoints/ | Identify the 5 files; any domain module importing entrypoints is a hard violation; extract referenced symbol to domain/ or core/ | 5 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| MIGRATE-005 | MIGRATE | domain/* 7 edges importing from application/ | Identify each file:line; move shared type to domain/ or core/; reverse dependency direction | 7 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 2 | high | no |
| MIGRATE-006 | MIGRATE | core/ 36 edges importing from domain/ | For each: move symbol to core/ or remove dependency; no core module may import domain | 36 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 1 | high | no |
| MIGRATE-007 | MIGRATE | core/ 13 edges importing from application/ | Same as MIGRATE-006 | 13 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 1 | high | no |
| MIGRATE-008 | MIGRATE | core/ 4 edges importing from adapters/ | Same as MIGRATE-006 | 4 | `2026-05-31-core-authority-imports-v2-reference` | architecture-boundaries Rule 1 | high | no |

### PROMOTE actions (identity primitives and error hierarchies requiring core promotion)

| Action ID | Category | Current site(s) | Target site | Consumers | Source audit | ADR rule | Risk | Latent-bug |
|---|---|---|---|---|---|---|---|---|
| PROMOTE-001 | PROMOTE | 54 bare-str sites emitting or consuming identity primitives without going through core/identity/ typed aliases (BucketId, ProfileId, NifString, NifIvaString) | Enroll each site in core/identity/ typed alias; add ADR rule extension for bare-str prohibition (amend) | 54 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries (amend) | high | no |
| PROMOTE-002 | PROMOTE | core/identity/__init__.py SubjectTaxId TypeAlias -- exported but 3 domain repository protocols do not declare it in method signatures | Annotate domain protocol method signatures; add structural conformance test | 3 | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | medium | no |
| PROMOTE-003 | PROMOTE | No shared CoreError base class for the 5 ValidationError subclasses across layers | Introduce core/errors/_base.py CoreError as root; make all layer-specific error hierarchies descend from it; see MERGE-011 | 5 | `2026-05-31-core-authority-semantic-v2-reference` | architecture-boundaries (amend) | medium | no |
| PROMOTE-004 | PROMOTE | AggregationSourceKind Enum declared in core/aggregation.py but not re-exported via core/__init__.py | Expose via core/__init__.py or core/aggregation/__init__.py; update callers to canonical import path | varies | `2026-05-31-core-authority-types-v2-reference` | architecture-boundaries | low | no |

---

## 3. Category Counts

| Category | Action IDs | Count |
|---|---|---|
| FIX | FIX-001 to FIX-002 | 2 |
| RELOC | RELOC-001 to RELOC-040 | 40 |
| MERGE | MERGE-001 to MERGE-015 | 15 |
| DELETE | DELETE-001 to DELETE-008 | 8 |
| RENAME | RENAME-001 to RENAME-014 | 14 |
| MIGRATE | MIGRATE-001 to MIGRATE-008 | 8 |
| PROMOTE | PROMOTE-001 to PROMOTE-004 | 4 |
| **Grand total** | | **91** |

Note on constants population: The v2 constants audit surfaces 2,435 total constants with
259 in the gap vs external_constants.py and 339 cross-layer coupling instances. The 91
action rows above aggregate same-direction violations into cluster rows (e.g., MIGRATE-003
covers 89 domain repository files as a single structural migration). Expanding to one row
per file would produce 250+ rows for MIGRATE-003 alone. The cluster granularity is
intentional: the Plan maps one Step per cluster row, with sub-steps per file within each
executing Step.

---

## 4. Per-Layer Impact

| Layer | Actions touching this layer | Primary role in action |
|---|---|---|
| core | RELOC-001..003, RELOC-025..027, MERGE-006..009, MERGE-011..012, PROMOTE-001..004, MIGRATE-006..008, DELETE-004..006 | Target for relocations; source of illegal outbound imports |
| domain | RELOC-004..008, RELOC-021..024, RELOC-028..030, RELOC-039..040, MERGE-001..005, MERGE-013..015, RENAME-002..004, MIGRATE-003..005, DELETE-003 | Largest violation surface; repository protocol extraction needed |
| application | RELOC-009..020, RELOC-033..038, MERGE-008..010, RENAME-006..009, MIGRATE-001..002, DELETE-001..002 | Middle layer with most upward import violations |
| adapters | RELOC-031..032, FIX-001, RENAME-001, MIGRATE-001..002, DELETE-007..008 | Bi-directional cycle edges with application; ExportFormatError collision |
| entrypoints | RELOC-030, RENAME-005, MIGRATE-004 | Illegal imports from domain; Literal duplicate |

---

## 5. Latent Bug Summary

Both latent bugs discovered via GPU-accelerated semantic search (RAG audit PAIR ER-01 and
the reversed-argument finding).

**FIX-001 -- ExportFormatError double registration (high risk)**
Two classes share the name ExportFormatError in the core/errors/_registry.py registry.
application/export/_errors.py inherits CoreError (correct hierarchy).
adapters/outbound/aeat/export/_errors.py inherits ExportError and ValueError (incorrect
hierarchy; ValueError leaks into the shared error surface). Any code catching ExportFormatError
by registry lookup may catch the wrong class or fail to catch the right one depending on
import order. The adapter class must be renamed AeatExportFormatError and the 4 call sites
updated before any new error handling code is added to the export path.

**FIX-002 -- _parse_decimal reversed argument order (high risk)**
domain/calculations/registry/_export_parse.py:402 calls _parse_decimal(field, raw) while
every other call site in the same file uses _parse_decimal(raw, field). This silently
extracts the wrong decimal value from export records; the field name is interpreted as the
raw string and vice versa, producing either a validation error or a silently wrong Decimal.
A regression test must assert that _parse_decimal extracts the correct numeric value from a
known fixture string before the fix is committed, so any reintroduction is caught.

---

## 6. Protect List

The following packages and patterns have been audited and classified as legitimate
architectural patterns. Do NOT add RELOC/DELETE/MERGE actions targeting these sites.

| Site | Classification | Rationale |
|---|---|---|
| aeat.core.identity | re-export-wall-shim LEGITIMATE | 8 symbols from 5 private submodules; documented public wall |
| aeat.adapters.persistence.storage | re-export-wall-shim LEGITIMATE | 100+ symbols from 15+ internal submodules; documented public wall |
| aeat.adapters.persistence.storage.sql | re-export-wall-shim LEGITIMATE | 15 symbols from engine/session/repository/records |
| aeat.application.auth | hybrid LEGITIMATE | Local defs (AuthProviderKind, AuthProviderDescription, AuthProvider) + catalogue re-exports; IS the canonical declaration site |
| domain.transactions.__init__ lazy __getattr__ | documented pattern | Lazy __getattr__ for 4 repository symbols to avoid eager SQLAlchemy import |
| domain.profile.__init__ lazy __getattr__ | documented pattern | Lazy __getattr__ for PROFILE_KEYS to break import cycle with wizard catalogue |
| application.user_profile.__init__ | side-effect-import | Imports _language_resolver for i18n resolver registration |
| domain.renta.__init__ | side-effect-import | Imports _first_slice_routing_integrity for registry validator registration |
| core/profile.py:142,149,156 importlib.import_module | cycle-breaking | Lazy cycle-breaking resolvers in __getattr__ handlers for domain.deadlines and domain.profile |
| Translatable as tr (13+ files) | brevity alias | Module-local implementation-internal brevity alias; not public API |
| Third-party boundary aliases (PlaywrightError, PikepdfError, XlrdSheet, AbstractSet) | adapter isolation | Correct pattern: localise third-party names at adapter boundary |
| 28 conditional imports (google-auth, keyring, playwright-stealth, questionary, openpyxl) | optional dependency guards | All guard optional third-party packages; none are internal shims |
| ENTRY constant 42x in domain/portals/_entries/ | intentional per-portal pattern | Each portal entry module defines its own ENTRY; structural not a duplicate |
| domain/calculations/registry/_snapshot.py:57 importlib.import_module | plugin loader | Dynamic plugin load for registry extension modules |

---

## 7. Open ADR Questions

The following questions require ADR amendment or new ADR before execution of the affected
action rows.

1. **PROMOTE-001 bare-str prohibition scope**: Should the bare-str ADR rule extend to all
   identity primitive use sites (BucketId, ProfileId, NifString, NifIvaString) or only to
   cross-layer boundaries? The answer determines whether 54 sites or a subset are in scope.
   Currently no ADR rule explicitly prohibits bare str where a typed alias exists.

2. **CCAA unification (MERGE-002, RELOC-021)**: Should CCAA and CalendarCCAA be merged into
   a single core/geography.py type, or kept in domain/profile/ and domain/deadlines/
   respectively with a documented alias? The answer determines whether core/ grows a new module.

3. **CoreError base hierarchy (PROMOTE-003, MERGE-011)**: Should a CoreError root class be
   introduced? All layer-specific error hierarchies must descend from it if yes. Requires
   ADR amendment to architecture-boundaries.

4. **Repository protocol ownership (MIGRATE-003)**: Should domain-layer repository protocols
   live in domain/*/_protocols.py or in a shared core/persistence/ module? The answer
   affects 89 files and the test strategy for structural conformance.

5. **External URL constants vs Settings (RELOC-004..008)**: Should URL constants derived from
   Settings.external_constants() be module-scope AnyUrl instances (current pattern) or should
   every call site call Settings.external_constants() lazily? The lazy pattern eliminates the
   domain-layer AnyUrl constants but adds noise at call sites.

6. **ProfileFactValue canonical site (MERGE-003, RELOC-023)**: Which of the two ProfileFactValue
   declarations is canonical: domain/calculations/registry/_schema.py or domain/user_profile/_values.py?
   The answer determines which is deleted and which is aliased.

7. **IVA rate mapping completeness (MERGE-013)**: Are the 2 missing entries in the
   domain/iva/_classification.py _IVA_RATE_TO_VAT_KIND mapping intentionally absent
   (regime-specific exclusion) or an oversight? A BOE or registry reference must confirm
   before the merge executes.

8. **_STRICT_FROZEN value semantics (MERGE-014)**: The 10 declarations of _STRICT_FROZEN
   across modules may have subtly different model_config values. An ADR must decide whether
   a single canonical ConfigDict should be exported from core/models.py or whether per-module
   declarations are intentionally distinct.

9. **SnapshotRepository Protocol enforcement (RELOC-040)**: Should Protocol conformance for
   LiveBorradorRepository, LiveCensusRepository, and LiveExpedientesRepository be enforced via
   explicit runtime_checkable decorator and isinstance assertion in tests, or via mypy
   structural subtyping only? The answer determines the test strategy.

10. **Indirection wall for domain.calculations (RELOC-039)**: Is the domain.calculations
    passthrough __init__ a permanent public API surface or a borderline shim that should be
    eliminated? If permanent, document it in the protect list and close RELOC-039. If shim,
    migrate the ~5 callers and delete the passthrough.
