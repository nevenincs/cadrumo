"""Encrypted SQL repository for verification reports."""

from __future__ import annotations

from datetime import UTC, datetime

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._errors import ModeloError
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket
from ._verification_report import VerificationReport, VerificationReportCatalogue

_LOGGER = get_logger(__name__)
_VERIFICATION_NAMESPACE = "aeat.domain.modelos.verification_reports"
_VERIFICATION_OBJECT_KEY = "catalogue"
_VERIFICATION_CATALOGUE_VERSION = 1


class VerificationReportPersistenceError(ModeloError):
    """Raised when the verification-report catalogue cannot be persisted or loaded."""


class VerificationReportCatalogueRepository:
    """Read / write verification reports in encrypted storage."""

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
        return self._bucket_id

    def exists(self) -> bool:
        return self._objects.exists(_VERIFICATION_NAMESPACE, _VERIFICATION_OBJECT_KEY)

    def load(self) -> VerificationReportCatalogue:
        try:
            record = self._objects.load(
                _VERIFICATION_NAMESPACE,
                _VERIFICATION_OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_VERIFICATION_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("verification-report catalogue integrity error", exc_info=True)
            raise VerificationReportPersistenceError(
                f"verification-report catalogue integrity error: {type(exc).__name__}: {exc}"
            ) from exc
        if record is None:
            return VerificationReportCatalogue()
        envelope = Envelope[VerificationReportCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise VerificationReportPersistenceError(
                f"verification-report catalogue has classification {envelope.classification}; FINANCIAL expected"
            )
        if envelope.schema_version > _VERIFICATION_CATALOGUE_VERSION:
            raise VerificationReportPersistenceError(
                f"verification-report catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_VERIFICATION_CATALOGUE_VERSION}"
            )
        return envelope.payload

    def save(self, catalogue: VerificationReportCatalogue) -> None:
        envelope = Envelope[VerificationReportCatalogue](
            schema_version=_VERIFICATION_CATALOGUE_VERSION,
            written_at=datetime.now(UTC),
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
    catalogue: VerificationReportCatalogue, report: VerificationReport
) -> VerificationReportCatalogue:
    """Return a new catalogue with ``report`` inserted or replaced."""
    mapping = dict(catalogue.reports)
    mapping[report.verification_report_id] = report
    return VerificationReportCatalogue(reports=mapping)


__all__ = [
    "VerificationReportCatalogueRepository",
    "VerificationReportPersistenceError",
    "upsert_verification_report",
]
