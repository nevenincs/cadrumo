"""Boundary DTO for one prepared secure-object upsert.

:class:`SecureObjectWrite` is the persistence-boundary contract between a domain
repository port — which declares ``to_secure_object_write(...) -> SecureObjectWrite``
in :mod:`domain.modelos` — and the storage adapter that persists it. It is a
pure value object depending only on :mod:`core`
(:data:`~core.STRICT_FROZEN_CONFIG`,
:class:`~core.classification.SensitivityClass`), so a domain port can name it
in a method signature without importing the ``aeat.adapters`` layer. The storage
adapter (:mod:`adapters.persistence.storage`) re-exports it unchanged.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .classification import SensitivityClass

DEFAULT_WRITE_PROVENANCE = "secure-object-repository"


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
    "DEFAULT_WRITE_PROVENANCE",
    "SecureObjectWrite",
]
