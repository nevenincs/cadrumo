"""Shared observation lookup for the multi-year-renta E2E fidelity tests."""

from __future__ import annotations

from datetime import datetime

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.application.calculations.observations_repository import ObservationEnvelopePayload
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.period_selector_match import selector_period_matches_request
from cadrumo.domain.calculations.registry.tests.registry_observations import revision_id_for_observation


def find_observation(
    repo: CalculationObservationRepository,
    modelo: str,
    *,
    filing_year: int,
    period: str,
) -> ObservationEnvelopePayload | None:
    """Scan ``iter_modelo`` and return the envelope matching (filing_year, period) or None.

    The production retrieval path: ``iter_modelo`` performs a full-scan over the
    namespace, decrypting and filtering in Python. Tests use that public
    repository surface instead of depending on its storage-key representation.
    """
    for payload in repo.iter_modelo(modelo):
        obs = payload.observation
        # Compare the way the domain does: an administrative coordinate such
        # as a censal alta normalises on the way in, so a raw == against the
        # registry's own lowercase declaration would never match.
        if obs.filing_year == filing_year and selector_period_matches_request(obs.period, period):
            return payload
    return None


def save_app_filing_observation(
    repo: CalculationObservationRepository,
    observation: RegistryModeloObservation,
    *,
    captured_at: datetime,
) -> None:
    """Persist ``observation`` as an application filing stamped with its own revision id."""
    repo.save(
        repo.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=captured_at,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )
