"""Encrypted SQL repository for modelo verification reports.

:class:`VerificationReportCatalogueRepository` persists and loads
:class:`VerificationReport` entries in a :class:`VerificationReportCatalogue`
via :class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass`. The
catalogue is stored as a single encrypted BLOB per profile bucket, wrapped in
:class:`~adapters.persistence.storage.Envelope` before serialisation.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.modelos.VerificationReportCatalogueRepositoryProtocol`. It
lives in the persistence adapter (not in :mod:`~domain.modelos`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`VerificationReportCatalogue` model and its pure mutators.

See Also:
    :mod:`~adapters.persistence.profile._modelo_runtime`
        Bucket-id resolution and runtime secure-object factory shared by modelo
        persistence adapters.
    :class:`~domain.modelos.VerificationReportCatalogue`
        Domain catalogue payload encrypted by this repository.
    :class:`~domain.modelos.VerificationReportCatalogueRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :data:`~adapters.persistence.storage.MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE`
        Central namespace, sensitivity, schema-version, and singleton-key
        contract for these secure objects.
    :mod:`~adapters.persistence.profile.modelos_calculation`
        Sibling calculation-revision repository whose revisions are assessed by
        verification reports stored here.
    :func:`~application.modelo.list_verification_reports`
        Read-side application service that loads reports through this repository
        boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.bucket_pointer import resolve_repository_bucket_id
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....domain.modelos import VerificationReportCatalogue, VerificationReportPersistenceError
from ....domain.modelos.errors import raise_catalogue_integrity_error
from ..storage import MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE, secure_object_repository_for_bucket
from ._secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository

_LOGGER = get_logger(__name__)
_VERIFICATION_NAMESPACE = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.namespace
_VERIFICATION_OBJECT_KEY = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.require_default_object_key()
_VERIFICATION_CATALOGUE_VERSION = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.schema_version
_VERIFICATION_CATALOGUE_SENSITIVITY = MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE.sensitivity
_VERIFICATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_verification_report_persistence"


class VerificationReportCatalogueRepository:
    """Repository over encrypted SQL-backed verification-report catalogue storage.

    The write path (``to_secure_object_write`` / ``save`` / ``exists``)
    composes
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the shared Envelope-construction mechanic; ``load`` stays hand-rolled
    here because it translates a classification or schema-version mismatch
    into :class:`VerificationReportPersistenceError` via
    :func:`~domain.modelos.raise_catalogue_integrity_error`. This class is
    the concrete load/save implementation behind
    :class:`~domain.modelos.VerificationReportCatalogueRepositoryProtocol`.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind to a profile bucket's secure-object store, or an injected one.

        Args:
            bucket_id: Profile bucket whose encrypted store backs this repository;
                resolved from the active session when ``None``.
            objects: Optional injected secure-object repository (testing seam).
        """
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is not None:
            self._objects = objects
        else:
            self._bucket_id = resolve_repository_bucket_id(
                bucket_id,
                error_type=VerificationReportPersistenceError,
            )
            self._objects = secure_object_repository_for_bucket(self._bucket_id)
        self._storage = ProfileEnvelopedModelSecurePersistence(
            objects=self._objects,
            definition=MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE,
            model_type=VerificationReportCatalogue,
            empty_document=VerificationReportCatalogue,
        )

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a stored verification-report catalogue is present."""
        return self._storage.exists()

    def _assert_reports_resolve_to_local_revisions(
        self,
        catalogue: VerificationReportCatalogue,
        *,
        boundary: str,
    ) -> None:
        """Refuse reports whose parent calculation revision is not in this bucket.

        A verification report is a decision *about* one
        :class:`~domain.modelos.CalculationRevision`; detached from that parent
        it asserts an audit outcome nothing in the bucket can be checked
        against. The sibling calculation catalogue is derived from this
        repository's own secure-object store rather than resolved
        independently, so the two reads cannot disagree about which bucket they
        are answering for.

        Args:
            catalogue: The catalogue being written or read back.
            boundary: ``"save"`` or ``"load"``, recorded on the refusal context.

        Raises:
            :class:`VerificationReportPersistenceError`: When any report names a
                ``calculation_revision_id`` this bucket does not hold.
        """
        if not len(catalogue):
            return
        from .modelos_calculation import CalculationRevisionCatalogueRepository

        revisions = CalculationRevisionCatalogueRepository(objects=self._objects).load()
        unresolved = sorted(
            {
                report.calculation_revision_id
                for report in catalogue.values()
                if revisions.get(report.calculation_revision_id) is None
            },
        )
        if not unresolved:
            return
        _LOGGER.error(
            "verification report references a calculation revision outside this bucket",
            extra={"boundary": boundary, "unresolved_count": len(unresolved)},
        )
        raise VerificationReportPersistenceError(
            "verification report references a calculation revision outside this bucket",
            translated_message=_VERIFICATION_PERSISTENCE_MESSAGE,
            context={
                "reason": "foreign_calculation_revision",
                "boundary": boundary,
                "calculation_revision_ids": unresolved,
            },
        )

    def load(self) -> VerificationReportCatalogue:
        """Load and decrypt this bucket's verification-report catalogue.

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
        from ..storage import (
            ClassificationError,
            Envelope,
            EnvelopeVersionError,
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )

        try:
            record = self._objects.load(
                _VERIFICATION_NAMESPACE,
                _VERIFICATION_OBJECT_KEY,
                expected_class=_VERIFICATION_CATALOGUE_SENSITIVITY,
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
        envelope = Envelope[VerificationReportCatalogue].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        if not inner_envelope_classification_is_expected(envelope.classification, _VERIFICATION_CATALOGUE_SENSITIVITY):
            _LOGGER.error(
                "verification-report catalogue classification mismatch",
                extra={
                    "expected_classification": _VERIFICATION_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise VerificationReportPersistenceError(
                "verification-report catalogue classification mismatch",
                translated_message=_VERIFICATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": _VERIFICATION_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _VERIFICATION_CATALOGUE_VERSION):
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
        self._assert_reports_resolve_to_local_revisions(envelope.payload, boundary="load")
        return envelope.payload

    def save(self, catalogue: VerificationReportCatalogue) -> None:
        """Encrypt and persist the verification-report catalogue for this bucket.

        Args:
            catalogue: The full :class:`VerificationReportCatalogue` to store,
                keyed by each report's verification-report identifier.
        """
        self._assert_reports_resolve_to_local_revisions(catalogue, boundary="save")
        self._storage.save(catalogue)


__all__ = [
    "VerificationReportCatalogueRepository",
]
