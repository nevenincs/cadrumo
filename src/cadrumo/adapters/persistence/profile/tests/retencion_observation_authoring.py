"""Finite fixture authoring over real typed and atomic storage kernels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from .....application.aggregation.retenciones import RetencionObservation
from .....core.aggregation import AggregationCaptureKind
from .....core.period import Period
from ..retencion_observations import RetencionObservationRepositoryAdapter, _translate_storage_failure
from .observation_window_authoring import replace_observation_window


def save_retencion_observation(
    self: object,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observation: RetencionObservation,
    source_kind: AggregationCaptureKind,
    captured_at: datetime | None = None,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Persist one per-perceptor retención observation."""
    if not isinstance(self, RetencionObservationRepositoryAdapter):
        raise TypeError("fixture requires the retencion persistence adapter")
    _translate_storage_failure(
        "retencion_save_observation",
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


def replace_retencion_observations(
    self: object,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[RetencionObservation],
    source_kind: AggregationCaptureKind,
    captured_at: datetime | None = None,
    source_metadata: Mapping[str, str] | None = None,
) -> None:
    """Atomically replace the complete per-perceptor observation window."""
    if not isinstance(self, RetencionObservationRepositoryAdapter):
        raise TypeError("fixture requires the retencion persistence adapter")
    _translate_storage_failure(
        "retencion_replace_observations",
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
