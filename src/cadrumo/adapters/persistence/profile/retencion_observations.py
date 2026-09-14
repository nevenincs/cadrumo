"""Encrypted persistence adapter for retención observation capabilities."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import datetime
from typing import ClassVar, TypeVar, override

from pydantic import BaseModel, Field

from ....application.aggregation.observation_window import replace_observation_window
from ....application.aggregation.retencion_observations_repository import (
    RetencionObservationPersistenceError,
    RetencionObservationRepository,
    retencion_observation_key,
)
from ....application.aggregation.retenciones import RetencionObservation
from ....core.aggregation import AggregationCaptureKind
from ....core.classification.policies import SensitivityClass
from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....core.time.clock import now
from ....core.time.utc import UtcInstant
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import StorageError
from ..storage.path_safety import safe_repository_id
from ..storage.secure_object_namespaces import RETENCION_OBSERVATIONS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository

_ResultT = TypeVar("_ResultT")


def _translate_storage_failure(operation: str, action: Callable[[], _ResultT]) -> _ResultT:
    """Translate storage failures into the application-owned error."""
    try:
        return action()
    except RetencionObservationPersistenceError:
        raise
    except (StorageError, OSError, TypeError, KeyError) as exc:
        raise RetencionObservationPersistenceError(operation) from exc


class _RetencionObservationEnvelopePayload(BaseModel):
    """Encrypted envelope payload for one per-perceptor retención row."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    observation: RetencionObservation
    captured_at: UtcInstant
    source_kind: AggregationCaptureKind
    source_metadata: Mapping[str, str] = Field(default_factory=dict)


class RetencionObservationRepositoryAdapter(
    SecureBoundRepository[_RetencionObservationEnvelopePayload],
    RetencionObservationRepository,
):
    """Bind the application retención port to encrypted secure-object storage."""

    namespace: ClassVar[str] = RETENCION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = RETENCION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = RETENCION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[_RetencionObservationEnvelopePayload]] = _RetencionObservationEnvelopePayload

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    def validate_observation_window_modelo(self, modelo: str) -> str:
        """Bind application window-key validation to persistence storage safety."""
        return _translate_storage_failure(
            "retencion_validate_observation_window_modelo",
            lambda: safe_repository_id(modelo, context="modelo"),
        )

    @override
    def extract_identifier(self, payload: _RetencionObservationEnvelopePayload) -> str:
        return retencion_observation_key(
            payload.modelo,
            payload.filing_year,
            payload.period,
            payload.observation.perceptor_nif,
            payload.observation.scheme,
        )

    def build_observation_payload(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: RetencionObservation,
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> _RetencionObservationEnvelopePayload:
        """Build one validated envelope payload before committing it."""
        return _RetencionObservationEnvelopePayload(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            captured_at=captured_at if captured_at is not None else now(),
            source_kind=source_kind,
            source_metadata=dict(source_metadata or {}),
        )

    def save_observation(
        self,
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

    @override
    def replace_observations(
        self,
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

    @override
    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        """Return all persisted observations for one modelo/period window."""
        return _translate_storage_failure(
            "retencion_load_observations",
            lambda: self._load_observations(modelo, period),
        )

    def _load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        safe_repository_id(modelo, context="modelo")
        return tuple(
            payload.observation
            for payload in self.iter_records()
            if payload.modelo == modelo
            and payload.filing_year == period.filing_year
            and payload.period.registry_token == period.registry_token
        )

    def iter_modelo(self, modelo: str) -> Iterator[_RetencionObservationEnvelopePayload]:
        """Yield encrypted payloads for one modelo in unspecified order."""
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.modelo == modelo:
                yield payload


__all__ = ["RetencionObservationRepositoryAdapter"]
