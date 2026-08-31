"""Governed-persistence repository for filing amendments.

Filing amendments carry corrected casilla deltas and original
submission references. They are stored as encrypted byte objects via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``AUDIT`` :class:`~adapters.persistence.storage.SensitivityClass`
sensitivity; no plaintext amendment JSON or envelope file lands on disk. Each
record is wrapped in an
:class:`~adapters.persistence.storage.Envelope` before serialisation.

This concrete repository is the persistence adapter behind the
:class:`~domain.filing.ModeloAmendmentRepositoryProtocol` port. It lives
in the persistence adapter (not in :mod:`domain.filing`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`~domain.filing.BaseAmendment` payload shapes.

See Also:
    :class:`~domain.filing.BaseAmendment`
        Shared typed payload shape saved by this repository.
    :class:`~domain.filing.ModeloComplementaria`
        LGT Art. 122.2 amendment variant for additional self-assessment.
    :class:`~domain.filing.ModeloSustitutiva`
        LGT Art. 122.1 amendment variant for full replacement.
    :data:`adapters.persistence.storage.FILING_AMENDMENTS_NAMESPACE`
        Namespace, sensitivity, schema-version, object-key, and custody
        contract for amendment secure objects.
    :func:`application.filing.build_complementaria`
        Application orchestration entry point that can produce and persist an
        amendment.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from ....core.logging import get_logger
from ....core.time.clock import now
from ....domain.filing.amendment import BaseAmendment, ModeloComplementaria, ModeloSustitutiva
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import FILING_AMENDMENTS_NAMESPACE
from ._filing_runtime import resolve_filing_repository_bucket_id

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.sql import SecureObjectRecord, SecureObjectRepository

type ModeloAmendment = ModeloComplementaria | ModeloSustitutiva

_log = get_logger(__name__)

_AMENDMENT_ENVELOPE_VERSION = FILING_AMENDMENTS_NAMESPACE.schema_version
_AMENDMENT_SENSITIVITY = FILING_AMENDMENTS_NAMESPACE.sensitivity
_AMENDMENT_NAMESPACE = FILING_AMENDMENTS_NAMESPACE.namespace


class ModeloAmendmentRepository:
    """Encrypted AUDIT repository for :class:`~domain.filing.BaseAmendment` records.

    Persists :class:`~domain.filing.ModeloComplementaria` and
    :class:`~domain.filing.ModeloSustitutiva` payloads under
    :data:`adapters.persistence.storage.FILING_AMENDMENTS_NAMESPACE`. The
    repository wraps the amendment union in an
    :class:`~adapters.persistence.storage.Envelope` before writing through
    :class:`~adapters.persistence.storage.SecureObjectRepository`; the
    amendment id is the natural key used for load, delete, and ordered
    iteration. The namespace definition supplies the ``AUDIT``
    :class:`~adapters.persistence.storage.SensitivityClass`, schema
    version, object-key grammar, and custody contract.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind the repository to a bucket, or to an explicit secure-object store for tests."""
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is not None:
            self._objects = objects
            return
        self._bucket_id = resolve_filing_repository_bucket_id(bucket_id)
        self._objects = secure_object_repository_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    @property
    def store_dir(self) -> Path:
        """Return a logical backend marker for diagnostic messages."""
        return Path("db://secure_objects") / _AMENDMENT_NAMESPACE

    def envelope_path_for(self, amendment_id: str) -> Path:
        """Return a logical object marker for ``amendment_id``."""
        from ..storage.path_safety import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        return self.store_dir / amendment_id

    def lock_target_for(self, amendment_id: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""
        from ..storage.path_safety import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        return self.store_dir / f"{amendment_id}.lock"

    @staticmethod
    def _verified_amendment(record: SecureObjectRecord) -> ModeloAmendment:
        """Return the row's payload, refusing one filed under another key.

        The amendment id is the object key, so the stored key and the decrypted
        payload are two encodings of one fact and must agree. Nothing compared
        them: a valid amendment B written under A's row key was returned by
        ``load("amend-A")`` as A's amendment, and enumeration reported B twice
        under two ids -- letting a complementaria consumer act on the wrong
        filing amendment.

        The comparison is on the stored digest rather than on the requested
        string so the one check serves both the targeted read and the scan,
        which never sees a natural id at all.

        Raises:
            ClassificationError: The stored envelope is not AUDIT-classified.
            EnvelopeVersionError: The stored envelope is above this consumer's
                supported version.
            SecureObjectRowIdentityError: The payload rebuilds a different
                amendment id than the key it is filed under.
        """
        from ..storage.crypto.encrypted_columns import secure_object_key_digest
        from ..storage.envelope.contract import Envelope
        from ..storage.errors import ClassificationError, EnvelopeVersionError, SecureObjectRowIdentityError
        from ..storage.schema_lineage import (
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )

        envelope = Envelope[ModeloAmendment].model_validate_json(record.payload.decode("utf-8"))
        if not inner_envelope_classification_is_expected(envelope.classification, _AMENDMENT_SENSITIVITY):
            raise ClassificationError(
                f"filing amendment row has classification {envelope.classification}; "
                f"consumer expected {_AMENDMENT_SENSITIVITY}",
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _AMENDMENT_ENVELOPE_VERSION):
            raise EnvelopeVersionError(
                f"filing amendment row is at version {envelope.schema_version}; "
                f"consumer supports up to {_AMENDMENT_ENVELOPE_VERSION}",
            )
        payload = envelope.payload
        if secure_object_key_digest(payload.amendment_id) != record.object_key:
            raise SecureObjectRowIdentityError(
                _AMENDMENT_NAMESPACE,
                expected_identifier=payload.amendment_id,
            )
        return payload

    def load(self, amendment_id: str) -> ModeloAmendment | None:
        """Return the persisted amendment or ``None`` if absent."""
        from ..storage.path_safety import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        record = self._objects.load(
            _AMENDMENT_NAMESPACE,
            amendment_id,
            expected_class=_AMENDMENT_SENSITIVITY,
            max_supported_version=_AMENDMENT_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        return self._verified_amendment(record)

    def save(self, amendment: BaseAmendment) -> None:
        """Persist ``amendment`` in the encrypted database object store.

        The row is stored under
        :data:`adapters.persistence.storage.FILING_AMENDMENTS_NAMESPACE`.
        """
        from ..storage.envelope.contract import Envelope
        from ..storage.path_safety import safe_repository_id

        safe_repository_id(amendment.amendment_id, context="amendment_id")
        envelope = Envelope[BaseAmendment](
            schema_version=_AMENDMENT_ENVELOPE_VERSION,
            written_at=now(),
            classification=_AMENDMENT_SENSITIVITY,
            payload=amendment,
        )
        self._objects.save(
            namespace=_AMENDMENT_NAMESPACE,
            object_key=amendment.amendment_id,
            classification=_AMENDMENT_SENSITIVITY,
            schema_version=_AMENDMENT_ENVELOPE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        kind = getattr(amendment, "amendment_kind", None)
        _log.debug("saved filing amendment %s kind=%s", amendment.amendment_id, kind)

    def delete(self, amendment_id: str) -> bool:
        """Remove the persisted amendment for ``amendment_id``."""
        from ..storage.path_safety import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        deleted = self._objects.delete(_AMENDMENT_NAMESPACE, amendment_id)
        if deleted:
            _log.debug("deleted filing amendment %s", amendment_id)
        return deleted

    def list_amendment_ids(self) -> tuple[str, ...]:
        """Return every amendment id persisted in this repository.

        Each id is read from its payload and confirmed against the key its row
        is filed under, through the one check :meth:`load` uses. Reading ids
        from payloads alone let a duplicated envelope report the same id twice
        while two distinct rows existed.

        Raises:
            SecureObjectRowIdentityError: A row's payload rebuilds a different
                amendment id than the key it is filed under. Raised rather than
                skipped: a caller enumerating amendment history must not be
                handed a quietly shortened set.
        """
        ids: list[str] = []
        for record in self._objects.list_records(
            _AMENDMENT_NAMESPACE,
            expected_class=_AMENDMENT_SENSITIVITY,
            max_supported_version=_AMENDMENT_ENVELOPE_VERSION,
        ):
            ids.append(self._verified_amendment(record).amendment_id)
        return tuple(sorted(ids))

    def iter_amendments(self) -> Iterator[ModeloAmendment]:
        """Yield every persisted amendment, in lexicographic id order."""
        for amendment_id in self.list_amendment_ids():
            payload = self.load(amendment_id)
            if payload is not None:
                yield payload


__all__ = [
    "ModeloAmendmentRepository",
]
