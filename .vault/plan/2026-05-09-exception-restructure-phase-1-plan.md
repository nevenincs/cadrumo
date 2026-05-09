---
tags:
  - "#plan"
  - "#exception-restructure"
date: 2026-05-09
related:
  - "[[2026-05-09-exception-restructure-research]]"
  - "[[2026-05-09-exception-restructure-adr]]"
---

# Exception Restructure Plan

## Overview
Recent refactors moved exception definitions towards submodule-based isolation instead of consolidated handling. We are reverting to centralized exception definitions under the `core` module.

## Checklist of Operations

### Phase 1: Migrate Definitions to `src/aeat/core/errors/`
- [ ] Migrate `BorradorParseError`, `ArtefactNotRecognisedError` from `src\aeat\adapters\inbound\borrador\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `DeclaracionParseError`, `TemplateNotDetectedError` from `src\aeat\adapters\inbound\declaracion\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `FinancialProviderError`, `UnsupportedFinancialSourceError`, `InvalidFinancialSourceError` from `src\aeat\adapters\inbound\financial\providers\_base.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `ScrubError` from `src\aeat\adapters\inbound\pdf\_scrub.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `TestPdfFilingImportError` from `src\aeat\adapters\inbound\pdf\test_shared.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `SanitizationError`, `SanitizerSourceParseError`, `SignaturePresentError`, `AlreadySanitizedError`, `UnknownSurfaceError` from `src\aeat\adapters\inbound\sanitizer\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `_PersistedSessionInvalidError` from `src\aeat\adapters\outbound\aeat\auth\_authenticator.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `ClaveMovilConfigurationError`, `ClaveMovilApprovalTimeoutError` from `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `CertificateError`, `CertificateLoadError`, `CertificatePasswordError`, `CertificateExpiredError`, `CertificatePreExpiryError`, `CertificateHandshakeError`, `CertificateNifParseError`, `AeatLoginAssertionError`, `AeatSessionExpiredError` from `src\aeat\adapters\outbound\aeat\auth\certificate.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `BrowserEvasionError` from `src\aeat\adapters\outbound\aeat\browser\evasion.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `BrowserError` from `src\aeat\adapters\outbound\aeat\browser\session.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `SedeError`, `SedeNavigationError`, `SedeParseError`, `ExpedienteNotFoundError`, `JustificanteFetchError` from `src\aeat\adapters\outbound\aeat\sede\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `GoogleAuthUnavailableError` from `src\aeat\adapters\outbound\google\__init__.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `LLMError`, `LLMProviderError`, `LLMCacheError`, `LLMRateLimitError`, `LLMConfigError` from `src\aeat\adapters\outbound\llm\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `StorageError`, `MigrationError`, `RepositoryError`, `PersistenceError`, `EncryptionError`, `DecryptionError`, `SecureObjectUnreadableError`, `KeyDerivationError`, `NonceCollisionError`, `SecretStoreError`, `KeyringUnavailableError`, `MasterKeyUnavailableError`, `MasterKeyKdfVersionError`, `MasterKeyKeychainLockedError`, `MasterKeyPassphraseMismatchError`, `MasterKeyMaterialMissingError`, `UnsecuredModeRefusedError`, `ClassificationError`, `EnvelopeVersionError`, `PathContainmentError`, `BlobNotFoundError`, `BlobIntegrityError`, `SecretNotFoundError`, `SecretAlreadyExistsError`, `RetentionPolicyError` from `src\aeat\adapters\persistence\storage\errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `AggregationError`, `AggregationPeriodError`, `AggregationUnsupportedModeloError`, `AggregationMissingClassificationError`, `AggregationCategoryCoverageError` from `src\aeat\application\aggregation\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `ArchiveError`, `ArchiveAdapterMissingError`, `ArchiveBundleSchemaError`, `ArchiveConflictError` from `src\aeat\application\archive\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `AuthAcquisitionLockedError` from `src\aeat\application\auth\_acquisition_lock.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `CorruptAuthSessionError`, `AuthSessionUnavailableError` from `src\aeat\application\auth\_sessions.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `ReviewError`, `ReviewSourceLoadError`, `FilterParseError`, `EditParseError`, `ReviewKindReservedError` from `src\aeat\application\review\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `SetupError`, `SetupAbortedError`, `SetupVerifyError`, `SetupAnswersError` from `src\aeat\application\setup\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `VerificationError` from `src\aeat\application\verification\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `WorkflowError`, `WorkflowComponentError`, `WorkflowAbortedError`, `WorkflowAbortSignal` from `src\aeat\application\workflow\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `AccessGateSubmissionError`, `AccessGateSubmissionPreflightError`, `LiveSubmitForbiddenError`, `AeatLiveReadNotEnabledError` from `src\aeat\core\access_gate\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `CorpusManifestError`, `CorpusManifestTamperError`, `CorpusManifestDriftError` from `src\aeat\core\corpus_manifest\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `IdentityError` from `src\aeat\core\identity\_documents.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `OutputSchemaError` from `src\aeat\core\json_contract.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `LockAcquisitionError` from `src\aeat\core\locks_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `RunContextMissingError`, `RunTraceValidationError`, `AeatCorpusDriftError` from `src\aeat\core\observability\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `AttachmentError`, `AttachmentValidationError`, `AttachmentPersistenceError`, `AttachmentNotFoundError` from `src\aeat\domain\attachments\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `RegistryError`, `RegistryLoadError`, `RegistryValidationError`, `RegistrySnapshotError` from `src\aeat\domain\calculations\registry\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `_BinaryXlsConversionError` from `src\aeat\domain\calculations\registry\_workbook_parity.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `DeadlineError`, `ProfileError`, `ScheduleComputationError` from `src\aeat\domain\deadlines\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `FilingDraftError`, `FilingBuilderError`, `FilingValidationError`, `FilingComputationError`, `FilingAmendmentError`, `FilingAmendmentValidationError`, `FilingImportError` from `src\aeat\domain\filing\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `InvoiceError`, `InvoiceCatalogueError`, `InvoicePersistenceError`, `InvoiceNotFoundError`, `InvoiceLinkError`, `InvoiceLinkInconsistencyError` from `src\aeat\domain\invoices\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `PdfFilingImportError`, `JustificanteError`, `JustificanteParseError`, `JustificanteCsvNotFoundError`, `JustificanteVerificationError` from `src\aeat\domain\justificante\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `ManualError`, `ManualNotFoundError`, `ManualParseError`, `ManualReviewRequiredError`, `RuleExtractionError`, `ManifestError` from `src\aeat\domain\manuals\errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `NormativeError`, `NormativeParseError`, `NormativeNotFoundError` from `src\aeat\domain\normatives\errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `PortalRegistryError`, `UnknownPortalError`, `PortalIntegrityError` from `src\aeat\domain\portals\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `TaxResidenceProfileError`, `ProfileNotConfiguredError`, `ForalRegimeError` from `src\aeat\domain\profile\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `AssetRecordError`, `AmortizationLedgerError`, `InventoryLedgerError`, `LIFOForbiddenError`, `BasisCapExceededError` from `src\aeat\domain\profile\errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `RentalRegisterError`, `FincaNotFoundError`, `ContractNotFoundError`, `TierResolutionError`, `AmortizationLedgerCapExceededError`, `RentalAggregationError` from `src\aeat\domain\rental\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `SubmissionError`, `SubmissionPreflightError` from `src\aeat\domain\submission\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `TransactionError`, `TransactionCatalogueError`, `TransactionPersistenceError`, `TransactionNotFoundError`, `LLMClassifierError` from `src\aeat\domain\transactions\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `UsageRatioError`, `UsageRatioPersistenceError` from `src\aeat\domain\usage_ratios\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `UserProfileSchemaLoadError` from `src\aeat\domain\user_profile\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `VatError`, `VatRateNotFoundError`, `VatCategoryNotFoundError`, `VatCatalogueError`, `VatRateOverlapError`, `VatClassificationError` from `src\aeat\domain\vat\errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError` from `src\aeat\entrypoints\cli\_errors.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `LogLevelResolutionError` from `src\aeat\entrypoints\cli\_log_levels.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `NonTtyRefusedError` from `src\aeat\entrypoints\cli\_tty.py` to `src/aeat/core/errors/_registry.py`
- [ ] Migrate `NoConfiguredProviderError`, `UnknownProviderError`, `ProviderUnavailableError` from `src\aeat\entrypoints\cli\auth\_registry.py` to `src/aeat/core/errors/_registry.py`

### Phase 2: Update References Codebase-Wide
- [ ] Update all codebase references for `BorradorParseError`, `ArtefactNotRecognisedError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `DeclaracionParseError`, `TemplateNotDetectedError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `FinancialProviderError`, `UnsupportedFinancialSourceError`, `InvalidFinancialSourceError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `ScrubError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `TestPdfFilingImportError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `SanitizationError`, `SanitizerSourceParseError`, `SignaturePresentError`, `AlreadySanitizedError`, `UnknownSurfaceError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `_PersistedSessionInvalidError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `ClaveMovilConfigurationError`, `ClaveMovilApprovalTimeoutError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `CertificateError`, `CertificateLoadError`, `CertificatePasswordError`, `CertificateExpiredError`, `CertificatePreExpiryError`, `CertificateHandshakeError`, `CertificateNifParseError`, `AeatLoginAssertionError`, `AeatSessionExpiredError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `BrowserEvasionError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `BrowserError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `SedeError`, `SedeNavigationError`, `SedeParseError`, `ExpedienteNotFoundError`, `JustificanteFetchError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `GoogleAuthUnavailableError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `LLMError`, `LLMProviderError`, `LLMCacheError`, `LLMRateLimitError`, `LLMConfigError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `StorageError`, `MigrationError`, `RepositoryError`, `PersistenceError`, `EncryptionError`, `DecryptionError`, `SecureObjectUnreadableError`, `KeyDerivationError`, `NonceCollisionError`, `SecretStoreError`, `KeyringUnavailableError`, `MasterKeyUnavailableError`, `MasterKeyKdfVersionError`, `MasterKeyKeychainLockedError`, `MasterKeyPassphraseMismatchError`, `MasterKeyMaterialMissingError`, `UnsecuredModeRefusedError`, `ClassificationError`, `EnvelopeVersionError`, `PathContainmentError`, `BlobNotFoundError`, `BlobIntegrityError`, `SecretNotFoundError`, `SecretAlreadyExistsError`, `RetentionPolicyError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `AggregationError`, `AggregationPeriodError`, `AggregationUnsupportedModeloError`, `AggregationMissingClassificationError`, `AggregationCategoryCoverageError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `ArchiveError`, `ArchiveAdapterMissingError`, `ArchiveBundleSchemaError`, `ArchiveConflictError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `AuthAcquisitionLockedError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `CorruptAuthSessionError`, `AuthSessionUnavailableError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `ReviewError`, `ReviewSourceLoadError`, `FilterParseError`, `EditParseError`, `ReviewKindReservedError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `SetupError`, `SetupAbortedError`, `SetupVerifyError`, `SetupAnswersError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `VerificationError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `WorkflowError`, `WorkflowComponentError`, `WorkflowAbortedError`, `WorkflowAbortSignal` to import from `aeat.core.errors`
- [ ] Update all codebase references for `AccessGateSubmissionError`, `AccessGateSubmissionPreflightError`, `LiveSubmitForbiddenError`, `AeatLiveReadNotEnabledError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `CorpusManifestError`, `CorpusManifestTamperError`, `CorpusManifestDriftError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `IdentityError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `OutputSchemaError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `LockAcquisitionError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `RunContextMissingError`, `RunTraceValidationError`, `AeatCorpusDriftError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `AttachmentError`, `AttachmentValidationError`, `AttachmentPersistenceError`, `AttachmentNotFoundError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `RegistryError`, `RegistryLoadError`, `RegistryValidationError`, `RegistrySnapshotError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `_BinaryXlsConversionError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `DeadlineError`, `ProfileError`, `ScheduleComputationError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `FilingDraftError`, `FilingBuilderError`, `FilingValidationError`, `FilingComputationError`, `FilingAmendmentError`, `FilingAmendmentValidationError`, `FilingImportError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `InvoiceError`, `InvoiceCatalogueError`, `InvoicePersistenceError`, `InvoiceNotFoundError`, `InvoiceLinkError`, `InvoiceLinkInconsistencyError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `PdfFilingImportError`, `JustificanteError`, `JustificanteParseError`, `JustificanteCsvNotFoundError`, `JustificanteVerificationError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `ManualError`, `ManualNotFoundError`, `ManualParseError`, `ManualReviewRequiredError`, `RuleExtractionError`, `ManifestError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `NormativeError`, `NormativeParseError`, `NormativeNotFoundError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `PortalRegistryError`, `UnknownPortalError`, `PortalIntegrityError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `TaxResidenceProfileError`, `ProfileNotConfiguredError`, `ForalRegimeError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `AssetRecordError`, `AmortizationLedgerError`, `InventoryLedgerError`, `LIFOForbiddenError`, `BasisCapExceededError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `RentalRegisterError`, `FincaNotFoundError`, `ContractNotFoundError`, `TierResolutionError`, `AmortizationLedgerCapExceededError`, `RentalAggregationError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `SubmissionError`, `SubmissionPreflightError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `TransactionError`, `TransactionCatalogueError`, `TransactionPersistenceError`, `TransactionNotFoundError`, `LLMClassifierError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `UsageRatioError`, `UsageRatioPersistenceError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `UserProfileSchemaLoadError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `VatError`, `VatRateNotFoundError`, `VatCategoryNotFoundError`, `VatCatalogueError`, `VatRateOverlapError`, `VatClassificationError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `LogLevelResolutionError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `NonTtyRefusedError` to import from `aeat.core.errors`
- [ ] Update all codebase references for `NoConfiguredProviderError`, `UnknownProviderError`, `ProviderUnavailableError` to import from `aeat.core.errors`

### Phase 3: Delete Original Files
- [ ] Delete `src\aeat\adapters\inbound\borrador\_errors.py`
- [ ] Delete `src\aeat\adapters\inbound\declaracion\_errors.py`
- [ ] Verify `src\aeat\adapters\inbound\financial\providers\_base.py` is clean of exception definitions
- [ ] Verify `src\aeat\adapters\inbound\pdf\_scrub.py` is clean of exception definitions
- [ ] Verify `src\aeat\adapters\inbound\pdf\test_shared.py` is clean of exception definitions
- [ ] Delete `src\aeat\adapters\inbound\sanitizer\_errors.py`
- [ ] Verify `src\aeat\adapters\outbound\aeat\auth\_authenticator.py` is clean of exception definitions
- [ ] Verify `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py` is clean of exception definitions
- [ ] Verify `src\aeat\adapters\outbound\aeat\auth\certificate.py` is clean of exception definitions
- [ ] Verify `src\aeat\adapters\outbound\aeat\browser\evasion.py` is clean of exception definitions
- [ ] Verify `src\aeat\adapters\outbound\aeat\browser\session.py` is clean of exception definitions
- [ ] Delete `src\aeat\adapters\outbound\aeat\sede\_errors.py`
- [ ] Verify `src\aeat\adapters\outbound\google\__init__.py` is clean of exception definitions
- [ ] Delete `src\aeat\adapters\outbound\llm\_errors.py`
- [ ] Delete `src\aeat\adapters\persistence\storage\errors.py`
- [ ] Delete `src\aeat\application\aggregation\_errors.py`
- [ ] Delete `src\aeat\application\archive\_errors.py`
- [ ] Verify `src\aeat\application\auth\_acquisition_lock.py` is clean of exception definitions
- [ ] Verify `src\aeat\application\auth\_sessions.py` is clean of exception definitions
- [ ] Delete `src\aeat\application\review\_errors.py`
- [ ] Delete `src\aeat\application\setup\_errors.py`
- [ ] Delete `src\aeat\application\verification\_errors.py`
- [ ] Delete `src\aeat\application\workflow\_errors.py`
- [ ] Delete `src\aeat\core\access_gate\_errors.py`
- [ ] Delete `src\aeat\core\corpus_manifest\_errors.py`
- [ ] Verify `src\aeat\core\identity\_documents.py` is clean of exception definitions
- [ ] Verify `src\aeat\core\json_contract.py` is clean of exception definitions
- [ ] Delete `src\aeat\core\locks_errors.py`
- [ ] Delete `src\aeat\core\observability\_errors.py`
- [ ] Delete `src\aeat\domain\attachments\_errors.py`
- [ ] Delete `src\aeat\domain\calculations\registry\_errors.py`
- [ ] Verify `src\aeat\domain\calculations\registry\_workbook_parity.py` is clean of exception definitions
- [ ] Delete `src\aeat\domain\deadlines\_errors.py`
- [ ] Delete `src\aeat\domain\filing\_errors.py`
- [ ] Delete `src\aeat\domain\invoices\_errors.py`
- [ ] Delete `src\aeat\domain\justificante\_errors.py`
- [ ] Delete `src\aeat\domain\manuals\errors.py`
- [ ] Delete `src\aeat\domain\normatives\errors.py`
- [ ] Delete `src\aeat\domain\portals\_errors.py`
- [ ] Delete `src\aeat\domain\profile\_errors.py`
- [ ] Delete `src\aeat\domain\profile\errors.py`
- [ ] Delete `src\aeat\domain\rental\_errors.py`
- [ ] Delete `src\aeat\domain\submission\_errors.py`
- [ ] Delete `src\aeat\domain\transactions\_errors.py`
- [ ] Delete `src\aeat\domain\usage_ratios\_errors.py`
- [ ] Delete `src\aeat\domain\user_profile\_errors.py`
- [ ] Delete `src\aeat\domain\vat\errors.py`
- [ ] Delete `src\aeat\entrypoints\cli\_errors.py`
- [ ] Verify `src\aeat\entrypoints\cli\_log_levels.py` is clean of exception definitions
- [ ] Verify `src\aeat\entrypoints\cli\_tty.py` is clean of exception definitions
- [ ] Verify `src\aeat\entrypoints\cli\auth\_registry.py` is clean of exception definitions

### Phase 4: Structural and Boundary Testing
- [ ] Create `src/aeat/core/errors/test_registry.py` if it does not exist
- [ ] Add test to verify all custom errors inherit from `AeatError` (avoid tautological logic)
- [ ] Add boundary test verifying `AeatError` trapping
