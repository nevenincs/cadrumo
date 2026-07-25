"""Governed-persistence repository for the invoice catalogue.

:class:`InvoiceCatalogueRepository` is the sanctioned read/write path for the
:class:`~domain.invoices.InvoiceCatalogue`. It stores the catalogue as an
encrypted byte object via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass` using
an :class:`~adapters.persistence.storage.Envelope` wrapper; no plaintext
invoice row, JSON catalogue, or envelope file lands on disk.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol`. It lives in
the persistence adapter (not in :mod:`domain.invoices`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`~domain.invoices.InvoiceCatalogue` model, its narrow port,
and the :class:`~domain.invoices.InvoicePersistenceError` boundary error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.invoices import InvoiceCatalogue, InvoicePersistenceError
from ..storage import INVOICE_CATALOGUE_NAMESPACE

if TYPE_CHECKING:
    from ..storage import SecureObjectRepository, SecureObjectWrite

_log = get_logger(__name__)

_INVOICE_CATALOGUE_VERSION = INVOICE_CATALOGUE_NAMESPACE.schema_version
_INVOICE_CATALOGUE_SENSITIVITY = INVOICE_CATALOGUE_NAMESPACE.sensitivity
_INVOICE_NAMESPACE = INVOICE_CATALOGUE_NAMESPACE.namespace
_INVOICE_OBJECT_KEY = INVOICE_CATALOGUE_NAMESPACE.require_default_object_key()


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ....core.config import load_settings
    from ..storage import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id, load_settings())


def _resolve_invoice_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit or active profile bucket id for the invoice catalogue."""
    from ....core import resolve_repository_bucket_id

    return resolve_repository_bucket_id(bucket_id, error_type=InvoicePersistenceError)


class InvoiceCatalogueRepository:
    """Repository over encrypted SQL-backed :class:`InvoiceCatalogue` storage.

    :data:`adapters.persistence.storage.INVOICE_CATALOGUE_NAMESPACE` is
    the central profile-local namespace, schema-version, sensitivity, and
    singleton-key contract for the encrypted invoice catalogue row. The
    :class:`InvoiceCatalogue` payload is wrapped in
    :class:`~adapters.persistence.storage.Envelope` before
    :class:`~adapters.persistence.storage.SecureObjectRepository`
    persists it, and :meth:`to_secure_object_write` exposes the same write for
    transaction/event co-commit paths. This class exposes the concrete load/save
    implementation behind
    :class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol`.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind to a profile bucket's secure-object store, or an injected one.

        Args:
            bucket_id: Profile bucket whose encrypted store backs this repository;
                resolved from the active session when ``None``.
            objects: Optional injected secure-object repository (testing seam).
        """
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
            :class:`~adapters.persistence.storage.ClassificationError`:
                If the persisted object's classification is not
                ``_INVOICE_CATALOGUE_SENSITIVITY``.
            :class:`~adapters.persistence.storage.EnvelopeVersionError`:
                If the envelope schema version is higher than the consumer
                supports.
        """
        from ..storage import Envelope

        record = self._objects.load(
            _INVOICE_NAMESPACE,
            _INVOICE_OBJECT_KEY,
            expected_class=_INVOICE_CATALOGUE_SENSITIVITY,
            max_supported_version=_INVOICE_CATALOGUE_VERSION,
        )
        if record is None:
            _log.debug("no invoice catalogue in database, returning empty")
            return InvoiceCatalogue()
        envelope = Envelope[InvoiceCatalogue].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        if envelope.classification is not _INVOICE_CATALOGUE_SENSITIVITY:
            from ..storage import ClassificationError

            raise ClassificationError(
                f"invoice catalogue has classification {envelope.classification}; "
                f"consumer expected {_INVOICE_CATALOGUE_SENSITIVITY}",
            )
        if envelope.schema_version > _INVOICE_CATALOGUE_VERSION:
            from ..storage import EnvelopeVersionError

            raise EnvelopeVersionError(
                f"invoice catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_INVOICE_CATALOGUE_VERSION}",
            )
        return envelope.payload

    def save(self, catalogue: InvoiceCatalogue) -> None:
        """Persist ``catalogue`` atomically under the file lock.

        The on-disk database value is an encrypted
        :class:`~adapters.persistence.storage.Envelope` BLOB at the
        :class:`~adapters.persistence.storage.SensitivityClass`
        ``FINANCIAL`` classification declared by
        :data:`adapters.persistence.storage.INVOICE_CATALOGUE_NAMESPACE`.
        No plaintext invoice row lands on disk.

        Args:
            catalogue: The :class:`InvoiceCatalogue` to persist.
        """
        from ..storage import Envelope

        envelope = Envelope[InvoiceCatalogue](
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=now(),
            classification=_INVOICE_CATALOGUE_SENSITIVITY,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=_INVOICE_CATALOGUE_SENSITIVITY,
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )
        _log.debug("saved invoice catalogue (%d invoices)", len(catalogue.invoices))

    def to_secure_object_write(self, catalogue: InvoiceCatalogue) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned :class:`~adapters.persistence.storage.SecureObjectWrite`
        carries the same :class:`~adapters.persistence.storage.Envelope`
        and :class:`~adapters.persistence.storage.SensitivityClass`
        classification that :meth:`save` would persist directly.

        Args:
            catalogue: The :class:`InvoiceCatalogue` to serialise.
        """
        from ..storage import Envelope, SecureObjectWrite

        envelope = Envelope[InvoiceCatalogue](
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=now(),
            classification=_INVOICE_CATALOGUE_SENSITIVITY,
            payload=catalogue,
        )
        return SecureObjectWrite(
            namespace=_INVOICE_NAMESPACE,
            object_key=_INVOICE_OBJECT_KEY,
            classification=_INVOICE_CATALOGUE_SENSITIVITY,
            schema_version=_INVOICE_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )


__all__ = [
    "InvoiceCatalogueRepository",
]
