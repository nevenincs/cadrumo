"""In-memory persistence support for application-owned verify tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..verify import VerifyObservation
from ..verify_ports import VerifyObservationPersistencePort


@dataclass
class InMemoryVerifyObservationPersistence(VerifyObservationPersistencePort):
    """Store application observations by bucket and content id.

    The fake models only the application persistence contract. It deliberately
    has no knowledge of secure-object records, envelopes, namespaces, or
    encryption; those concerns belong to the concrete adapter's tests.
    """

    _observations: dict[tuple[str, str], VerifyObservation] = field(default_factory=dict)

    def load(self, *, bucket_id: str, observation_id: str) -> VerifyObservation | None:
        """Return the observation addressed by its bucket and content id."""
        return self._observations.get((bucket_id, observation_id))

    def list_observations(self, *, bucket_id: str) -> tuple[VerifyObservation, ...]:
        """Return bucket observations in deterministic capture order."""
        observations = [
            observation
            for (stored_bucket_id, _), observation in self._observations.items()
            if stored_bucket_id == bucket_id
        ]
        return tuple(sorted(observations, key=lambda item: (item.checked_at, item.observation_id)))

    def save(self, observation: VerifyObservation) -> None:
        """Store one application observation under its bucket and content id."""
        self._observations[(observation.bucket_id, observation.observation_id)] = observation


__all__ = ["InMemoryVerifyObservationPersistence"]
