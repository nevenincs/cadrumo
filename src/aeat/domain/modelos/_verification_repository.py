"""Encrypted SQL repository for verification reports.

:class:`~aeat.domain.modelos.VerificationReportCatalogueRepository` persists
and loads :class:`VerificationReport` entries in a
:class:`VerificationReportCatalogue` via
:class:`~aeat.adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~aeat.adapters.persistence.storage.SensitivityClass`.
The catalogue is stored as a single encrypted BLOB per profile bucket and
wrapped in :class:`~aeat.adapters.persistence.storage.Envelope` before
serialisation.
The storage contract is declared by
:data:`aeat.adapters.persistence.storage.MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE`;
its default object key is the singleton ``catalogue`` row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ...core.time import now
from ._errors import ModeloError, raise_catalogue_integrity_error
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket
from ._verification_report import VerificationReport, VerificationReportCatalogue

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository

_LOGGER = get_logger(__name__)
_VERIFICATION_NAMESPACE = "aeat.domain.modelos.verification_reports"
_VERIFICATION_OBJECT_KEY = "catalogue"
_VERIFICATION_CATALOGUE_VERSION = 1
_VERIFICATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_verification_report_persistence"


class VerificationReportPersistenceError(ModeloError):
    """Raised when the verification-report catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from
    :class:`~aeat.domain.modelos.VerificationReportCatalogueRepository` while
    preserving translated recovery context for callers.
    """


class VerificationReportCatalogueRepository:
    """Repository over encrypted SQL-backed verification-report catalogue storage.

    :data:`aeat.adapters.persistence.storage.MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE`
    is the central namespace, schema-version, sensitivity, and singleton-key
    contract for the encrypted :class:`VerificationReportCatalogue` row. The
    catalogue payload is wrapped in
    :class:`~aeat.adapters.persistence.storage.Envelope` before
    :class:`~aeat.adapters.persistence.storage.SecureObjectRepository`
    persists it, while this class exposes the concrete load/save implementation
    behind
    :class:`~aeat.domain.modelos.VerificationReportCatalogueRepositoryProtocol`.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is not None:
            self._objects = objects
            return
        self._bucket_id = resolve_modelo_repository_bucket_id(
            bucket_id,
            error_type=VerificationReportPersistenceError,
        )
        self._objects = secure_objects_for_modelo_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """The profile bucket this repository reads from and writes to.

        A bucket is the per-profile partition of encrypted storage; every
        modelo (an AEAT tax form/declaration) the profile works on shares one
        bucket. The value is the trimmed bucket identifier resolved at
        construction, or ``None`` when the repository was built directly from
        an injected
        :class:`~aeat.adapters.persistence.storage.SecureObjectRepository`
        and no bucket was named.

        Returns:
            The resolved bucket identifier, or ``None`` when none was supplied.
        """
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a stored verification-report catalogue is present.

        Checks the encrypted store for a catalogue object under this
        repository's namespace and key without decrypting or loading it.
        Use this to distinguish a never-written profile from one whose
        catalogue is empty.

        Returns:
            ``True`` if a catalogue record exists for this bucket, else
            ``False``.
        """
        return self._objects.exists(_VERIFICATION_NAMESPACE, _VERIFICATION_OBJECT_KEY)

    def load(self) -> VerificationReportCatalogue:
        """Load and decrypt this bucket's verification-report catalogue.

        Reads the single encrypted catalogue record, validates that it was
        stored at the ``FINANCIAL`` sensitivity class, and parses the wrapping
        :class:`~aeat.adapters.persistence.storage.Envelope` to recover the
        typed catalogue. A verification report records the outcome of checking
        a drafted modelo (an AEAT tax
        form/declaration) against its registry definition, casilla by casilla
        (a casilla is a numbered box/field on the form). When no record has
        ever been written, an empty catalogue is returned rather than raising.

        Returns:
            The stored :class:`VerificationReportCatalogue`, or an empty one
            when nothing has been persisted for this bucket.

        Raises:
            :class:`VerificationReportPersistenceError`: If the stored record
                fails the sensitivity-class check, carries an envelope schema
                version newer than this consumer supports, or trips a
                storage-layer classification or envelope-version integrity
                error.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _VERIFICATION_NAMESPACE,
                _VERIFICATION_OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_VERIFICATION_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise_catalogue_integrity_error(
                exc,
                error_cls=VerificationReportPersistenceError,
                label="verification-report",
                translated_message=_VERIFICATION_PERSISTENCE_MESSAGE,
                logger=_LOGGER,
            )
        if record is None:
            return VerificationReportCatalogue()
        envelope = Envelope[VerificationReportCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            _LOGGER.error(
                "verification-report catalogue classification mismatch",
                extra={
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise VerificationReportPersistenceError(
                "verification-report catalogue classification mismatch",
                translated_message=_VERIFICATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if envelope.schema_version > _VERIFICATION_CATALOGUE_VERSION:
            _LOGGER.error(
                "verification-report catalogue envelope version unsupported",
                extra={
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _VERIFICATION_CATALOGUE_VERSION,
                },
            )
            raise VerificationReportPersistenceError(
                "verification-report catalogue envelope version unsupported",
                translated_message=_VERIFICATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _VERIFICATION_CATALOGUE_VERSION,
                },
            )
        return envelope.payload

    def save(self, catalogue: VerificationReportCatalogue) -> None:
        """Encrypt and persist the verification-report catalogue for this bucket.

        Wraps ``catalogue`` in
        :class:`~aeat.adapters.persistence.storage.Envelope` stamped with the
        current schema version, the write timestamp, and the ``FINANCIAL``
        sensitivity class, then overwrites the single catalogue object held
        under this repository's namespace and key. The write replaces any prior
        catalogue wholesale; merge a new report into the existing catalogue
        with :func:`upsert_verification_report` before calling this.

        Args:
            catalogue: The full :class:`VerificationReportCatalogue` to store,
                keyed by each report's verification-report identifier.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass

        envelope = Envelope[VerificationReportCatalogue](
            schema_version=_VERIFICATION_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_VERIFICATION_NAMESPACE,
            object_key=_VERIFICATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_VERIFICATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


def upsert_verification_report(
    catalogue: VerificationReportCatalogue,
    report: VerificationReport,
) -> VerificationReportCatalogue:
    """Return a new catalogue with ``report`` inserted or replaced.

    Returns:
        A :class:`VerificationReportCatalogue` with the given report added or updated.
    """
    mapping = dict(catalogue.reports)
    mapping[report.verification_report_id] = report
    return VerificationReportCatalogue(reports=mapping)


__all__ = [
    "VerificationReportCatalogueRepository",
    "VerificationReportPersistenceError",
    "upsert_verification_report",
]
