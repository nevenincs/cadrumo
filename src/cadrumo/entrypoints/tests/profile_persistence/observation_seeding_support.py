"""Persist one revision-stamped registry observation through its repository."""

from __future__ import annotations

from datetime import datetime

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import revision_id_for_observation


def save_stamped_observation(
    repository: CalculationObservationRepository,
    observation: RegistryModeloObservation,
    *,
    source_kind: str,
    captured_at: datetime | None = None,
) -> None:
    """Save ``observation`` stamped with the canonical revision of its own coordinates."""
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=source_kind,
            captured_at=captured_at,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )
