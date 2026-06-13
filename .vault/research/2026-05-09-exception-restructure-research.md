---
tags:
  - "#research"
  - "#exception-restructure"
date: 2026-05-09
modified: '2026-05-09'
related:
---

# Exception Handling Restructure Research

This document serves as an inventory of all exception and error definitions currently scattered across the `src/` directory. Our goal is to migrate all definitions into the `core` module and delete any definitions that do not live in the `core` module.\n\n## `src\aeat\adapters\inbound\borrador\_errors.py`

```python
class BorradorParseError(PdfFilingImportError):
    """Raised when a Modelo 100 PDF cannot be parsed into a filing record.

    Base class for every domain-specific failure raised by the borrador
    pipeline. Subclasses (e.g. :class:`ArtefactNotRecognisedError`)
    refine the failure mode.
    """
```

```python
class ArtefactNotRecognisedError(BorradorParseError):
    """Raised when the PDF does not match any known Modelo 100 artefact shape.

    Surfaced by :func:`aeat.adapters.inbound.borrador._detect.detect_artefact_kind`
    when none of the BORRADOR / VISTA PREVIA / CSV markers can be located.
    """
```

## `src\aeat\adapters\inbound\declaracion\_errors.py`

```python
class DeclaracionParseError(PdfFilingImportError):
    """Raised when a PDF cannot be parsed into a declaración filing.

    Base class for all parse-time errors emitted by
    :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
    :exc:`TemplateNotDetectedError` signals a recoverable template
    detection failure; the bare class is raised for low-level failures
    (PDF unreadable, header field missing, missing registry coverage,
    etc.).
    """
```

```python
class TemplateNotDetectedError(DeclaracionParseError):
    """Raised when the PDF's template revision cannot be auto-detected.

    Emitted by
    :func:`aeat.adapters.inbound.declaracion._detect.detect_template_revision`
    when neither the header nor the footer of the PDF carries enough
    signal to pin a ``(modelo, año, revision)`` triple. Callers may
    recover by passing explicit ``modelo`` / ``año`` overrides to
    :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
    """
```

## `src\aeat\adapters\inbound\financial\providers\_base.py`

```python
class FinancialProviderError(AeatError):
    """Base error raised by financial-ingest providers.

    Subclasses :class:`aeat.core.errors.AeatError` so the application
    layer can catch every provider failure with one ``except`` clause.
    """
```

```python
class UnsupportedFinancialSourceError(FinancialProviderError):
    """Raised when no provider can interpret a source document."""
```

```python
class InvalidFinancialSourceError(FinancialProviderError):
    """Raised when a source document is unreadable or structurally invalid."""
```

## `src\aeat\adapters\inbound\pdf\test_shared.py`

```python
class TestPdfFilingImportError:
    """The shared error root inherits from :class:`AeatError`."""

    def test_is_aeat_error(self) -> None:
        assert issubclass(PdfFilingImportError, AeatError)

    def test_can_be_caught_as_aeat_error(self) -> None:
        with pytest.raises(AeatError):
            raise PdfFilingImportError("test")

    def test_can_be_caught_as_pdf_filing_import_error(self) -> None:
        with pytest.raises(PdfFilingImportError):
            raise PdfFilingImportError("test")
```

## `src\aeat\adapters\inbound\pdf\_scrub.py`

```python
class ScrubError(PdfFilingImportError):
    """Raised when scrubbing cannot produce a safe output."""
```

## `src\aeat\adapters\inbound\sanitizer\_errors.py`

```python
class SanitizationError(AeatError):
    """Base error for the :mod:`aeat.adapters.inbound.sanitizer` subpackage."""

    pass
```

```python
class SanitizerSourceParseError(SanitizationError):
    """Raised when the source PDF cannot be opened by :mod:`pikepdf`.

    The original :class:`pikepdf.PdfError` (or whatever underlying
    cause QPDF surfaced) is chained as ``__cause__`` so the caller
    can inspect it via ``raise ... from``.
    """

    pass
```

```python
class SignaturePresentError(SanitizationError):
    """Raised when the source PDF carries a digital signature.

    Modifying a signed PDF silently invalidates the signature; the
    sanitiser refuses such inputs and requires the operator to
    escalate to human review.
    """

    pass
```

```python
class AlreadySanitizedError(SanitizationError):
    """Raised when the source SHA-256 is already in :data:`SANITIZED_SHAS`.

    Prevents accidental "re-sanitise an already-committed fixture".
    Callers can opt out via
    ``sanitize_pdf(..., refuse_if_already_sanitized=False)``.
    """

    def __init__(self, *, source_sha256: str) -> None:
        """Construct the error carrying the offending source hash.

        Args:
            source_sha256: The SHA-256 of the source bytes that
                matched a known committed fixture.
        """
        super().__init__(
            f"source PDF sha256={source_sha256!r} is already a committed sanitised fixture; "
            "pass refuse_if_already_sanitized=False to override"
        )
        self.source_sha256: str = source_sha256
```

```python
class UnknownSurfaceError(SanitizationError):
    """Raised when a PII surface is detected that the sanitiser does not handle.

    Used for threat-model surfaces this version of the sanitiser is
    not yet wired to scrub (e.g. a future modelo introduces an
    ``OCProperties`` shape we have not characterised). The default
    policy is *fail*; callers can downgrade to a warning by toggling
    the relevant ``drop_*`` flag off and accepting the resulting
    warning.
    """

    pass
```

## `src\aeat\adapters\outbound\aeat\auth\certificate.py`

```python
class CertificateError(AeatError):
    """Base class for every certificate-auth domain error."""
```

```python
class CertificateLoadError(CertificateError):
    """Raised when PKCS#12 bytes cannot be parsed at all."""
```

```python
class CertificatePasswordError(CertificateError):
    """Raised when the passphrase env var is missing/empty or wrong."""
```

```python
class CertificateExpiredError(CertificateError):
    """Raised when a loaded certificate's ``not_after`` is in the past."""
```

```python
class CertificatePreExpiryError(CertificateError):
    """Raised when a certificate is within the pre-expiry danger window.

    Distinct from :class:`CertificateExpiredError` (which fires after
    ``not_after`` has elapsed): this error is raised proactively by the
    workflow gate and CLI surfaces when a loaded certificate's
    ``days_until_expiry`` has fallen below the configured critical
    threshold, before the bundle becomes technically unusable. Callers
    may suppress it via an explicit override flag on the narrow
    programmatic surfaces that still support certificate probes.
    """
```

```python
class CertificateHandshakeError(CertificateError):
    """Raised when handshake input is structurally invalid.

    TLS failures encountered during :func:`verify_handshake` are
    returned as ``HandshakeResult(success=False, ...)`` rather than
    raised; this exception is reserved for cases where the caller
    passed nonsense (e.g. an empty URL).
    """
```

```python
class CertificateNifParseError(CertificateError):
    """Raised when no NIF / NIE can be parsed from a certificate subject.

    The project's authenticator derives the taxpayer NIF from the
    FNMT certificate subject (canonical source: the ``serialNumber``
    RDN, OID 2.5.4.5). Certificates that carry no such attribute,
    that use a CIF (legal-entity) shape, or whose CN/serialNumber
    lacks a recognisable DNI (``[0-9]{7,8}[A-Z]``) or NIE
    (``[XYZ][0-9]{7}[A-Z]``) identifier produce this error. Callers
    MUST propagate it rather than guess the identifier from other
    fields.
    """
```

```python
class AeatLoginAssertionError(CertificateError):
    """Raised when a post-auth verification attempt cannot be produced.

    Distinct from a *negative* assertion result (which returns a
    :class:`AeatLoginAssertion` with ``is_valid=False``). This
    exception fires when the assertion cannot even be built — for
    example a Playwright context is missing the thumbprint marker,
    the authenticator was never authenticated, or a structural
    precondition failed before the navigation could complete.
    """
```

```python
class AeatSessionExpiredError(CertificateError):
    """Raised when an authenticated AEAT session is no longer usable.

    Three conditions feed this error:

    1. An :class:`AeatSession` whose ``idle_deadline`` has elapsed
       (``is_stale`` returns True) is passed to
       :meth:`AeatAuthenticator.verify_login`.
    2. A single :meth:`AeatAuthenticator.reauthenticate` attempt
       still yields ``certificate_recognised=False``; the caller
       MUST NOT loop and MUST raise this upwards.
    3. An HTTP 401 / 403 surfaced by a downstream live-read call
       site that consumed the session.

    The error deliberately does not carry the session instance —
    callers re-derive authentication from ``Settings`` rather than
    retry with stale state.
    """
```

## `src\aeat\adapters\outbound\aeat\auth\_authenticator.py`

```python
class _PersistedSessionInvalidError(AeatLoginAssertionError):
    """Raised when a persisted AEAT browser session cannot be trusted."""
```

## `src\aeat\adapters\outbound\aeat\auth\_clave_movil.py`

```python
class ClaveMovilConfigurationError(AeatError):
    """Raised when required Cl@ve Móvil settings are missing or malformed."""
```

```python
class ClaveMovilApprovalTimeoutError(AeatError):
    """Raised when the operator does not approve the Cl@ve push within the time window."""

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: ClaveMovilFailureMode | str | None = None,
        context: dict[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        """Construct a Cl@ve Móvil approval failure with stable mode context."""

        enriched_context = dict(context) if context is not None else {}
        if failure_mode is not None:
            failure_mode_value = (
                failure_mode.value if isinstance(failure_mode, ClaveMovilFailureMode) else str(failure_mode)
            )
            enriched_context["failure_mode"] = failure_mode_value
            self.failure_mode: str | None = failure_mode_value
        else:
            self.failure_mode = None
        super().__init__(message, context=enriched_context or None, suggestion=suggestion)
```

## `src\aeat\adapters\outbound\aeat\browser\evasion.py`

```python
class BrowserEvasionError(AeatError):
    """Raised when browser evasion setup cannot be applied."""
```

## `src\aeat\adapters\outbound\aeat\browser\session.py`

```python
class BrowserError(AeatError):
    """Base class for browser-related errors."""

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: BrowserFailureMode | str | None = None,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a browser error with a stable failure-mode tag."""

        enriched_context = dict(context) if context is not None else {}
        if failure_mode is not None:
            failure_mode_value = (
                failure_mode.value if isinstance(failure_mode, BrowserFailureMode) else str(failure_mode)
            )
            enriched_context["failure_mode"] = failure_mode_value
            self.failure_mode: str | None = failure_mode_value
        else:
            self.failure_mode = None
        super().__init__(
            message,
            context=enriched_context or None,
            suggestion=suggestion,
            translated_message=translated_message,
        )
```

## `src\aeat\adapters\outbound\aeat\sede\_errors.py`

```python
class SedeError(AeatError):
    """Base class for post-auth AEAT sede errors.

    Extends :exc:`aeat.core.errors.AeatError` so callers tracking
    cross-package errors can catch the whole AEAT surface uniformly.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        failure_mode: SedeFailureMode | str | None = None,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a Sede error with optional stable failure-mode context."""

        enriched_context = dict(context) if context is not None else {}
        if failure_mode is not None:
            failure_mode_value = failure_mode.value if isinstance(failure_mode, SedeFailureMode) else str(failure_mode)
            enriched_context["failure_mode"] = failure_mode_value
            self.failure_mode: str | None = failure_mode_value
        else:
            self.failure_mode = None
        super().__init__(
            message,
            context=enriched_context or None,
            suggestion=suggestion,
            translated_message=translated_message,
        )
```

```python
class SedeNavigationError(SedeError):
    """Raised when a navigation step fails (goto, click, wait)."""
```

```python
class SedeParseError(SedeError):
    """Raised when the captured HTML cannot be parsed to a record."""
```

```python
class ExpedienteNotFoundError(SedeError):
    """Raised when no expediente matches the requested filter."""
```

```python
class JustificanteFetchError(SedeError):
    """Raised when the CSV-keyed PDF download fails or is malformed."""
```

## `src\aeat\adapters\outbound\google\__init__.py`

```python
class GoogleAuthUnavailableError(RuntimeError):
    """Raised when Google credentials are requested without a configured backend."""
```

## `src\aeat\adapters\outbound\llm\_errors.py`

```python
class LLMError(AeatError):
    """Base exception for LLM package failures."""
```

```python
class LLMProviderError(LLMError):
    """Raised when a provider returns an unrecoverable error."""
```

```python
class LLMCacheError(LLMError):
    """Raised when a cache entry cannot be read, written, or parsed."""
```

```python
class LLMRateLimitError(LLMProviderError):
    """Raised when a provider rejects a request because of rate limits.

    Args:
        message: Human-readable error message.
        retry_after_seconds: Optional server-provided retry delay in seconds.
    """

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
```

```python
class LLMConfigError(LLMError):
    """Raised when the LLM client configuration is invalid or incomplete."""
```

## `src\aeat\adapters\persistence\storage\errors.py`

```python
class StorageError(AeatError):
    """Base class for every error raised by :mod:`aeat.adapters.persistence.storage`."""
```

```python
class MigrationError(StorageError):
    """Raised when an Alembic migration operation fails."""
```

```python
class RepositoryError(StorageError):
    """Raised when a repository operation fails (not-found, integrity, etc.)."""
```

```python
class PersistenceError(StorageError):
    """Base class for governed-persistence error subtypes.

    Errors raised by the at-rest crypto primitives, the secret store, the
    encrypted blob store, the schema-version envelope, the file-lock helper,
    the path containment helper, and the audit-sink redaction contract all
    inherit from this class.
    """
```

```python
class EncryptionError(PersistenceError):
    """Base class for AEAD encryption / decryption failures."""
```

```python
class DecryptionError(EncryptionError):
    """Raised when AEAD decryption fails (tag mismatch, malformed input)."""
```

```python
class SecureObjectUnreadableError(DecryptionError):
    """Raised when one stored secure object cannot be decrypted under the current master key.

    Distinct from the generic :class:`DecryptionError` so iterator-shaped
    consumers can surface a structured per-row failure (namespace, row id,
    underlying cause) without aborting the iteration. The plaintext bound
    to such a row is cryptographically unrecoverable from this process: the
    master key under which it was sealed is no longer available.
    """

    def __init__(self, namespace: str, row_id: int, *, cause: BaseException | None = None) -> None:
        message = f"secure object {namespace}/#{row_id} cannot be decrypted under the current master key"
        super().__init__(message)
        self.namespace = namespace
        self.row_id = row_id
        self.__cause__ = cause
```

```python
class KeyDerivationError(EncryptionError):
    """Raised when a key-derivation step fails."""
```

```python
class NonceCollisionError(EncryptionError):
    """Raised on a defensive nonce-uniqueness invariant violation."""
```

```python
class SecretStoreError(PersistenceError):
    """Base class for secret-store I/O failures."""
```

```python
class KeyringUnavailableError(SecretStoreError):
    """Raised when the OS keychain backend is unusable.

    Either no backend is registered (e.g. headless Linux without
    libsecret), the backend rejected the operation, or the configured
    backend is the no-op ``null`` keyring.
    """
```

```python
class MasterKeyUnavailableError(SecretStoreError):
    """Raised when no master key can be acquired from any provider."""
```

```python
class MasterKeyKdfVersionError(MasterKeyUnavailableError):
    """Raised when the on-disk ``master.kdf`` declares a KDF version this build cannot consume.

    The substrate gates the master.kdf parameters by version. Mismatch means
    the operator's passphrase may be correct, but the on-disk parameters do not
    match this build's supported key-derivation contract.
    """
```

```python
class MasterKeyKeychainLockedError(MasterKeyUnavailableError):
    """Raised when the OS keychain is reachable but the entry is locked.

    Distinct from :class:`KeyringUnavailableError` (no usable backend at
    all). This class signals a recoverable state: the operator unlocks
    the OS keychain (Touch ID / Windows Hello / desktop-wallet unlock)
    and retries. The CLI's error envelope renders the actionable hint.
    """
```

```python
class MasterKeyPassphraseMismatchError(MasterKeyUnavailableError):
    """Raised when the file-fallback passphrase does not unwrap ``master.key``.

    Recoverable by re-entering the passphrase. If the passphrase has
    been forgotten, the operator can use
    ``aeat security recover --recovery-key`` to re-mint the master key
    from a recovery-key backup. The CLI's error envelope distinguishes
    this case from :class:`MasterKeyMaterialMissingError` so retries
    do not waste backoff budget on missing-file errors.
    """
```

```python
class MasterKeyMaterialMissingError(MasterKeyUnavailableError):
    """Raised when no master-key material exists at all.

    Neither the keyring entry nor the file-fallback artefacts
    (``master.key`` / ``master.kdf`` / ``salt``) are present. The
    substrate has not been provisioned. The operator's actionable
    next step is ``aeat security provision`` or, if a recovery key
    is available, ``aeat security recover --recovery-key``.

    Reserved for callers that need to distinguish "not provisioned"
    from "wrong passphrase" — the default ``get_master_key`` path
    silently mints when material is absent (the first-
    run mint contract), so this class does not fire on the canonical
    load path. Future load-only / probe-only entry points (e.g. a
    diagnostic API or a ``--no-mint`` CLI option) raise this class
    instead of triggering a silent mint.
    """
```

```python
class UnsecuredModeRefusedError(SecretStoreError):
    """Raised when the unsecured backend is requested without proper gating.

    Two refusal classes:

    1. The unsecured backend was selected (``aeat_secret_store_backend=unsecured``)
       but the operator did not set ``AEAT_ALLOW_UNENCRYPTED=1``. The hostile-
       named env var is the legible-and-embarrassing opt-out gate.
    2. The unsecured backend is active AND the operator profile carries a
       real NIF/NIE/CIF (NIF-canary). Real tax data is incompatible with a
       published deterministic master key; the substrate refuses to write
       such records into the unsecured store.
    """
```

```python
class ClassificationError(PersistenceError):
    """Raised when a record's declared sensitivity class is incompatible with its repository.

    Example: writing a CORPUS-class blob through the encrypted-blob path,
    or loading an envelope under a different classification than the
    one persisted on disk.
    """
```

```python
class EnvelopeVersionError(PersistenceError):
    """Raised when an on-disk envelope is older or newer than the consumer expects.

    Older envelopes may be migrated forward via
    :func:`migrate_envelope`; newer envelopes are not safely
    consumable by older code and refuse to load.
    """
```

```python
class PathContainmentError(PersistenceError, ValueError):
    """Raised when a computed path escapes its configured root directory.

    Inherits from :class:`ValueError` as well as :class:`PersistenceError` so
    legacy call-sites that catch ``ValueError`` from the path helpers in
    :mod:`aeat.core.paths` continue to work; new code should catch the
    typed :class:`PathContainmentError` instead.

    Method-resolution order: :class:`PathContainmentError` ->
    :class:`PersistenceError` -> :class:`StorageError` ->
    :class:`AeatError` -> :class:`Exception` and (separately)
    :class:`ValueError` -> :class:`Exception`. Python's C3 linearisation
    resolves cleanly because both bases share :class:`Exception` as their
    common ancestor; the registered :class:`ErrorCode`
    (``INTEGRITY_STORAGE_PATH_CONTAINMENT``) is keyed by fully qualified
    class name, so the multi-inheritance does not introduce shadowing.
    """
```

```python
class BlobNotFoundError(PersistenceError):
    """Raised when a blob lookup misses on the encrypted blob store."""
```

```python
class BlobIntegrityError(PersistenceError):
    """Raised when a blob's on-disk SHA-256 disagrees with its manifest."""
```

```python
class SecretNotFoundError(SecretStoreError):
    """Raised when a secret-store ``get`` does not find a record for the requested key."""
```

```python
class SecretAlreadyExistsError(SecretStoreError):
    """Raised when a secret-store ``put`` would overwrite an existing key without ``overwrite=True``."""
```

```python
class RetentionPolicyError(PersistenceError):
    """Raised when a record's retention metadata violates its classification policy."""
```

## `src\aeat\application\aggregation\_errors.py`

```python
class AggregationError(AeatError):
    """Base class for financial transaction aggregation failures.

    The :attr:`message` field is a translation key resolved by the
    internationalization system at runtime.
    """

    def __init__(
        self,
        message: tr,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(translated_message=message, context=context, suggestion=suggestion)
```

```python
class AggregationPeriodError(AggregationError):
    """Raised when a requested filing period cannot be parsed unambiguously."""
```

```python
class AggregationUnsupportedModeloError(AggregationError):
    """Raised when no aggregation contract is available for the requested modelo."""
```

```python
class AggregationMissingClassificationError(AggregationError):
    """Raised when in-period transactions still need business classification."""
```

```python
class AggregationCategoryCoverageError(AggregationError):
    """Raised when a business transaction lacks category or profile coverage."""
```

## `src\aeat\application\archive\_errors.py`

```python
class ArchiveError(AeatError):
    """Base class for every archive export/import failure."""
```

```python
class ArchiveAdapterMissingError(ArchiveError):
    """Raised when an archive operation references an unregistered namespace."""
```

```python
class ArchiveBundleSchemaError(ArchiveError):
    """Raised when a bundle's wire schema is unsupported by this consumer."""
```

```python
class ArchiveConflictError(ArchiveError):
    """Raised when restoring a record would overwrite an existing object.

    Surfaces only under :attr:`ConflictPolicy.FAIL`. Carries the
    namespace and natural object key on the standard message so
    operators can resolve manually.
    """
```

## `src\aeat\application\auth\_acquisition_lock.py`

```python
class AuthAcquisitionLockedError(AeatError):
    """Raised when another process is already acquiring AEAT auth."""
```

## `src\aeat\application\auth\_sessions.py`

```python
class CorruptAuthSessionError(AeatError):
    """Raised when persisted session metadata cannot be parsed."""
```

```python
class AuthSessionUnavailableError(AeatError):
    """Raised when no verified active AEAT session can be supplied."""
```

## `src\aeat\application\review\_errors.py`

```python
class ReviewError(AeatError):
    """Base class for every error raised by :mod:`aeat.application.review`."""
```

```python
class ReviewSourceLoadError(ReviewError):
    """Raised when a source disk file is present but cannot be parsed."""
```

```python
class FilterParseError(ReviewError):
    """Raised when ``--filter KEY=VALUE`` cannot be parsed.

    Carries the raw token plus a stable reason code so the CLI can render
    a per-language repair hint.

    Attributes:
        raw_token: The string the operator supplied (e.g. ``"status="`` or
            ``"period: 2026-Q1"``).
        reason: One of ``"missing-equals"``, ``"empty-key"``,
            ``"empty-value"``, ``"unknown-key-{scope}"``,
            ``"invalid-value-{scope}"``, ``"duplicate-key-{scope}"``.
    """

    def __init__(self, raw_token: str, *, reason: str) -> None:
        super().__init__(f"cannot parse filter token {raw_token!r}: {reason}")
        self.raw_token = raw_token
        self.reason = reason
```

```python
class EditParseError(ReviewError):
    """Raised when ``--set KEY=VALUE`` cannot be parsed.

    Attributes:
        raw_token: The string the operator supplied.
        reason: One of ``"missing-equals"``, ``"empty-key"``,
            ``"empty-value"``, ``"unknown-key-{scope}"``,
            ``"invalid-value-{scope}"``, ``"duplicate-key-{scope}"``.
    """

    def __init__(self, raw_token: str, *, reason: str) -> None:
        super().__init__(f"cannot parse edit token {raw_token!r}: {reason}")
        self.raw_token = raw_token
        self.reason = reason
```

```python
class ReviewKindReservedError(ReviewError):
    """Raised when the CLI receives a reserved kind token.

    Carries the blocking reason returned by
    :func:`aeat.application.review._enums.reserved_kind_reason`.

    Attributes:
        token: The ``--kind`` value supplied by the user.
        reason: Human-readable explanation naming the blocking upstream
            record type.
    """

    def __init__(self, token: str, reason: str) -> None:
        """Construct the error with the offending token and its blocking reason.

        Args:
            token: The ``--kind`` value supplied by the user.
            reason: Human-readable explanation naming the blocking
                upstream record type.
        """
        super().__init__(f"--kind {token!r} is reserved and is not an emitted review kind: {reason}")
        self.token = token
        self.reason = reason
```

## `src\aeat\application\setup\_errors.py`

```python
class SetupError(AeatError):
    """Base class for every setup-wizard error."""
```

```python
class SetupAbortedError(SetupError):
    """Raised when the user explicitly aborts the wizard."""
```

```python
class SetupVerifyError(SetupError):
    """Raised when the verify step finds an ERROR-severity problem."""
```

```python
class SetupAnswersError(SetupError):
    """Raised when a :class:`SetupAnswers` payload cannot be loaded or validated."""
```

## `src\aeat\application\verification\_errors.py`

```python
class VerificationError(AeatError):
    """Raised on catastrophic verification failures.

    Reserved for unrecoverable conditions (corrupt registry data, broken engine
    contract, missing core dependency). Discrepancies between the printed
    casilla values and the engine-derived values are not exceptions; they
    surface as
    :class:`aeat.application.verification.ClassifiedDiscrepancy` entries
    on the verdict.
    """
```

## `src\aeat\application\workflow\_errors.py`

```python
class WorkflowError(AeatError):
    """Base exception for all :mod:`aeat.application.workflow` failures."""
```

```python
class WorkflowComponentError(WorkflowError):
    """Raised when a cross-module component raises an unexpected exception.

    The engine catches every exception raised by an injected Protocol
    component, wraps it in a :class:`WorkflowComponentError`, records the
    context on the surrounding :class:`aeat.application.workflow.WorkflowStep`, and
    lets the workflow abort with
    :attr:`aeat.application.workflow.WorkflowAbortReason.UNHANDLED_EXCEPTION`.
    """
```

```python
class WorkflowAbortedError(WorkflowError):
    """Raised only when a caller explicitly opts in to exception-on-abort.

    The default driver path returns a populated
    :class:`aeat.application.workflow.WorkflowResult` whose ``aborted_reason`` is set.
    This exception is reserved for callers that prefer raising over
    inspecting (e.g. a future cron runner that wants a non-zero exit).
    """
```

```python
class WorkflowAbortSignal(WorkflowError):  # noqa: N818 - internal control-flow signal, not a public Error
    """Internal control-flow signal raised by stage methods to bail out.

    Named ``WorkflowAbortSignal`` deliberately (rather than
    ``WorkflowAbortSignalError``) because the engine treats it as an
    internal control-flow vehicle, not as a public error type — it
    never propagates outside :class:`aeat.application.workflow.WorkflowEngine`.
    :meth:`WorkflowEngine._drive` always catches it and materialises the
    :class:`aeat.application.workflow.WorkflowResult`. Subclasses
    :class:`WorkflowError` so the project-wide error-hierarchy rule
    still holds and the registry can bind a stable
    ``INTERNAL_WORKFLOW_ABORT_SIGNAL`` code for telemetry.

    Attributes:
        reason: The :class:`WorkflowAbortReason` that classifies the bailout.
        summary: Human-readable :class:`str` summary surfaced on
            the resulting :class:`WorkflowResult`.
    """

    def __init__(
        self,
        *,
        reason: WorkflowAbortReason,
        summary: str,
    ) -> None:
        super().__init__(reason.value)
        self.reason = reason
        self.summary = summary
```

## `src\aeat\core\json_contract.py`

```python
class OutputSchemaError(AeatError):
    """Raised when the CLI output-schema registry is misconfigured.

    Triggered by :func:`register_schema` when a non-schema class is
    decorated, when a command path is registered twice with different
    schemas, or when the command path is blank.
    """
```

## `src\aeat\core\locks_errors.py`

```python
class LockAcquisitionError(AeatError):
    """Raised when an exclusive file lock cannot be acquired within the timeout.

    Bound to a registered :class:`aeat.core.errors.ErrorCode` so callers
    can present a stable error identifier rather than a raw message.
    """
```

## `src\aeat\core\access_gate\_errors.py`

```python
class AccessGateSubmissionError(AeatError):
    """Base class for live-write access-gate submission policy failures.

    Attributes:
        translated_message: Optional :class:`aeat.core.i18n.str`
            payload carrying a user-facing version of the message.
    """

    def __init__(self, message: str, *, translated_message: str | None = None) -> None:
        """Construct a submission error.

        Args:
            message: English-authoritative error message (logged).
            translated_message: Optional multilingual payload surfaced
                to the CLI and any user-facing consumer.
        """
        super().__init__(message)
        self.translated_message: str | None = translated_message
```

```python
class AccessGateSubmissionPreflightError(AccessGateSubmissionError):
    """Raised when access-gate preflight rejects a write-shaped operation."""
```

```python
class LiveSubmitForbiddenError(AccessGateSubmissionPreflightError):
    """Raised when any caller attempts a permanently forbidden live AEAT write."""

    def __init__(
        self,
        message: str = (
            "live AEAT submission is permanently forbidden; use produce -> verify -> "
            "export and upload the file yourself in the AEAT portal"
        ),
        *,
        translated_message: str | None = None,
    ) -> None:
        """Construct the permanent live-submit refusal error."""
        default_translatable: str = "access_gate.errors.default_translatable"
        super().__init__(
            message,
            translated_message=translated_message or default_translatable,
        )
```

```python
class AeatLiveReadNotEnabledError(AeatError):
    """Raised when live-read access is required but the gate is shut.

    Emitted by :meth:`AeatAccessGate.require_live_read` when
    ``AEAT_LIVE_TESTS_ENABLED`` is not set to ``"1"``. The existing
    per-test ``if os.environ[...] != "1": pytest.skip(...)``
    boilerplate is not replaced — this error gives non-test callers
    (future live-read CLI commands, sync runners) a typed failure
    shape.
    """
```

## `src\aeat\core\corpus_manifest\_errors.py`

```python
class CorpusManifestError(AeatError):
    """Base error for any failure in corpus-manifest parsing or validation.

    Concrete failure modes derive from this class; callers can catch
    :class:`CorpusManifestError` to handle every manifest failure
    uniformly, or catch a leaf such as :class:`CorpusManifestTamperError`
    to react to a specific condition.
    """
```

```python
class CorpusManifestTamperError(CorpusManifestError):
    """Raised when a manifest's self-attesting digest does not match its body.

    Indicates the manifest body has been edited without recomputing the
    embedded checksum — usually a sign of corruption or tampering rather
    than legitimate drift between the manifest and the on-disk corpus
    (which is signalled by :class:`CorpusManifestDriftError`).
    """
```

```python
class CorpusManifestDriftError(CorpusManifestError):
    """Raised when the on-disk corpus diverges from the manifest's expectations.

    Distinct from :class:`CorpusManifestTamperError`: the manifest itself
    is internally consistent, but the files it describes have been
    added, removed, or modified relative to the manifest's recorded
    digests.
    """
```

## `src\aeat\core\errors\__init__.py`

```python
class AeatError(Exception):
    """Base exception for all AEAT domain errors."""

    code: ClassVar[ErrorCode]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Bind a registered :class:`ErrorCode` to each declared subclass."""

        super().__init_subclass__(**kwargs)
        from ._registry import bind_error_code

        bind_error_code(cls)

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        suggestion: str | None = None,
        translated_message: str | None = None,
    ) -> None:
        """Construct a domain error with optional structured metadata.

        Args:
            message: Optional human-readable message override.
            context: Optional structured context that can be redacted and
                emitted in the JSON envelope.
            suggestion: Optional copy-paste recovery command override.
            translated_message: Optional multilingual message override.
        """

        if message is None:
            super().__init__()
        else:
            super().__init__(message)
        self.context: dict[str, object] | None = dict(context) if context is not None else None
        self.suggestion: str | None = suggestion
        self.translated_message: str | None = translated_message
```

```python
class AeatObservabilityError(AeatError):
    """Base class for observability-layer errors.

    Lives in :mod:`aeat.core.errors` (rather than the leaf
    :mod:`aeat.core.observability` subpackage) so other subpackages can
    catch it without importing observability internals. Concrete
    subclasses are declared in :mod:`aeat.core.observability._errors`.
    """
```

```python
class FixtureProvisioningError(AeatError):
    """Raised when Google Workspace test-fixture provisioning fails.

    Thrown by the provisioning and teardown scripts under ``scripts/``
    whenever a Drive / Sheets / Docs call cannot satisfy the catalogued
    intent (missing parent, quota exhausted, unexpected dedup result, etc).
    """
```

```python
class FilingFixtureError(AeatError):
    """Raised when a synthetic filing-history fixture cannot be loaded.

    Thrown by :mod:`aeat.application.filing.testing` when the fixtures directory cannot be
    resolved, a fixture file cannot be read, JSON decoding fails, or a
    payload fails strict pydantic validation (including the synthetic-
    only invariant checks on the ``synthetic`` and ``_comment`` fields).
    """
```

```python
class SiteHealthError(AeatError):
    """Raised when AEAT site-health detection classifies a non-OK state.

    Carries a strict :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
    attribute describing the detected state (mantenimiento, WAF challenge,
    rate limit, unreachable, unknown error) together with the evidence
    used to classify it. The workflow engine catches this error in a typed
    arm that precedes the generic exception handler so a planned
    mantenimiento never collapses into ``UNHANDLED_EXCEPTION``.

    The error lives in :mod:`aeat.core.errors` (and not in either leaf
    subpackage) to break the circular import between
    :mod:`aeat.adapters.outbound.aeat.browser` (which raises it) and :mod:`aeat.application.workflow`
    (which consumes it).
    """

    def __init__(self, *, status: Any) -> None:
        """Construct a SiteHealthError carrying a detected status.

        Args:
            status: The strict
                :class:`aeat.adapters.outbound.aeat.browser._site_health.SiteHealthStatus`
                instance describing the detected non-OK state.
        """

        state = status.state
        state_value = getattr(state, "value", state)
        evidence = status.evidence
        context: dict[str, object] = {
            "state": str(state_value),
            "url": str(evidence.url),
            "http_status": evidence.http_status,
            "detected_markers": tuple(evidence.detected_markers),
            "observed_at": status.observed_at.isoformat(),
        }
        if status.retry_after_seconds is not None:
            context["retry_after_seconds"] = status.retry_after_seconds
        super().__init__(str(state_value), context=context)
        self.status: Any = status
```

```python
class McpLaunchError(AeatError):
    """Raised when a repo-managed MCP process cannot be launched safely."""
```

## `src\aeat\core\identity\_documents.py`

```python
class IdentityError(AeatError):
    """Raised when a candidate string is not a valid Spanish identity document.

    Bound to the registered error code ``INTEGRITY_IDENTITY_DOCUMENT``
    in :data:`aeat.core.errors.ERROR_REGISTRY`. Carries a human-readable
    diagnostic that names the failing shape (``NIF``, ``NIE``, ``CIF``)
    and, where relevant, the expected vs observed check character.
    """
```

## `src\aeat\core\observability\_errors.py`

```python
class RunContextMissingError(AeatObservabilityError):
    """Raised when :func:`record_event` runs outside an active :func:`run_context`.

    Caused by calling the recorder from a thread that did not propagate
    the contextvar bound by :func:`aeat.core.observability.run_context`,
    or by calling it from CLI bootstrap code that runs before the run
    context enters.
    """

    pass
```

```python
class RunTraceValidationError(AeatObservabilityError):
    """Raised when persisted ``trace.json`` or ``events.jsonl`` fails strict validation.

    Surfaces both shape-level rejections (bad ``run_id``, malformed
    JSON line) and pydantic strict-mode validation failures.
    """

    pass
```

```python
class AeatCorpusDriftError(AeatObservabilityError):
    """Raised when replay detects that ``corpus_sha256`` has drifted.

    Carries both the recorded and observed hashes plus the entrypoint
    so the caller can render an actionable diff.
    :func:`aeat.core.observability.replay_run` is the only call site
    that raises this.

    Attributes:
        run_id: Identifier of the recorded run being replayed.
        recorded: ``corpus_sha256`` captured at the original run.
        observed: ``corpus_sha256`` computed against the current tree.
        entrypoint: CLI entrypoint string of the recorded run.
    """

    def __init__(
        self,
        *,
        run_id: str,
        recorded: str,
        observed: str,
        entrypoint: str,
    ) -> None:
        """Build the drift error and its diagnostic message.

        Args:
            run_id: Identifier of the recorded run being replayed.
            recorded: ``corpus_sha256`` captured at the original run.
            observed: ``corpus_sha256`` computed against the current tree.
            entrypoint: CLI entrypoint string of the recorded run.
        """
        super().__init__(
            f"corpus drift on replay of run {run_id!r}: "
            f"recorded={recorded[:12]}... observed={observed[:12]}... "
            f"entrypoint={entrypoint!r}",
        )
        self.run_id: str = run_id
        self.recorded: str = recorded
        self.observed: str = observed
        self.entrypoint: str = entrypoint
```

## `src\aeat\domain\attachments\_errors.py`

```python
class AttachmentError(AeatError):
    """Base error for every attachment-service failure.

    All other exceptions in :mod:`aeat.domain.attachments` derive from this
    class so callers can install a single catch.
    """
```

```python
class AttachmentValidationError(AttachmentError):
    """Raised when an attachment payload fails domain validation.

    Used both by pydantic-driven validation on :class:`aeat.domain.attachments.Attachment`
    and by :class:`aeat.domain.attachments.AttachmentStore` when an untrusted
    digest token does not match the expected 64-character lowercase hex shape.
    """
```

```python
class AttachmentPersistenceError(AttachmentError):
    """Raised when the attachment store cannot read or write bytes or manifests.

    Wraps the underlying :exc:`OSError` so callers do not have to reason about
    raw filesystem failures.
    """
```

```python
class AttachmentNotFoundError(AttachmentError):
    """Raised when a manifest or blob lookup targets a missing attachment.

    Distinct from :exc:`AttachmentPersistenceError` so callers can treat a
    missing record differently from a filesystem failure.
    """
```

## `src\aeat\domain\calculations\registry\_errors.py`

```python
class RegistryError(ValueError):
    """Base error for registry loading, resolution, and validation."""
```

```python
class RegistryLoadError(RegistryError):
    """Raised when registry files cannot be parsed into strict schema objects."""
```

```python
class RegistryValidationError(RegistryError):
    """Raised when registry definitions are incomplete or contradictory."""
```

```python
class RegistrySnapshotError(RegistryError):
    """Raised when a filing-grade snapshot cannot be selected."""
```

## `src\aeat\domain\calculations\registry\_workbook_parity.py`

```python
class _BinaryXlsConversionError(Exception):
    """Failure raised after a valid LibreOffice runner starts XLS conversion."""
```

## `src\aeat\domain\deadlines\_errors.py`

```python
class DeadlineError(AeatError):
    """Base class for every error raised by :mod:`aeat.domain.deadlines`."""
```

```python
class ProfileError(DeadlineError):
    """Raised when an :class:`aeat.domain.deadlines.AutonomoProfile` cannot be loaded or validated."""
```

```python
class ScheduleComputationError(DeadlineError):
    """Raised when :meth:`aeat.domain.deadlines.DeadlineEngine.compute` cannot produce a schedule.

    Typical triggers include a configured year outside the supported
    calendar range, or an injected catalogue loader returning an
    unknown modelo.
    """
```

## `src\aeat\domain\filing\_errors.py`

```python
class FilingDraftError(AeatError):
    """Base class for every error raised inside :mod:`aeat.domain.filing`."""
```

```python
class FilingBuilderError(FilingDraftError):
    """Raised when builder selection or execution fails."""
```

```python
class FilingValidationError(FilingDraftError):
    """Raised when validation surfaces a blocking finding.

    The validator itself never raises; this error is reserved for
    callers that opt into ``fail_on_warning`` and want a hard fail.
    """
```

```python
class FilingComputationError(FilingDraftError):
    """Raised when a builder cannot evaluate a formula casilla."""
```

```python
class FilingAmendmentError(FilingDraftError):
    """Base class for every amendment-related filing error."""
```

```python
class FilingAmendmentValidationError(FilingAmendmentError):
    """Raised when an amendment violates legal or shape invariants."""
```

```python
class FilingImportError(FilingDraftError):
    """Raised when importing a filing from a justificante PDF fails."""
```

## `src\aeat\domain\invoices\_errors.py`

```python
class InvoiceError(AeatError):
    """Base error for every invoice-catalogue failure."""
```

```python
class InvoiceCatalogueError(InvoiceError):
    """Raised when an invoice catalogue is invalid or inconsistent."""
```

```python
class InvoicePersistenceError(InvoiceCatalogueError):
    """Raised when invoice catalogue persistence cannot be completed."""
```

```python
class InvoiceNotFoundError(InvoiceCatalogueError):
    """Raised when a catalogue lookup targets a missing invoice."""
```

```python
class InvoiceLinkError(InvoiceCatalogueError):
    """Raised when a bidirectional invoice/transaction link cannot proceed."""
```

```python
class InvoiceLinkInconsistencyError(InvoiceLinkError):
    """Raised when a bidirectional link leaves the two catalogues out of sync.

    Carries both filesystem paths and both identifiers so an operator can
    manually reconcile the invoice and transaction catalogues.

    Attributes:
        invoice_path: Path to the invoice catalogue file.
        transactions_path: Path to the transaction catalogue file.
        invoice_id: Invoice identifier involved in the failed link.
        transaction_id: Transaction identifier involved in the failed link.
    """

    def __init__(
        self,
        *,
        invoice_path: Path,
        transactions_path: Path,
        invoice_id: str,
        transaction_id: str,
        message: str,
    ) -> None:
        """Construct a link-inconsistency error carrying both sides of the failure.

        Args:
            invoice_path: Path to the invoice catalogue file.
            transactions_path: Path to the transaction catalogue file.
            invoice_id: Invoice identifier involved in the failed link.
            transaction_id: Transaction identifier involved in the failed link.
            message: Human-readable explanation.
        """
        super().__init__(message)
        self.invoice_path: Path = invoice_path
        self.transactions_path: Path = transactions_path
        self.invoice_id: str = invoice_id
        self.transaction_id: str = transaction_id
```

## `src\aeat\domain\justificante\_errors.py`

```python
class PdfFilingImportError(AeatError):
    """Domain-level root for PDF filing import failures."""
```

```python
class JustificanteError(PdfFilingImportError):
    """Base class for every justificante-related failure."""
```

```python
class JustificanteParseError(JustificanteError):
    """Raised when a PDF cannot be parsed into a :class:`Justificante`."""
```

```python
class JustificanteCsvNotFoundError(JustificanteParseError):
    """Raised when a PDF does not contain a Código Seguro de Verificación."""
```

```python
class JustificanteVerificationError(JustificanteError):
    """Raised when the live CSV verification round-trip fails."""
```

## `src\aeat\domain\manuals\errors.py`

```python
class ManualError(AeatError):
    """Base error for every :mod:`aeat.domain.manuals` failure mode."""
```

```python
class ManualNotFoundError(ManualError):
    """Raised when a requested manual/year/part is missing on disk."""
```

```python
class ManualParseError(ManualError):
    """Raised when a committed manual record fails schema validation."""
```

```python
class ManualReviewRequiredError(ManualError):
    """Raised when a persisted record lacks reviewer metadata.

    The verify CLI rejects any :class:`~aeat.domain.manuals.Manual`,
    :class:`~aeat.domain.manuals.Section`, or
    :class:`~aeat.domain.manuals.Rule` record missing
    ``definition_reviewed_by`` or ``definition_reviewed_at`` when the
    ``AEAT_MANUALS_REVIEW_REQUIRED`` setting is enabled.
    """
```

```python
class RuleExtractionError(ManualError):
    """Raised by LLM-dependent CLI subcommands that have no backing implementation.

    The ``structure``, ``extract-rules``, and ``translate`` subcommands
    define their public CLI shape but raise this exception until the
    :mod:`aeat.adapters.outbound.llm` subpackage is available.
    """
```

```python
class ManifestError(ManualError):
    """Raised when a ``manifest.json`` fails schema or sha256 checks."""
```

## `src\aeat\domain\normatives\errors.py`

```python
class NormativeError(AeatError):
    """Base error for every ``aeat.domain.normatives`` failure mode."""
```

```python
class NormativeParseError(NormativeError):
    """Raised when a committed normative JSON fails schema validation."""
```

```python
class NormativeNotFoundError(NormativeError):
    """Raised when a requested normative or article is missing."""
```

## `src\aeat\domain\portals\_errors.py`

```python
class PortalRegistryError(AeatError):
    """Base class for every error raised from :mod:`aeat.domain.portals`."""
```

```python
class UnknownPortalError(PortalRegistryError):
    """Raised by :func:`aeat.domain.portals.get_portal` on unknown names.

    Attributes:
        portal: The offending portal name or value as supplied by the
            caller.
    """

    def __init__(self, portal: str) -> None:
        """Initialise with the offending portal identifier."""
        super().__init__(f"unknown portal: {portal!r}")
        self.portal = portal
```

```python
class PortalIntegrityError(PortalRegistryError):
    """Raised at import time when the registry fails a structural check.

    Signals that a portal registry entry violates a structural
    invariant, such as a missing member, extra member, duplicate entry,
    or dangling ``replaced_by`` reference. It can also surface invalid
    registry-backed portal bindings during lookup.
    """
```

## `src\aeat\domain\profile\errors.py`

```python
class AssetRecordError(AeatError):
    """Raised when an asset record is structurally invalid."""
```

```python
class AmortizationLedgerError(AeatError):
    """Raised when an amortization ledger operation is invalid."""
```

```python
class InventoryLedgerError(AeatError):
    """Raised when an inventory ledger operation is invalid."""
```

```python
class LIFOForbiddenError(InventoryLedgerError):
    """Raised when a caller attempts LIFO inventory valuation.

    LIS art. 17.1 does not admit LIFO for tax-purpose stock valuation
    in this regime; the message routes the operator to FIFO, PMP, or
    coste medio.
    """

    def __init__(self, method: str = "lifo") -> None:
        """Construct a refusal citing the LIS art. 17 valuation boundary.

        Args:
            method: User-supplied valuation method.
        """
        super().__init__(
            "LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1.",
            context={"method": method, "legal_basis": "LIS art. 17.1"},
        )
```

```python
class BasisCapExceededError(AmortizationLedgerError):
    """Raised when cumulative amortization would exceed cost basis."""
```

## `src\aeat\domain\profile\_errors.py`

```python
class TaxResidenceProfileError(AeatError):
    """Base class for tax-residence profile failures.

    Concrete subclasses (:class:`ProfileNotConfiguredError`,
    :class:`ForalRegimeError`) carry their own translated messages and
    suggestions; this base type exists only so callers can catch the
    family with a single ``except`` clause.
    """
```

```python
class ProfileNotConfiguredError(TaxResidenceProfileError):
    """Raised when RENTA verification needs a tax-residence profile.

    Attached to a ``suggestion`` pointing the operator at
    ``aeat profile set tax-region <ccaa>``.
    """

    def __init__(self) -> None:
        """Build the multilingual no-profile-configured error."""
        super().__init__(
            "No tax-residence profile is configured for RENTA.",
            translated_message="profile.errors.not_configured",
            suggestion="aeat profile set tax-region <ccaa>",
        )
```

```python
class ForalRegimeError(TaxResidenceProfileError):
    """Raised when the user selects a foral regime not modelled by this profile.

    Attributes:
        value: The foral CCAA identifier supplied by the caller.
    """

    def __init__(self, value: str) -> None:
        """Build the multilingual foral-regime-out-of-scope error."""
        super().__init__(
            f"{value!r} is a foral regime outside the scope of this profile.",
            context={"tax_region": value},
            translated_message="profile.errors.foral_regime",
        )
        self.value = value
```

## `src\aeat\domain\rental\_errors.py`

```python
class RentalRegisterError(AeatError):
    """Base error for the rental-register subpackage."""
```

```python
class FincaNotFoundError(RentalRegisterError):
    """Raised when a referenced finca id is not present in the register."""
```

```python
class ContractNotFoundError(RentalRegisterError):
    """Raised when a referenced rental contract id is not present in the register."""
```

```python
class TierResolutionError(RentalRegisterError):
    """Raised when contract metadata is inconsistent and a tier cannot be resolved.

    Examples: ``tenant_min_age > tenant_max_age``,
    ``qualifying_co_tenant_count > tenant_count`` (also enforced at
    DB level), or a tier-90-a candidate with no prior-contract data.
    """
```

```python
class AmortizationLedgerCapExceededError(RentalRegisterError):
    """Raised in strict mode when cumulative amortización would exceed the cap.

    Default ``compute_amortization_for_year`` clamps to the remaining
    cap and never raises. Strict callers (e.g. preflight verifiers
    that want to flag the surface) opt in via ``strict=True``.
    """
```

```python
class RentalAggregationError(RentalRegisterError):
    """Raised when the rental register cannot produce coherent aggregates.

    Surface causes: contract referencing a non-existent finca; income
    record without a contract; ledger entry whose
    ``cumulative_amortization_through_year`` is out of order with
    surrounding entries (re-stated mid-year accrual without a prior
    recompute).
    """
```

## `src\aeat\domain\submission\_errors.py`

```python
class SubmissionError(AeatError):
    """Base class for submission-domain failures."""
```

```python
class SubmissionPreflightError(SubmissionError):
    """Raised when a draft cannot pass local submission preflight."""
```

## `src\aeat\domain\transactions\_errors.py`

```python
class TransactionError(AeatError):
    """Base error for every transaction-catalogue failure."""
```

```python
class TransactionCatalogueError(TransactionError):
    """Raised when a transaction catalogue is invalid or inconsistent."""
```

```python
class TransactionPersistenceError(TransactionCatalogueError):
    """Raised when catalogue persistence cannot be completed."""
```

```python
class TransactionNotFoundError(TransactionCatalogueError):
    """Raised when a catalogue lookup targets a missing transaction."""
```

```python
class LLMClassifierError(TransactionError):
    """Raised when an LLM classification attempt fails."""
```

## `src\aeat\domain\usage_ratios\_errors.py`

```python
class UsageRatioError(AeatError):
    """Base error for every :mod:`aeat.domain.usage_ratios` failure mode.

    Subclassed by every concrete error raised by the package so callers can
    catch the broad family with a single ``except`` clause.
    """
```

```python
class UsageRatioPersistenceError(UsageRatioError):
    """Raised when the usage-ratio profile cannot be read or written.

    Surfaced by :func:`aeat.domain.usage_ratios.load_usage_ratios` and
    :func:`aeat.domain.usage_ratios.save_usage_ratios` for OS-level I/O
    failures and for envelope payloads that fail strict validation.
    """
```

## `src\aeat\domain\user_profile\_errors.py`

```python
class UserProfileSchemaLoadError(ValueError):
    """Raised when the committed user-profile schema cannot be loaded."""
```

## `src\aeat\domain\vat\errors.py`

```python
class VatError(AeatError):
    """Base error for every :mod:`aeat.domain.vat` failure mode."""
```

```python
class VatRateNotFoundError(VatError):
    """Raised when :func:`aeat.domain.vat.lookup_rate` cannot resolve a rate.

    The lookup fails either because the requested member state is absent from
    :data:`aeat.domain.vat.VAT_RATE_TABLE`, because no rate of the requested
    :class:`aeat.domain.vat.VATRateKind` is registered for that member state,
    or because every registered rate's effective window excludes the
    requested date.
    """
```

```python
class VatCategoryNotFoundError(VatError):
    """Raised when a lookup against a resolved VAT catalogue misses."""
```

```python
class VatCatalogueError(VatError):
    """Raised when a VAT catalogue cannot be loaded, resolved, or validated."""
```

```python
class VatRateOverlapError(VatError):
    """Raised when two :class:`aeat.domain.vat.VATRate` records share a window.

    The substrate enforces that for every ``(member_state, kind)`` partition
    of :data:`aeat.domain.vat.VAT_RATE_TABLE` no two records have overlapping
    ``effective_from`` / ``effective_until`` ranges. Adding a new record that
    violates this invariant raises this error at module import time so the
    regression surfaces in CI rather than silently affecting
    :func:`aeat.domain.vat.lookup_rate` results.
    """
```

```python
class VatClassificationError(VatError):
    """Raised when :func:`aeat.domain.vat.classify_vat` cannot return a deterministic match.

    The classifier exposes a closed first-match-wins table; the only
    structural failure is when the input criteria cannot be represented under
    the closed enum set, which is caught at construction time by pydantic.
    This error is reserved for future extensions such as ambiguous rule
    rankings.
    """
```

## `src\aeat\entrypoints\cli\_errors.py`

```python
class CliValidationBoundaryError(AeatError):
    """Raised when a CLI callback leaks a :exc:`pydantic.ValidationError`.

    The original exception is preserved on :attr:`original_exception` so
    downstream renderers and tests can inspect it without losing the
    typed pydantic detail.

    Attributes:
        original_exception: The underlying :exc:`pydantic.ValidationError`.
    """

    def __init__(self, error: ValidationError) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The pydantic validation error raised inside the
                Typer callback.
        """

        super().__init__(
            "The command input failed validation.",
            context={
                "error_type": type(error).__name__,
                "detail": str(error),
            },
        )
        self.original_exception: ValidationError = error
```

```python
class CliUnexpectedBoundaryError(AeatError):
    """Raised when a CLI callback leaks an unexpected exception.

    Used for any exception that is not :class:`AeatError`,
    :exc:`pydantic.ValidationError`, or Typer/Click control flow. The
    original exception is preserved on :attr:`original_exception`.

    Attributes:
        original_exception: The underlying exception raised by the
            callback.
    """

    def __init__(self, error: Exception) -> None:
        """Wrap ``error`` in the structured CLI boundary contract.

        Args:
            error: The unexpected exception raised inside the Typer
                callback.
        """

        super().__init__(
            "The command failed due to an unexpected internal error.",
            context={
                "error_type": type(error).__name__,
                "detail": str(error) or type(error).__name__,
            },
        )
        self.original_exception: Exception = error
```

```python
class CliRefusedBoundaryError(AeatError):
    """Raised when JSON-mode CLI must refuse a request with stderr-only output.

    Refusals are emitted as plain stderr text even in JSON mode because
    the structured payload contract intentionally does not expose them
    on stdout.
    """
```

## `src\aeat\entrypoints\cli\_log_levels.py`

```python
class LogLevelResolutionError(AeatError):
    """Raised when the requested CLI log-level inputs are contradictory.

    Examples include passing more than one of ``--quiet`` / ``--verbose``
    / ``--debug`` together, or setting ``AEAT_LOG_LEVEL`` to a value
    outside the :class:`LogLevel` vocabulary.
    """
```

## `src\aeat\entrypoints\cli\_tty.py`

```python
class NonTtyRefusedError(AeatError):
    """Raised when a command requires interactive stdin but stdin is piped.

    Carries the operator-facing recovery hint on :attr:`suggestion` so
    the renderer can append it to the standard refusal message.

    Attributes:
        suggestion: Copy-paste-ready recovery hint shown to the user.
    """

    def __init__(self, suggestion: str) -> None:
        """Initialise the refusal with a copy-paste-ready suggestion.

        Args:
            suggestion: Recovery hint to attach to the refusal message.
        """

        message = "Interactive stdin is unavailable on a non-TTY input stream."
        if suggestion.strip():
            message = f"{message} {suggestion.strip()}"
        super().__init__(message)
        self.suggestion: str = suggestion
```

## `src\aeat\entrypoints\cli\auth\_registry.py`

```python
class NoConfiguredProviderError(AeatError):
    """No auth provider is configured and no default was specified."""
```

```python
class UnknownProviderError(AeatError):
    """The requested provider kind is not registered."""
```

```python
class ProviderUnavailableError(AeatError):
    """The provider kind is known but unavailable."""
```
