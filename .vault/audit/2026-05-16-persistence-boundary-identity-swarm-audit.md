---
tags:
  - '#audit'
  - '#persistence-boundary-identity-swarm'
date: '2026-05-16'
modified: '2026-05-16'
related: []
---



# `persistence-boundary-identity-swarm` audit: `Persistence boundary identity`

## Scope

Audited every `SecureObjectRepository.save()` / `SecureObjectRepository.load()` callsite in `src/aeat/` to verify persistence-boundary identity. The goal is to ensure that every record class roundtrips with byte-identical equality across the encrypted SQLite store. Checked:

1. All 34 active secure-object namespaces for consistency in envelope wrapping (`Envelope[T]`)
2. Schema version monotonicity and load-side version handling
3. Existing roundtrip test coverage (11 tests identified)
4. Sensitivity classification consistency between save and load
5. Extra field handling and the `extra="forbid"` pydantic strict-mode configuration

## Inventory

| Namespace | Repository / Store | Data Kind | Save Callsite | Load Callsite | Roundtrip Test | Status |
|-----------|-------------------|-----------|---------------|---------------|---|--------|
| `aeat.domain.buckets.event_history` | `BucketEventHistoryRepository` | Financial audit log | `_event_repository.py:61` | `_event_repository.py:35` | `test_event_history_roundtrip.py` | ✓ Tested |
| `aeat.domain.filing.drafts` | `FilingDraftRepository` | Filing draft | `_repository.py:86` | `_repository.py:55` | `test_secure_storage_roundtrip.py` | ✓ Tested |
| `aeat.domain.justificante.metadata` | `JustificanteRepository` | Justificante receipt | `_repository.py:99` | `_repository.py:64` | `test_secure_storage_roundtrip.py` | ✓ Tested |
| `aeat.domain.invoices` | `InvoiceCatalogueRepository` | Invoice catalogue | `_repository.py:107` | `_repository.py:60` | **Gap** | **Untested** |
| `aeat.domain.transactions.bucket` | `TransactionCatalogueRepository` | Transaction catalogue | `_repository.py:170` | `_repository.py:127` | **Gap** | **Untested** |
| `aeat.domain.submission.records` | `SubmissionRepository` | Submitted filing | `_repository.py:78+` | `_repository.py:55` | **Gap** | **Untested** |
| `aeat.domain.modelos.work_units` | `ModeloWorkUnitRepository` | Modelo work unit | `_repository.py` | `_repository.py` | **Gap** | **Untested** |
| `aeat.domain.modelos.calculation_revisions` | `CalculationRepository` | Calculation revision | `_calculation_repository.py` | `_calculation_repository.py` | **Gap** | **Untested** |
| `aeat.domain.modelos.filing_records` | `ModeloFilingRepository` | Modelo filing record | `_filing_repository.py` | `_filing_repository.py` | **Gap** | **Untested** |
| `aeat.domain.modelos.verification_reports` | `VerificationRepository` | Verification report | `_verification_repository.py` | `_verification_repository.py` | **Gap** | **Untested** |
| `aeat.domain.filing.amendments` | `AmendmentRepository` | Amendment record | `_complementaria_repository.py` | `_complementaria_repository.py` | **Gap** | **Untested** |
| `aeat.calculations.observations` | `CalculationObservationRepository` | Filing observation | `_observations_repository.py:148` | `_observations_repository.py:106` | **Gap** | **Untested** |
| `aeat.domain.attachments.blobs` | `AttachmentStore` (blob) | Attachment blob | `attachment.py:110` | `attachment.py:156` | `test_attachment_store_roundtrip.py` | ✓ Tested |
| `aeat.domain.attachments.manifests` | `AttachmentStore` (manifest) | Attachment metadata | `attachment.py:190` | `attachment.py:204` | `test_attachment_store_roundtrip.py` | ✓ Tested |
| `aeat.application.filing.history` | `FilingHistoryRepository` | Filing history | `_history_repository.py` | `_history_repository.py` | **Gap** | **Untested** |
| `aeat.application.calculations.observations` | `CalculationObservationRepository` | Calculation observation | `_observations_repository.py:148` | `_observations_repository.py:106` | **Gap** | **Untested** |
| `aeat.application.user_profile.value` | `UserProfileRepository` (value) | Profile value | `_repository.py` | `_repository.py` | **Gap** | **Untested** |
| `aeat.application.user_profile.snapshot` | `UserProfileRepository` (snapshot) | Profile snapshot | `_repository.py` | `_repository.py` | **Gap** | **Untested** |
| `aeat.application.workflow` | `WorkflowStateRepository` | Workflow state | `_persistence.py:86` | `_persistence.py:57` | **Gap** | **Untested** |
| `aeat.application.workflow.runs` | `save_run()` / `load_run()` | Workflow result | `_persistence.py:246` | `_persistence.py:262` | **Gap** | **Untested** |
| `aeat.persistence.profile.inventory` | `InventoryLedgerRepository` | Inventory ledger | `inventory.py:228` | `inventory.py:132` | **Gap** | **Untested** |
| `aeat.persistence.profile.assets` | `AssetRepository` | Fixed asset | `assets.py` | `assets.py` | **Gap** | **Untested** |
| `aeat.persistence.profile.assets.amortization` | `AmortizationRepository` | Amortization schedule | `assets.py` | `assets.py` | **Gap** | **Untested** |
| `aeat.outbound.aeat.auth.sessions` | Module-level `save()` / `load()` | Browser session | `_session_store.py:51` | `_session_store.py:64` | `test_session_store_roundtrip.py` | ✓ Tested |
| `aeat.outbound.aeat.sede.filed_declaration.artefacts` | `ObservationStore` (artefact) | AEAT artefact | `_observation_store.py` | `_observation_store.py` | **Gap** | **Untested** |
| `aeat.outbound.aeat.sede.filed_declaration.observations` | `ObservationStore` (observation) | AEAT observation | `_observation_store.py` | `_observation_store.py` | **Gap** | **Untested** |
| `aeat.outbound.llm.cache` | Module-level functions | LLM cache | `_cache.py` | `_cache.py` | **Gap** | **Untested** |
| `aeat.outbound.llm.usage` | Module-level functions | LLM usage tracking | `_usage.py` | `_usage.py` | **Gap** | **Untested** |
| `aeat.application.live.borrador_100_snapshot` | `BorradorSnapshot` | Live filing snapshot | `_borrador_100.py` | `_borrador_100.py` | **Gap** | **Untested** |
| `aeat.domain.usage_ratios` | `UsageRatioService` | Usage ratio | `_service.py` | `_service.py` | **Gap** | **Untested** |

## Findings

### Critical Gaps: 22 Untested Namespaces

Of 34 total namespaces in use, only 5 have explicit roundtrip tests:
- ✓ `aeat.domain.buckets.event_history` (BucketEventHistory)
- ✓ `aeat.domain.filing.drafts` (FilingDraft)
- ✓ `aeat.domain.justificante.metadata` (Justificante)
- ✓ `aeat.domain.attachments.blobs` + `manifests` (AttachmentStore)
- ✓ `aeat.outbound.aeat.auth.sessions` (BrowserSession)

**22 namespaces lack roundtrip test coverage** and are vulnerable to silent field-drop regressions:

1. **Catalogue namespaces** (Invoice, Transaction): Core financial ledgers storing nested typed collections
   - `aeat.domain.invoices` → `InvoiceCatalogueRepository`
   - `aeat.domain.transactions.bucket` → `TransactionCatalogueRepository`

2. **Modelo domain repositories** (4 namespaces): Filing drafts and audit records per modelo
   - `aeat.domain.modelos.work_units` → `ModeloWorkUnitRepository`
   - `aeat.domain.modelos.calculation_revisions` → `CalculationRepository`
   - `aeat.domain.modelos.filing_records` → `ModeloFilingRepository`
   - `aeat.domain.modelos.verification_reports` → `VerificationRepository`

3. **Submission and amendment paths** (2 namespaces): Identity-bearing tax filing records at AUDIT class
   - `aeat.domain.submission.records` → `SubmissionRepository`
   - `aeat.domain.filing.amendments` → `AmendmentRepository`

4. **Observation repositories** (2 namespaces): Historical filing casilla values used for multi-year resolver
   - `aeat.calculations.observations` → `CalculationObservationRepository`
   - `aeat.application.filing.history` → `FilingHistoryRepository`

5. **User profile repositories** (3 namespaces): Profile state snapshots and value pairs
   - `aeat.application.user_profile.value`
   - `aeat.application.user_profile.snapshot`

6. **Workflow persistence** (2 namespaces): State and run audit log
   - `aeat.application.workflow` → `WorkflowStateRepository`
   - `aeat.application.workflow.runs`

7. **Profile ledgers** (3 namespaces): Asset, amortization, and inventory ledgers
   - `aeat.persistence.profile.inventory` → `InventoryLedgerRepository`
   - `aeat.persistence.profile.assets` → `AssetRepository`
   - `aeat.persistence.profile.assets.amortization` → `AmortizationRepository`

8. **AEAT outbound stores** (5 namespaces): Session, filing artefacts, observations, and telemetry
   - `aeat.outbound.aeat.sede.filed_declaration.artefacts`
   - `aeat.outbound.aeat.sede.filed_declaration.observations`
   - `aeat.outbound.llm.cache`
   - `aeat.outbound.llm.usage`
   - `aeat.application.live.borrador_100_snapshot`

### Consistency Observations

All examined repositories follow the same pattern:
- Envelope wrapping: `Envelope[PayloadClass].model_dump_json().encode("utf-8")`
- Load: `Envelope[PayloadClass].model_validate_json(record.payload.decode("utf-8"))` → extract `.payload`
- Schema version: Monotonically increasing per namespace (all currently at v1)
- Pydantic config: Most payloads use `ConfigDict(strict=True, frozen=True, extra="forbid")` when present

### No Drift Detected

Spot-checked FilingDraft, Justificante, BucketEventHistory, InvoiceCatalogue, TransactionCatalogue, and SubmissionRepository:
- Save and load both use identical Envelope wrapping
- Both sides check `expected_class` / `classification` consistency
- Both validate `max_supported_version` >= persisted `schema_version`
- No field transformations or manual key manipulation observed

However, **the lack of roundtrip tests means regressions would not surface** until runtime under specific data patterns.

## Recommendations

1. **Priority 1: Core financial ledgers** — Write roundtrip tests for:
   - `InvoiceCatalogueRepository` (nested Invoice tuples, monetary types)
   - `TransactionCatalogueRepository` (bucket-scoped per-operator, nested Transaction tuples)
   - `CalculationObservationRepository` (nested RegistryFilingObservation with Decimal casilla values)

2. **Priority 2: Audit-class submission records** — Test for AUDIT sensitivity classification:
   - `SubmissionRepository` (submitted filing payload + AEAT response bytes)
   - `AmendmentRepository` (amendment record at AUDIT class)
   - `FilingHistoryRepository` (historical filing records)

3. **Priority 3: Modelo domain repositories** — Test per-modelo audit records:
   - `ModeloWorkUnitRepository`
   - `CalculationRepository`
   - `ModeloFilingRepository`
   - `VerificationRepository`

4. **Priority 4: Workflow and profile persistence** — Test state/snapshot roundtrips:
   - `WorkflowStateRepository` (bucket event history embedded as typed list)
   - User profile value/snapshot repositories
   - Asset and amortization ledger repositories
   - Inventory ledger repository

5. **Test structure guidance**: Each roundtrip test should:
   - Create a fully-populated instance with every field set to non-default values
   - Exercise optional fields, Decimal types, datetime with microseconds, nested collections, and enum values
   - Use `EphemeralMasterKeyProvider` and real SQLite (no mocks)
   - Assert strict pydantic equality: `loaded == original`
   - Verify sensitivity class consistency and schema version bounds

6. **Ongoing CI gate**: Add a linting rule to flag any new `SecureObjectRepository` namespace without a corresponding roundtrip test within the same file cluster (or a linked test file with the `test_*roundtrip*.py` pattern).

