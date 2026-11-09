"""Boundary DTO for one prepared secure-object upsert.

:class:`SecureObjectWrite` is the persistence-boundary contract between a domain
repository port — which declares ``to_secure_object_write(...) -> SecureObjectWrite``
in :mod:`~domain.modelos` — and the storage adapter that persists it. It is a
pure value object depending only on :mod:`~core`
(:data:`~core.models.STRICT_FROZEN_CONFIG`,
:class:`~core.classification.policies.SensitivityClass`), so a domain port can name it
in a method signature without importing the ``cadrumo.adapters`` layer. The storage
adapter (:mod:`~adapters.persistence.storage`) re-exports it unchanged.

See Also:
    :class:`~core.secure_object_write.SecureObjectWrite`
        Public core facade export for this DTO.
    :class:`~core.classification.policies.SensitivityClass`
        Classification carried by every prepared secure-object write.
    :class:`~CalculationRevisionCatalogueRepositoryProtocol`
        Domain repository port that can prepare a calculation catalogue write
        without importing adapters.
    :class:`~ModeloRecordCatalogueRepositoryProtocol`
        Domain repository port that can co-write filing records through the same
        DTO.
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
        Storage adapter that consumes these prepared writes.
    :meth:`~adapters.persistence.storage.sql.secure_object_writes.SecureObjectWriteOperations.save_many`
        Unit-of-work API that persists one or more prepared writes atomically.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .classification.policies import SensitivityClass
from .hex import Hex64Str
from .models import STRICT_FROZEN_CONFIG

DEFAULT_WRITE_PROVENANCE = "secure-object-repository"
ABSENT_SECURE_OBJECT_REVISION_ID = "0" * 64
"""CAS sentinel requiring that the addressed secure-object row is absent."""


class SecureObjectWrite(BaseModel):
    """One encrypted secure-object upsert prepared for a unit of work.

    ``written_at`` must be a UTC-aware instant. That contract is enforced at
    the storage write funnel rather than declared here as
    :data:`~core.time.utc.UtcInstant`: this DTO is imported during ``core``
    package initialisation, and reaching ``core.time`` from here loads
    ``core.config`` through the clock's logger and closes an import cycle.
    The funnel is the honest single owner in any case -- the constraint is a
    storage-substrate fact, not a property of the value. The stored row's
    revision id hashes the instant, and SQLite drops ``tzinfo`` on write, so
    an offset-bearing value is persisted as its local wall clock while its
    revision was derived from the UTC instant: the row commits and then fails
    its own read-time self-consistency gate permanently.

    See Also:
        :meth:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository.save`
            Direct write boundary carrying the same UTC-aware contract.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes = Field(min_length=1)
    write_provenance: str = Field(default=DEFAULT_WRITE_PROVENANCE, min_length=1, max_length=255)
    source_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    expected_revision_id: Hex64Str | None = None


class SecureObjectRevisionAssertion(BaseModel):
    """Read-only source revision required by a derived-data write transaction.

    The storage batch checks each assertion inside the transaction that commits
    its writes, so the batch commits only while the asserted row still holds
    exactly this revision, or is still absent when ``expected_revision_id`` is
    :data:`ABSENT_SECURE_OBJECT_REVISION_ID`. The asserted row is never written.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    expected_revision_id: Hex64Str


class SecureObjectWriteUnit(BaseModel):
    """Writes and source assertions that one repository needs committed in a single batch.

    A repository whose record is stored across several rows returns this
    instead of a single :class:`SecureObjectWrite`. A caller composing it into
    another repository's batch carries every write and every assertion into
    that same transaction; committing the writes without the assertions would
    let the record commit while a row it depends on is missing.
    """

    model_config = STRICT_FROZEN_CONFIG

    writes: tuple[SecureObjectWrite, ...] = Field(min_length=1)
    assertions: tuple[SecureObjectRevisionAssertion, ...] = ()


__all__ = [
    "ABSENT_SECURE_OBJECT_REVISION_ID",
    "DEFAULT_WRITE_PROVENANCE",
    "SecureObjectRevisionAssertion",
    "SecureObjectWrite",
    "SecureObjectWriteUnit",
]
