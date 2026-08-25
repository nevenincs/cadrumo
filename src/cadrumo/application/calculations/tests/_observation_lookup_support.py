"""Shared observation lookup for the multi-year-renta E2E fidelity tests."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.period_selector_match import selector_period_matches_request
from .._observations_repository import CalculationObservationRepository, ObservationEnvelopePayload


def find_observation(
    repo: CalculationObservationRepository,
    modelo: str,
    *,
    filing_year: int,
    period: str,
) -> ObservationEnvelopePayload | None:
    """Scan ``iter_modelo`` and return the envelope matching (filing_year, period) or None.

    The production retrieval path: ``iter_modelo`` performs a full-scan over the
    namespace, decrypting and filtering in Python. The SQL ``WHERE object_key = ?``
    path cannot match the stored ciphertext since ``EncryptedString`` uses
    AES-256-GCM with a random nonce.
    """
    for payload in repo.iter_modelo(modelo):
        obs = payload.observation
        # Compare the way the domain does: an administrative coordinate such
        # as a censal alta normalises on the way in, so a raw == against the
        # registry's own lowercase declaration would never match.
        if obs.filing_year == filing_year and selector_period_matches_request(obs.period, period):
            return payload
    return None
