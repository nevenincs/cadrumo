"""Governed-persistence repository for the invoice catalogue.

The repository is the only sanctioned read/write path for the invoice
catalogue. It stores the catalogue as an encrypted byte object via
:class:`SecureObjectRepository` at :class:`SensitivityClass` FINANCIAL
using an :class:`Envelope` wrapper; no plaintext invoice row, JSON
catalogue, or envelope file lands on disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ...core.time import now
from ._errors import InvoicePersistenceError
from ._models import InvoiceCatalogue

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectRepository, SecureObjectWrite

_log = get_logger(__name__)

_INVOICE_CATALOGUE_VERSION = 1
_INVOICE_NAMESPACE = "aeat.domain.invoices"
_INVOICE_OBJECT_KEY = "catalogue"


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ...adapters.persistence.storage import secure_object_repository_for_bucket
    from ...core.config import load_settings

    return secure_object_repository_for_bucket(bucket_id, load_settings())


def _resolve_invoice_bucket_id(bucket_id: str | None) -> str:
    trimmed = (bucket_id or "").strip()
    if trimmed:
        return trimmed
    from ...core import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None:
        raise InvoicePersistenceError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )
    return active


class InvoiceCatalogueRepository:
    """Repository over the encrypted SQL-backed invoice catalogue."""

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if bucket_id is not None and not self._bucket_id:
            raise InvoicePersistenceError(
                translated_message="application.workflow.errors.no_active_profile_bucket",
            )
        if objects is not None:
            self._objects = objects
            return
        self._bucket_id = _resolve_invoice_bucket_id(bucket_id)
        self._objects = _secure_objects_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether an invoice catalogue has been persisted."""
        return self._objects.exists(_INVOICE_NAMESPACE, _INVOICE_OBJECT_KEY)

    def load(self) -> InvoiceCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The deserialised :class:`InvoiceCatalogue`, or a fresh empty
            instance when no database object is present.

        Raises:
            ClassificationError: If the persisted object's classification is
                not ``SensitivityClass.FINANCIAL``.
            EnvelopeVersionError: If the envelope schema version is higher
                than the consumer supports.
        """
        from ...adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
        )

        record = self._objects.load(
            _INVOICE_NAMESPACE,
            _INVOICE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        if record is None:
            _log.debug("no invoice catalogue in database, returning empty")
            return InvoiceCatalogue()
        envelope = Envelope[InvoiceCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            from ...adapters.persistence.storage.errors import ClassificationError

            raise ClassificationError(
                f"invoice catalogue has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _INVOICE_CATALOGUE_VERSION:
            from ...adapters.persistence.storage.errors import EnvelopeVersionError

            raise EnvelopeVersionError(
                f"invoice catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_INVOICE_CATALOGUE_VERSION}",
            )
        return envelope.payload

    def save(self, catalogue: InvoiceCatalogue) -> None:
        """Persist ``catalogue`` atomically under the file lock.

        The on-disk database value is an encrypted BLOB at the
        :attr:`~aeat.core.classification.SensitivityClass.FINANCIAL`
        classification. No plaintext invoice row lands on disk.

        Args:
            catalogue: The :class:`InvoiceCatalogue` to persist.
        """
        from ...adapters.persistence.storage import (
            Envelope,
            SensitivityClass,
        )

        envelope = Envelope[InvoiceCatalogue](
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.debug("saved invoice catalogue (%d invoices)", len(catalogue.invoices))

    def to_secure_object_write(self, catalogue: InvoiceCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` upsert for ``catalogue`` without committing it.

        Args:
            catalogue: The :class:`InvoiceCatalogue` to serialise.
        """
        from ...adapters.persistence.storage import Envelope, SecureObjectWrite, SensitivityClass

        envelope = Envelope[InvoiceCatalogue](
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        return SecureObjectWrite(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


__all__ = [
    "InvoiceCatalogueRepository",
]
