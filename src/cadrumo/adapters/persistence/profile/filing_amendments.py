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
from ....core.time import now
from ....domain.filing import (
    BaseAmendment,
    ModeloComplementaria,
    ModeloSustitutiva,
)
from ..storage import FILING_AMENDMENTS_NAMESPACE
from ._filing_runtime import resolve_filing_repository_bucket_id, secure_objects_for_filing_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository

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
        self._objects = secure_objects_for_filing_bucket(self._bucket_id)

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
        from ..storage import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        return self.store_dir / amendment_id

    def lock_target_for(self, amendment_id: str) -> Path:
        """Return a logical lock marker; SQL transactions govern writes."""
        from ..storage import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        return self.store_dir / f"{amendment_id}.lock"

    def load(self, amendment_id: str) -> ModeloAmendment | None:
        """Return the persisted amendment or ``None`` if absent."""
        from ..storage import (
            ClassificationError,
            Envelope,
            EnvelopeVersionError,
            safe_repository_id,
        )

        safe_repository_id(amendment_id, context="amendment_id")
        record = self._objects.load(
            _AMENDMENT_NAMESPACE,
            amendment_id,
            expected_class=_AMENDMENT_SENSITIVITY,
            max_supported_version=_AMENDMENT_ENVELOPE_VERSION,
        )
        if record is None:
            return None
        envelope = Envelope[ModeloAmendment].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not _AMENDMENT_SENSITIVITY:
            raise ClassificationError(
                f"filing amendment {amendment_id} has classification {envelope.classification}; "
                f"consumer expected {_AMENDMENT_SENSITIVITY}",
            )
        if envelope.schema_version > _AMENDMENT_ENVELOPE_VERSION:
            raise EnvelopeVersionError(
                f"filing amendment {amendment_id} is at version {envelope.schema_version}; "
                f"consumer supports up to {_AMENDMENT_ENVELOPE_VERSION}",
            )
        return envelope.payload

    def save(self, amendment: BaseAmendment) -> None:
        """Persist ``amendment`` in the encrypted database object store.

        The row is stored under
        :data:`adapters.persistence.storage.FILING_AMENDMENTS_NAMESPACE`.
        """
        from ..storage import Envelope, safe_repository_id

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
        from ..storage import safe_repository_id

        safe_repository_id(amendment_id, context="amendment_id")
        deleted = self._objects.delete(_AMENDMENT_NAMESPACE, amendment_id)
        if deleted:
            _log.debug("deleted filing amendment %s", amendment_id)
        return deleted

    def list_amendment_ids(self) -> tuple[str, ...]:
        """Return every amendment id persisted in this repository."""
        from ..storage import Envelope

        ids: list[str] = []
        for record in self._objects.list_records(
            _AMENDMENT_NAMESPACE,
            expected_class=_AMENDMENT_SENSITIVITY,
            max_supported_version=_AMENDMENT_ENVELOPE_VERSION,
        ):
            envelope = Envelope[ModeloAmendment].model_validate_json(record.payload.decode("utf-8"))
            ids.append(envelope.payload.amendment_id)
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
