"""Application-owned persistence port for live verification observations.

The verify use case needs only bucket-scoped observation reads and writes. The
outer composition supplies the implementation that encrypts, envelopes, and
indexes those observations; none of those storage details belong in this
module or in :mod:`cadrumo.application.live.verify`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .verify import VerifyObservation


class VerifyObservationPersistencePort(Protocol):
    """Persist and retrieve application-level verify observations by bucket.

    Implementations own storage encryption, envelope/schema validation,
    namespace selection, natural-key addressing, and translation of backend
    failures into the application's error vocabulary. The port deliberately
    exposes no storage record, envelope, namespace, SQL, or crypto type.
    """

    def load(
        self,
        *,
        bucket_id: str,
        observation_id: str,
    ) -> VerifyObservation | None:
        """Return one observation by its full content id, or ``None`` when absent."""
        ...

    def list_observations(
        self,
        *,
        bucket_id: str,
    ) -> tuple[VerifyObservation, ...]:
        """Return every observation in ``bucket_id`` in deterministic capture order."""
        ...

    def save(self, observation: VerifyObservation) -> None:
        """Persist one observation under its application-owned bucket and id."""
        ...


__all__ = ["VerifyObservationPersistencePort"]
