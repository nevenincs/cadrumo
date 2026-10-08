"""Finite fixture authoring over real typed and atomic storage kernels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from .....core.aggregation import AggregationCaptureKind
from .....core.period import Period
from .....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ..percepciones_observations import PercepcionObservationRepositoryAdapter, _translate_storage_failure
from .observation_window_authoring import replace_observation_window


def save_percepcion_observation(
    self: object,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observation: WithholdingObservation,
    source_kind: AggregationCaptureKind,
    captured_at: datetime | None = None,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Persist one per-perceptor-clave observation."""
    if not isinstance(self, PercepcionObservationRepositoryAdapter):
        raise TypeError("fixture requires the percepcion persistence adapter")
    _translate_storage_failure(
        "percepcion_save_observation",
        lambda: self.save(
            self.build_observation_payload(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                observation=observation,
                source_kind=source_kind,
                captured_at=captured_at,
                source_metadata=source_metadata,
            )
        ),
    )


def replace_percepcion_observations(
    self: object,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[WithholdingObservation],
    source_kind: AggregationCaptureKind,
    captured_at: datetime | None = None,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Atomically replace the complete per-perceptor-clave window."""
    if not isinstance(self, PercepcionObservationRepositoryAdapter):
        raise TypeError("fixture requires the percepcion persistence adapter")
    _translate_storage_failure(
        "percepcion_replace_observations",
        lambda: replace_observation_window(
            self,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=observations,
            source_kind=source_kind,
            build_payload=self.build_observation_payload,
            captured_at=captured_at,
            source_metadata=source_metadata,
        ),
    )
