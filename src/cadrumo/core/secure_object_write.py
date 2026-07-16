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
    :class:`~domain.modelos.CalculationRevisionCatalogueRepositoryProtocol`
        Domain repository port that can prepare a calculation catalogue write
        without importing adapters.
    :class:`~domain.modelos.ModeloRecordCatalogueRepositoryProtocol`
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

from ._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .classification import SensitivityClass

DEFAULT_WRITE_PROVENANCE = "secure-object-repository"
ABSENT_SECURE_OBJECT_REVISION_ID = "0" * 64
"""CAS sentinel requiring that the addressed secure-object row is absent."""


class SecureObjectWrite(BaseModel):
    """One encrypted secure-object upsert prepared for a unit of work."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes = Field(min_length=1)
    write_provenance: str = Field(default=DEFAULT_WRITE_PROVENANCE, min_length=1, max_length=255)
    source_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    expected_revision_id: str | None = Field(default=None, min_length=64, max_length=64)


__all__ = [
    "ABSENT_SECURE_OBJECT_REVISION_ID",
    "DEFAULT_WRITE_PROVENANCE",
    "SecureObjectWrite",
]
