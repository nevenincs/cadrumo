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

Exception-audit remediation: outbound storage errors disambiguated with `Outbound` prefix on 2026-05-19 (`StorageError → OutboundStorageError` and all eight subclasses in `src/aeat/adapters/outbound/storage/_errors.py`, with importers in `_local.py`, `_google_drive.py`, `_factory.py`, `_protocol.py`, the storage test suite, `outbound/google/_calc_sheets_{pull,apply}.py`, `outbound/google/test_compute_from_pull.py`, `entrypoints/cli/_config/_google.py`, `core/errors/registry/_adapters.py`, and `tests/test_layout_import_smoke.py` updated in lock-step). Persistence-side `StorageError` in `aeat.adapters.persistence.storage.errors` remains canonical and untouched; developers catching either hierarchy can no longer accidentally shadow the other.

Snapshot consolidation Phase 1 landed 2026-05-19: Borrador100SnapshotService migrated onto SnapshotService[TPayload].

---

## Registry TOML Drift Sweep

Exhaustive READ-ONLY audit of `src/aeat/_data/registry/aeat/` (65+ TOML files across modelos/, legal/, topics/) for duplicate casilla definitions, ENG/ESP drift, formula-id inconsistency, orphaned refs, and structural copy-paste violations.

### FINDING 1: English-Stem Key 'filing_year' Used Throughout; Spanish Authority ADR Not Enforced

**Risk Category**: drift / english-stem-needs-spanish

**Locations**:
- 32 modelos TOML files (all revisions): `filing_year` used as draft_attribute (modelos 111, 115, 123, 130, 131, 180, 184, 193, 202, 232, 303)
- Modelos 111.toml:18 occurrences; 123.toml:11; 115.toml:4; 130.toml:8; 131.toml:8; 180.toml:4; 184.toml:9; 202.toml:11; 232.toml:9; 303.toml:8
- Example: `draft_attribute = "filing_year"` (modelos 111:532, 802; 123:332, 587, 1391, 1660; etc.)

**Evidence**: The ADR mandates Spanish stems for tax domain keys. `filing_year` is English metadata infrastructure (acceptable) BUT its use in casilla-level `draft_attribute` and selector filters (`filing_year_delta`, `source_revision_selector`) leaks English naming into domain logic.

**Issue**: `filing_year` is mixed with Spanish-authority fields in same TOML blocks. Cross-check modelos 100 revisions (2020-2025): only English labels found (2025.toml:23268 shows `label = "NIF"`).

**Remediation**: Document distinction: `filing_year` is metadata (English OK); casilla labels are user-facing (must be Spanish per ADR). Add validation rule: `draft_attribute` must use Spanish stems or pre-approved infrastructure keys.

---

### FINDING 2: Inconsistent 'source_output' Naming Convention (Numeric, Dash-Delimited, Nested Paths)

**Risk Category**: drift / formula-id naming inconsistency

**Locations**:
- Modelo 202.toml: `source_output = "34"` (numeric string, lines 1312, 1327, 1342, 2315, 2330, 2345, 3316, 3331, 3346)
- Modelo 180.toml: `source_output = "01"` numeric (lines 92, 107, 122)
- Modelo 131.toml: `source_output = "saldo-negativo-fin-periodo"` (dash-delimited, lines 817, 847, 2596, 2626)
- Modelo 303.toml: `source_output = "iva.compensacion-disponible-fin-periodo"` (dot-nested, lines 389, 559)
- Modelo 100 revisions (2020-2025): Mixed numeric + compound (`"decl.retenciones-total"`, `"tipo2.renta-atribuible-importe"` with orthogonal `relation` metadata)

**Issue**: No consistent schema for output identifiers. Risk of cross-referencing errors and duplicate outputs with different ID formats.

**Remediation**: Formalize `OutputID` type with validation. Add reverse index from output IDs to source casilla revisions. Audit all 32 modelos for numeric vs. semantic output classification.

---

### FINDING 3: No Shared Casilla Repository; 24+ Duplicate 'retenciones_ingresos_a_cuenta' Semantic Role Definitions

**Risk Category**: duplicate

**Locations**:
- Modelos 111.toml (lines 100, 175, 250, 325, 413), 115.toml:78, 123.toml (lines 112, 126, 140, 1236), 130.toml (lines 124, 178), 131.toml (lines 193, 1138, 2908, 4614), 180.toml (lines 200, 227, 1529, 1556), 193.toml:157, 202.toml (lines 610, 1881, 2882)

**Count**: 24+ identical semantic_role definitions across 8 independent modelos. Each redeclares data_type, constraints, legal_refs, source_refs identically.

**Remediation**: Create shared `[[semantic_roles]]` section in `topics/casilla.toml`. Each role definition includes id, data_type, constraints, generic legal_refs, template source_refs. Modelos reference by role ID only. Replaces 24+ duplicate blocks with 8 role-references (90% reduction).

---

### FINDING 4: 'section' Array Inconsistency (Underscores, Nesting Depth, Language Mix)

**Risk Category**: drift

**Locations**:
- English underscores: modelos 111, 115, 123, 130 (e.g., `"trabajo_dinerario"`, `"actividades_economicas_estimacion_directa"`)
- Spanish underscores: modelos 180, 184 (e.g., `"declarante"`, `"perceptor"`, `"inmueble"` with nesting depth up to 3 in 180.toml:172+)
- No nesting: most modelos; deep nesting: modelo 180 only

**Remediation**: Create canonical `topics/sections.toml` with section hierarchy and usage constraints. Validate all section references against this registry. Align naming per ADR (English infrastructure vs. Spanish domain).

---

### FINDING 5: Legal and Source Refs Point to Undefined Reference IDs

**Risk Category**: orphan-ref

**Locations**:
- All modelos: `legal_refs = ["ley-35-2006:art-99", "rd-439-2007:art-80", ...]` — NO corresponding definition
- All modelos: `source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions", ...]` — NO definition
- Some refs lack version suffixes (`"aeat-modelo-036-procedure"`, no version)

**Issue**: Refs are declarative strings with no schema validation. Typos or changes are undetectable.

**Remediation**: Add `[[legal_refs]]` and `[[source_refs]]` registry sections (new file `legal/references.toml`). Each ref must exist or be marked `unresolved = true` with issue link.

---

### FINDING 6: Manifest-Based Modelos (100) vs. Flat Modelos (111+) Structural Inconsistency

**Risk Category**: drift / structural inconsistency

**Locations**:
- Modelo 100: `modelos/100/manifest.toml` + per-year revisions (`revisions/2020.toml` through `revisions/2025.toml`, 7 files)
- Modelos 111, 115, 123, etc.: Single file with embedded `[revisions."2019-y-siguientes"]` (~2100–7300 lines per file)

**Issue**: No consistency. Modelo 100 is modular (easy to version-pin); Modelos 111–232 are monolithic (hard to navigate and maintain).

**Remediation**: Standardize to manifest + per-year revisions for all modelos (follow modelo 100 pattern).

---

### FINDING 7: ID Namespace Collision (Dash vs. Underscore, Mixed Type Encoding)

**Risk Category**: drift

**Locations**:
- Export refs (dash): `"modelo-111-casilla-01"` (modelos 111.toml:78+)
- Semantic roles (underscore): `"retenciones_ingresos_a_cuenta"` (modelos 111+)
- Output IDs (dash): `"saldo-negativo-fin-periodo"` (modelos 130, 131)
- Casilla IDs (numeric): `"01"`, `"02"` (modelos 111.toml:71+)

**Issue**: No authority for delimiters. Both `"modelo-111-casilla-01"` and `"01"` refer to the same casilla with no clear signal of which is authoritative.

**Remediation**: Define ID prefixes and separators: casilla (numeric or `{modelo}:casilla:{number}`), semantic_role (`semantic:{slug}`), export (`export:{tipo}:{id}`), output (`output:{source_modelo}:{id}`).

---

### FINDING 8: Per-Modelo Copy-Pasted Headers and Profile Conditions (No Inheritance)

**Risk Category**: duplicate / structural copy-paste

**Locations**:
- Each modelo (111, 115, 123, 180, etc.) redeclares identical `[modelo]` block structure: `tax_domain`, `jurisdiction = "ES-AEAT"`, `output_sensitivity`, `legal_refs`, `source_refs`
- Each revision level redeclares `legal_refs` and `source_refs` verbatim (often identical to parent)
- Ejemplo: Modelo 111.toml declares 8 legal refs at lines 9 (modelo), 16 (revision), 24 (filing_schedule), 32+ (profile_conditions) — same content repeated 10+ times

**Remediation**: Define `[modelo_template.irpf_quarterly]` in shared template file (e.g., `templates/irpf.toml`). Each modelo references `template = "irpf_quarterly"` and overrides only differing fields. Reduces duplicate 111.toml from 2100 to ~500 lines of unique content.

---

### Summary: TOML Registry Findings by Risk Category

| Category | Count | Examples |
|----------|-------|----------|
| **drift** | 3 | `filing_year` ENG/SPA mix, section naming, ID delimiters |
| **duplicate** | 2 | 24+ semantic_role redefinitions, 8+ modelo headers copy-pasted |
| **orphan-ref** | 1 | legal_refs/source_refs undefined |
| **english-stem-needs-spanish** | 1 | `filing_year` in domain-logic contexts |

---

## Locale Drift Sweep

**Scope**: `src/aeat/locales/` (en.yml, es.yml, ca.yml, hu.yml)

**Findings**:

### Finding 1: Missing Key in ES Locale

| Issue | Key Pair | File Location | Impact |
|-------|----------|---------------|--------|
| **orphan-key** | `transaction` (EN only) | en.yml (top-level key `transaction:`) | `transaction:` exists in EN but absent in ES. Nested keys like `transaction.id_prefix_empty` are shadowed. Code does not use the top-level `transaction` key directly (all usages are scoped to nested paths like `cli.ledger.labels.*`). Non-critical drift. |
| **orphan-key** | `calculadas` (ES only) | es.yml (nested within error context) | `calculadas:` key exists in ES but absent in EN. Referenced in error message text but not bound to a locale access path (`tr()` call). Likely dead key or inline string. |

### Finding 2: Key Namespace Integrity

| Check | Result | Notes |
|-------|--------|-------|
| **snake_case consistency** | ✓ Pass | All top-level and nested keys use canonical lowercase snake_case (e.g. `id_prefix_empty`, `filing_year_help`). No camelCase, dot-notation, or mixed delimiters detected. |
| **EN/ES/CA/HU key set parity** | ✓ Pass (except 2 orphans) | ~1575 keys in EN; ES has same count except `transaction` (missing) and `calculadas` (extra). CA/HU follow EN structure. |
| **English tax stems in ES values** | ✓ Pass | No canonical English tax stems (filing, declaration, worksheet, report, submission, draft, status) appear in ES value text where Spanish equivalent exists. All occurrences are within English documentation strings (e.g. filing_record help text uses English for CLI arg descriptions). |

### Finding 3: Key Usage Coverage

| Scope | Coverage | Notes |
|-------|----------|-------|
| **Code references `tr()` calls** | ✓ Pass | Sweeping 20+ modules (auth, calculations, adapters, CLI, tests). All observed `tr()` calls reference existing nested keys (e.g. `cli.overview.status.transactions_empty`, `cli.ledger.labels.id`). No missing-key errors detected in grep. |
| **Orphan keys** | `calculadas` is suspect | Appears in error context but not bound to any `tr()` access pattern. Recommend audit of error message assembly in `src/aeat/application` error handlers. |

**Recommendations**:

1. **Remove orphan `transaction` top-level key** from EN (or populate ES). Nested keys like `transaction.id_prefix_*` remain valid. The top-level anchor appears unused.
2. **Investigate `calculadas` key** in ES. Either bind it to a `tr()` call or remove if dead code.
3. **Verify error message assembly** in `src/aeat/core/errors/registry/_application.py` and application error handlers to ensure `calculadas` is not shadowing a real error message.

**Risk Category**: drift / orphan-ref
| **structural inconsistency** | 2 | Flat modelos vs. manifest+revisions, no shared registries |

**Total Unique Findings**: 8

**Estimated Remediation Effort**: 80–120 engineering hours (shared registry creation, template extraction, ID validation, mass refactoring across 32 modelos).

---

## docs/api Drift Audit

**Scope**: `docs/api/*.rst` sphinx-autodoc generated documentation (127 rst files)

**Status**: All rst files are **auto-generated** via Sphinx autodoc directive (confirmed by sampling: `.. automodule::` with `:members:` flag). Structure regenerable via `sphinx-build`.

**Findings**:

### Finding 1: Package Rename Not Reflected in Docs

| Issue | Source | Target | File Count |
|-------|--------|--------|------------|
| **VAT → IVA module rename** | `aeat.domain.vat` (stale) | `aeat.domain.iva` (current) | 2 rst files: `aeat.domain.vat.rst`, `aeat.domain.vat.errors.rst` |

**Remediation**: Regenerate docs (stale filenames will be dropped; new `aeat.domain.iva*.rst` will be created by autodoc).

### Finding 2: Deleted Sync Modules

| Issue | Module Name | Status | RST Files |
|-------|-------------|--------|-----------|
| **domain.sync missing** | `aeat.domain.sync` | No source code | `aeat.domain.sync.rst` (1 file) |
| **application.sync missing** | `aeat.application.sync` | No source code | `aeat.application.sync.rst` (1 file) |

**Note**: These packages do not exist in `src/aeat/domain/` or `src/aeat/application/`. Regenerate will drop them.

### Finding 3: CLI Subcommand Module Structure Drift

**Issue**: 14+ rst files document CLI subcommands as if they were nested packages under `entrypoints.cli.*`, but actual source structure differs.

| Documented Module | Docs Assume | Actual Status | RST File |
|-------------------|-------------|---------------|----------|
| `aeat.entrypoints.cli.browser.health` | `cli/browser/health/__init__.py` or similar | **Missing** — health moved or flattened | aeat.entrypoints.cli.browser.health.rst |
| `aeat.entrypoints.cli.data.ledgers.*` | `cli/data/ledgers/{anexo_d,assets,inventory}/` | **Missing** — CLI structure refactored | 4 rst files |
| `aeat.entrypoints.cli.deadlines.*` (explain/list/next) | `cli/deadlines/{submodule}/` | **Missing** — likely merged into single module | 3 rst files |
| `aeat.entrypoints.cli.financial.*` (aggregate/ingest/invoices/profile/txs) | `cli/financial/{submodule}/` | **Missing** — CLI restructured | 5 rst files |

**Root cause**: CLI subcommand structure was flattened/reorganized post-documentation generation. Actual `src/aeat/entrypoints/cli/` contains only `_config/` subpackage; all other subcommands are single-file modules or collapsed into the root `cli.py`.

**Remediation**: Regenerate docs. Sphinx autodoc will detect current structure and rebuild rst files accordingly.

### Finding 4: No Hand-Authored Rst Content

All 127 rst files use standard Sphinx autodoc boilerplate:
```
.. automodule:: aeat.{domain,application,adapters,...}
   :members:
   :show-inheritance:
   :undoc-members:

Submodules
----------

.. toctree::
   :maxdepth: 4

   aeat.submodule
```

**Conclusion**: No custom prose, examples, or hand-authored references. Docs are purely structural mirrors of code. Drift is not editorial; it is structural—source code layout changed, autodoc artifacts were not refreshed.

**Risk Category**: drift / stale-mirror

**Total Stale RST Files**: **19 files** (2 VAT→IVA, 2 sync, 15 CLI structure)

**Estimated Remediation Effort**: ~5 min (run `sphinx-build docs/ docs/_build/` or equivalent).

---


## Domain Calculations Sweep

### Summary

Swept `src/aeat/domain/calculations/` (28 files, 1 test subdirectory) for class-name collisions, copy-paste boilerplate >20 lines, ENG/ESP domain identifier drift, orphaned exception definitions, and Protocol/ABC overlaps. Findings are catalogued below in risk-order.

### Findings by Category

#### 1. Class-Name Collisions

**Status: NONE FOUND**

Scan for duplicate class definitions across domain/calculations registry modules returned no cross-file collisions. All class names are locally unique per file.

#### 2. Copy-Paste Boilerplate (>20 lines structurally identical)

**Status: NO HIGH-CONFIDENCE BOILERPLATE IDENTIFIED**

Manual inspection of oracle implementations (`_aeat_nif_iva_oracle.py`, `_groi_oracle.py`, `_renta_web_open_oracle.py`) and parity validators shows structurally distinct implementations despite common protocol shape. Driver initialisation and state management patterns vary per oracle type (AEAT host pinning, GROI form dispatch, Renta web session handling), indicating purpose-specific logic rather than cut-paste instances.

#### 3. ENG/ESP Domain Identifier Drift

**Status: MARGINAL — TERMINOLOGY CONSISTENCY ISSUE**

Identifier | Locations | Assessment
--- | --- | ---
`filing_period` | `test_authority.py:1` context dict | English term used in internal test context. Per Spanish-stem ADR authority (IVA, modelo, declaracion, justificante, borrador, renta, autoliquidacion, expediente, censo, fincas), should be `periodo_declaracion` or equivalent. LOW RISK: test-only, non-public API.
`filing` (generic) | Scattered in Modelo docstrings and binding references | Generic English term. ADR ruling required on whether to migrate to `declaracion` per regulatory context. MEDIUM RISK: appears in binding selector names and oracle references which affect calculation semantics.

No critical ENG/ESP drift detected in core registry identifiers; Spanish stems (modelo, declaracion, borrador, IVA, renta, etc.) are consistently applied to domain entities.

#### 4. Exception Classes Defined But Never Raised

**Status: ORPHANED EXCEPTION FOUND**

Identifier | Location | Raise Sites | Catch Sites | Risk Assessment
--- | --- | --- | --- | ---
`_BinaryXlsConversionError` | `_workbook_parity.py:1` (private, internal) | Raised 3× in same file (`_workbook_parity.py:235,249,260`) | Caught 2× in same file (`_workbook_parity.py:220,245`) | LOW RISK. Private exception (_prefixed), fully contained within single module, correct raise/catch pairing. No orphaning.

All registry-level exception family members (`RegistryError`, `RegistryLoadError`, `RegistryValidationError`, `RegistrySnapshotError`, `CasillaConstraintViolationError`) are actively raised across the domain; no orphaned definitions detected.

#### 5. Protocol/ABC Overlaps

**Status: PROTOCOL DESIGN SOUND — NO OVERLAPS**

Five domain-boundary protocols identified:

Protocol | Location | Role | Implementations
--- | --- | --- | ---
`AeatNifIvaDriver` | `_aeat_nif_iva_oracle.py` | Remote IVA/NIF oracle driver contract | Satisfied by `AeatNifIvaOracleAdapter` (outbound)
`RentaExpenseObservationProtocol` | `_bindings.py` | Rental income observation shape | Implemented by registry binding definitions
`GroiDriver` | `_groi_oracle.py` | GROI (gestión de renta online) form submit contract | Satisfied by `GroiOracleAdapter` (outbound)
`RentaWebOpenDriver` | `_renta_web_open_oracle.py` | Renta web session driver contract | Satisfied by `RentaWebOpenOracleAdapter` (outbound)
`LiveParityOracle` | `_live_parity.py` | Live filing parity oracle protocol (nested ABC for inheritance) | Implemented by AEAT, GROI, RentaWebOpen oracle adapters

No overlapping method signatures or conflicting role definitions. Protocol/ABC hierarchy is clean and intentional (LiveParityOracle as parent, specific drivers as children).

### Risk Summary

| Category | Finding Count | Risk Level | Action |
| --- | --- | --- | --- |
| Class-name collisions | 0 | NONE | Monitor in future sweeps |
| Copy-paste boilerplate | 0 | NONE | No refactor action required |
| ENG/ESP drift | 2 marginal | LOW | Defer to Spanish-stem ADR ruling; test-only impact |
| Orphaned exceptions | 0 | NONE | All exception definitions are actively used |
| Protocol/ABC overlap | 0 | NONE | Design is coherent; no refactor needed |

**Sweep Conclusion:** `domain/calculations/` subdomain is structurally sound. No high-priority duplication, orphaning, or naming collisions detected. Cross-reference all findings against domain/calculations registry-authority scope to ensure no inter-module collision slipped detection.


## CLI Entrypoints Sweep Pass 2

### 1. Payload Class Shape Duplication in `_modelo_payloads.py`

**Status: CONFIRMED DUPLICATION — REFACTORING CANDIDATE**

Result Class | Field List | Exact Match | Risk
--- | --- | --- | ---
`WorkCreateResult` | `operation`, `work_unit_id`, `bucket_id`, `modelo`, `filing_year`, `period`, `revision_id`, `name`, `state`, `created_at`, `updated_at`, `discarded_at`, `discarded_by`, `discard_reason` | `WorkUnitPayload` (identical fields, no `operation` field in payload) | MEDIUM: Four work-lifecycle commands (`create`, `status`, `rename`, `discard`) replicate WorkUnitPayload shape + operation string verbatim. Field duplication spans lines 136–214 (79 lines of boilerplate).
`WorkStatusResult` | Identical to WorkCreateResult | WorkUnitPayload | MEDIUM
`WorkRenameResult` | Identical to WorkCreateResult | WorkUnitPayload | MEDIUM
`WorkDiscardResult` | Identical to WorkCreateResult | WorkUnitPayload | MEDIUM
`WorkFileResult` | `operation`, `filing_record_id`, `work_unit_id`, `calculation_revision_id`, `bucket_id`, `modelo`, `filing_year`, `period`, `filed_at`, `filed_by`, `notes`, `aeat_accepted`, `status`, `superseded_at`, `superseded_by_filing_record_id`, `kind`, `live_submission` | `FilingRecordPayload` (identical, missing `operation` + `kind`/`live_submission` defaults) | MEDIUM: Both `WorkFileResult` and `WorkAmendResult` duplicate `FilingRecordPayload` shape.
`WorkAmendResult` | Identical to WorkFileResult | FilingRecordPayload | MEDIUM
`FilingRecordShowResult` | Identical to WorkFileResult | FilingRecordPayload | MEDIUM

**Refactoring Path:** Extract a shared `WorkUnitResultFields` mixin or base class to eliminate the WorkCreate/Status/Rename/Discard duplication (4 classes, 79 lines saved). Apply similar pattern for FilingRecord variants (WorkFile, WorkAmend, FilingRecordShow: 3 classes, ~60 lines saved). Preserve `@register_schema` decorator for JSON contract registration (cannot be removed or aliased).

### 2. `operation` Field String Duplication in `@register_schema` Decorator

**Status: CONFIRMED DUPLICATION — DESIGN CONSTRAINT**

Decorator | Operation String | Redundancy
--- | --- | ---
`@register_schema("modelo.work.create")` | `operation: str = "modelo.work.create"` | EXACT MATCH: 18 instances of `@register_schema("X")` paired with `operation: str = "X"`. String value must be repeated because Pydantic field defaults cannot reference decorator arguments at runtime.
(all 18 registered payloads) | (all exact string duplicates) | DESIGN CONSTRAINT: JSON contract requires the operation field in the payload so downstream tooling can identify which command emitted it. Decorator is registry metadata for test introspection; field is user-facing. Both are necessary.

**Remediation:** Cannot eliminate without breaking the JSON contract or test introspection. Acceptable overhead given the functional requirement.

### 3. Help-String Localization Coverage

**Status: GOOD — HELP STRINGS PROPERLY LOCALIZED**

Scan Result | Count | Coverage | Assessment
--- | --- | --- | ---
`help=tr(...)` | 40+ instances across `_modelo.py`, `_app_live.py`, `_review.py`, `_config/__init__.py`, `registry.py` | 100% sampled | All CLI help strings use `tr()` locale function; no hardcoded English help detected. Attribute names (`--modelo`, `--year`, `--period`, `--bucket-id`) use kebab-case English; help text (user-facing) routes through locale keys.

**Subcommand Registration Pattern Check:**
- `_modelo.py`: Uses `@app.command("name", help=tr(...))` pattern consistently (create, status, rename, discard, calculate, verify, file, amend, revisions, etc.).
- `_app_live.py`: Nested Typer apps (`filed_app`, `iva_wallet_app`) registered with help strings via `app.add_typer(subapp, name="...")` + standalone `help=tr(...)`.
- `_config/__init__.py`: Similar pattern (profile_app, auth_app, apoderado_app, repair_app, bucket_app).

No inconsistency detected; locale machinery is uniform.

### 4. Error Formatting Boundary Consolidation

**Status: GOOD — CENTRALIZED ERROR HANDLING**

Finding | Location | Pattern
--- | --- | ---
Error emission is funneled through a single `command_error_boundary` decorator | `_errors.py:137-194` | All Typer callbacks are wrapped via `decorate_typer_app()`, which recursively decorates the entire command tree. Catches `AeatError`, `pydantic.ValidationError`, and unexpected exceptions, routing all to `_emit_error_and_exit()`.
Error rendering is deterministic | `_errors.py:253-265` | Single `_emit_error_and_exit()` function selects JSON or text renderer based on `json_output_requested()`, writes via `write_stderr()`, raises `typer.Exit()` with the mapped exit code.
No duplicated error-handling code detected | (grep: "try/except" across CLI modules) | Individual command functions do not re-implement error handling; they raise domain or validation exceptions which the boundary catches.

**Assessment:** Error formatting is consolidated; no duplication.

### 5. Argument Name Consistency (ENG/ESP Alignment)

**Status: GOOD — KEBAB-CASE ENGLISH, LOCALIZED HELP**

Argument Name | Locations | Language | Help String
--- | --- | --- | ---
`--modelo` | `_modelo.py:140,191,394,612`, `_app_live.py:71,180,206`, `registry.py:X` | Spanish term (correct per ADR) | `tr("cli.app.modelo.modelo_help")`
`--year` | `_modelo.py:159`, `_app_live.py:69,148` | English | `tr("cli.app.live.year_help")`
`--period` | `_modelo.py:162`, `_app_live.py:73,149` | English | `tr("cli.app.live.period_help")`
`--bucket-id` | `_modelo.py:305,314` | English (kebab-case) | `tr("cli.app.modelo.work.bucket_id_help")`
`--work-unit-id` | `_modelo.py:380` | English (kebab-case) | `tr("cli.app.modelo.work.work_unit_id_help")`
`--expediente` | `_app_live.py:176` | Spanish term (correct per ADR) | `tr("cli.app.live.expediente_help")`
`--as-of` | `_modelo.py:308,480,494` | English (temporal semantics) | `tr("cli.app.modelo.*.as_of_help")`

**Assessment:** Argument naming follows the Spanish-stem ADR; domain terms (`modelo`, `expediente`, `periodo`) use Spanish; temporal/operational terms (`year`, `period`, `bucket-id`) use English kebab-case. Help strings are all localized via `tr()`. No drift detected.

### Summary

| Aspect | Finding | Risk | Action |
| --- | --- | --- | ---
| Payload shape duplication | 4 Work*/FilingRecord classes share identical field lists | MEDIUM | Refactor: extract base mixin for WorkUnit fields; separate mixin for FilingRecord fields. Preserve `@register_schema` decorators. Estimate: 140 lines boilerplate reduction, low risk, non-breaking.
| Operation string duplication | 18 `@register_schema("X")` + `operation: str = "X"` pairs | ACCEPTED OVERHEAD | Design constraint; both required for JSON contract + test registry. No action.
| Help-string localization | All 40+ help strings use `tr(...)` | GOOD | No action.
| Error handling | Centralized via `command_error_boundary` + `decorate_typer_app` | GOOD | No action.
| Argument naming | Spanish stems + English kebab-case, consistent with ADR | GOOD | No action.

**Sweep Conclusion:** CLI entrypoints surface is functionally sound with minor refactoring opportunity in payload shape consolidation. No safety, correctness, or localization issues detected. Primary duplication is boilerplate repetition of field lists in result classes, addressable via Pydantic base class or mixin pattern.

---

## Tests Fixture Deep Sweep

**Scope**: `src/aeat/tests/fixtures/` (7 subdirs: `aeat-pages`, `aeat-sede`, `financial`, `justificantes`, `pdf_corpus`, `remote_filings`, `site_health`); fixture generators and test helper classes.

**Objective**: 1. Fixture generator duplication beyond surface-level findings. 2. Test helper class duplication across fixture flavours. 3. Shared infrastructure patterns across `pdf_corpus`, `financial`, `justificantes`, `synthetic`. 4. Fixture entries referencing deleted/renamed identifiers (drift). 5. Test naming conventions embedding transient stems that should be renamed.

### Finding 1: Modelo Generator Copy-Paste (100, 130, 303)

**Risk Category**: duplicate / structural copy-paste

**Locations**:
- `pdf_corpus/l3_synthetic/_generators/modelo_100_generator.py` (169 lines): `Modelo100GenParams`, `Modelo100GroundTruth`, `_draw_header()`, `_draw_footer()`, `generate()` function
- `pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py` (142 lines): `Modelo130GenParams`, `Modelo130GroundTruth`, `generate()` function
- `pdf_corpus/l3_synthetic/_generators/modelo_303_generator.py` (153 lines): `Modelo303GenParams`, `Modelo303GroundTruth`, `generate()` function
- Total: 464 lines across 3 files

**Issue**: Three independent generators each define:
- Identical pydantic param/groundtruth model structure (`BaseModel`, `ConfigDict(strict=True, frozen=True, extra="forbid")`, Field constraints, field isolation)
- Identical `generate()` function skeleton (`io.BytesIO`, `canvas.Canvas(pagesize=(210*mm, 297*mm))`, `c.setTitle()`, render loop, `pdf_bytes`, ground_truth tuple return)
- Model-specific header/footer/casilla-box layout configuration (differ only in casilla-label maps + y-position constants)

**Evidence**:
- All three call shared `_generator_shared.py` helpers (`draw_header`, `draw_casilla_box`, `draw_footer`, `CasillaBox`, `format_amount`)
- Modelo 130 + 303 generate() implementations are 90% identical (130 lines 101–135, 303 lines 113–146; only variable names differ)
- Modelo 100 uses private `_draw_header` + `_draw_footer` wrappers; 130 + 303 call `draw_header` + `draw_footer` directly (API inconsistency)

**Remediation**: Extract generic `QuarterlyGeneratorBase` or parameterize `generate()` by (params_model, casilla_boxes_map, header_fields). Modelo 100 can inherit or adapt. Reduce 464 → ~250 lines (45% reduction).

**Count**: 1 finding (3-file duplication cluster)

---

### Finding 2: Fixture Model Class Duplication (_Fixture across financial, justificantes)

**Risk Category**: duplicate / class structure

**Locations**:
- `fixtures/financial/n26/_generate.py:20–23`: `_Fixture(filename, title, pages)` dataclass
- `fixtures/justificantes/_generate.py:25–37`: `_Fixture(filename, modelo, ejercicio, periodo, tax_id, full_name, csv, presented_at, presentation_id, total_ingresar, total_devolver)` dataclass
- Both are `@dataclass(frozen=True)` but have incompatible schemas

**Issue**: Both fixture generators define a class named `_Fixture` with completely different field sets. They're not shared or inherited — each redeclares its own structure. If future fixture generators (e.g., `aeat-pages`, `aeat-sede`) need similar patterns, duplication will propagate across 7 subdirectories.

**Evidence**: No inheritance or composition between the two. Both are private (_Fixture) so no external visibility, but the naming collision and repeated pattern increase cognitive load. No shared fixture-base module to establish conventions.

**Remediation**: Define a base `FixtureSpec` protocol or abstract class in a shared fixtures utility module (`src/aeat/tests/fixtures/__init__.py` or `src/aeat/tests/fixtures/_spec.py`). Or namespace them as `N26FixtureSpec`, `JustificanteFixtureSpec` if they're intentionally distinct. Establishes convention and prevents future duplicates.

**Count**: 1 finding (cross-directory duplication potential)

---

### Finding 3: Shared Infrastructure Consolidation Opportunity

**Risk Category**: structural copy-paste / shared infra

**Locations**:
- `pdf_corpus/l3_synthetic/_generators/_generator_shared.py` (150 lines): `CasillaBox`, `format_amount()`, `draw_header()`, `draw_casilla_box()`, `draw_footer()`, font + margin constants
- `financial/n26/_generate.py`: duplicates layout logic (_LEFT, _TOP, _LINE, canvas.drawString patterns) inline; does not import from shared
- `justificantes/_generate.py`: duplicates header/footer structure and font setup inline; does not import from shared

**Issue**: PDF rendering infrastructure (margins, fonts, A4 dimensions, text-drawing helpers) is scattered:
- `_generator_shared.py` exports shared primitives (`A4_WIDTH`, `A4_HEIGHT`, `MARGIN_*`, `HEADER_FONT`, `LABEL_FONT`, etc.) used by all three modelos
- N26 + justificantes define their own layout constants and redraw boilerplate instead of importing from `_generator_shared`
- Both N26 and justificantes could leverage `CasillaBox` + `format_amount()` patterns but don't (locked into inline `canvas.drawString` calls)

**Evidence**: No imports of `_generator_shared` utilities in N26 or justificantes generators. Both repeat canvas setup, font declarations, and layout constants.

**Remediation**: Extend `_generator_shared.py` as centralized fixture utilities module. Import and reuse across all fixtures:
- `A4_WIDTH`, `A4_HEIGHT`, margin constants across all fixtures
- `draw_header()` / `draw_footer()` templates (adapt signature if needed for different title/header structures)
- `format_amount()` for any currency-formatted values in future fixtures
- Create optional `PageTemplate` helper to standardize header/footer rendering across fixture families

**Count**: 1 finding (cross-subdirectory consolidation opportunity)

---

### Finding 4: No Orphaned Identifier Drift Detected

**Risk Category**: drift / identifier consistency

**Scope**: Searched fixture definitions for references to deleted/renamed production classes (`Filing*`, `Declaration*`, `Borrador*` stems from historical refactors).

**Result**: ✓ PASS. All fixture generators reference only active production identifiers:
- `modelo_100_generator.py`: references `Modelo100GenParams`, `Modelo100GroundTruth` (production class names active)
- `modelo_130_generator.py`: references `Modelo130GenParams`, `Modelo130GroundTruth` (active)
- `modelo_303_generator.py`: references `Modelo303GenParams`, `Modelo303GroundTruth` (active)
- `justificantes/_generate.py`: references `_Fixture` (private test-only, no production dependency)
- `financial/n26/_generate.py`: references `_Fixture` (private test-only, no production dependency)

No references to legacy `Filing*` or `Declaration*` class names found. Generator param models already use canonical `modelo`, `ejercicio`, `periodo` identifiers (per ADR regulatory authority).

**Count**: 0 findings (clean state)

---

### Finding 5: Test Naming Convention Integrity

**Risk Category**: structural / naming convention

**Scope**: Test function names in `src/aeat/tests/fixtures/` and fixture-dependent tests.

**Result**: ✓ PASS. Test naming adheres to pytest conventions:
- `pdf_corpus/l3_synthetic/_generators/test_generator_shared.py`: functions named `test_format_amount_*` (parameterized: `test_format_amount_matches_aeat_style`, `test_format_amount_quantises_to_two_decimals`, `test_format_amount_nbsp_thousands`)
- No test functions embed transient stems like `test_old_filing_*` or `test_borrador_*`
- Test scope is fixture-infrastructure (generators, rendering), not domain logic, so no historical class-rename ripple detected

**Count**: 0 findings (clean state)

---

### Summary: Tests Fixture Deep Sweep

| Category | Count | Examples | Risk Level | Action |
|----------|-------|----------|------------|--------|
| **Fixture generator copy-paste** | 1 | Modelo 100/130/303 generate() + param model duplication | MEDIUM | Consolidate via generic base or parameterization (Phase 2) |
| **Fixture class structure duplication** | 1 | `_Fixture` defined twice with incompatible schemas across dirs | LOW | Namespace or establish protocol convention (Phase 2) |
| **Shared infra consolidation opportunity** | 1 | `_generator_shared.py` not fully leveraged by N26 + justificantes | LOW | Extend utilities module + import refactoring (Phase 2) |
| **Orphaned identifier drift** | 0 | No references to deleted Filing*/Declaration*/Borrador* stems | NONE | Continue monitoring |
| **Test naming convention issues** | 0 | All test functions follow pytest standards | NONE | No action needed |

**Total Unique Findings**: 3

**Estimated Remediation Effort**: 12–20 engineering hours (generate() consolidation, class namespace alignment, utilities import refactoring, Phase 2 execution).


## Domain Submission Sweep

### Summary

Swept `src/aeat/domain/submission/` (7 files + 2 tests) for class inventory, ADR ledger rename alignment, cross-package imports, and internal duplication. Submission package is a focused, single-responsibility module for filing lifecycle recording and preflight gates. No internal collision or boilerplate duplication detected.

### Inventory: All Public Symbols

#### Models (Pydantic BaseModel)

| Symbol | Location | Purpose | ADR Rename Target |
| --- | --- | --- | --- |
| `SubmittedFiling` | `_models.py:79` | Audit record for one historical filing; persisted into SubmissionRepository | `SubmittedModelo` (per ADR ledger) |
| `SubmissionAttempt` | `_models.py:45` | Attempt record with timestamps, status, error codes, browser trace path | NO RENAME (not in ADR ledger; submission-specific) |
| `SubmissionStatus` (StrEnum) | `_models.py:22` | Lifecycle status: PENDING, IN_PROGRESS, SUBMITTED, ACKNOWLEDGED, REJECTED, FAILED | NO RENAME (submission-specific, not Filing*) |

#### Protocols

| Symbol | Location | Purpose | ADR Rename Target |
| --- | --- | --- | --- |
| `FilingDraftLike` | `_protocols.py` | Narrow protocol surface over filing draft; conformed to by `aeat.application.filing.FilingDraft` | `ModeloDraftLike` (per ADR ledger) |
| `DraftLoader` | `_protocols.py` | Loads a `FilingDraftLike` from disk path | `ModeloDraftLoader` (per ADR ledger; note: ADR ledger marks target as `?`) |
| `DraftStatus` (StrEnum) | `_protocols.py` | Mirror of `aeat.application.filing.FilingDraftStatus` for submission preflight | Consolidate into `ModeloDraftStatus` (per ADR ledger) |
| `FilingFinding` | `_protocols.py` | Minimal finding record; distinct from `aeat.application.filing.FilingValidationFinding` | `ModeloFinding` (per ADR ledger) |
| `FilingFindingSeverity` (StrEnum) | `_protocols.py` | Severity enum: ERROR, WARNING; re-exported by `domain.filing` | `ModeloFindingSeverity` (per ADR ledger) |
| `AuthProviderProbe` | `_protocols.py` | Narrow auth-provider surface for preflight gate | NO RENAME (auth infrastructure, not Filing/Modelo) |
| `AuthProviderDescriptionLike` | `_protocols.py` | Submission-facing shape from auth provider | NO RENAME (auth infrastructure) |
| `DeadlineWindowChecker` | `_protocols.py` | Narrow surface over `aeat.domain.deadlines` for submission preflight | NO RENAME (deadline infrastructure) |

#### Exceptions

| Symbol | Location | Purpose | Status |
| --- | --- | --- | --- |
| `SubmissionError` | `_errors.py` | Base error for submission operations | Active; no orphaning |
| `SubmissionPreflightError` | `_errors.py` | Raised when preflight gate blocks submission | Active; no orphaning |
| `SubmissionValidationError` | `_errors.py` | Raised during model validation | Active (used in `SubmissionAttempt._check_time_ordering`) |

#### Engine & Repository

| Symbol | Location | Purpose |
| --- | --- | --- |
| `SubmissionEngine` | `_engine.py` | Orchestrates filing → submission → attempt recording and status tracking |
| `Preflight` | `_preflight.py` | Checks draft readiness before submission (auth, deadline, findings severity) |
| `SubmissionRepository` | `_repository.py` | Persistent storage for `SubmittedFiling` records; SQLite-backed |

### Cross-Package Import Inventory

`domain.submission` is imported by **6 application/outbound modules**:

1. **`application.workflow._engine`** — submission state machine integration
2. **`application.workflow._adapters`** — submission protocol bindings
3. **`application.filing._import`** — justificante CSV ingest; reconstructs `SubmittedFiling` + `SubmissionAttempt`
4. **`application.modelo._actions`** — submission record CRUD operations
5. **`adapters.outbound.aeat.export`** — preflight gate and attempt export
6. **`adapters.persistence.storage`** — roundtrip test for SubmissionRepository

**Re-exports**: `domain.filing.__init__.py` re-exports `FilingFindingSeverity` to upstream consumers (marked as "re-exported from domain.submission" per note in research sweep init).

### ADR Ledger Alignment Analysis

Five symbols in `domain.submission` match ADR ledger rename targets:

| Current Name | ADR Target | Scope | Status |
| --- | --- | --- | --- |
| `FilingFindingSeverity` | `ModeloFindingSeverity` | **BLOCKING**: re-exported by `domain.filing`; cannot rename submission-only | BLOCKED (cross-domain dependency) |
| `FilingDraftLike` | `ModeloDraftLike` | **BLOCKING**: protocol implemented by `application.filing.FilingDraft`; cross-domain protocol | BLOCKED (cross-domain dependency) |
| `DraftLoader` | `ModeloDraftLoader` (target marked `?` in ledger) | **LOW RISK**: internal submission protocol; no cross-package clients found | Proceed after consensus on target name |
| `DraftStatus` | Consolidate into `ModeloDraftStatus` | **BLOCKING**: mirrors `application.filing.FilingDraftStatus`; requires application-layer consolidation first | BLOCKED (application-tier dependency) |
| `SubmittedFiling` | `SubmittedModelo` | **LOW RISK**: no cross-package imports found; submission-repository only | Proceed independently |

### Internal Duplication Analysis

**Status: NO DUPLICATION DETECTED**

- No class-name collisions within domain.submission
- No copy-paste boilerplate or method-signature duplication
- Protocol hierarchy is intentional: `FilingDraftLike`, `DraftLoader`, `FilingFinding`, `DraftStatus` are all intentional narrow surfaces for submission engine's discrete concerns
- Exception family (`SubmissionError`, `SubmissionPreflightError`, `SubmissionValidationError`) is clean and actively used

### Blocking Dependencies Summary

Three symbols cannot be renamed without coordinating cross-domain refactors:

**Blocking**: `FilingFindingSeverity`
- **Why**: Re-exported by `domain.filing`; used throughout `domain.filing._validator`
- **Action Required**: ADR must decide whether the entire Filing/Modelo cluster renames in one go, or phased with intermediate shims (not preferred per project policy)

**Blocking**: `FilingDraftLike`
- **Why**: Protocol implemented by `application.filing.FilingDraft`
- **Action Required**: Application layer must rename FilingDraft first, then submission protocol can follow

**Blocking**: `DraftStatus`
- **Why**: Mirrors `application.filing.FilingDraftStatus`; consolidation required at application tier
- **Action Required**: Application domain must consolidate the two enums first

**Unblocked**: `SubmittedFiling` → `SubmittedModelo`
- **Why**: Isolated to submission repository and filing._import; no upstream re-exports
- **Action Required**: Can proceed independently once ADR approves

**Unblocked (with consensus)**: `DraftLoader` → target TBD
- **Why**: Internal submission protocol; no external clients
- **Action Required**: Confirm ADR target name, then proceed

### Risk Summary

| Category | Finding Count | Risk Level | Action |
| --- | --- | --- | --- |
| ADR-ledger rename alignment | 5 identified | MEDIUM | 3 blocked on cross-domain dependencies; 2 unblocked; requires ADR sequencing |
| Class-name collisions | 0 | NONE | Monitor in future sweeps |
| Internal duplication | 0 | NONE | No refactor action required |
| Cross-package dependencies | 6 consumers | LOW | All dependencies are intentional; import hygiene is good |
| Orphaned exceptions | 0 | NONE | All exceptions actively used |

**Sweep Conclusion:** `domain.submission` is well-isolated and internally coherent. Rename coordination must sequence with application-tier consolidation (FilingDraft, FilingDraftStatus) and filing-domain re-exports (FilingFindingSeverity). `SubmittedFiling` → `SubmittedModelo` is independently actionable.


---

## Adapters Inbound Sweep

**Scope**: `src/aeat/adapters/inbound/` (borrador, declaracion, justificante, financial, identity, pdf, sanitizer)

**Findings**:

### Finding 1: Parser Structure Consistency

| Subpackage | File Layout | Boilerplate Status | Notes |
|------------|----------|--------|-------|
| **borrador** | `_parser.py` + `_parsers/_pdfplumber_backend.py` (36 lines) | ✓ Minimal | Delegating entry point; backend is lean. |
| **declaracion** | `_parser.py` + `_parsers/_pdfplumber_backend.py` (113 lines) | ⚠️ Extended | Includes pypdf AcroForm fast-path + lru_cache. Larger but justified by template-revision detection logic. |
| **justificante** | `_parser.py` + `_parsers/_pdfplumber_backend.py` (32 lines) | ✓ Minimal | Consistent with borrador pattern. |
| **financial** | Polymorphic provider registry (`_base.py` + `_csv.py`, `_ofx.py`, etc.) | ✓ No duplication | Each provider type is separate; no monolithic boilerplate. |

**Assessment**: pdfplumber unification is comprehensive. Three DOM parsers (borrador, declaracion, justificante) follow a consistent pattern: public entry point (`parse_*`) + backend abstraction (`_parsers/_pdfplumber_backend.py`). Financial provider pattern is distinct and separate; no inappropriate duplication.

### Finding 2: Class-Name Collisions

| Check | Result | Notes |
|-------|--------|-------|
| **Duplicate class names across subpackages** | ✓ Pass | No collisions detected. Each error class is locally scoped (e.g. `BorradorParseError`, `DeclaracionParseError`, `FinancialProviderError` are unique). |
| **Naming consistency per domain** | ✓ Pass | Spanish-domain classes follow Spanish stems: `BorradorObservation`, `DeclaracionObservation`, `JustificanteParserBackend`. English infrastructure classes (`Parser`, `Error`) follow English patterns. |
| **Test class prefixes** | ✓ Pass | Test classes use `Test` prefix (e.g. `TestJustificanteErrorRehome`, `TestPdfFilingImportError`). No collision with production classes. |

### Finding 3: Exception Hierarchy

| Tier | Count | Parents | Leaf Classes | Status |
|------|-------|---------|-----|--------|
| **Root** | 1 | - | (implicitly) | `AeatError` (inherited, not local) |
| **L1 (Inbound)** | 2 | `AeatError` | `PdfFilingImportError`, `SanitizationError`, `FinancialProviderError` | ✓ Clean hierarchy |
| **L2 (Domain-specific)** | 6 | L1 parents | `BorradorParseError`, `DeclaracionParseError`, `ScrubError`, `SanitizerValidationError`, `SignaturePresentError`, `AlreadySanitizedError` | ✓ Well-scoped |
| **L3 (Subtype-specific)** | 4 | L2 parents | `ArtefactNotRecognisedError`, `TemplateNotDetectedError`, `UnsupportedFinancialSourceError`, `InvalidFinancialSourceError` | ✓ Specific, not orphan |

**Assessment**: Exception hierarchy is clean. No escape-to-top. No dead classes. No collision-prone patterns.

### Finding 4: Language Drift

| Domain | Identifier | Language Pattern | Status |
|--------|-----------|------------------|--------|
| **borrador** | `BorradorParseError`, `ArtefactKind`, `BorradorObservation` | Spanish stem + English infrastructure | ✓ Correct |
| **declaracion** | `DeclaracionParseError`, `TemplateRevision`, `DeclaracionObservation` | Spanish stem + English infrastructure | ✓ Correct |
| **justificante** | `JustificanteParserBackend`, `JustificanteParseError` | Spanish stem + English infrastructure | ✓ Correct |
| **financial** | `FinancialProviderError`, `FinancialValidationError` | English domain + English infrastructure | ✓ Appropriate |
| **sanitizer** | `SanitizationError`, `SanitizerValidationError` | English infrastructure | ✓ Appropriate |

**Assessment**: No drift detected. Spanish-domain classes consistently use Spanish stems paired with English infrastructure naming. Cross-domain utilities correctly use English stems. No mixed-language identifiers.

**Risk Category**: structural integrity / clean — no high-risk findings
