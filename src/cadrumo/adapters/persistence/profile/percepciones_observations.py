"""Encrypted persistence adapter for percepciones observation capabilities.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, Field

from ....application.aggregation.observation_window import replace_observation_window
from ....application.aggregation.percepciones_observations_repository import (
    PercepcionObservationPersistenceError,
    PercepcionObservationRepository,
    percepcion_observation_key,
)
from ....core.aggregation import AggregationCaptureKind
from ....core.classification.policies import SensitivityClass
from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ....core.time.clock import now
from ....core.time.utc import UtcInstant
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import StorageError
from ..storage.path_safety import safe_repository_id
from ..storage.secure_object_namespaces import WITHHOLDING_OBSERVATIONS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository


def _translate_storage_failure[ResultT](operation: str, action: Callable[[], ResultT]) -> ResultT:
    """Translate persistence failures into the application-owned error."""
    try:
        return action()
    except PercepcionObservationPersistenceError:
        raise
    except (StorageError, OSError, TypeError, KeyError) as exc:
        raise PercepcionObservationPersistenceError(operation) from exc


class _PercepcionObservationEnvelopePayload(BaseModel):
    """Encrypted envelope payload for one per-perceptor-clave row."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    observation: WithholdingObservation
    captured_at: UtcInstant
    source_kind: AggregationCaptureKind
    source_metadata: Mapping[str, str] = Field(default_factory=dict)
    projection_identity: str | None = Field(default=None, min_length=64, max_length=64)


class PercepcionObservationRepositoryAdapter(
    SecureBoundRepository[_PercepcionObservationEnvelopePayload],
    PercepcionObservationRepository,
):
    """Bind the percepciones port to encrypted secure-object storage."""

    namespace: ClassVar[str] = WITHHOLDING_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = WITHHOLDING_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = WITHHOLDING_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[_PercepcionObservationEnvelopePayload]] = _PercepcionObservationEnvelopePayload

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    def validate_observation_window_modelo(self, modelo: str) -> str:
        """Bind application window-key validation to persistence storage safety."""
        return _translate_storage_failure(
            "percepcion_validate_observation_window_modelo",
            lambda: safe_repository_id(modelo, context="modelo"),
        )

    @override
    def extract_identifier(self, payload: _PercepcionObservationEnvelopePayload) -> str:
        observation = payload.observation
        return percepcion_observation_key(
            payload.modelo,
            payload.filing_year,
            payload.period,
            observation.perceptor_tax_id,
            observation.clave,
            observation.subclave,
            payload.projection_identity,
        )

    def build_observation_payload(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: WithholdingObservation,
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
        projection_identity: str | None = None,
    ) -> _PercepcionObservationEnvelopePayload:
        """Build one validated envelope payload before committing it."""
        return _PercepcionObservationEnvelopePayload(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            captured_at=captured_at if captured_at is not None else now(),
            source_kind=source_kind,
            source_metadata=dict(source_metadata or {}),
            projection_identity=projection_identity,
        )

    def save_observation(
        self,
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

    @override
    def replace_observations(
        self,
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

    @override
    def load_observations(self, modelo: str, period: Period) -> tuple[WithholdingObservation, ...]:
        """Return all persisted observations for one modelo/period window."""
        return _translate_storage_failure(
            "percepcion_load_observations",
            lambda: self._load_observations(modelo, period),
        )

    def _load_observations(self, modelo: str, period: Period) -> tuple[WithholdingObservation, ...]:
        safe_repository_id(modelo, context="modelo")
        return tuple(
            payload.observation
            for payload in self.iter_records()
            if payload.modelo == modelo
            and payload.filing_year == period.filing_year
            and payload.period.registry_token == period.registry_token
        )

    def iter_modelo(self, modelo: str) -> Iterator[_PercepcionObservationEnvelopePayload]:
        """Yield encrypted per-perceptor-clave payloads for one modelo."""
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.modelo == modelo:
                yield payload


__all__ = ["PercepcionObservationRepositoryAdapter"]
