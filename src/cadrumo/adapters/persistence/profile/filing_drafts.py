"""Governed-persistence repository for filing drafts.

:class:`~domain.filing.ModeloDraft` records carry exact casilla
arithmetic and tax due values. They are stored as encrypted byte objects via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass` and
serialised through an :class:`~adapters.persistence.storage.Envelope` by
:class:`~adapters.persistence.storage.SecureBoundRepository`; no plaintext
draft JSON or envelope file lands on disk.

This concrete repository is the persistence adapter behind the
:class:`~domain.filing.ModeloDraftRepositoryProtocol` port. It lives in
the persistence adapter (not in :mod:`domain.filing`) because its
:class:`~adapters.persistence.storage.SecureBoundRepository` base is
SQL/crypto-coupled; the domain package owns only the typed
:class:`~domain.filing.ModeloDraft` payload and the narrow read/save
port that domain-facing service code depends on.

See Also:
    :class:`~domain.filing.ModeloDraft`
        Strict filing payload persisted by this repository.
    :class:`~adapters.persistence.storage.SecureBoundRepository`
        Generic encrypted-envelope repository base used for the draft store.
    :data:`adapters.persistence.storage.FILING_DRAFTS_NAMESPACE`
        Namespace, sensitivity, schema-version, object-key, and custody
        contract for draft secure objects.
    :mod:`application.filing`
        Application review flow that reads and updates persisted drafts.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar, override

from ....domain.filing import ModeloDraft
from ..storage import FILING_DRAFTS_NAMESPACE, SecureBoundRepository, SensitivityClass
from ._filing_runtime import resolve_filing_repository_bucket_id, secure_objects_for_filing_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository


class ModeloDraftRepository(SecureBoundRepository[ModeloDraft]):
    """Encrypted FINANCIAL repository for :class:`~domain.filing.ModeloDraft` payloads.

    The :class:`~adapters.persistence.storage.SecureBoundRepository`
    base wraps each draft in an
    :class:`~adapters.persistence.storage.Envelope` and writes it under
    :data:`adapters.persistence.storage.FILING_DRAFTS_NAMESPACE`. The
    draft id is the natural key, so list and iteration APIs expose draft
    aggregates rather than submission or amendment records. The namespace
    definition supplies the ``FINANCIAL``
    :class:`~adapters.persistence.storage.SensitivityClass`, schema
    version, object-key grammar, and custody contract.
    """

    # namespace/sensitivity/schema_version sourced from the sole registry authority
    namespace: ClassVar[str] = FILING_DRAFTS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = FILING_DRAFTS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = FILING_DRAFTS_NAMESPACE.schema_version

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind the repository to a bucket, or to an explicit secure-object store for tests."""
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is None:
            self._bucket_id = resolve_filing_repository_bucket_id(bucket_id)
            objects = secure_objects_for_filing_bucket(self._bucket_id)
        super().__init__(objects=objects)

    @override
    @classmethod
    def payload_model(cls) -> type[ModeloDraft]:
        """Return the :class:`~domain.filing.ModeloDraft` encrypted payload model for filing drafts."""
        return ModeloDraft

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    @override
    def extract_identifier(self, payload: ModeloDraft) -> str:
        return payload.draft_id

    def list_draft_ids(self) -> tuple[str, ...]:
        """Return every draft id persisted in this repository, in lexicographic order."""
        return tuple(sorted(self.iter_ids()))

    def iter_drafts(self) -> Iterator[ModeloDraft]:
        """Yield every persisted :class:`~domain.filing.ModeloDraft`, in lexicographic id order."""
        return iter(sorted(self.iter_records(), key=self.extract_identifier))


__all__ = [
    "ModeloDraftRepository",
]
