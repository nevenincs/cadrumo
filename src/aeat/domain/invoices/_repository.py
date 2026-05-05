"""Governed-persistence repository for the invoice catalogue.

The repository is the only sanctioned read/write path for the invoice
catalogue. It stores the catalogue as an encrypted byte object in the
primary SQL backend at FINANCIAL sensitivity; no plaintext invoice row,
JSON catalogue, or envelope file lands on disk.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ...core.logging import get_logger
from ._models import InvoiceCatalogue

_log = get_logger(__name__)

_INVOICE_CATALOGUE_VERSION = 1
_INVOICE_NAMESPACE = "aeat.domain.invoices"
_INVOICE_OBJECT_KEY = "catalogue"


class InvoiceCatalogueRepository:
    """Repository over the encrypted SQL-backed invoice catalogue."""

    def __init__(self) -> None:
        from ...adapters.persistence.storage.sql import SecureObjectRepository

        self._objects = SecureObjectRepository()

    def exists(self) -> bool:
        """Return whether an invoice catalogue has been persisted."""

        return self._objects.exists(_INVOICE_NAMESPACE, _INVOICE_OBJECT_KEY)

    def load(self) -> InvoiceCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The deserialised :class:`InvoiceCatalogue`, or a fresh empty
            instance when no database object is present.

        Raises:
            :exc:`aeat.adapters.persistence.storage.errors.ClassificationError`:
                If the persisted object's classification is not
                :attr:`~aeat.adapters.persistence.storage.SensitivityClass.FINANCIAL`.
            :exc:`aeat.adapters.persistence.storage.errors.EnvelopeVersionError`:
                If the envelope schema version is higher than the
                consumer supports.
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
        :attr:`~aeat.adapters.persistence.storage.SensitivityClass.FINANCIAL`
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
            written_at=datetime.now(UTC),
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


__all__ = [
    "InvoiceCatalogueRepository",
]
