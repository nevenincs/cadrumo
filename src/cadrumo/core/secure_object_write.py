"""Boundary DTO for one prepared secure-object upsert.

:class:`SecureObjectWrite` is the persistence-boundary contract between a domain
repository port — which declares ``to_secure_object_write(...) -> SecureObjectWrite``
in :mod:`~domain.modelos` — and the storage adapter that persists it. It is a
pure value object depending only on :mod:`~core`
(:data:`~core.STRICT_FROZEN_CONFIG`,
:class:`~core.classification.SensitivityClass`), so a domain port can name it
in a method signature without importing the ``cadrumo.adapters`` layer. The storage
adapter (:mod:`~adapters.persistence.storage`) re-exports it unchanged.

See Also:
    :class:`~core.SecureObjectWrite`
        Public core facade export for this DTO.
    :class:`~core.classification.SensitivityClass`
        Classification carried by every prepared secure-object write.
    :class:`~CalculationRevisionCatalogueRepositoryProtocol`
        Domain repository port that can prepare a calculation catalogue write
        without importing adapters.
    :class:`~ModeloRecordCatalogueRepositoryProtocol`
        Domain repository port that can co-write filing records through the same
        DTO.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Storage adapter that consumes these prepared writes.
    :meth:`~adapters.persistence.storage.SecureObjectRepository.save_many`
        Unit-of-work API that persists one or more prepared writes atomically.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ._hex import Hex64Str
from .models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .classification import SensitivityClass

DEFAULT_WRITE_PROVENANCE = "secure-object-repository"
ABSENT_SECURE_OBJECT_REVISION_ID = "0" * 64
"""CAS sentinel requiring that the addressed secure-object row is absent."""


class SecureObjectWrite(BaseModel):
    """One encrypted secure-object upsert prepared for a unit of work.

    ``written_at`` must be a UTC-aware instant. That contract is enforced at
    the storage write funnel rather than declared here as
    :data:`~core.time.UtcInstant`: this DTO is imported during ``core``
    package initialisation, and reaching ``core.time`` from here loads
    ``core.config`` through the clock's logger and closes an import cycle.
    The funnel is the honest single owner in any case -- the constraint is a
    storage-substrate fact, not a property of the value. The stored row's
    revision id hashes the instant, and SQLite drops ``tzinfo`` on write, so
    an offset-bearing value is persisted as its local wall clock while its
    revision was derived from the UTC instant: the row commits and then fails
    its own read-time self-consistency gate permanently.

    See Also:
        :meth:`~adapters.persistence.storage.SecureObjectRepository.save`
            Direct write boundary carrying the same UTC-aware contract.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes = Field(min_length=1)
    write_provenance: str = Field(default=DEFAULT_WRITE_PROVENANCE, min_length=1, max_length=255)
    source_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    expected_revision_id: Hex64Str | None = None


__all__ = [
    "ABSENT_SECURE_OBJECT_REVISION_ID",
    "DEFAULT_WRITE_PROVENANCE",
    "SecureObjectWrite",
]
