---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
tags:
  - '#research'
  - '#code-duplication-sweep'
date: '2026-05-19'
related: []
title: "Accidental Redefinition and Overlapping Module Definitions Audit"
source: "Manual Codebase Sweep and AST Analysis"
relevance: 10
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `code-duplication-sweep` research: `Accidental Redefinition and Overlapping Module Definitions Audit`

This audit presents the results of a comprehensive manual and automated sweep of the `src/aeat` codebase, focused on identifying accidental symbol redefinitions, duplicate class names, and overlapping module responsibilities. Having duplicate identifiers across different subdomains increases cognitive overhead, causes import shadowed variables, and introduces fragile error-catching paths.

---

## Duplicated Symbol Findings

Below is the structured, per-row inventory of duplicated classes and exception hierarchies discovered during the codebase sweep, along with their location, design differences, and architectural impact.

### 1. `CCAA` (StrEnum)
* **Locations**:
  * `src/aeat/domain/deadlines/_festivos.py`
  * `src/aeat/domain/profile/_ccaa.py`
* **Structural & Semantic Differences**:
  * The deadline/calendar enum uses uppercase ISO-3166-2:ES country/region subcodes (e.g., `ES-AN`, `ES-MD`, `ES-PV`) and spans all Spanish territories (including Foral regimes like País Vasco/Navarra and autonomous cities like Ceuta/Melilla).
  * The profile/residence enum uses lowercase ordinary Spanish region names (e.g., `andalucia`, `madrid`, `catalunya`) and strictly represents common-regime territories (excluding Foral regimes and autonomous cities).
* **Architectural Risk**:
  * Cognitive overhead when developers deal with tax residence vs. deadline computation in the same context.
  * Importing both enums in the same file causes name shadow issues.
  * High risk of mismatched key lookups in downstream routing tables.

### 2. `ForeignAssetObservation` (Pydantic BaseModel)
* **Locations**:
  * `src/aeat/application/aggregation/_foreign_assets.py`
  * `src/aeat/domain/calculations/registry/_bindings.py`
* **Structural & Semantic Differences**:
  * The aggregator model represents the raw, unrefined ingest state. It uses string schemas for dates, boolean flags like `held_at_year_end`, and parses the `ForeignAssetClass` enum.
  * The registry model represents the formalized, post-processed boundary inputs bound directly to Modelo 720 casillas. It enforces strict `datetime.date` objects for acquisition dates, `Decimal` for valuations, and uppercase ISO codes for currency and countries.
* **Architectural Risk**:
  * Developers tracing the ingestion pipeline can easily conflate the pre-aggregation data layout with the computed registry bindings.
  * Type validation gaps (e.g., strings vs. real dates) can lead to silent validation failures if models are crossed.

### 3. `KdfParams` (Pydantic BaseModel)
* **Locations**:
  * `src/aeat/adapters/persistence/storage/bucket/_manifest.py`
  * `src/aeat/adapters/persistence/storage/master_key/_kdf_params.py`
* **Structural & Semantic Differences**:
  * The manifest-side model is deliberately lenient. It allows any historically valid Argon2id parameter values to guarantee backward compatibility with previously enrolled secure buckets.
  * The master key model is highly constrained, wrapping strict OWASP-baseline validators (e.g., memory cost bounded between 19MiB and 1GiB, time cost between 2 and 16, and literal 32-byte output lengths) to govern new provisions.
* **Architectural Risk**:
  * High risk of importing the wrong schema. If a developer registers a new bucket using the manifest-side `KdfParams`, it will bypass the strict cryptographic baseline validation, potentially allowing weak encryption keys to be provisioned.

### 4. `ModeloRepository` (Class)
* **Locations**:
  * `src/aeat/core/resources/_repos/modelos.py`
  * `src/aeat/adapters/persistence/storage/sql/repository.py`
* **Structural & Semantic Differences**:
  * The core resource repository acts as a read-only façade wrapping `ValidatedRegistryAuthority` to yield static, built-in tax form metadata definitions (e.g., `ModeloDefinition`).
  * The persistence SQL repository acts as a write-active database repository managing dynamic, user-created tax filing entities (e.g., `ModeloRecord`).
* **Architectural Risk**:
  * Severe naming collision. Developers importing `ModeloRepository` to read registry definitions or persist dynamic filings face high potential for type confusion and mismatched method signatures.

### 5. `PortalRow` (Class/BaseModel)
* **Locations**:
  * `src/aeat/adapters/persistence/storage/sql/_orm.py`
  * `src/aeat/application/portals/_service.py`
* **Structural & Semantic Differences**:
  * The ORM class represents real database entries in the `portals` table, supporting relational foreign keys and DB constraint checks.
  * The service class is a lightweight presentation Pydantic DTO used exclusively for CLI outputs, stripping DB surrogate IDs and localizing portal labels.
* **Architectural Risk**:
  * Terminology collision. "Row" typically denotes database ORM elements. Reusing it for application presentation models violates naming consistency and invites shadowing.

### 6. `StorageError` and `StorageValidationError` (Exceptions)
* **Locations**:
  * `src/aeat/adapters/outbound/storage/_errors.py`
  * `src/aeat/adapters/persistence/storage/errors.py`
* **Structural & Semantic Differences**:
  * Both packages share the final namespace `storage` (`outbound/storage` vs. `persistence/storage`).
  * Both declare identical exception families (`StorageError` and `StorageValidationError`) but target different boundaries (outbound API adapters vs. at-rest database persistence).
* **Architectural Risk**:
  * Critical import and catching hazard. Developers attempting to catch a `StorageError` may import from the wrong package, allowing uncaught exceptions to crash the application due to class mismatch.

### 7. `WorkUnitNotFoundError` (Exceptions)
* **Locations**:
  * `src/aeat/application/modelo/_actions.py`
  * `src/aeat/application/modelo/_reconcile.py`
* **Structural & Semantic Differences**:
  * The action error inherits from `ModeloError` and `KeyError`, and is officially exported in the package `__init__.py`.
  * The reconciliation error inherits from `AeatError` and is raised exclusively by `modelo_reconcile` inside `_reconcile.py`, remaining unexported.
* **Architectural Risk**:
  * High-severity catching bug. Downstream clients importing `WorkUnitNotFoundError` from `aeat.application.modelo` will fail to catch errors thrown by `modelo_reconcile` because they represent two distinct Python classes under the hood.

### 8. `Borrador100Snapshot` (Pydantic BaseModel & Storage Engines)
* **Locations**:
  * `src/aeat/application/live/_borrador.py`
  * `src/aeat/application/live/_borrador_100.py`
* **Structural & Semantic Differences**:
  * The model in `_borrador.py` supports a local, raw filesystem line-delimited JSON database located in `settings.aeat_audit_dir / "live" / "borrador100"`.
  * The model in `_borrador_100.py` is the official secure-bucket active object database model using `SecureObjectRepository` with detailed state transition tracking (`active`, `superseded`, `discarded`).
* **Architectural Risk**:
  * Severe overlapping implementation and split state storage for drafts. Maintaining two completely separate, active persistence strategies for Modelo 100 drafts within the same application package represents severe code duplication and technical debt.

### 9. `_Fixture` (Class)
* **Locations**:
  * `src/aeat/tests/fixtures/financial/n26/_generate.py`
  * `src/aeat/tests/fixtures/justificantes/_generate.py`
* **Structural & Semantic Differences**:
  * Internal helper classes for managing raw test fixture schema shapes.
* **Architectural Risk**:
  * Negligible production risk, as these are restricted to test fixture generation utilities, but naming them identically under the same codebase is a minor stylistic overlap.

### 10. `Renta` vs. `Rental` (Phonetic & Semantic Overlap)
* **Locations**:
  * `src/aeat/domain/renta/`
  * `src/aeat/domain/rental/`
* **Structural & Semantic Differences**:
  * `domain/renta` governs the personal income tax calculations (IRPF) for Spanish taxpayers, utilizing Spanish-centric modeling (`RentaDeductibleExpenseFact`, `RentaFamilyProfile`).
  * `domain/rental` governs properties, real estate, and tenancy operations (Fincas), utilizing English terminology (`RentalExpense`, `RentalContract`).
* **Architectural Risk**:
  * Severe spelling and conceptual confusion hazard. The Spanish word "Renta" is very phonetically and typographically close to the English word "Rental". A developer working on real estate income tax declarations can easily import models from the wrong package, causing type mismatches or incorrect formulas (e.g., using `RentalExpense` inside a general `renta` deduction context).

### 11. `IVA` vs. `VAT` (Dual Acronym Architectures)
* **Locations**:
  * `src/aeat/domain/vat/`
  * `src/aeat/domain/invoices/_iva_classification.py`
  * `src/aeat/application/aggregation/_iva_ledger.py`
* **Structural & Semantic Differences**:
  * The `vat` package implements general Value-Added Tax models in English (`VatClassification`, `VatReconciliation`).
  * The `iva` files implement the Spanish Value-Added Tax specifications (`IvaInvoiceClassification`, `_IvaLedgerSelector`).
* **Architectural Risk**:
  * Duplicate, split domain architectures. Parallel classification logic exists in `IvaInvoiceClassification` and `VatClassification`. This divergence creates fragmented logic routes, naming inconsistencies, and double implementation of identical tax schemas.

### 12. `Filing` vs. `Modelo` vs. `Declaración` (Triple Terminology Split)
* **Locations**:
  * `src/aeat/domain/filing/`
  * `src/aeat/domain/modelos/`
  * `src/aeat/adapters/inbound/declaracion/`
* **Structural & Semantic Differences**:
  * The domain uses the English term `FilingDraft` / `FilingRecord` for tax return returns.
  * SQL persistence and ORM schemas use the Spanish term `ModeloRecord` / `ModeloRow` / `ModeloRepository`.
  * The inbound parser uses `DeclaracionObservation` under `inbound/declaracion/`.
* **Architectural Risk**:
  * Significant cognitive translation cost across architectural layers. A developer tracing a payload from inbound ingest to persistence must map `Declaracion` -> `Filing` -> `Modelo` as they traverse boundary lines.

### 13. `Borrador` vs. `Draft` vs. `Snapshot` (Triple State Abstractions)
* **Locations**:
  * `src/aeat/application/live/_borrador_100.py`
  * `src/aeat/domain/filing/_schema.py`
  * `src/aeat/application/live/_census.py`
* **Structural & Semantic Differences**:
  * Sede-captured records are named `Borrador100Snapshot` or `CensusSnapshot` (using the hybrid Spanish/English word "Borrador" alongside "Snapshot").
  * Domain representations are called `FilingDraft` (using "Draft").
* **Architectural Risk**:
  * Terminology pollution. Combining raw state capture nouns with domain nouns makes the exact lifecycle state of a record highly ambiguous (e.g., is a `Borrador100Snapshot` in the same state lifecycle as a `FilingDraft`?).

### 14. `Repository` (Class Name Collision)
* **Locations**:
  * `src/aeat/adapters/persistence/storage/sql/repository.py`
  * `src/aeat/core/resources/_repository.py`
* **Structural & Semantic Differences**:
  * The SQL persistence `Repository` serves as a write-active database collection for ORM elements.
  * The core resource `Repository` serves as a read-only generic `Repository[T, K]` for bundled packaged data (e.g. `NormativeRepository`).
* **Architectural Risk**:
  * Name shadowing and import confusion. If a developer imports `Repository` they might inadvertently pull the read-only core resource base instead of the SQL DB repository, causing type checking and method resolution errors.

### 15. `FilingDraftStatus` vs. `DraftStatus` (Dual State Enums)
* **Locations**:
  * `src/aeat/domain/filing/_schema.py` (`FilingDraftStatus`)
  * `src/aeat/domain/submission/_protocols.py` (`DraftStatus`)
* **Structural & Semantic Differences**:
  * Both enums share the exact same values (`ACKNOWLEDGED`, `AMENDED`, `APPROVAL_STALE`, `APPROVED`, `CANCELLED`, `DRAFT`, `READY_TO_SUBMIT`, `REJECTED`, `SUBMITTED`, `VALIDATED`).
  * One is scoped to filing schemas, the other to submission protocols.
* **Architectural Risk**:
  * Double definition of lifecycle states. A state machine update requires synchronization between two distinct domain enumerations. Functions checking statuses could fail if passed the semantically equivalent but typographically different enum class.

### 16. `InvoiceKind` vs. `InvoiceDirection` (Terminology Overlap)
* **Locations**:
  * `src/aeat/domain/invoices/_enums.py` (`InvoiceKind`)
  * `src/aeat/domain/vat/_classification.py` (`InvoiceDirection`)
* **Structural & Semantic Differences**:
  * Both share exact values (`ISSUED`, `RECEIVED`).
  * `InvoiceKind` is used generally for business operations, whereas `InvoiceDirection` is scoped specifically to Value-Added Tax classification routing.
* **Architectural Risk**:
  * Cognitive overlap. Representing the same binary concept (inbound vs. outbound invoice) via two different enum types requires developers to map between `Kind` and `Direction` depending on which subsystem they are interacting with.

### 17. `IssuerResidency` vs. `CustomerResidency` (Symmetric Duplication)
* **Locations**:
  * `src/aeat/domain/vat/_classification.py`
* **Structural & Semantic Differences**:
  * Both share exact values (`ES_CANARIAS`, `ES_CEUTA_MELILLA`, `ES_MAINLAND`, `EU_MEMBER`, `THIRD_COUNTRY`).
  * They distinguish the residency classification of the issuer vs. the customer in a transaction.
* **Architectural Risk**:
  * Code duplication. The concept of "Residency/Jurisdiction" is singular, but splitting it into two identical enum types makes type hinting brittle when passing a generic jurisdiction to a tax calculator.

### 18. `AmendmentKind` vs. `CalculationRevisionAmendmentKind` (Redundant Tax Modifiers)
* **Locations**:
  * `src/aeat/domain/filing/_amendment.py` (`AmendmentKind`)
  * `src/aeat/domain/modelos/_calculation_revision.py` (`CalculationRevisionAmendmentKind`)
* **Structural & Semantic Differences**:
  * Both share exact values (`COMPLEMENTARIA`, `SUSTITUTIVA`).
  * One is attached to the filing domain for overall return amendments, the other to calculation revisions for engine outputs.
* **Architectural Risk**:
  * Domain drift. An amendment is a legally distinct tax concept. Splitting its definition across calculation and filing domains means type-checkers will reject a `COMPLEMENTARIA` flag if imported from the wrong module.

### 19. `ConfigResetScope` vs. `SetupResetScope` (Parallel CLI Commands)
* **Locations**:
  * `src/aeat/application/config_reset.py` (`ConfigResetScope`)
  * `src/aeat/application/setup_reset.py` (`SetupResetScope`)
* **Structural & Semantic Differences**:
  * Both share exact values (`ALL`, `AUTH`, `DATA`, `PROFILE`).
  * Represents identical CLI operator arguments but duplicated per-command.
* **Architectural Risk**:
  * Application-layer redundancy. If a new reset scope (e.g., `CACHE`) is added, it must be wired and updated in multiple independent enum declarations.

### 20. Diagnostic & Validation Severity Dissonance
* **Locations**:
  * `src/aeat/application/transactions/_diagnostics.py` (`LedgerImportDiagnosticSeverity`)
  * `src/aeat/application/user_profile/__init__.py` (`ProfileValidationSeverity`)
  * `src/aeat/domain/submission/_protocols.py` (`FilingFindingSeverity`)
* **Structural & Semantic Differences**:
  * All three declare exactly `ERROR`, `INFO`, `WARNING`.
  * They cover imports, profile completeness, and filing submissions.
* **Architectural Risk**:
  * Harder to unify logging/diagnostic visualization if the central concept of severity uses 3 different typing contracts. Unifying to a standard `SeverityLevel` enum would streamline UI rendering.

### 21. PDF Plumber Inbound Backends
* **Locations**:
  * `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`
  * `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`
  * `src/aeat/adapters/inbound/justificante/_parsers/_pdfplumber_backend.py`
* **Structural & Semantic Differences**:
  * The borrador parser delegates directly to the shared `src/aeat/adapters/inbound/pdf/_pdfplumber.py` module.
  * The declaracion parser implements a performance optimization using `pypdfium2` as a fast cache-backed text extractor with a fallback to `pdfplumber`.
  * The justificante parser bypasses the shared primitive intentionally because of a different return shape (returning a concatenated single string instead of a page-level tuple split). However, it implements a custom `pdfminer` debug logging suppression function `_suppress_pdfminer_debug_logging` that is absent in the shared implementation, which causes log pollution when running other modules.
* **Architectural Risk**:
  * Debt/Safeguard hybrid. The bypass in justificante is semantically justified by the layout difference, but the local replication of logging controls and helper boilerplate increases tech debt. Fixes or improvements to logging silence are not shared.

### 22. Category vs. VAT Catalogue Loaders
* **Locations**:
  * `src/aeat/domain/categories/_registry.py`
  * `src/aeat/domain/vat/_catalogue.py`
* **Structural & Semantic Differences**:
  * Both modules exhibit identical copy-pasted TOML parsing boilerplate (such as `_file_fingerprint`, `_to_str_dict`, and caching logic).
* **Architectural Risk**:
  * Architectural Safeguard (Positive Overlap). By keeping their files and loaders separate, changes to the VAT domain structure (e.g. `VATCatalogue`) will never leak into or break the general spending categories domain (`CategoryProfile`).

### 23. Asset vs. Inventory Ledger
* **Locations**:
  * `src/aeat/domain/profile/assets/__init__.py`
  * `src/aeat/domain/profile/inventory/__init__.py`
* **Structural & Semantic Differences**:
  * Both modules define `SCHEMA_VERSION = "1"`, a local `_quantize` cent-rounding helper, and Pydantic validators for VAT decomposition (`_validate_vat_decomposition` vs `_validate_movement_amounts`).
* **Architectural Risk**:
  * Architectural Safeguard with minor Utility Duplication. Capital assets and short-term stock flow represent completely different financial sub-domains. However, the basic tax arithmetic (deductible ratio, VAT rates, gross calculations) duplicates boilerplate that could reside in a common tax-primitive module.

---

## Actionable Remediation Pathway

To maintain architectural hygiene and safeguard the system against shadowed imports and fragile error paths, the following refactoring steps are proposed:

1. **Establish a Domain Terminology Dictionary**:
   * Enforce a unified coding language strategy. Place a definitive glossary in the architecture reference rules specifying when to use English Spanish tax terms (e.g., map all general Spanish tax names to English concepts or retain Spanish terms natively but uniformly across all boundaries).

2. **Unify Value-Added Tax Terminology (`IVA` vs. `VAT`)**:
   * Consolidate the parallel `iva` and `vat` subpackages. Migrate `IvaInvoiceClassification` and `VatClassification` into a single, unified Value-Added Tax classification schema under `domain/vat` (or `domain/iva`), standardizing the acronym across the codebase.

3. **Align Filing, Modelo, and Declaración**:
   * Standardize the core return noun. Rename database records (e.g., `ModeloRecord` to `FilingRecord`) or rename domain concepts (e.g., `FilingDraft` to `ModeloDraft`) to ensure that the identical return concept uses a single naming convention from inbound ingestion through DB persistence.

4. **Consolidate Modelo 100 Draft Storage (`Borrador100Snapshot`)**:
   * Deprecate the raw local file-based `_borrador.py` persistence. Migrate all consumers and commands to the canonical secure-bucket implementation in `_borrador_100.py` that utilizes `SecureObjectRepository` for cryptographic isolation.

5. **Resolve Exception Shadowing (`WorkUnitNotFoundError`)**:
   * Consolidate the two definitions under a unified exception hierarchy. Place the canonical `WorkUnitNotFoundError` in a centralized error module under `src/aeat/application/modelo/errors.py` or within `_actions.py`, and have `_reconcile.py` raise the canonical exported exception.

6. **Differentiate CCAA Definitions**:
   * Rename `CCAA` in `_festivos.py` to `CalendarCCAA` or `TerritoryCCAA` to reflect its exhaustive regional coverage.
   * Maintain `CCAA` in `_ccaa.py` (or rename to `CommonRegimeCCAA`) to explicitly signal its common-tax-regime semantic boundaries.

7. **Differentiate Repository Names**:
   * Rename the core resource authority to `StaticModeloRepository` or `ModeloDefinitionRepository`.
   * Rename the SQL storage repository to `SqlModeloRepository` or `ModeloRecordRepository`.

8. **Differentiate Exception Namespaces (`StorageError`)**:
   * Disambiguate the outbound adapters from persistence by renaming the outbound exception root to `OutboundStorageError` (and its sub-exceptions to `OutboundStorageValidationError`, etc.).

9. **Differentiate Presentation and Database Models (`PortalRow`, `ForeignAssetObservation`)**:
   * Rename the application-facing `PortalRow` in the portal service to `PortalDTO` or `PortalListItem`.
   * Rename the aggregation-side `ForeignAssetObservation` to `RawForeignAssetObservation` or `IngestForeignAssetObservation` to clearly separate pre-aggregation inputs from domain-validated registry bindings.

---

## Comprehensive Prose Inventory of Overlapping Naming & Design Concerns

Following a complete scan of the 2,189 class and model definitions across the codebase, a series of deeper, systemic naming collisions and architectural boundary overlaps have been identified. While some of these definitions do not overlap textually (i.e. they reside in separate modules and use distinct classes), their phonetic, semantic, or conceptual equivalence presents significant structural risk.

### 1. The Spanish-English Financial Proof Duality: `Justificante` vs. `Invoice` vs. `Receipt`
The Spanish tax system relies heavily on the term `justificante` to denote any formal receipt, filing proof, or transactional justification. Across the codebase, this has produced a dual-language naming divide:
* **The Sede Filing Receipt**: In `src/aeat/domain/justificante/_models.py` and `src/aeat/adapters/inbound/justificante/test_parser.py`, `Justificante` refers exclusively to the official electronic receipt issued by the Sede Electrónica when a tax declaration is successfully submitted.
* **The General Expense Proof**: In application services and tests like `src/aeat/application/ledger/test_business_operation_invoice.py` and `src/aeat/domain/invoices/_models.py`, expense tracking relies on `Invoice`, `CollectibleInvoice`, and `PayableInvoice`. 
* **The Concern**: A developer writing logic to "verify a transaction using a justificante" faces severe semantic ambiguity. They may conflate the physical transaction proof (a vendor invoice or receipt) with the government's declaration filing receipt (`Justificante`). This terminology collision obscures the data flow and boundary between user-provided source documentation and government-emitted filing proof.

### 2. Collection Abstraction Overloading: The Proliferation of `Catalogue` Classes
The codebase relies on the term `Catalogue` to represent collections or static indexes of entities. However, this pattern is applied inconsistently across different subdomains:
* `src/aeat/domain/auth/apoderamientos/_catalogue.py` uses `Catalogue` for delegation authorization levels.
* `src/aeat/domain/vat/_schema.py` uses `VATCatalogue` to manage Value-Added Tax rates.
* `src/aeat/domain/transactions/_models.py` uses `TransactionCatalogue` for transactional records.
* `src/aeat/application/topics/__init__.py` uses `TopicCatalogue` for documentation topics.
* `src/aeat/domain/modelos/_work_unit.py` uses `WorkUnitCatalogue` for tax work units.
* `src/aeat/domain/modelos/_verification_report.py` uses `VerificationReportCatalogue` for reports.
* **The Concern**: In some cases, a `Catalogue` represents a static, built-in tax reference table (e.g., `VATCatalogue` or `TopicCatalogue`). In other cases, it represents a dynamic, stateful database collection (e.g., `TransactionCatalogue` or `WorkUnitCatalogue`) that relies on an underlying `Repository` class. Standardizing this pattern is critical to separating read-only reference data catalogs from write-active business domain repositories.

### 3. State-Entity Splitting: `Fact` vs. `Observation` vs. `Record` vs. `Snapshot` vs. `Revision`
When modeling the lifecycle of data as it transitions from raw external files to persisted database records, the codebase uses five overlapping state abstractions:
* **`Fact`**: Declared in `src/aeat/domain/user_profile/_values.py` as `UserProfileFact` to represent profile statements.
* **`Observation`**: Declared in `src/aeat/domain/calculations/registry/_bindings.py` (e.g., `CasillaObservation`, `RegistryFilingObservation`, `ForeignAssetObservation`) to represent inputs bound to Modelo fields.
* **`Record`**: Used under SQL schemas and persistent storage models (e.g., `ModeloRecord`, `FilingRecord`, `UserProfileRecord`) to represent the DB row state.
* **`Snapshot`**: Declared in `src/aeat/application/live/_borrador.py` and `src/aeat/domain/user_profile/_values.py` (e.g., `Borrador100Snapshot`, `CensusSnapshot`, `UserProfileSnapshot`) to represent point-in-time raw extracts.
* **`Revision`**: Declared in `src/aeat/domain/calculations/registry/_bindings.py` as `CalculationRevision` to encapsulate computed engine outputs.
* **The Concern**: The lack of a clear, unified lifecycle boundary between a `Snapshot` (raw scrape/extract), a `Fact` (profile input), an `Observation` (registry-bound casilla value), a `Revision` (calculated engine output), and a `Record` (persisted database row) invites state leakage. Developers frequently face confusion over whether a specific model represents a raw input, a validated domain entity, or a persisted SQL record.

### 4. Overlapping Operational Verbs: `Verify` vs. `Validate` vs. `Check` vs. `Audit`
Verification and checking are core requirements of the tax filing pipeline. However, these verbs have been independently implemented across four distinct domains:
* **Sede scraping validation**: Declared in `src/aeat/application/live/_verify.py` as `VerifyService` and `VerifySurface` to log into Sede Electrónica and confirm that a filing is officially registered.
* **Accounting rule audits**: Declared in `src/aeat/application/verification/_schema.py` as `VerificationVerdict` and `src/aeat/domain/modelos/_verification_report.py` as `VerificationReport` to check that financial ledgers comply with Spanish tax rules.
* **Interactive wizard inputs**: Declared in `src/aeat/application/wizard/_verifier.py` as `WizardVerifier` and `WizardCheck` to validate user input logic.
* **The Concern**: Developers tracing an "audit or verification" failure are forced to navigate completely separate systems. If a system failure surfaces as a `VerificationError` or a `VerificationReport` failure, it is structurally ambiguous whether the error originates from a network scraping timeout (`VerifyService`), a spreadsheet parity mismatch, or a local tax calculation rule violation (`VerificationReport`).

### 5. Cryptographic Isolation Duality: Column-Level `Encrypted` vs. Object-Level `Secure` Storage
For securing sensitive user identifiers (such as NIFs, IBANs, and financial data) at rest, the persistence layer implements two duplicate, parallel strategies:
* **Document-level security**: Handled by `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py` using `SecureObjectRepository`, which serializes entire Pydantic objects inside encrypted SQLite blobs using `Envelope` and `Ciphertext`.
* **Column-level security**: Handled by `src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py` using `EncryptedColumns` to encrypt specific database columns individually in standard ORM tables.
* **The Concern**: Having parallel column-level and document-level encryption schemas creates fragmented security bounds. Developers implementing new database tables must choose between relational ORM storage with encrypted columns or serialized object storage inside the secure repository. This splits the cryptographic threat model and increases the surface area for key management leaks.

### 6. Duplicated Sede Snapshot Structures under `application/live`
The scraping and local caching architecture under `src/aeat/application/live/` implements separate modules for each category of Sede Electrónica data:
* `src/aeat/application/live/_borrador.py` (`Borrador100Snapshot`)
* `src/aeat/application/live/_census.py` (`CensusSnapshot`)
* `src/aeat/application/live/_expedientes.py` (`ExpedienteSnapshot`)
* `src/aeat/application/live/_notifications.py` (`NotificationSnapshot`)
* **The Concern**: While the parsed content of these snapshots is necessarily different, the boilerplate logic managing local folder layout (`settings.aeat_audit_dir / "live" / ...`), JSON serialization, raw HTML file backup, page navigation, and state transitions is copied and pasted across all four files. This creates high maintenance overhead when adapting to AEAT browser-evasion or certificate authentication updates.

---

## Production Function & Method Redundancy Analysis

A deep AST and MD5 analysis of production function names and method signatures has uncovered substantial code duplication and structural replication across domain packages. Unlike the high-level semantic conflicts, these findings represent direct, copy-paste implementation boilerplate that can be resolved via unified abstractions.

### 1. Governed Repository Cryptographic Adapters
The codebase makes extensive use of the `SecureObjectRepository` adapter to persist sensitive Pydantic models inside SQLite database blobs. However, the exact repository boilerplate wrapping these object loads, saves, deletes, and listings has been copied line-for-line across eight distinct classes:
* `FilingDraftRepository` in `src/aeat/domain/filing/_repository.py`
* `SubmissionRepository` in `src/aeat/domain/submission/_repository.py`
* `FilingHistoryRepository` in `src/aeat/application/filing/_history_repository.py`
* `ComplementariaRepository` in `src/aeat/domain/filing/_complementaria_repository.py`
* `JustificanteRepository` in `src/aeat/domain/justificante/_repository.py`
* `ObservationsRepository` in `src/aeat/application/calculations/_observations_repository.py`
* `AssetsRepository` in `src/aeat/adapters/persistence/profile/assets.py`
* `InventoryRepository` in `src/aeat/adapters/persistence/profile/inventory.py`

#### Identical Method Redundancy:
* **`envelope_path_for` & `lock_target_for`**: Every single one of these classes implements an identical logical path generator (`return self.store_dir / identifier` and `return self.store_dir / f"{identifier}.lock"`), only varying the string parameter name (`draft_id`, `submission_id`, `observation_id`, etc.).
* **`load` & `save`**: The deserialization and serialization loop over `Envelope[T]` is repeated exactly: calling `self._objects.load()` or `self._objects.save()`, validating `SensitivityClass` (e.g. `FINANCIAL` or `AUDIT`), asserting `envelope.schema_version <= _ENVELOPE_VERSION`, and returning the nested Pydantic model payload.
* **`list_*_ids` & `iter_*`**: Listing operations all deserialize all records in the SQL namespace, parse their JSON wrappers, pull the identifier from the payload, sort them, and yield them sequentially.
* **The Concern**: A change to the security classification structure or version checking logic requires updating eight separate source files. This replication represents direct, structural boilerplate debt.
* **Remediation**: Introduce a generic `SecureBoundRepository[T]` base class or mixin parameterized by Pydantic model type `T` and `SensitivityClass`, centralizing this serialization loop.

### 2. Oracle Execution Pipeline & Driver Clones
The oracle verification systems under `src/aeat/domain/calculations/registry/` handle verification requests (e.g. confirming VAT IDs or autonomous region holiday lists) using a two-tier adapter design (the main `Oracle` orchestrator and an execution `Driver` protocol). The logic for verifying payloads, defining planned actions, and checking guard policies is copy-pasted across:
* `AeatNifIvaCheckerOracle` and `AeatNifIvaReplayDriver` in `_aeat_nif_iva_oracle.py`
* `GroiCheckerOracle` and `GroiReplayDriver` in `_groi_oracle.py`
* `RentaWebOpenOracle` and `RentaWebOpenReplayDriver` in `_renta_web_open_oracle.py`

#### Identical Method Redundancy:
* **`planned_operations` & `verify_payload`**: These orchestrator methods execute identical guard assertion calls (`assert_oracle_operations_allowed(self, policy, operations)`), check driver status, catch `RegistryValidationError`, compare values via identical helpers (`_compare_expected_*`), and pack results into a standard `ParityResult`.
* **`collect_observation`**: The replay drivers contain identical UTF-8 JSON decoders, dictionary type-checkers, and validation error raisers, differing only in the target observation model names.
* **The Concern**: Extending the remote state guard policy rules or adding new auditing fields to `ParityResult` requires manual modifications across all three files.
* **Remediation**: Extract a shared base class `BaseCheckerOracle` and standard JSON-decoding replay utility in `src/aeat/domain/calculations/registry/_live_parity.py`.

### 3. PDF Page Text Extraction Boilerplate
Reading raw PDF bytes to extract text for downstream scraping or filing parsing is duplicated across inbound boundaries:
* `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py` (`extract_pages_text`)
* `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py` (`extract_pages_text_from_bytes`)
* `src/aeat/adapters/inbound/pdf/_pdfplumber.py` (`extract_pages_text_from_bytes`)

#### Identical Method Redundancy:
* **`pdfplumber` block**: All three implementations load PDF file streams or raw bytes, initialize a `pdfplumber.open()` context, walk pages, call `page.extract_text()`, handle missing page structures, and join string results.
* **The Concern**: PDF parsing performance or encoding fixes must be triplicated across all three locations to maintain consistent text ingestion behavior.
* **Remediation**: Migrate all callers to the canonical `src/aeat/adapters/inbound/pdf/_pdfplumber.py` implementation, deleting the local copies in the parsed domain subpackages.

### 4. General CRUD Repository Operations
Standard read/write collection signatures are implemented independently across different persistent storage systems without sharing common interfaces:
* `src/aeat/adapters/persistence/storage/sql/repository.py` (`list_all`, `upsert`, `delete`)
* `src/aeat/domain/rental/_repository.py` (`list_all`, `upsert`, `delete`)
* `src/aeat/application/ledger/_business_operation_invoice.py` (`list_all`, `add`, `remove`)
* `src/aeat/application/ledger/_evidence.py` (`list_all`, `add`, `remove`)

#### The Concern**:
* Inconsistent method naming conventions (`add` vs `upsert` vs `save` and `remove` vs `delete`) for identical write operations.
* Inconsistent collection listing names (`list_all` vs `all` vs `iter_*` vs `list_*_ids`).
* Standardizing these interfaces will improve readability and simplify high-level transaction orchestrations.

---

## Test Suite & Verification Boilerplate Redundancy Analysis

A systemic sweep of all test suites in the codebase has uncovered high volumes of verbatim test assertion duplication and duplicate test function names. Because testing boundaries represent a substantial part of the codebase, consolidating these patterns reduces maintenance overhead when testing conventions or core schemas evolve.

### 1. Secure Storage and Repository Anti-Tautology Tests
The eight repositories wrapping `SecureObjectRepository` have cloned test suites that verify roundtrips, database encryption, deletion idempotency, and invalid identifiers.
* **Overlapped Test Functions**:
  * `test_database_payload_is_encrypted_audit_data()`
  * `test_delete_missing_returns_false()`, `test_delete_removes()`, `test_delete_removes_object()`
  * `test_load_returns_none_when_absent()`, `test_foreign_class_object_refused()`
  * `test_object_marker_identifies_secure_backend()`
  * `test_round_trip_preserves_payload()`, `test_save_is_idempotent()`
  * `test_unsafe_id_rejected()`, `test_boundary_catches_simulated_field_drop_via_corrupted_payload()`
* **Spanned Files**:
  * `src/aeat/adapters/persistence/storage/test_submission_repository.py`
  * `src/aeat/application/filing/test_complementaria_repository.py`
  * `src/aeat/application/filing/test_history_repository.py`
  * `src/aeat/application/filing/test_repository.py` (filing drafts)
  * `src/aeat/domain/justificante/test_repository.py`
  * `src/aeat/domain/submission/test_repository.py`
  * `src/aeat/application/user_profile/test_repository_anti_tautology.py`
  * `src/aeat/domain/filing/test_roundtrip_anti_tautology.py`
* **The Concern**: Verbatim assertion blocks verifying encrypted database payloads, invalid characters in keys, and Pydantic exception behaviors are duplicated line-for-line.
* **Remediation**: Extract a reusable repository test suite or test suite generator (e.g. using `pytest` class inheritance or parameterized fixtures) that runs this standardized battery of roundtrip and safety assertions on any `SecureObjectRepository` subclass.

### 2. Live Scraping Snapshot and Service Tests
The caching, backup, and page retrieval snapshot tests under `src/aeat/application/live/` contain identical verification loops for folder storage scopes, full snapshot lists, and missing record handling.
* **Overlapped Test Functions**:
  * `test_capture_deduplicates_identical_snapshots()`
  * `test_capture_persists_with_content_addressed_id()`
  * `test_snapshots_are_bucket_scoped()`
  * `test_show_refuses_unknown_id()`
  * `test_show_resolves_full_and_prefix()`
  * `test_service_has_no_write_methods()`
* **Spanned Files**:
  * `src/aeat/application/live/test_borrador.py`
  * `src/aeat/application/live/test_expedientes.py`
  * `src/aeat/application/live/test_notifications.py`
  * `src/aeat/application/live/test_verify.py`
* **The Concern**: Because each snapshot class implements identical directories and properties under different domain names, their testing suites assert the same logical expectations (e.g., verifying that a partial ID matches its full hash, or that directory paths are properly scoped).
* **Remediation**: Create a unified testing mixin or parameterized fixture in `src/aeat/application/live/conftest.py` to assert standard snapshot storage capabilities.

### 3. Oracle Guard & Registry Parity Validation Tests
Oracle verification systems use duplicated test functions to verify the behavior of remote-state guard policy bypasses and validation boundaries.
* **Overlapped Test Functions**:
  * `test_verify_payload_reports_guard_block_when_aeat_host_not_in_policy()`
  * `test_verify_payload_without_driver_returns_unverifiable_after_guard_preflight()`
  * `test_planned_operations_rejects_empty_expected()`
  * `test_register_default_under_production_environment()`, `test_register_default_test_environment_classification_supported()`
  * `test_observation_model_rejects_empty_nif()`, `test_observation_model_rejects_unknown_verdict()`
* **Spanned Files**:
  * `src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py`
  * `src/aeat/domain/calculations/registry/test_groi_oracle.py`
  * `src/aeat/adapters/outbound/aeat/sede/test_groi_check.py`
  * `src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py`
* **The Concern**: Mock/replay drivers are validated using copy-pasted parameters and identical assertion limits.
* **Remediation**: Standardize registry checker preflights into a shared test utility module.

### 4. Bucket & Manifest Parsing Constraints
Parsing constraints for cryptographic salt lengths, UTC timestamp offsets, and unexpected keys are checked via duplicated test assertions.
* **Overlapped Test Functions**:
  * `test_rejects_naive_created_at()`, `test_rejects_non_utc_offset_created_at()`
  * `test_rejects_unknown_keys()`
  * `test_rejects_empty_bucket_id()`, `test_rejects_non_positive_schema_version()`
  * `test_rejects_wrong_salt_length()`
* **Spanned Files**:
  * `src/aeat/adapters/persistence/storage/bucket/test_export_header.py`
  * `src/aeat/adapters/persistence/storage/bucket/test_manifest.py`
  * `src/aeat/application/workflow/test_bucket_pointer.py`
  * `src/aeat/adapters/persistence/storage/master_key/test_recovery_record.py`
  * `src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py`
* **Remediation**: Share metadata validation test helpers under `src/aeat/adapters/persistence/storage/conftest.py`.

### 5. Ingestion Binding Evaluators
Aggregation rules and Value-Added Tax rate lookup parameters are tested via cloned assertion routines.
* **Overlapped Test Functions**:
  * `test_validate_rejects_non_sum_aggregation()`
  * `test_validate_rejects_unknown_fact()`, `test_validate_rejects_unknown_rate_kind()`
  * `test_validate_rejects_wrong_source_kind()`
  * `test_resolve_handles_multiple_bindings_independently()`, `test_resolve_supports_base_amount_sum_fact()`
* **Spanned Files**:
  * `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
  * `src/aeat/domain/calculations/registry/test_ledger_oss_aggregation_binding.py`

### 6. Reset & Quarantine Lifecycles
System configuration state and user cache resets share identical multi-stage setup testing flows.
* **Overlapped Test Functions**:
  * `test_reset_all_combines_all_scopes()`, `test_reset_auth_only_clears_session()`
  * `test_reset_data_invokes_quarantine_pipeline()`
  * `test_reset_profile_deletes_bucket_id_when_profile_key_differs()`
  * `test_reset_profile_only_clears_active_profile_record()`
* **Spanned Files**:
  * `src/aeat/application/test_config_reset.py`
  * `src/aeat/application/test_setup_reset.py`

---

## Prose Analysis of Python File List & Structural Overlaps Sweep

A comprehensive prose analysis of the complete flat Python file list (`tmp/duplicates/python_files_flat.txt`) has been executed. The following sections provide an explicit, repetitive enumeration of the exact files, classes, and definitions impacted by architectural overlaps, dual-acronym structures, and semantic collisions:

### 1. Borrador Storage Substrate Split
* **Impacted Source Files**:
  * `src/aeat/application/live/_borrador.py`
  * `src/aeat/application/live/_borrador_100.py`
* **Impacted Test Files**:
  * `src/aeat/application/live/test_borrador.py`
  * `src/aeat/application/live/test_borrador_100.py`
  * `src/aeat/application/live/test_borrador_100_roundtrip.py`
* **Impacted Classes**:
  * `BorradorPrefillEntry` (redefined under both files)
  * `Borrador100Snapshot` (redefined under both files)
  * `BorradorSnapshotNotFoundError` (redefined under both files)
  * `BorradorService` (legacy service writing to JSONL)
  * `Borrador100SnapshotService` (canonical service writing to SecureObjectRepository)
  * `Borrador100SnapshotRepository` (canonical database repository)
* **Impacted Functions**:
  * `_derive_snapshot_id` (content-addressed hash derivation cloned in both files)

### 2. Dual Acronym Architecture: IVA vs. VAT
* **Impacted Source Files**:
  * `src/aeat/domain/vat/_flow.py`
  * `src/aeat/domain/vat/_classification.py`
  * `src/aeat/domain/invoices/_iva_classification.py`
  * `src/aeat/application/aggregation/_iva_ledger.py`
* **Impacted Classes & Enums**:
  * `IvaInvoiceClassification` vs. `VatClassification`
  * `_IvaLedgerSelector` vs. `VatLedgerSelector`
  * `VATRateKind` vs. `IvaRateKind`
  * `VatRegulation` vs. `IvaRegulation`

### 3. Jurisdictional Duplication: Issuer vs. Customer Residency Models
* **Impacted Source Files**:
  * `src/aeat/domain/vat/_classification.py`
* **Impacted Enums**:
  * `IssuerResidency` (StrEnum)
  * `CustomerResidency` (StrEnum)

### 4. Static Authority Façades vs. Active SQL Persistence (`ModeloRepository`)
* **Impacted Source Files**:
  * `src/aeat/core/resources/_repos/modelos.py`
  * `src/aeat/adapters/persistence/storage/sql/repository.py`
* **Impacted Classes**:
  * `ModeloRepository` (in `core/resources/_repos/modelos.py`)
  * `ModeloRepository` (in `adapters/persistence/storage/sql/repository.py`)

### 5. Fragile Exception Catching Gaps: `WorkUnitNotFoundError` Redefinitions
* **Impacted Source Files**:
  * `src/aeat/application/modelo/_actions.py`
  * `src/aeat/application/modelo/_reconcile.py`
* **Impacted Exceptions**:
  * `WorkUnitNotFoundError` (in `_actions.py`, inheriting from `ModeloError` and `KeyError`)
  * `WorkUnitNotFoundError` (in `_reconcile.py`, inheriting from `AeatError`)

### 6. Relational Column-Level vs. Serialized Object-Level Encryption
* **Impacted Source Files**:
  * `src/aeat/adapters/persistence/storage/sql/repository.py`
  * `src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py`
* **Impacted Classes**:
  * `SecureObjectRepository` (fully serialized envelope persistence)
  * `EncryptedColumns` (column-level SQL interception)
  * `EncryptedString` (field-level decryption hook)

### 7. Ingestion Spectrum Confusion: Justificante vs. Invoice vs. Receipt
* **Impacted Source Files**:
  * `src/aeat/domain/justificante/_models.py`
  * `src/aeat/domain/invoices/_models.py`
* **Impacted Classes**:
  * `Justificante` (official AEAT submission proof from Sede Electrónica)
  * `Invoice` (standard transactional business document)
  * `CollectibleInvoice` (accounts receivable / clients)
  * `PayableInvoice` (accounts payable / suppliers)

### 8. Semantic & Phonetic Drifts: Renta vs. Rental
* **Impacted Source Files**:
  * `src/aeat/domain/renta/_ledger_expenses.py`
  * `src/aeat/domain/rental/_amortization_ledger.py`
* **Impacted Classes & Contexts**:
  * `Renta` (LIRPF general income tax context)
  * `Rental` (Residential lease tenancy context)
  * `RentalExpense` (deductible lease asset amortization scheduler)
  * `RentaExpense` (deductible general business expense categories)





---

## Application Sweep Pass 2: Deep Structural Analysis of src/aeat/application/**

This pass focuses on READ-ONLY discovery of code duplication within the application layer only, identifying patterns beyond the 8 SecureObjectRepository wrappers and 4 snapshot files already documented.

---

### Category A: Service Class Method Signature Collisions

#### Finding A1: Evidence, Inventory, Portals Service Interfaces
* **Affected Services**:
  * `src/aeat/application/evidence/_service.py:EvidenceBundleService`
  * `src/aeat/application/inventory/_service.py:InventoryService`
  * `src/aeat/application/portals/_service.py:PortalsService`
* **Common Method Patterns**:
  * `build()` / `create()`: Constructor methods with bucket-scoped initialization and event emission (Evidence/Inventory).
  * `show()`: Single-entity lookup returning a DTO with bucket/id scope (Evidence/Inventory/Portals).
  * `check()` / `list_all()`: Enumeration operations with optional filtering and sorting.
* **Structural Diff**:
  * Evidence: Returns verification reports; Inventory: returns ledger summaries; Portals: returns metadata rows.
  * All three use identical error-raising patterns on missing entities (NotFoundError subclasses with suggestion= guidance).
* **Risk Category**: Minor Boilerplate Reuse — method names and signatures are consistent, but return types differ sufficiently that generic refactoring is modest-value.

---

### Category B: Snapshot Service Architecture Duplication in application/live

#### Finding B1: Four-Part Snapshot Lifecycle Pattern
* **Affected Snapshots**:
  * `src/aeat/application/live/_borrador.py:BorradorService` (legacy JSONL)
  * `src/aeat/application/live/_borrador_100.py:Borrador100SnapshotService` (canonical)
  * `src/aeat/application/live/_census.py:CensusSyncService` (SecureObjectRepository)
  * `src/aeat/application/live/_notifications.py:NotificationsService` (JSONL)
  * `src/aeat/application/live/_expedientes.py:ExpedientesService` (JSONL)
* **Identical Method Signatures**:
  * `capture()`: Deduplication via content-addressed ID.
  * `list_snapshots()`: Load-all from bucket scope.
  * `show()`: Lookup by full ID or prefix match.
  * `discard()`: Mark as retired (Borrador/Census only).
* **Shared Boilerplate**:
  * All implement identical `_storage_path()`, `_load()`, `_save()`, `_derive_snapshot_id()` helpers.
  * All wrap Settings and UTC datetime helpers.
* **Risk Category**: HIGH — Maintenance burden when snapshot persistence strategy or state machine rules change.

#### Finding B2: Snapshot State Machine Redundancy
* **Affected Enums**:
  * `Borrador100SnapshotState` (ACTIVE, SUPERSEDED, DISCARDED)
  * `CensusSnapshotState` (ACTIVE, SUPERSEDED, DISCARDED)
* **Shared Invariants**:
  * ACTIVE: Cannot carry superseded_by pointers.
  * SUPERSEDED: Must carry superseded_by_snapshot_id.
  * DISCARDED: Must carry discarded_at and discarded_by.
* **Risk Category**: HIGH — Any state machine change requires triplicate updates.

---

### Category C: Aggregation Service Architecture Overlaps

#### Finding C1: Ledger Aggregation Providers
* **Affected Modules**:
  * `src/aeat/application/aggregation/_iva_ledger.py`
  * `src/aeat/application/aggregation/_renta_ledger.py`
* **Identical Function Signatures**:
  * Both accept `(bucket_id, period, *_repository = None)`.
  * Both validate bucket_id parity before delegating to lower-level aggregation.
* **Shared Error Handling**:
  * Parallel issue-reason enums with overlapping concepts (UNSUPPORTED_DIRECTION, UNSUPPORTED_CURRENCY, UNCLASSIFIED_BUSINESS_STATE, etc.).
* **Risk Category**: MODERATE — Extending issue types requires synchronized updates.

---

### Category E: Repository Method Naming Inconsistencies

#### Finding E1: Application-Layer CRUD Naming Divergence
* **Inconsistent Verb Choices**:
  * Creation: `create()` vs. `build()`.
  * Reading: `show()` vs. `load()`.
  * Listing: `list_all()` vs. `iter_*()` vs. `list_*_ids()`.
  * Deletion: `remove()` vs. `delete()`.
* **Risk Category**: Low-Risk, High-Friction.

---

## Summary of New Findings

**New Duplication Categories Found**: 5 (A–C, E)
**High-Risk Items**: 2 (B1 Snapshot Services, B2 State Machine Validators)
**Moderate-Risk Items**: 1 (C1 Ledger Provider Architecture)
**Low-Risk, High-Value Cleanup**: 1 (E1 CRUD Naming)

### Confirmed Already-Known Duplications Revisited
- 8 SecureObjectRepository wrappers (Filing, Submission, Complementaria, Justificante, Observations, Assets, Inventory, UserProfile)
- 4 legacy snapshot files with heightened severity evidence
- Duplicate WorkUnitNotFoundError in application/modelo
- Duplicate ForeignAssetObservation models
- Duplicate Borrador100Snapshot in application/live


## Domain Sweep Pass 2

This sweep expands upon the initial findings by conducting a focused AST and enum-value analysis across the `src/aeat/domain/**` package tree.

### 24. `FilingDraftStatus` vs. `DraftStatus` (Identical Value Sets)
* **Locations**:
  * `src/aeat/domain/filing/_schema.py:26` (FilingDraftStatus)
  * `src/aeat/domain/submission/_protocols.py:135` (DraftStatus)
* **Structural Risk**: Both enums carry the identical 10 status values. DraftStatus is a copy-pasted mirror explicitly documented as "kept in sync" in source comments, yet remains unresolved boilerplate.

### 25. Triple Direction Taxonomies: `InvoiceKind` / `InvoiceDirection` / `IvaFlowDirection` / `TransactionDirection`
* **Locations**:
  * `src/aeat/domain/invoices/_enums.py:25` (InvoiceKind - ISSUED/RECEIVED)
  * `src/aeat/domain/vat/_classification.py:196` (InvoiceDirection - issued/received)
  * `src/aeat/domain/vat/_flow.py:95` (IvaFlowDirection - REPERCUTIDO/SOPORTADO/AUTOREPERCUTIDO)
  * `src/aeat/domain/transactions/_enums.py:12` (TransactionDirection - INCOMING/OUTGOING)
* **Structural Risk**: Four overlapping "direction" concepts at different abstraction layers (invoice binary, VAT flow, account movement). Severe cognitive overhead and type fragility across financial layers.

### 26. `IssuerResidency` vs. `CustomerResidency` (Symmetric Duplication)
* **Locations**:
  * `src/aeat/domain/vat/_classification.py:70` (IssuerResidency)
  * `src/aeat/domain/vat/_classification.py:94` (CustomerResidency)
* **Structural Risk**: Both enums carry identical five values (ES_MAINLAND, ES_CANARIAS, ES_CEUTA_MELILLA, EU_MEMBER, THIRD_COUNTRY). Defined side-by-side; violates DRY. Changes to tiers must be synchronized in both.

### 27. Protocol Name Collision: `DeadlineChecker` vs. `DeadlineWindowChecker`
* **Locations**:
  * `src/aeat/domain/filing/_protocols.py:162` (DeadlineChecker)
  * `src/aeat/domain/submission/_protocols.py:93` (DeadlineWindowChecker)
* **Structural Risk**: Both describe identical cross-domain surface (filing window open check) but carry different method signatures. Runtime fragility; consolidation needed.

### 28. Error Module Naming Inconsistency: `profile/_errors.py` vs. `profile/errors.py`
* **Locations**:
  * `src/aeat/domain/profile/_errors.py` (tax residence/config errors)
  * `src/aeat/domain/profile/errors.py` (ledger-level errors)
* **Structural Risk**: Inconsistent underscore naming signals unclear intent. Developers must hunt for correct module. Consolidation recommended.

### Summary

**New Collisions Found**: 5 (items 24-28)
**Confirmed from Seed**: All 10 class-name collisions verified within domain/ scope.
**Key Insight**: Enum-value duplications and Protocol overlaps outnumber class-name collisions in domain/ but represent systemic duplication that the seed data did not enumerate.

---

## Adapter ENG/ESP Drift

Findings transcribed from the adapter sweep into this durable record by the project manager because the source agent reported results out-of-band. 13 drift candidates across 4 categories within `src/aeat/adapters/**`.

### Category A: English class names where Spanish tax-domain stems should prevail

| Identifier | Location | Current | Proposed | Risk |
| --- | --- | --- | --- | --- |
| `ModeloRecord` | `src/aeat/adapters/persistence/storage/sql/records.py:47` | English suffix `-Record` | confirm vs ADR Specialist (consider `ModeloRow` consolidation, NOT `RegistroModelo` — stem stuttering) | High - boundary layer |
| `ModeloRow` | `src/aeat/adapters/persistence/storage/sql/_orm.py:36` | English suffix `-Row` | confirm canonical persistence naming (avoid `FilaModelo` — over-translation of generic infra suffix) | High - ORM refactor |
| `FiledDeclarationArtefact` | `src/aeat/adapters/outbound/aeat/sede/_schema.py:164` | Pure English | `FiledDeclaracionArtefact` (stem only) | High - public API |
| `FiledDeclarationObservation` | `src/aeat/adapters/outbound/aeat/sede/_schema.py:242` | Pure English | `FiledDeclaracionObservation` (stem only) | High - public API |
| `Declaration` | `src/aeat/adapters/outbound/aeat/sede/_declarations.py:130` | Pure English | `Declaracion` | High - 50+ refs across adapters |
| `RentalFincaRow` | `src/aeat/adapters/persistence/storage/sql/_orm.py:176` | Mixed (Renta vs Rental ambiguity) | NEEDS ADR ADJUDICATION — see Renta/Rental finding #10 in research above | High - rental core |
| `RentalContractRow` | `src/aeat/adapters/persistence/storage/sql/_orm.py:230` | Same | NEEDS ADR ADJUDICATION | High |
| `RentalIncomeRecordRow` | `src/aeat/adapters/persistence/storage/sql/_orm.py:312` | Mixed Rental+Income+Record+Row | NEEDS ADR ADJUDICATION | High |
| `RentalExpenseRow` | `src/aeat/adapters/persistence/storage/sql/_orm.py:355` | Same | NEEDS ADR ADJUDICATION | High |
| `RentalAmortizationLedgerRow` | `src/aeat/adapters/persistence/storage/sql/_orm.py:396` | Same | NEEDS ADR ADJUDICATION | High |

### Category B: Mixed-language identifiers (Spanish stem + English suffix)

| Identifier | Location | Notes |
| --- | --- | --- |
| `BorradorParseError` | `src/aeat/adapters/inbound/borrador/_errors.py:14` | Borrador + ParseError; consistent with file location convention; likely accept as-is |
| `ArtefactNotRecognisedError` | `src/aeat/adapters/inbound/borrador/_errors.py:23` | Borrador-context error; English name; review if stem should be `BorradorArtefactNotRecognisedError` |
| `DeclaracionParseError` | `src/aeat/adapters/inbound/declaracion/_errors.py:15` | Same pattern as BorradorParseError; accept |
| `BorradorObservation` | `src/aeat/adapters/inbound/borrador/_schema.py:56` | Spanish stem + English Observation; likely accept (Observation is generic infra) |
| `DeclaracionObservation` | `src/aeat/adapters/inbound/declaracion/_schema.py:77` | Same; likely accept |
| `JustificanteRef` | `src/aeat/adapters/outbound/aeat/sede/_schema.py:101` | Justificante + Ref; abbreviation acceptable |

### Category C: Boundary modules with inconsistent naming

- `DeclarationsRegisterSession` at `src/aeat/adapters/outbound/aeat/sede/_declarations.py:217` — English `Declarations` should be `Declaraciones`; suffix `RegisterSession` is OK
- `FiledDeclarationObservationStore` at `src/aeat/adapters/outbound/aeat/sede/_observation_store.py:26` — same; rename to `FiledDeclaracionObservationStore`

### Category D: Adapter exception classes

- `JustificanteFetchError` at `src/aeat/adapters/outbound/aeat/sede/_errors.py:76` — Justificante + FetchError; likely accept

### Cross-boundary inconsistencies flagged for ADR Specialist

1. **Persistence layer dual-pattern**: `ModeloRecord` (pydantic) vs `ModeloRow` (SQLAlchemy ORM) — same domain entity, two naming patterns in adjacent layers. ADR Specialist must rule on canonical choice.
2. **Observation pattern**: `BorradorObservation`, `DeclaracionObservation`, `FiledDeclarationObservation` — first two are Spanish-stem, third is English. Standardise.
3. **Rental domain**: The entire `Rental*Row` cluster is the largest single-domain drift surface. Linked to the `Renta` vs `Rental` semantic split (research item #10). Must be resolved as one coordinated refactor, not piecemeal.
4. **Outbound sede module**: Lives under `declaraciones` namespace but exposes English `Declaration*` boundary records. Standardise stems to Spanish.

---

## Exception Hierarchy Audit

Findings transcribed by the project manager. Full scan of `src/aeat/**` exception classes.

### Inventory totals

- 251 exception class definitions total
- 3 exception class name collisions
- 2 dead exceptions (never raised)
- 4 escape-to-top exceptions (raised but never caught in production)
- 1 critical parent-class divergence (the already-inventoried `WorkUnitNotFoundError`)

### A. Exception class collisions (same name, different modules)

| Class | Location 1 | Parent 1 | Location 2 | Parent 2 | Risk |
| --- | --- | --- | --- | --- | --- |
| `StorageError` | `src/aeat/adapters/outbound/storage/_errors.py:16` | `AeatError` | `src/aeat/adapters/persistence/storage/errors.py:20` | `AeatError` | **CRITICAL** — same parent, different module, distinct subclass trees; catching one will not catch the other |
| `StorageValidationError` | `src/aeat/adapters/outbound/storage/_errors.py:20` | `StorageError, ValueError` | `src/aeat/adapters/persistence/storage/errors.py:38` | `PersistenceError, ValueError` | **CRITICAL** — parent chains diverge entirely |
| `NoActiveBucketError` family | `src/aeat/adapters/persistence/storage/bucket/_errors.py:20` (bucket-scope, never raised in production) | `BucketError` | `src/aeat/domain/transactions/_errors.py:24` (`LedgerNoActiveBucketError`, actively raised + caught) | `LedgerStorageError` | High — three+ "no active bucket" variants across bucket / transaction / master_key / auth scopes; consolidation needed |

### B. Dead exceptions (defined but never raised)

| Class | Definition | Status |
| --- | --- | --- |
| `AccessGateSubmissionError` | `src/aeat/core/access_gate/_errors.py:20` | Base-only; only subclasses raised (`LiveSubmitForbiddenError`, `AccessGateSubmissionPreflightError`). Acceptable if intentional base. |
| `BucketAlreadyPresentError` | `src/aeat/adapters/persistence/storage/bucket/_errors.py:43` | Never instantiated in raise statements. Candidate for deletion. |

### C. Escape-to-top exceptions (raised, never caught in production)

| Class | Definition | Raise sites | Catch sites | Disposition |
| --- | --- | --- | --- | --- |
| `RecoveryUnavailableError` | `src/aeat/adapters/persistence/storage/bucket/_errors.py:68` | Test files only | None in production | LOW — remove or activate raise site |
| `RecoveryVerificationError` | `src/aeat/adapters/persistence/storage/bucket/_errors.py:82` | `master_key/_recovery_facade.py` (2 raises) | Only tests + self-catch in `_recovery_facade.py` | MEDIUM — bubble pattern expected for recovery workflow |
| `OutputSchemaError` | `src/aeat/core/json_contract.py:43` | 4 raise sites in `json_contract.py` | Never caught; bubbles to CLI boundary | LOW — intentional bubble to CLI error boundary |
| `BucketLockedError` | `src/aeat/adapters/persistence/storage/bucket/_errors.py:55` | `master_key/_bucket_session.py` (3 raises) | Never caught in production | MEDIUM — intentional lock-contention signal |

### Recommendation

1. Rename outbound `StorageError`/`StorageValidationError` to `OutboundStorageError`/`OutboundStorageValidationError`. This is the most urgent catch-shadow bug in the inventory.
2. Consolidate the three+ `*NoActiveBucketError` variants into a single hierarchy or establish clear domain ownership.
3. Delete `BucketAlreadyPresentError` (never used) and decide whether `AccessGateSubmissionError` should remain as a base-only.
4. Add docstring comments to the intentional-bubble exceptions documenting why they escape top-level handlers.

---

## ENG/ESP Full Inventory (RAW — needs ADR Specialist QC pass)

Findings transcribed by the project manager from the full-codebase cross-cutting sweep. **189 rows. Quality WARNING:** This inventory was produced by a haiku discovery agent and contains known stem-stuttering errors (e.g. `BorradorBorrador`, `RentaRenta`, `FincasFinca`). Treat every "Proposed" value as a *candidate* for ADR Specialist adjudication, not as a directive. Coding agents MUST NOT execute against this list directly.

### Distribution

- `rename-only`: 80 items (42.3%)
- `public-API-change`: 54 items (28.6%)
- `schema-impact`: 51 items (27.0%)
- `cross-module-renames`: 4 items (2.1%)

### Known invalid proposals to filter at QC

- `BorradorSnapshotNotFoundError` → `BorradorBorradorNotFoundError` (stem stuttering)
- `Borrador100Snapshot` → `Borrador100Borrador` (stem stuttering — Snapshot here is generic infra)
- `RentaIncomeType` → `RentaRentaType` (stem stuttering)
- `RentalFinca` → `FincasFinca` (Fincas is a plural noun, wrong as singular-class prefix; also requires Renta/Rental adjudication first)
- All `Snapshot → Borrador` proposals where Snapshot refers to generic capture/cache state (NOT to AEAT pre-filled Modelo drafts)

### Confirmed KEEP — international standard

- All `VAT*` classes in `src/aeat/domain/vat/_schema.py` and `_classification.py` (VAT is an internationally recognised tax acronym; ADR Specialist will rule whether to migrate to `IVA*` per Spanish-stem mandate, but currently flagged keep)

### Confirmed KEEP — generic infra

- `ProfileSnapshot`, `UserProfileSnapshot`, `AeatGateEnvSnapshot`, `RegistrySnapshot`, `RegistrySnapshotRef`, `RegistrySnapshotError`, `ProfileSnapshotPolicy`, `ProfileSnapshotHashMismatchError`, `ProfileSnapshotNotFoundError` — Snapshot used as generic state-capture pattern, not AEAT-Borrador semantic

### Inventory rows — top-priority refactor targets (clean subset)

The full 189-row table is voluminous and will be persisted by the ADR Specialist after QC. Below is the high-confidence subset that survives an initial PM filter:

#### Filing → Modelo cluster (domain & application)

| Current | Location |
| --- | --- |
| `FilingDraft` | `src/aeat/domain/filing/_schema.py:138` |
| `FilingDraftStatus` | `src/aeat/domain/filing/_schema.py:26` |
| `FilingValue` / `FilingValueKind` / `FilingBindingValue` / `FilingValidationFinding` / `FilingApprovalBasis` | `src/aeat/domain/filing/_schema.py` |
| `FilingValidator` | `src/aeat/domain/filing/_validator.py:33` |
| `FilingAmendment` / `FilingAmendmentError` family | `src/aeat/domain/filing/_amendment.py`, `_errors.py` |
| `FilingDraftError` / `FilingBuilderError` / `FilingValidationError` / `FilingComputationError` / `FilingImportError` / `FilingExportError` / `FilingExportValidationError` | `src/aeat/domain/filing/_errors.py` |
| `FilingProfile` | `src/aeat/domain/filing/_protocols.py:171` |
| `FilingDraftRepository` | `src/aeat/domain/filing/_repository.py:27` |
| `FilingRecord` / `FilingRecordStatus` / `FilingRecordCatalogue` / `FilingRecordPersistenceError` / `FilingRecordCatalogueRepository` | `src/aeat/domain/modelos/_filing_record.py`, `_filing_repository.py` |
| `FilingObligation` / `FilingEnrollment` / `FilingIVAProfile` | `src/aeat/domain/deadlines/_models.py` |
| `FilingScheduleDefinition` | `src/aeat/domain/calculations/registry/_schema.py:1140` |
| `RegistryFilingObservation` / `OracleFilingObservation` / `RegistryFilingObservationRequirement` / `_PreviousFilingSelector` | `src/aeat/domain/calculations/registry/_bindings.py` |
| `FilingApplicationError` / `FilingCalculateError` | `src/aeat/application/filing/errors.py` |
| `FilingHistory` / `FilingHistoryEntry` / `FilingHistoryRepository` | `src/aeat/application/filing/_history_models.py`, `_history_repository.py` |
| `FilingApprovalStaleReason` | `src/aeat/application/filing/_review.py:52` |
| `FilingDivergenceKind` / `FilingDraftRef` | `src/aeat/application/filing/reconciliation/` |
| `FilingOperatorProfile` / `RegistryFilingSubview` / `FilingTestProfile` / `FilingTestDeadlineStatus` / `FilingTestDeadlineChecker` | `src/aeat/application/filing/runtime.py`, `testing.py` |
| `FilingDraftBuilderAdapter` / `RegistryFilingDraftProtocol` / `FilingDraftBuilderProtocol` / `FilingInputsProviderProtocol` | `src/aeat/application/workflow/_adapters.py`, `_protocols.py` |
| `FilingRecordNotFoundError` / `ExternalFilingImportError` | `src/aeat/application/modelo/_actions.py` |
| `FilingFixtureError` | `src/aeat/core/errors/__init__.py:87` |
| `FilingRecordPayload` / `FilingRecordListResult` / `FilingRecordShowResult` | `src/aeat/entrypoints/cli/_modelo_payloads.py` |
| `FilingFindingSeverity` / `FilingFinding` / `FilingDraftLike` / `DraftLoader` / `DraftStatus` / `SubmittedFiling` | `src/aeat/domain/submission/` |
| `PdfFilingImportError` | `src/aeat/domain/justificante/_errors.py:15` |

#### Declaration → Declaracion cluster (outbound + application + domain)

| Current | Location |
| --- | --- |
| `Declaration` / `DeclarationsRegisterSession` | `src/aeat/adapters/outbound/aeat/sede/_declarations.py` |
| `FiledDeclarationArtefact` / `FiledDeclarationObservation` | `src/aeat/adapters/outbound/aeat/sede/_schema.py` |
| `FiledDeclarationObservationStore` | `src/aeat/adapters/outbound/aeat/sede/_observation_store.py` |
| `DeclarationCalculateNextAction` / `DeclarationCalculateSummary` | `src/aeat/application/filing/_calculate.py` |
| `DeclarationExportFormat` / `DeclarationVerifyVerdict` / `DeclarationExportResult` / `DeclarationVerifyResult` | `src/aeat/application/filing/_export.py` |
| `DeclarationEditSpec` | `src/aeat/application/review/_edit.py:479` |
| `DeclarationReviewFilterKey` / `DeclarationReviewStatus` / `DeclarationReviewFilterSpec` | `src/aeat/application/review/_filter.py` |
| `DeclarationPointer` | `src/aeat/application/workflow/_models.py:94` |
| `DeclarationParseError` | `src/aeat/domain/filing/reconciliation/_errors.py:17` |
| `ReconciliationDeclarationSourceUnsupportedError` | `src/aeat/application/modelo/_reconcile.py:112` |
| `CrossReferenceApplicabilityDeclaration` | `src/aeat/domain/calculations/registry/_live_parity.py:513` |
| `RentaDeclarationType` | `src/aeat/domain/profile/_renta_codes.py:14` |

#### Census → Censo cluster (application + domain + outbound)

| Current | Location |
| --- | --- |
| `CensusSyncError` / `CensusNotAvailableError` / `CensusFieldValidationError` / `CensusApplyConflictError` | `src/aeat/application/profile/_census_errors.py` |
| `CensusComparisonStatus` / `CensusFieldComparison` / `CensusProfileComparison` / `CensusApplyResult` / `CensusSyncService` | `src/aeat/application/profile/_census_sync.py` |
| `CensusStaleRefusedError` | `src/aeat/domain/modelos/_errors.py:36` |
| `CensusRatioMismatchError` | `src/aeat/domain/usage_ratios/_errors.py:46` |
| `RatiosCensusOverrideWarning` | `src/aeat/application/ledger/_ratios.py:187` |
| `CensusModeloRole` / `CensusModeloEventKind` / `CensusModeloFoundationLogFields` / `CensusModeloOwnership` / `CensusModeloFoundationContract` / `CensusModeloFoundationCommand` / `CensusModeloFoundationResult` | `src/aeat/domain/calculations/registry/_census_modelos.py` |
| `CensusFactSet` / `CensusParseError` | `src/aeat/adapters/outbound/aeat/sede/_census.py` |

#### Rental cluster (Renta/Rental adjudication required FIRST)

All `Rental*` identifiers in `src/aeat/domain/rental/_models.py`, `_repository.py`, `_aggregates.py`, `_errors.py` and `src/aeat/adapters/persistence/storage/sql/_orm.py` are blocked pending ADR ruling on whether the rental domain becomes:
- `domain/fincas` (real-estate-property-focused naming), or
- `domain/alquiler` (rental-contract-focused naming), or
- stays `domain/rental` because it is operational, not regulatory

ADR Specialist must rule on this BEFORE coding agents touch any of these identifiers.

### Disposition

The full raw table (189 rows) is too long for direct inclusion here without context bloat. The high-priority subset above gives ADR Specialist sufficient surface to build the canonical rename ledger. If a missing identifier is needed during ADR drafting, the project manager has the raw data in conversation state and will inject it on request.
---

## Snapshot Service Consolidation Proposal

This section presents a detailed consolidation strategy for the 5 near-identical snapshot services flagged in Finding B1 (Category B). Structural analysis reveals 70%+ method-signature and validation-logic duplication across \_borrador.py\, \_borrador_100.py\, \_census.py\, \_expedientes.py\, and \_notifications.py\.

### 1. Body Delta Inventory: Structural Overlap Analysis

#### Summary Table

| Artifact | Borrador Legacy | Borrador100 Canonical | Census | Expedientes | Notifications | Status |
|----------|---|---|---|---|---|---|
| **NotFoundError** | Custom | Uses LiveApplicationInputError | Uses LiveApplicationInputError | Custom | Custom | INCONSISTENT: 3/5 custom, 2/5 delegate |
| **SnapshotPayload** | Borrador100Snapshot | Borrador100Snapshot | CensusSnapshot | PersistedExpedientesSnapshot | PersistedNotificationsSnapshot | 100% DUPLICATED: Same 7-9 fields, domain-specific data field |
| **StateEnum** | None | Borrador100SnapshotState (3-state) | CensusSnapshotState (3-state) | None | None | SPLIT: 2/5 with identical enums; 3/5 stateless |
| **capture()** | Lines 147-178 | Lines 243-284 | Lines 328-372 | Lines 112-133 | Lines 117-145 | ~95% IDENTICAL: dedup pattern, params differ |
| **list_snapshots()** | Lines 180-189 | Lines 286-297 | Lines 374-386 | Lines 135-136 | Lines 147-148 | ~85% IDENTICAL: load + filter, axes differ |
| **show()** | Lines 191-213 | Lines 299-300 | Lines 388-389 | Lines 138-160 | Lines 150-173 | ~80% IDENTICAL: prefix-match logic |
| **latest()** | Lines 215-225 | Lines 302-310 | Lines 391-395 | Lines 162-170 | Lines 175-184 | ~90% IDENTICAL: max-by-captured_at |
| **discard()** | Lines 227-252 | State transition | Lines 397-428 | None | None | PARTIAL: Only Borrador100/Census |
| **Repository** | None (JSONL) | Borrador100SnapshotRepository | CensusSnapshotRepository | None (JSONL) | None (JSONL) | SPLIT: SecureObject vs. file-based |
| **_derive_snapshot_id()** | Lines 97-110 | Lines 81-107 | Lines 150-175 | Lines 74-76 | Lines 76-78 | ~70% DUPLICATED: SHA-256, canonical format differs |
| **State Validator** | None | Lines 52-66 | Lines 111-135 | None | None | VERBATIM DUPLICATED: 14-line identical block |
| **_supersede_current_for_axis()** | None | Lines 312-328 | Lines 430-444 | None | None | VERBATIM DUPLICATED: axis parameter only differs |

#### Key Findings

1. **Verbatim-Identical Code** (~70 lines safe to extract):
   - State-machine validator (Borrador100 vs. Census): identical 14-line validation block
   - Supersession/auto-latest logic: identical conditional patterns, axis parameter differs
   - Deduplication flow: check-exists → dedup → save → return

2. **Structurally-Identical, Field-Renamed** (parameterizable):
   - SnapshotPayload: snapshot_id, bucket_id, captured_at, source_url, persisted_at + domain-specific data (binding_values, census_facts, rows, declarations)
   - capture() signature: identical dedup logic, parameter set by domain axis (tax_year, filing_year, profile_id, etc.)
   - _derive_snapshot_id(): identical SHA-256 algorithm, canonical format differs (custom strings vs. JSON serialization)

3. **Genuinely Subclass-Specific** (cannot consolidate):
   - State enum (present Borrador100/Census, absent Expedientes/Notifications/legacy Borrador)
   - Repository backend (SecureObjectRepository for Borrador100/Census, file-based _load/_save for legacy)
   - Discard semantics (Borrador100: reason field; Census: actor audit metadata; Expedientes/Notifications: absent)
   - Domain axis for filtering and supersession (filing_year/period vs. profile_id vs. bare bucket_id)

---

### 2. Proposed Consolidation Architecture

#### Base Classes (New Module: src/aeat/application/live/_snapshot_base.py)

**SnapshotLifecycleState** - Shared 3-state enum:
- ACTIVE: Currently valid; consumable by readers
- SUPERSEDED: Replaced by newer snapshot; retained for audit
- DISCARDED: Explicitly retired by operator; ignored by readers

**SnapshotRepository[TPayload]** - Storage protocol:
- bucket_id property
- exists(snapshot_id: str) -> bool
- load(snapshot_id: str) -> TPayload
- list_snapshots() -> tuple[TPayload, ...]
- resolve(snapshot_id: str) -> TPayload (full or prefix match)
- save(snapshot: TPayload) -> None

**SnapshotService[TPayload]** - Abstract lifecycle base:
- __init__(bucket_id, repository=None)
- capture(**kwargs) -> TPayload (dedup by content-addressed id)
- list_snapshots(**kwargs) -> tuple[TPayload, ...] (load + filter)
- resolve_snapshot(snapshot_id: str) -> TPayload (lookup by full/prefix)
- _supersede_current_for_axis(replacement: TPayload) -> None (mark prior ACTIVE as SUPERSEDED)
- _latest_active_for_axis(snapshot: TPayload) -> TPayload | None (query prior ACTIVE)

**Shared Helpers**:
- derive_snapshot_id_from_json(parts: dict[str, Any]) -> str (SHA-256 hex)
- enforce_snapshot_state_invariants(snapshot: SnapshotPayloadBase) -> None (state machine validation)

---

### 3. Migration Sequence (4 Phases)

#### Phase 1: Borrador100 (Proof-of-Concept)
- Extract _snapshot_base.py with shared classes
- Refactor Borrador100SnapshotRepository to implement protocol
- Move validators, helpers to base
- Gate: Run full test suite; validate zero behavior change
- **Risk: LOW** (pure extraction; no semantic change)

#### Phase 2: Census Service
- Migrate to inherited SnapshotService base
- Consolidate validators and supersession logic
- Gate: Run full test suite; validate state transitions
- **Risk: LOW** (isomorphic to Borrador100)

#### Phase 3: Legacy Services (Expedientes, Notifications, Borrador)
- Create StatelessSnapshotService variant (no state machine)
- Consolidate _storage_path(), _load(), _save() into file-based repository
- Decide: Retire legacy Borrador or keep as-is? (Recommend retirement)
- Gate: Per-service test suite validation
- **Risk: MODERATE** (file-based services have minor path differences)

#### Phase 4: Exception Alignment
- Define shared SnapshotNotFoundError base
- Update legacy services to inherit; preserve CLI-compat aliases
- Gate: Validate exception catching in CLI handlers
- **Risk: LOW** (exception name aliases preserve compat)

---

### 4. Risk Assessment: State-Machine Semantic Differences

#### Risk: LOW (Borrador100 + Census)
- State machines are **semantically identical**: ACTIVE (no pointer) → SUPERSEDED (pointer required) → DISCARDED (audit)
- Both auto-supersede on newer capture; both support explicit discard
- Mitigation: Shared validator with optional audit-metadata parameters

#### Risk: MODERATE (Expedientes + Notifications)
- **Stateless**: Append-only JSONL; no supersession; no discard semantics
- Operators see chronological history only
- Mitigation: Use StatelessSnapshotService variant; do NOT inherit stateful base

#### Risk: MODERATE-TO-HIGH (Legacy Borrador)
- Discard incompatible with 3-state enum (uses bool flag instead of DISCARDED state)
- Not a state machine; lacks auto-supersession logic
- Mitigation: **Mark deprecated**; recommend migration to Borrador100. Do NOT consolidate. Retire per 2026-05-19 ADR.

---

### 5. Out-of-Scope: Operator-Visible Contracts

**MUST NOT change** (affect CLI and API boundaries):

1. Exception class names (BorradorSnapshotNotFoundError, etc.) → keep aliases; inherit from base
2. Service class names (Borrador100SnapshotService, etc.) → refactor internals only
3. Method signatures (keyword-only args: bucket_id, snapshot_id, etc.) → base uses **kwargs
4. Storage paths (aeat_audit_dir/live/{type}/*.jsonl) → preserve exactly
5. Snapshot ID format (SHA-256 hex) → existing snapshots remain valid

---

### 6. Quantified Metrics

| Metric | Value |
|--------|-------|
| Total lines of code (5 services) | ~1,040 |
| Redundant lines (validator + helpers) | ~380 (37%) |
| Deduplication savings | 200–250 lines (19–24%) |
| Methods with >90% overlap | 4 (capture, list_snapshots, show, latest) |
| Verbatim-identical blocks (>10 lines) | 3 (validator, supersession, load) |
| Proposed base class members | 12 (6 abstract + 6 helpers) |
| Consolidation risk level | **MODERATE**: Stateful=LOW, Stateless=MODERATE-HIGH |
| Estimated refactoring effort | 40–60 engineering hours (3–4 parallel agents, 1 week) |

---

### 7. Recommendations

**Consolidation is HIGH-VALUE and FEASIBLE** under:

**DO consolidate**:
- Borrador100 + Census → SnapshotService[TPayload, TStateEnum] base
- State machine validator → enforce_snapshot_state_invariants()
- Supersession/auto-latest → axis-parameterized helpers
- derive_snapshot_id_from_json() across all 5

**DO NOT consolidate**:
- Legacy Borrador → deprecate per ADR; retire
- Expedientes/Notifications → use StatelessSnapshotService variant
- Exception class names → preserve for CLI compat

**Defer**:
- File-based path consolidation → tentative; Phase 3 only if orthogonal
- Audit metadata standardization → document in base; allow subclass customization

**Next Steps**: Draft consolidation ADR, implement Phase 1 PoC, validate test suite, coordinate Phases 2–4.
