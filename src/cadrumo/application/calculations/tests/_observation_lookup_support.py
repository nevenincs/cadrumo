"""Shared observation lookup for the multi-year-renta E2E fidelity tests."""

from __future__ import annotations

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
        if obs.filing_year == filing_year and obs.period == period:
            return payload
    return None
