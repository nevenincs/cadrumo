"""Governed-persistence repository for filing drafts.

:class:`ModeloDraft` records carry exact casilla arithmetic and tax due
values. They are stored as encrypted byte objects via
:class:`SecureObjectRepository` at :class:`SensitivityClass` FINANCIAL;
no plaintext draft JSON or envelope file lands on disk.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar, override

from ...adapters.persistence.storage import SecureBoundRepository, SensitivityClass
from ._runtime_repository import resolve_filing_repository_bucket_id, secure_objects_for_filing_bucket
from ._schema import ModeloDraft

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository


class ModeloDraftRepository(SecureBoundRepository[ModeloDraft]):
    """Repository over encrypted SQL-backed filing drafts."""

    namespace: ClassVar[str] = "aeat.domain.filing.drafts"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.FINANCIAL
    schema_version: ClassVar[int] = 1

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is None:
            self._bucket_id = resolve_filing_repository_bucket_id(bucket_id)
            objects = secure_objects_for_filing_bucket(self._bucket_id)
        super().__init__(objects=objects)

    @override
    @classmethod
    def payload_model(cls) -> type[ModeloDraft]:
        """Return the :class:`ModeloDraft` encrypted payload model for filing drafts."""
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
        """Yield every persisted :class:`ModeloDraft`, in lexicographic id order."""
        return iter(sorted(self.iter_records(), key=self.extract_identifier))


__all__ = [
    "ModeloDraftRepository",
]
