"""Governed-persistence repository for the transaction catalogue.

The repository is the only sanctioned read/write path for the
transaction catalogue. It stores the catalogue as an encrypted byte
object in the primary SQL backend at FINANCIAL sensitivity; no
plaintext transaction row, JSON catalogue, or envelope file lands on
disk.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...adapters.persistence.storage.envelope._envelope import Envelope
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository, SecureObjectWrite
from ...core.classification import SensitivityClass
from ...core.identity import BucketId
from ...core.logging import get_logger
from ._errors import LedgerStorageError, StoredTransactionDriftError
from ._models import BucketTransactionRef, TransactionCatalogue

_log = get_logger(__name__)

_TX_CATALOGUE_VERSION = 1
TX_BUCKET_NAMESPACE = "aeat.domain.transactions.bucket"


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""

    from ...adapters.persistence.storage import inspect_bucket_storage_runtime
    from ...core.config import load_settings

    return inspect_bucket_storage_runtime(bucket_id, load_settings()).secure_object_repository()


def transaction_catalogue_object_key(bucket_id: str) -> str:
    """Return the secure object key for one profile bucket's transaction catalogue.

    The catalogue is per profile bucket: every read and write resolves
    through the active profile bucket's id. Cross-bucket aggregation
    must qualify with ``(bucket_id, tx_id)``; ``tx_id`` alone is unique
    only within one bucket.
    """

    trimmed = bucket_id.strip()
    if not trimmed:
        raise LedgerStorageError(
            "bucket_id must not be blank",
            context={"repository": "transaction_catalogue", "operation": "object_key"},
        )
    return f"transaction-catalogue:{trimmed}"


class ImportSummary(BaseModel):
    """Frozen summary of one ledger import persistence operation.

    Attributes:
        imported: Number of new transactions persisted by this call.
        skipped: Number of input rows already present in the catalogue.
            A row is a duplicate when its stable import fingerprint
            (:func:`derive_import_fingerprint`) is already present —
            the fingerprint is stamped at import and survives both
            later edits and a re-export in a different file format.
        errors: Reserved for future per-row error counts; today the
            repository raises on any error rather than tallying.
        likely_duplicate_refs: Rows that were imported but share an
            effective date and amount with an existing transaction
            while carrying a divergent narrative — a probable, but
            not confident, cross-format duplicate. The operator is
            warned so they can review rather than discovering a silent
            double-count later.
        catalogue_path: Logical URI of the encrypted database object.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    bucket_id: BucketId
    imported_refs: tuple[BucketTransactionRef, ...] = ()
    skipped_refs: tuple[BucketTransactionRef, ...] = ()
    likely_duplicate_refs: tuple[BucketTransactionRef, ...] = ()
    catalogue_path: str


class TransactionCatalogueRepository:
    """Repository over the encrypted SQL-backed transaction catalogue.

    Every instance is bound to one profile bucket via ``bucket_id``.
    All reads and writes operate on the per-bucket secure object
    ``transaction-catalogue:{bucket_id}`` inside the
    ``aeat.domain.transactions.bucket`` namespace, so two operator
    profiles never share transaction storage.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._object_key = transaction_catalogue_object_key(bucket_id)
        self._bucket_id = bucket_id.strip()
        self._objects = objects or _secure_objects_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket id this repository is bound to."""

        return self._bucket_id

    def exists(self) -> bool:
        """Return whether this bucket's transaction catalogue has been persisted."""

        return self._objects.exists(TX_BUCKET_NAMESPACE, self._object_key)

    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Raises:
            ClassificationError: If the persisted object's class is not
                FINANCIAL.
            EnvelopeVersionError: If the persisted object's schema version is
                higher than the consumer supports.
        """
        record = self._objects.load(
            TX_BUCKET_NAMESPACE,
            self._object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        if record is None:
            _log.debug(
                "transaction catalogue not found; returning empty catalogue bucket_id=%s object_key=%s",
                self._bucket_id,
                self._object_key,
            )
            return TransactionCatalogue()
        try:
            envelope = Envelope[TransactionCatalogue].model_validate_json(record.payload.decode("utf-8"))
        except (ClassificationError, EnvelopeVersionError):
            _log.error("transaction catalogue integrity error", exc_info=True)
            raise
        except ValidationError as exc:
            # Wave-3 audit W09.P41.S214: pydantic ValidationError previously
            # propagated raw and lost the typed drift signal at the CLI
            # boundary. Mirror the StoredProfileDriftError pattern so the
            # CLI can route stored-data-validation failures to the repair-
            # oriented surface instead of a generic refusal.
            _log.error(
                "transaction catalogue schema drift bucket_id=%s object_key=%s",
                self._bucket_id,
                self._object_key,
                exc_info=True,
            )
            raise StoredTransactionDriftError(self._bucket_id, exc) from exc
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"transaction catalogue has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _TX_CATALOGUE_VERSION:
            raise EnvelopeVersionError(
                f"transaction catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_TX_CATALOGUE_VERSION}",
            )
        catalogue = envelope.payload
        _log.debug(
            "loaded transaction catalogue bucket_id=%s object_key=%s entries=%d",
            self._bucket_id,
            self._object_key,
            len(catalogue.transactions),
        )
        return catalogue

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` in the encrypted database object store.

        The on-disk database value is an encrypted BLOB at FINANCIAL
        class. No plaintext transaction row lands on disk.
        """
        self._objects.save_many((self.to_secure_object_write(catalogue),))
        _log.info(
            "saved transaction catalogue bucket_id=%s object_key=%s entries=%d",
            self._bucket_id,
            self._object_key,
            len(catalogue.transactions),
        )

    def to_secure_object_write(self, catalogue: TransactionCatalogue) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it."""

        envelope = Envelope[TransactionCatalogue](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        return SecureObjectWrite(
            namespace=TX_BUCKET_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work."""

        self._objects.save_many((self.to_secure_object_write(catalogue), *extra_writes))
        _log.info(
            "saved transaction catalogue bucket_id=%s object_key=%s entries=%d extra_writes=%d",
            self._bucket_id,
            self._object_key,
            len(catalogue.transactions),
            len(extra_writes),
        )


__all__ = [
    "TX_BUCKET_NAMESPACE",
    "ClassificationError",
    "EnvelopeVersionError",
    "ImportSummary",
    "TransactionCatalogueRepository",
    "transaction_catalogue_object_key",
]
