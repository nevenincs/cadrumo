"""Governed-persistence repository for the invoice catalogue.

:class:`InvoiceCatalogueRepository` is the sanctioned read/write path for the
:class:`~domain.invoices.InvoiceCatalogue`. It stores the catalogue as an
encrypted byte object via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass` using
an :class:`~adapters.persistence.storage.Envelope` wrapper; no plaintext
invoice row, JSON catalogue, or envelope file lands on disk. The
Envelope-wrapping mechanic itself is owned by
:class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
(``_secure_enveloped_document.py``); this class retains only the invoice
bucket-ownership guard, which the shared kernel has no domain knowledge of.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol`. It lives in
the persistence adapter (not in :mod:`domain.invoices`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`~domain.invoices.InvoiceCatalogue` model, its narrow port,
and the :class:`~domain.invoices.InvoicePersistenceError` boundary error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ....core.logging import get_logger
from ....domain.invoices.errors import InvoicePersistenceError
from ....domain.invoices.models import InvoiceCatalogue
from ..storage._secure_object_namespaces import INVOICE_CATALOGUE_NAMESPACE
from ._secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:
    from ..storage.sql import SecureObjectRepository, SecureObjectWrite

_log = get_logger(__name__)

_INVOICE_CATALOGUE_VERSION = INVOICE_CATALOGUE_NAMESPACE.schema_version
_INVOICE_CATALOGUE_SENSITIVITY = INVOICE_CATALOGUE_NAMESPACE.sensitivity
_INVOICE_NAMESPACE = INVOICE_CATALOGUE_NAMESPACE.namespace
_INVOICE_OBJECT_KEY = INVOICE_CATALOGUE_NAMESPACE.require_default_object_key()


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ....core.config import load_settings
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id, load_settings())


def _resolve_invoice_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit or active profile bucket id for the invoice catalogue."""
    from ....core.bucket_pointer import resolve_repository_bucket_id

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
    :class:`~domain.invoices.InvoiceCatalogueRepositoryProtocol`, composing
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the shared envelope/exists/load/save mechanic and retaining only the
    invoice-specific bucket-ownership guard.
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
        else:
            self._bucket_id = _resolve_invoice_bucket_id(bucket_id)
            self._objects = _secure_objects_for_bucket(self._bucket_id)
        self._storage = ProfileEnvelopedModelSecurePersistence(
            objects=self._objects,
            definition=INVOICE_CATALOGUE_NAMESPACE,
            model_type=InvoiceCatalogue,
            empty_document=InvoiceCatalogue,
        )

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether an invoice catalogue has been persisted."""
        return self._storage.exists()

    def _assert_catalogue_bucket(self, catalogue: InvoiceCatalogue, *, direction: str) -> None:
        """Refuse a catalogue carrying an invoice attributed to another bucket.

        The repository is opened against ONE bucket's encrypted store, so an
        invoice naming a different bucket is a foreign row: reading it surfaces
        another profile's invoice as this profile's, and writing it stamps that
        profile's identity into this database. Neither read nor write checked,
        even though the sibling purchase-invoice and business-operation stores
        do, so the rich invoice catalogue was the one invoice surface where a
        foreign row passed silently.

        Applied on both directions through one helper: a check on only one of
        them leaves the other as the way in.

        ``bucket_id is None`` is UNATTRIBUTED, not foreign, and is allowed.
        Only a populated, mismatching bucket is refused. A repository
        constructed with an injected store and no resolved bucket has nothing
        to compare against and checks nothing.

        That tolerance is deliberate but it is NOT evidence that unattributed
        invoices are ordinary. An earlier form of this docstring justified the
        allowance by asserting that most invoices carry no bucket at all, and
        the writers refute it: ``create_catalogue_invoice`` types ``bucket_id``
        as a required ``str``, and each of its production callers -- the CLI
        create verb, the evidence confirm boundary, the guided wizard and the
        bulk importer -- resolves one before calling. No production path
        persists an unattributed invoice. The allowance covers injected-store
        test seams and keeps a legitimately-unattributed record readable rather
        than stranding it; it does not describe the normal case, and a reader
        must not conclude from it that leaving the bucket unset is
        unremarkable.

        Raises:
            InvoicePersistenceError: An invoice names a bucket other than the
                one this repository is bound to.
        """
        bound = self._bucket_id
        if bound is None:
            return
        foreign = sorted(
            {
                str(invoice.bucket_id)
                for invoice in catalogue.invoices.values()
                if invoice.bucket_id is not None and str(invoice.bucket_id) != bound
            },
        )
        if foreign:
            raise InvoicePersistenceError(
                f"invoice catalogue {direction} bucket {bound!r} carries invoices "
                f"attributed to {', '.join(repr(value) for value in foreign)}",
                context={"bucket_id": bound, "foreign_bucket_ids": ",".join(foreign), "direction": direction},
            )

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
        catalogue = self._storage.load()
        self._assert_catalogue_bucket(catalogue, direction="read from")
        return catalogue

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
        self._assert_catalogue_bucket(catalogue, direction="saved through")
        self._storage.save(catalogue)
        _log.debug("saved invoice catalogue (%d invoices)", len(catalogue.invoices))

    def mutate(self, mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue]) -> InvoiceCatalogue:
        """Apply ``mutation`` to the stored catalogue as one guarded unit of work.

        The catalogue is a SINGLETON row, so adding one invoice is really
        read-whole-catalogue, rebuild, write whole catalogue. Two operators
        adding DIFFERENT invoices at once both read the same catalogue and the
        later write discards the earlier invoice -- silently, because the
        duplicate-identity check never sees the other invoice. A dropped
        invoice under-declares, which is the failure this repository exists to
        make impossible.

        The bucket-ownership guard runs on the mutation's OWN result rather
        than once before it, so a mutation that introduces a foreign invoice is
        refused on every attempt instead of only the first.

        Args:
            mutation: Builds the next catalogue from the current one. Raising
                refuses the whole mutation, unretried.

        Returns:
            The catalogue as written.
        """

        def _guarded(current: InvoiceCatalogue) -> InvoiceCatalogue:
            self._assert_catalogue_bucket(current, direction="read from")
            updated = mutation(current)
            self._assert_catalogue_bucket(updated, direction="saved through")
            return updated

        catalogue = self._storage.mutate(_guarded)
        _log.debug("mutated invoice catalogue (%d invoices)", len(catalogue.invoices))
        return catalogue

    def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
        """Return the catalogue and the revision id it was read at.

        The read a guarded co-commit needs. Linking and reconciliation both
        write this catalogue inside a batch with the transaction store, so
        neither can use the self-committing :meth:`mutate`; without the revision
        the batch rewrites the whole singleton row and drops an invoice another
        caller added in between.
        """
        return self._storage.load_revisioned()

    def to_secure_object_write(
        self,
        catalogue: InvoiceCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned :class:`~adapters.persistence.storage.SecureObjectWrite`
        carries the same :class:`~adapters.persistence.storage.Envelope`
        and :class:`~adapters.persistence.storage.SensitivityClass`
        classification that :meth:`save` would persist directly.

        Args:
            catalogue: The :class:`InvoiceCatalogue` to serialise.
            expected_revision_id: The revision :meth:`load_revisioned` reported
                for the catalogue this one was derived from. This is a SINGLETON
                row, so without it the write lands over any invoice another
                caller committed since the read, and a dropped invoice
                under-declares.
        """
        # The co-commit path is a WRITE like save(); leaving it unchecked would
        # leave the transaction/event route as the way a foreign row still gets in.
        self._assert_catalogue_bucket(catalogue, direction="saved through")
        return self._storage.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


__all__ = [
    "InvoiceCatalogueRepository",
]
